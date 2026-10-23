//! The mix, offline — the one render the screen's playback and every export go through: each clip into its
//! own buffer (content, speed, reverse, glitch, filter sweep, tone, fades and gain, reverb), clips summed into
//! their track (tone, inserts), the track placed in the bed (stereo: the pan law; surround or an object: the
//! panner, panner.rs; a bed track: as it is), its reverb send (tracks.rs); ducking under the dialogue / sfx
//! level and each track's measures (placed.rs); the tracks summed into the master bus (bus.rs); the stems
//! written through the master's gain (stems.rs). Each track lives on disk once rendered (tape.rs) and the later
//! stages read it in blocks: each track's measures, the master bus, the mastering stage and the file's measures
//! work block by block from disk (bus.rs, fx/master.rs), so memory holds a few tracks being rendered and a few
//! blocks, never every track or the whole song. What is still whole: one clip's own render (clip.rs) and a
//! ducked track (its ducks follow other tracks over the whole song). Jobs run in parallel, combined in a fixed order: the result does not depend on
//! the thread count. Every stage after the panner works on the bed's channels (bed/).

mod clip;
pub mod levels;
mod placed;
pub mod stats;
pub mod stems;
#[cfg(test)]
pub(crate) mod tests;
mod track;
mod tracks;

use std::sync::Arc;

use crate::mix::schedule::Schedule;
use crate::mix::tape::Tape;
use stats::Mix;

/// Tracks placed and measured at once: a ducked track is held whole while it is ducked, so a few at a time keep a
/// long soundtrack's peak memory near the sequential one's (a measure alone holds a chunk).
const MEASURE_THREADS: usize = 3;

/// ROSTRUM_SOUND_PROFILE=1: each stage's time on stderr.
pub fn prof(what: &str, since: std::time::Instant) {
    if std::env::var_os("ROSTRUM_SOUND_PROFILE").is_some() {
        eprintln!("[rostrum-sound] {what}: {:.0} ms", since.elapsed().as_secs_f64() * 1000.0);
    }
}

pub fn render(s: &Schedule) -> Result<Mix, String> {
    render_with(s, crate::mix::trackcache::TrackCache::default_dir().as_ref())
}

/// The mix, each track read back from `cache` when its content was rendered before (trackcache.rs).
pub fn render_with(s: &Schedule, cache: Option<&crate::mix::trackcache::TrackCache>) -> Result<Mix, String> {
    render_keep(s, cache, &[])
}

/// The mix, and the tracks marked in `keep` (by schedule index) kept as stems: each as it reaches the master
/// (after its effects, fader and ducks), on disk; `stems::write` writes them through the master's gain.
pub fn render_keep(s: &Schedule, cache: Option<&crate::mix::trackcache::TrackCache>, keep: &[bool]) -> Result<Mix, String> {
    let buf = s.total_samples + s.tail_samples;
    let rendered = tracks::render_tracks(s, cache, buf)?;
    let t2 = std::time::Instant::now();
    let placed = placed::place_all(s, &rendered.outs, keep, buf)?;
    prof("ducks and track stats", t2);
    // What reaches the master bus, in the order it is summed (the same sum every run): the direct tracks in schedule
    // order, then the buses (bus.rs sums them block by block from disk).
    let mut inputs: Vec<Arc<Tape>> = vec![];
    let (mut ducks, mut stats, mut stems) = (vec![], vec![], vec![]);
    // What the buses take (buses.rs): the outputs of the tracks that route or send to one.
    let mut routed: Vec<Option<Arc<Tape>>> = s.tracks.iter().map(|_| None).collect();
    for (k, p) in placed.into_iter().enumerate() {
        let track = &s.tracks[k];
        let out = p.ducked.unwrap_or_else(|| rendered.outs[k].clone());
        ducks.extend(p.duck);
        if keep.get(k).copied().unwrap_or(false) {
            stems.push((track.name.clone(), out.clone()));
        }
        let Some(st) = p.stats else { continue };
        stats.push(st);
        // A feeder reaches the master through its bus.
        if track.into.is_some() {
            continue;
        }
        if crate::mix::buses::direct(s, track) {
            inputs.push(out.clone());
        }
        if crate::mix::buses::feeds_buses(track) {
            routed[k] = Some(out);
        }
    }
    let keep_stems = keep.iter().any(|&k| k);
    let (bus_stats, bus_stems, bus_outs) = crate::mix::buses::mix(s, routed, &rendered.pres, buf, keep_stems)?;
    inputs.extend(bus_outs);
    let t3 = std::time::Instant::now();
    let mut mix = crate::mix::bus::master(s, &inputs)?;
    prof("master", t3);
    mix.buses = bus_stats;
    mix.ducks = ducks;
    mix.tracks = stats;
    mix.stems = stems;
    mix.bus_stems = bus_stems;
    Ok(mix)
}
