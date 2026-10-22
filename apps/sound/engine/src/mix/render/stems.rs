//! The stems written: each kept track (and bus) read from its tape block by block, through the master's
//! linear gain (the very gain the mix took: fader, lane, fades, loudness gain), so they add up to the mix
//! wherever its glue and limiter did not act. Every file is written as it goes; nothing is gathered whole.

use std::path::PathBuf;

use super::stats::Mix;
use crate::mix::tape::{Tape, BLOCK};
use crate::mix::wavwriter::WavWriter;

/// Writes each (tape, file) pair, `mix.gain.total` frames long (from song frame `mix.gain.offset`: a range), at rate `sr`.
pub fn write(mix: &Mix, files: &[(&Tape, PathBuf)], sr: u32) -> Result<(), String> {
    if files.is_empty() {
        return Ok(());
    }
    let gain = mix.gain.as_ref().ok_or("the mix has no master gain for its stems")?;
    let total = gain.total;
    let mut writers = files.iter().map(|(tape, file)| WavWriter::create(file, tape.channels(), total, mix.layout, sr)).collect::<Result<Vec<_>, _>>()?;
    for at in (0..total).step_by(BLOCK) {
        let n = BLOCK.min(total - at);
        let g: Vec<f32> = (at..at + n).map(|i| gain.stem(i)).collect();
        for ((tape, _), w) in files.iter().zip(writers.iter_mut()) {
            let mut block = tape.read(gain.offset + at, n)?;
            block.iter_mut().for_each(|c| c.iter_mut().zip(&g).for_each(|(v, g)| *v *= g));
            w.write(&block)?;
        }
    }
    writers.into_iter().try_for_each(WavWriter::finish)
}
