//! Every track rendered to a tape (tape.rs): read back from the render cache when its content was rendered
//! before, else its clips rendered, summed and placed (track.rs) and the result stored — in the cache, or in a
//! scratch tape of this render. A few tracks at a time (par.rs budget), so memory holds a few tracks, never all.

use std::sync::Arc;

use super::clip::render_track_clips;
use super::prof;
use super::track::track_out;
use crate::mix::schedule::Schedule;
use crate::mix::tape::Tape;
use crate::mix::trackcache::TrackCache;

pub(super) struct Tracks {
    /// Each track's output (after its effects, fader and reverb send; before any duck), in schedule order.
    pub outs: Vec<Arc<Tape>>,
    /// The tap before the fader of a track that sends from there (buses.rs), else None.
    pub pres: Vec<Option<Tape>>,
}

/// Bytes one track's job holds at its peak: its clips, its sum and its placed output, in the bed's channels.
pub(super) fn job_bytes(s: &Schedule, buf: usize) -> usize {
    buf * s.layout.channels().max(2) * 4 * 3
}

/// `held`: a `measure` request's run (held.rs): a track's clips rendered before in the run are used again.
pub(super) fn render_tracks(s: &Schedule, cache: Option<&TrackCache>, buf: usize, held: bool) -> Result<Tracks, String> {
    let n = s.tracks.len();
    let t0 = std::time::Instant::now();
    let cache = cache.filter(|_| s.track_keys.len() == n);
    // A track that sends from before its fader renders (its tap is not cached).
    let mut outs: Vec<Option<Arc<Tape>>> = (0..n)
        .map(|k| match cache {
            Some(c) if !crate::mix::buses::has_pre(&s.tracks[k]) => c.tape(&s.track_keys[k], buf).map(Arc::new),
            _ => None,
        })
        .collect();
    let want: Vec<bool> = outs.iter().map(Option::is_none).collect();
    prof(&format!("cached tracks read ({} of {n})", want.iter().filter(|w| !**w).count()), t0);
    let mut pres: Vec<Option<Tape>> = (0..n).map(|_| None).collect();
    let threads = crate::mix::par::threads_for(job_bytes(s, buf));
    // Feeders first, then the buses they feed (one level of grouping: a layered instrument's layers).
    let feeds = |k: usize| s.tracks.iter().any(|t| t.into == Some(k));
    for buses in [false, true] {
        let level: Vec<usize> = (0..n).filter(|&k| want[k] && feeds(k) == buses).collect();
        let done = &outs;
        let rendered = crate::mix::par::map_n(level, threads, |k| -> Result<(usize, Tape, Option<Tape>), String> {
            // A heard stretch (window.rs): a track that renders now covers its span only, and is not cached (not whole).
            let span = crate::mix::window::track_span(s).filter(|_| !held && !reads_whole(s, k));
            let clips = clips_of(s, k, held, span)?;
            let feeders: Vec<&Tape> = s.tracks.iter().enumerate().filter(|(_, t)| t.into == Some(k)).filter_map(|(j, _)| done[j].as_deref()).collect();
            let (out, pre) = track_out(s, &s.tracks[k], &clips, feeders, buf, span)?;
            let tape = out.finish(cache.filter(|_| span.is_none()).map(|c| (c, s.track_keys[k].as_str())))?;
            Ok((k, tape, pre.map(|p| p.finish(None)).transpose()?))
        });
        for r in rendered {
            let (k, tape, pre) = r?;
            outs[k] = Some(Arc::new(tape));
            pres[k] = pre;
        }
    }
    prof("tracks", t0);
    Ok(Tracks { outs: outs.into_iter().map(|t| t.expect("every track rendered")).collect(), pres })
}

/// Track `k`'s rendered clips: from the run's memory when `held` and rendered before (held.rs), else rendered (and,
/// when `held`, kept for the run's next request).
fn clips_of(s: &Schedule, k: usize, held: bool, span: Option<(usize, usize)>) -> Result<crate::mix::held::Clips, String> {
    let key = s.clip_keys.get(k).filter(|_| held);
    if let Some(c) = key.and_then(|key| crate::mix::held::clips(key)) {
        return Ok(c);
    }
    let clips = Arc::new(render_track_clips(s, k, span)?);
    if let Some(key) = key {
        crate::mix::held::keep_clips(key, clips.clone());
    }
    Ok(clips)
}

/// Track `k`'s effects read the whole take at once (fx/chain.rs): it renders whole, even for a heard stretch.
fn reads_whole(s: &Schedule, k: usize) -> bool {
    let t = &s.tracks[k];
    let layout = if t.bed { s.layout } else { crate::bed::Layout::Stereo };
    crate::fx::chain::Chain::new(&t.effects, layout, s.sample_rate as f64).map_or(true, |c| c.whole())
}
