//! A track written to a tape block by block (tape.rs layout), so a track's render holds a block, never the
//! whole track. The length is known up front, so each block goes straight to its place in one file (channel
//! after channel, every frame); the sounding span is tracked on the way. At the end the file becomes the tape as
//! it is (renamed into the cache, or kept as a scratch tape), or, when a quarter or more of it is silent, only its
//! sounding span is copied out (the tape's trimmed form, as `tape::write_to` writes it). Samples read back bit for bit.

use std::fs::File;
use std::io::{BufReader, Read, Seek, SeekFrom, Write};
use std::path::PathBuf;

use crate::mix::tape::{Tape, BLOCK, HEADER};

pub struct TapeWriter {
    path: PathBuf,
    file: Option<File>,
    chs: usize,
    len: usize,
    at: usize,
    /// The frame after the last one pushed (`len`, or a span's end).
    end: usize,
    /// A span (`span`): its first frame and its frames so far, held in memory (a stretch is a few seconds); no file.
    held: Option<(usize, Vec<Vec<f32>>)>,
    /// The first and one past the last frame where any channel is not +0.0.
    from: Option<usize>,
    to: usize,
}

impl TapeWriter {
    /// A tape of `channels` × `len` frames, filled by `push`.
    pub fn new(channels: usize, len: usize) -> Result<TapeWriter, String> {
        TapeWriter::span(channels, len, 0, len)
    }

    /// A tape of `channels` × `len` frames of which only frames `from .. to` are pushed (a heard stretch, window.rs):
    /// the rest reads as silence.
    pub fn span(channels: usize, len: usize, from: usize, to: usize) -> Result<TapeWriter, String> {
        let to = to.min(len);
        if from > 0 || to < len {
            let held = Some((from, vec![Vec::with_capacity(to.saturating_sub(from)); channels]));
            return Ok(TapeWriter { path: PathBuf::new(), file: None, chs: channels, len, at: from, end: to, held, from: None, to: 0 });
        }
        use std::sync::atomic::{AtomicUsize, Ordering};
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let dir = std::env::temp_dir().join("rostrum-sound-render");
        let path = dir.join(format!("{}-w{}.f32", std::process::id(), NEXT.fetch_add(1, Ordering::Relaxed)));
        let fail = |e: std::io::Error| format!("could not write the render's scratch file {}: {e}", path.display());
        std::fs::create_dir_all(&dir).map_err(fail)?;
        let file = File::create(&path).and_then(|f| f.set_len((HEADER + channels * len * 4) as u64).map(|_| f)).map_err(fail)?;
        Ok(TapeWriter { path, file: Some(file), chs: channels, len, at: from, end: to, held: None, from: None, to: 0 })
    }

    fn fail(&self, e: std::io::Error) -> String {
        format!("could not write the render's scratch file {}: {e}", self.path.display())
    }

    /// The next block of every channel (all the same length).
    pub fn push(&mut self, chs: &[Vec<f32>]) -> Result<(), String> {
        let n = chs.first().map_or(0, Vec::len);
        if chs.len() != self.chs || self.at + n > self.end {
            return Err(format!("a track's tape got {} channels to frame {}, made for {} × {} (an engine fault)", chs.len(), self.at + n, self.chs, self.len));
        }
        for i in 0..n {
            if chs.iter().any(|c| c[i].to_bits() != 0) {
                self.from.get_or_insert(self.at + i);
                self.to = self.at + i + 1;
            }
        }
        if let Some((_, held)) = &mut self.held {
            held.iter_mut().zip(chs).for_each(|(h, c)| h.extend_from_slice(c));
            self.at += n;
            return Ok(());
        }
        let mut buf = Vec::with_capacity(n * 4);
        for (c, ch) in chs.iter().enumerate() {
            buf.clear();
            ch.iter().for_each(|s| buf.extend_from_slice(&s.to_le_bytes()));
            let pos = (HEADER + (c * self.len + self.at) * 4) as u64;
            let f = self.file.as_mut().expect("open until finished");
            if let Err(e) = f.seek(SeekFrom::Start(pos)).and_then(|_| f.write_all(&buf)) {
                return Err(self.fail(e));
            }
        }
        self.at += n;
        Ok(())
    }

    /// The sounding span copied out in the tape layout.
    fn write_span(&self, w: &mut impl Write, from: usize, to: usize) -> std::io::Result<()> {
        for word in [self.chs, self.len, from, to - from] {
            w.write_all(&(word as u64).to_le_bytes())?;
        }
        let mut r = BufReader::new(File::open(&self.path)?);
        let mut buf = vec![0u8; BLOCK * 4];
        for c in 0..self.chs {
            r.seek(SeekFrom::Start((HEADER + (c * self.len + from) * 4) as u64))?;
            let mut left = (to - from) * 4;
            while left > 0 {
                let k = left.min(buf.len());
                r.read_exact(&mut buf[..k])?;
                w.write_all(&buf[..k])?;
                left -= k;
            }
        }
        w.flush()
    }

    /// Into the render cache under `key` (when it can be written), else a scratch tape of this render.
    pub fn finish(mut self, cache: Option<(&crate::mix::trackcache::TrackCache, &str)>) -> Result<Tape, String> {
        if self.at != self.end {
            return Err(format!("a track's tape ended at frame {} of {} (an engine fault)", self.at, self.end));
        }
        let from = self.from.unwrap_or(self.len);
        let to = self.to.max(from);
        let len = self.len;
        if let Some((start, held)) = self.held.take() {
            // A span: its sounding part written as a scratch tape (never into the cache: the track is not whole).
            let (a, b) = if from >= to { (start, start) } else { (from, to) };
            return Tape::spill_with(len, |w| {
                for word in [self.chs, len, a, b - a] {
                    w.write_all(&(word as u64).to_le_bytes())?;
                }
                for c in &held {
                    let bytes: Vec<u8> = c[a - start..b - start].iter().flat_map(|s| s.to_le_bytes()).collect();
                    w.write_all(&bytes)?;
                }
                w.flush()
            });
        }
        if (len - (to - from)) * 4 >= len {
            // A quarter or more is silence: keep only the sounding span.
            drop(self.file.take());
            if let Some((c, key)) = cache {
                if let Some(t) = c.store_with(key, len, |w| self.write_span(w, from, to)) {
                    return Ok(t);
                }
            }
            return Tape::spill_with(len, |w| self.write_span(w, from, to));
        }
        // Every frame stored: the header says so and the file is the tape.
        let mut f = self.file.take().expect("open until finished");
        let head: Vec<u8> = [self.chs, len, 0, len].iter().flat_map(|w| (*w as u64).to_le_bytes()).collect();
        if let Err(e) = f.seek(SeekFrom::Start(0)).and_then(|_| f.write_all(&head)).and_then(|_| f.flush()) {
            return Err(self.fail(e));
        }
        drop(f);
        if let Some((c, key)) = cache {
            if let Some(t) = c.adopt(key, &self.path, len) {
                self.path = PathBuf::new(); // renamed into the cache
                return Ok(t);
            }
            // Not movable (the cache on another drive): copied in.
            if let Some(t) = c.store_with(key, len, |w| self.write_span(w, 0, len)) {
                return Ok(t);
            }
        }
        let t = Tape::open_scratch(&self.path, len).ok_or_else(|| format!("the render's scratch file {} did not read back", self.path.display()))?;
        self.path = PathBuf::new(); // the tape owns the file now
        Ok(t)
    }
}

impl Drop for TapeWriter {
    fn drop(&mut self) {
        drop(self.file.take());
        if !self.path.as_os_str().is_empty() {
            let _ = std::fs::remove_file(&self.path);
        }
    }
}
