//! A signal written once block by block and read back as often as needed: in memory (a short signal, a fold-down
//! in bed/) or on disk (the mix's master stage, tape.rs), so the stages that pass over a whole song more than once
//! (the mastering stage) hold a block, never the song. Samples read back bit for bit.

use crate::mix::tape::Tape;
use crate::mix::tapewriter::TapeWriter;

/// Frames per pass of the stages that read a whole song more than once or measure it (the mastering stage, the measures):
/// 16 blocks (8 MB of stereo f32), so their per-block work (threads, reads) is paid 16 times less often.
pub const CHUNK: usize = 16 * crate::mix::tape::BLOCK;

pub enum Spool {
    Mem(Vec<Vec<f32>>),
    Writing(TapeWriter),
    Disk(Tape),
}

impl Spool {
    /// An empty spool of `channels` × `len` frames, on disk or in memory.
    pub fn new(channels: usize, len: usize, on_disk: bool) -> Result<Spool, String> {
        Ok(if on_disk { Spool::Writing(TapeWriter::new(channels, len)?) } else { Spool::Mem(vec![Vec::with_capacity(len); channels]) })
    }

    /// The next block of every channel.
    pub fn push(&mut self, block: &[Vec<f32>]) -> Result<(), String> {
        match self {
            Spool::Mem(chs) => chs.iter_mut().zip(block).for_each(|(c, b)| c.extend_from_slice(b)),
            Spool::Writing(w) => w.push(block)?,
            Spool::Disk(_) => return Err("a finished spool was written to (an engine fault)".into()),
        }
        Ok(())
    }

    /// Every block written: ready to read.
    pub fn done(self) -> Result<Spool, String> {
        match self {
            Spool::Writing(w) => Ok(Spool::Disk(w.finish(None)?)),
            s => Ok(s),
        }
    }

    /// Frames `at .. at + n` of every channel (past the end: 0).
    pub fn read(&self, at: usize, n: usize) -> Result<Vec<Vec<f32>>, String> {
        match self {
            Spool::Mem(chs) => Ok(chs
                .iter()
                .map(|c| {
                    let end = (at + n).min(c.len());
                    let mut v = if at < end { c[at..end].to_vec() } else { Vec::with_capacity(n) };
                    v.resize(n, 0.0);
                    v
                })
                .collect()),
            Spool::Disk(t) => t.read(at, n),
            Spool::Writing(_) => Err("a spool was read before it was finished (an engine fault)".into()),
        }
    }

    pub fn into_whole(self) -> Result<Vec<Vec<f32>>, String> {
        match self {
            Spool::Mem(chs) => Ok(chs),
            Spool::Disk(t) => t.whole(),
            Spool::Writing(_) => Err("a spool was read before it was finished (an engine fault)".into()),
        }
    }
}
