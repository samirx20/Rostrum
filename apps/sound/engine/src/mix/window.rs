//! A heard stretch rendered on its own (`render` with from / to and the whole song's mastering decisions,
//! fx/master_window.rs): which frames each stage works on, so the stretch comes out as the whole song's render has it
//! there. The master stage starts LEAD_IN_S before the stretch (its reverb, glue and limiter have settled by the first
//! frame kept) and runs AFTER_S past it (the limiter's look-ahead); a track that is not in the render cache renders
//! another LEAD_IN_S before that (its own reverb, delay and compressor), and of its notes only those that sound in its
//! span. Spans start on a block boundary (tape::BLOCK), where the whole render's blocks start too. A song that reads
//! itself whole (time warps, a whole-take master insert, a loop's wrap, ducks that follow other tracks) renders whole.

use crate::mix::schedule::Schedule;
use crate::mix::tape::BLOCK;

/// Seconds of lead-in before each stage's part of the stretch.
pub const LEAD_IN_S: f64 = 3.0;
/// Seconds past the stretch the master stage runs (the limiter answers a frame once its look-ahead is in).
const AFTER_S: f64 = 0.05;
/// Seconds a note may ring past its written end (its release); a note that ends sooner than this before a span is
/// left out of it.
pub const TAIL_S: f64 = 4.0;

/// Whether the stretch renders on its own (else the song renders whole and the stretch is cut from it).
pub fn windowed(s: &Schedule) -> bool {
    let whole_master = crate::fx::chain::Chain::new(&s.effects, s.layout, s.sample_rate as f64).is_ok_and(|c| c.whole());
    s.range.is_some() && s.master_as.is_some() && s.time_warps.is_empty() && s.tail_samples == 0 && !whole_master && s.tracks.iter().all(|t| t.ducks.is_empty())
}

fn lead(s: &Schedule) -> usize {
    (LEAD_IN_S * s.sample_rate as f64) as usize
}

/// The song frames the master stage works on: None, the whole song.
pub fn master_span(s: &Schedule) -> Option<(usize, usize)> {
    let (from, to) = s.range.filter(|_| windowed(s))?;
    let buf = s.total_samples + s.tail_samples;
    let after = (AFTER_S * s.sample_rate as f64) as usize;
    Some((from.saturating_sub(lead(s)) / BLOCK * BLOCK, (to + after).min(buf)))
}

/// The song frames a track that renders now (not from the cache) covers: None, the whole song.
pub fn track_span(s: &Schedule) -> Option<(usize, usize)> {
    master_span(s).map(|(lo, hi)| (lo.saturating_sub(lead(s)) / BLOCK * BLOCK, hi))
}

/// Whether something sounding from `start` for `len` frames (plus a note's ring, TAIL_S) is heard in `span`.
pub fn heard(span: Option<(usize, usize)>, start: usize, len: usize, sr: f64) -> bool {
    span.is_none_or(|(lo, hi)| start < hi && start + len + (TAIL_S * sr) as usize > lo)
}
