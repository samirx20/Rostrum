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

pub(super) fn render_tracks(s: &Schedule, cache: Option<&TrackCache>, buf: usize) -> Result<Tracks, String> {
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
            let clips = render_track_clips(s, k)?;
            let feeders: Vec<&Tape> = s.tracks.iter().enumerate().filter(|(_, t)| t.into == Some(k)).filter_map(|(j, _)| done[j].as_deref()).collect();
            let (out, pre) = track_out(s, &s.tracks[k], clips, feeders, buf)?;
            let tape = out.finish(cache.map(|c| (c, s.track_keys[k].as_str())))?;
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
