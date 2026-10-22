//! A rendered track on disk, read back in blocks (render/): the mix keeps each track here rather than in
//! memory, so what it holds follows the block size, not the number of tracks. One file layout for the render
//! cache (trackcache.rs) and the render's own scratch files: four little-endian u64 words (channels, length,
//! first sounding sample, samples stored), then each channel's stored span as f32 — the silence on either
//! side is not stored and reads back as 0. Samples read back bit for bit.

use std::fs::File;
use std::io::{BufWriter, Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Mutex;

/// Frames per block, everywhere the mix works block by block (64 k frames: 512 KB of stereo f32).
pub const BLOCK: usize = 1 << 16;

pub(crate) const HEADER: usize = 32;

pub struct Tape {
    file: Mutex<File>,
    path: PathBuf,
    /// A scratch file of this render: removed when the tape is dropped.
    scratch: bool,
    chs: usize,
    len: usize,
    from: usize,
    n: usize,
}

/// Writes channels in the tape layout (silence before and after the sounding span left out).
pub fn write_to(w: &mut impl Write, chs: &[Vec<f32>]) -> std::io::Result<()> {
    let len = chs.first().map_or(0, Vec::len);
    let sounding = |i: &usize| chs.iter().any(|c| c[*i].to_bits() != 0);
    let from = (0..len).find(sounding).unwrap_or(len);
    let to = (from..len).rev().find(sounding).map_or(from, |i| i + 1);
    for word in [chs.len(), len, from, to - from] {
        w.write_all(&(word as u64).to_le_bytes())?;
    }
    let mut buf = Vec::with_capacity(BLOCK * 4);
    for c in chs {
        for part in c[from..to].chunks(BLOCK) {
            buf.clear();
            part.iter().for_each(|s| buf.extend_from_slice(&s.to_le_bytes()));
            w.write_all(&buf)?;
        }
    }
    w.flush()
}

impl Tape {
    /// A tape file, `len` frames long; None when it is absent, of another length, or not whole.
    pub fn open(path: &Path, len: usize) -> Option<Tape> {
        let mut file = File::open(path).ok()?;
        let mut head = [0u8; HEADER];
        file.read_exact(&mut head).ok()?;
        let word = |i: usize| usize::try_from(u64::from_le_bytes(head[8 * i..8 * i + 8].try_into().ok()?)).ok();
        let (chs, total, from, n) = (word(0)?, word(1)?, word(2)?, word(3)?);
        let size = file.metadata().ok()?.len();
        if chs == 0 || total != len || from + n > len || size != (HEADER + chs * n * 4) as u64 {
            return None;
        }
        Some(Tape { file: Mutex::new(file), path: path.to_path_buf(), scratch: false, chs, len, from, n })
    }

    /// A whole tape file made by this render (tapewriter.rs), opened as a scratch tape (removed when dropped).
    pub fn open_scratch(path: &Path, len: usize) -> Option<Tape> {
        let mut t = Tape::open(path, len)?;
        t.scratch = true;
        Some(t)
    }

    /// Channels written to a scratch file of this render (removed when the tape is dropped).
    pub fn spill(chs: &[Vec<f32>]) -> Result<Tape, String> {
        Tape::spill_with(chs.first().map_or(0, Vec::len), |w| write_to(w, chs))
    }

    /// A scratch tape of `len` frames that `write` fills in the tape layout (tapewriter.rs streams one).
    pub fn spill_with(len: usize, write: impl FnOnce(&mut BufWriter<File>) -> std::io::Result<()>) -> Result<Tape, String> {
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let dir = std::env::temp_dir().join("rostrum-sound-render");
        static SWEPT: std::sync::Once = std::sync::Once::new();
        SWEPT.call_once(|| super::sweep::dead_files(&dir));     // what an engine that died mid-render left here
        let path = dir.join(format!("{}-{}.f32", std::process::id(), NEXT.fetch_add(1, Ordering::Relaxed)));
        let fail = |e: std::io::Error| format!("could not write the render's scratch file {}: {e}", path.display());
        std::fs::create_dir_all(&dir).map_err(fail)?;
        let written = File::create(&path).and_then(|f| write(&mut BufWriter::new(f)));
        let opened = written.map_err(fail).and_then(|_| Tape::open(&path, len).ok_or_else(|| format!("the render's scratch file {} did not read back", path.display())));
        match opened {
            Ok(mut tape) => {
                tape.scratch = true;
                Ok(tape)
            }
            Err(e) => {
                let _ = std::fs::remove_file(&path);
                Err(e)
            }
        }
    }

    pub fn channels(&self) -> usize {
        self.chs
    }

    /// Frames `at .. at + n` of every channel (past the end: 0). A file that cannot be read is an error naming it.
    pub fn read(&self, at: usize, n: usize) -> Result<Vec<Vec<f32>>, String> {
        let mut out = vec![vec![0.0f32; n]; self.chs];
        let (a, b) = (at.max(self.from), (at + n).min(self.from + self.n));
        if a >= b {
            return Ok(out);
        }
        let mut file = self.file.lock().unwrap();
        let mut bytes = vec![0u8; (b - a) * 4];
        for (c, ch) in out.iter_mut().enumerate() {
            let pos = HEADER + (c * self.n + (a - self.from)) * 4;
            file.seek(SeekFrom::Start(pos as u64)).and_then(|_| file.read_exact(&mut bytes)).map_err(|e| format!("{}: {e}", self.path.display()))?;
            for (dst, s) in ch[a - at..b - at].iter_mut().zip(bytes.chunks_exact(4)) {
                *dst = f32::from_le_bytes([s[0], s[1], s[2], s[3]]);
            }
        }
        Ok(out)
    }

    /// Every frame (one track's worth: for the stages that still need a whole track).
    pub fn whole(&self) -> Result<Vec<Vec<f32>>, String> {
        self.read(0, self.len)
    }

    /// The tape added into `into` (from frame 0), block by block: `into[c][i] += tape[c][i]` over every frame (the
    /// silence too: adding 0 turns a −0 into 0, as the sum in memory did).
    pub fn add_into(&self, into: &mut [Vec<f32>]) -> Result<(), String> {
        let len = into.first().map_or(0, Vec::len).min(self.len);
        for at in (0..len).step_by(BLOCK) {
            let n = BLOCK.min(len - at);
            for (dst, src) in into.iter_mut().zip(self.read(at, n)?) {
                dst[at..at + n].iter_mut().zip(&src).for_each(|(d, s)| *d += *s);
            }
        }
        Ok(())
    }
}

impl Drop for Tape {
    fn drop(&mut self) {
        if self.scratch {
            let _ = std::fs::remove_file(&self.path);
        }
    }
}
