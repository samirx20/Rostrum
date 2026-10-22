//! A float WAV written block by block (the mix and its stems): the header first (its length known), then
//! each block of frames as it is made, into `<file>.partial`; `finish` checks the file holds every frame and
//! only then renames it into place, so a failed write never leaves a file under the real name.

use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};

use crate::bed::Layout;

pub struct WavWriter {
    out: BufWriter<File>,
    partial: PathBuf,
    path: PathBuf,
    nch: usize,
    frames: usize,
    written: usize,
    bytes: Vec<u8>,
}

impl WavWriter {
    /// A WAV of `nch` channels and `frames` frames at `path` (its folder made when missing).
    pub fn create(path: &Path, nch: usize, frames: usize, layout: Layout, sr: u32) -> Result<WavWriter, String> {
        if let Some(dir) = path.parent() {
            std::fs::create_dir_all(dir).map_err(|e| format!("{}: {e}", dir.display()))?;
        }
        let partial = PathBuf::from(format!("{}.partial", path.display()));
        let fail = |e: std::io::Error| format!("{}: {e}", partial.display());
        let mut out = BufWriter::with_capacity(1 << 20, File::create(&partial).map_err(fail)?);
        out.write_all(&crate::mix::wavio::header(nch, frames, layout, sr)).map_err(fail)?;
        Ok(WavWriter { out, partial, path: path.to_path_buf(), nch, frames, written: 0, bytes: vec![] })
    }

    /// The next frames, one buffer per channel (all the same length).
    pub fn write(&mut self, block: &[Vec<f32>]) -> Result<(), String> {
        let n = block.first().map_or(0, Vec::len);
        if block.len() != self.nch || self.written + n > self.frames {
            return Err(format!("{}: {} channels × {n} frames after {} of {} (the file has {} channels)", self.partial.display(), block.len(), self.written, self.frames, self.nch));
        }
        self.bytes.clear();
        for i in 0..n {
            for c in block {
                self.bytes.extend_from_slice(&c[i].to_le_bytes());
            }
        }
        self.out.write_all(&self.bytes).map_err(|e| format!("{}: {e}", self.partial.display()))?;
        self.written += n;
        Ok(())
    }

    /// Every frame written: flushed, its size checked, renamed into place.
    pub fn finish(self) -> Result<(), String> {
        let WavWriter { out, partial, path, nch, frames, written, .. } = self;
        if written != frames {
            return Err(format!("{}: {written} of {frames} frames written; kept for inspection", partial.display()));
        }
        drop(out.into_inner().map_err(|e| format!("{}: {}", partial.display(), e.error()))?);
        let want = crate::mix::wavio::header(nch, frames, Layout::Stereo, 0).len() as u64 + (frames * nch * 4) as u64;
        if std::fs::metadata(&partial).map(|m| m.len()).unwrap_or(0) != want {
            return Err(format!("{} was not written whole; kept for inspection", partial.display()));
        }
        let _ = std::fs::remove_file(&path);
        std::fs::rename(&partial, &path).map_err(|e| format!("{} → {}: {e}", partial.display(), path.display()))
    }
}

/// A whole bed written through the writer (the mix: its channels are in memory for its measures).
pub fn write_whole(path: &Path, chs: &[Vec<f32>], layout: Layout, sr: u32) -> Result<(), String> {
    let frames = chs.first().map_or(0, Vec::len);
    let mut w = WavWriter::create(path, chs.len(), frames, layout, sr)?;
    for at in (0..frames).step_by(crate::mix::tape::BLOCK) {
        let n = crate::mix::tape::BLOCK.min(frames - at);
        w.write(&chs.iter().map(|c| c[at..at + n].to_vec()).collect::<Vec<_>>())?;
    }
    w.finish()
}
