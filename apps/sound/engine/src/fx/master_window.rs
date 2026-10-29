//! The mastering stage on a stretch of the song, acting there as it acts in the whole song's render. What the stage
//! decides over the whole song — the program's loudness (the glue's level), the gain to the loudness target and how far
//! the mix is held under it (`master_blocks`' passes) — are `Decisions`: worked out once over the whole song, then
//! given. The stretch (with a lead-in, so the glue and the limiter have settled by the frames that are kept) runs the
//! same chain once: glue, that gain, the limiter. One pass over a few seconds instead of several over the song.

use super::{glue_pass, limited, Dynamics, MasterReport, MasterSpec, Source};
use crate::mix::spool::Spool;

/// The whole song's mastering decisions (from its MasterReport).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Decisions {
    /// The program's integrated loudness before the stage (LUFS).
    pub program: f64,
    /// The gain applied before the limiter (dB): to the target, less `held_db`.
    pub gain_db: f64,
    pub held_db: f64,
}

/// Masters the `total` frames `read` gives (a stretch of the song) as the whole song's stage did: the glue over the
/// song's program loudness, the song's gain, the limiter. The report's glue and limiter figures are this stretch's.
#[allow(clippy::too_many_arguments)]
pub fn master_window(read: Source, nch: usize, total: usize, weights: &[f64], spec: &MasterSpec, sr: f64, d: &Decisions, on_disk: bool) -> Result<(Spool, MasterReport, Dynamics), String> {
    let ceiling = 10f64.powf((spec.true_peak - 0.3) / 20.0);
    let report = MasterReport { program: d.program, gain_db: d.gain_db, held_db: d.held_db, ..Default::default() };
    if d.program <= -69.0 {
        // The song had no loudness to read: its stage only limited (master_blocks does the same).
        let p = limited(read, nch, total, None, ceiling, sr, on_disk, None)?;
        return Ok((p.out, MasterReport { limiter_db: p.deepest, ..report }, Dynamics { glue: None, limiter: p.gains }));
    }
    let glue = if spec.glue > 0.0 { Some(glue_pass(read, nch, total, weights, spec.glue, d.program, sr, on_disk, false)?) } else { None };
    let from_glued = |at: usize, n: usize| glue.as_ref().expect("glued").out.read(at, n);
    let src: Source = if glue.is_some() { &from_glued } else { read };
    let g = 10f64.powf(d.gain_db / 20.0) as f32;
    let p = limited(src, nch, total, Some(g), ceiling, sr, on_disk, None)?;
    let glue_db = glue.as_ref().map_or(0.0, |g| g.deepest);
    Ok((p.out, MasterReport { glue_db, limiter_db: p.deepest, ..report }, Dynamics { glue: glue.map(|g| g.gains), limiter: p.gains }))
}
