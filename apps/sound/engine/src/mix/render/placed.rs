//! Each track as it reaches the mix: ducked under the levels of the tracks its ducks name (duck.rs) and
//! measured (stats.rs). One track at a time per job, a few jobs at once (par.rs budget); a ducked track
//! goes back to a tape of its own.

use std::sync::Arc;

use super::stats::{track_stats, TrackMeter, TrackStats};
use crate::mix::duck::{self, DuckSpan};
use crate::mix::schedule::Schedule;
use crate::mix::spool::CHUNK;
use crate::mix::tape::{Tape, BLOCK};

pub(super) struct Placed {
    pub duck: Option<(String, Vec<DuckSpan>)>,
    pub stats: Option<TrackStats>,
    /// The track after its ducks, when it has any (else its output tape is what reaches the mix).
    pub ducked: Option<Arc<Tape>>,
}

/// The loudest of the `from` tracks at each frame (before anything ducks): what a duck follows.
fn level(outs: &[Arc<Tape>], from: &[usize], buf: usize) -> Result<Vec<f32>, String> {
    let mut t = vec![0.0f32; buf];
    for tape in from.iter().filter_map(|&k| outs.get(k)) {
        for at in (0..buf).step_by(BLOCK) {
            let n = BLOCK.min(buf - at);
            for c in tape.read(at, n)? {
                t[at..at + n].iter_mut().zip(&c).for_each(|(d, s)| *d = d.max(s.abs()));
            }
        }
    }
    Ok(t)
}

fn place(s: &Schedule, outs: &[Arc<Tape>], k: usize, keep: bool, buf: usize, held: bool) -> Result<Placed, String> {
    let track = &s.tracks[k];
    if track.ducks.is_empty() && !track.mix {
        return Ok(Placed { duck: None, stats: None, ducked: None });
    }
    let sr = s.sample_rate as f64;
    if track.ducks.is_empty() {
        // A `measure` run (held.rs): the same tape measured before in the run has the same measures.
        let key = s.track_keys.get(k).filter(|_| held).map(|t| format!("{t}|{}|{}", track.name, s.total_samples));
        if let Some(st) = key.as_deref().and_then(crate::mix::held::stats) {
            return Ok(Placed { duck: None, stats: Some(st), ducked: None });
        }
        // Measured from its tape, block by block.
        let mut m = TrackMeter::new(&track.name, outs[k].channels(), s.total_samples, sr, s.layout);
        for at in (0..s.total_samples).step_by(CHUNK) {
            m.push(&outs[k].read(at, CHUNK.min(s.total_samples - at))?);
        }
        let st = m.finish();
        if let Some(key) = &key {
            crate::mix::held::keep_stats(key, &st);
        }
        return Ok(Placed { duck: None, stats: Some(st), ducked: None });
    }
    // A duck follows the level of other tracks over the whole song (duck.rs): this track is ducked whole.
    let mut chs = outs[k].whole()?;
    let mut dips: Vec<DuckSpan> = vec![];
    let mut report = false;
    for d in &track.ducks {
        let trigger = level(outs, &d.from, buf)?;
        let spans = duck::duck_n(&mut crate::bed::slices(&mut chs), &trigger, sr, d);
        if d.report {
            report = true;
            dips.extend(spans);
        }
    }
    let duck = report.then(|| {
        dips.sort_by(|a, b| a.0.total_cmp(&b.0));
        (track.name.clone(), dips)
    });
    let stats = track.mix.then(|| track_stats(&track.name, &chs, s.total_samples, sr, s.layout));
    let ducked = if track.mix || keep { Some(Arc::new(Tape::spill(&chs)?)) } else { None };
    Ok(Placed { duck, stats, ducked })
}

/// Every track placed, in schedule order (`keep`: the tracks kept as stems).
pub(super) fn place_all(s: &Schedule, outs: &[Arc<Tape>], keep: &[bool], buf: usize, held: bool) -> Result<Vec<Placed>, String> {
    let threads = crate::mix::par::threads_for(super::tracks::job_bytes(s, buf)).min(super::MEASURE_THREADS);
    crate::mix::par::map_n((0..s.tracks.len()).collect(), threads, |k| place(s, outs, k, keep.get(k).copied().unwrap_or(false), buf, held)).into_iter().collect()
}
