//! The mix, offline — the one render the screen's playback and every export go through: each clip into its
//! own buffer (content, speed, reverse, glitch, filter sweep, tone, fades and gain, reverb), clips summed into
//! their track (tone, inserts), the track placed in the bed (stereo: the pan law; surround or an object: the
//! panner, panner.rs; a bed track: as it is), its reverb send (tracks.rs); ducking under the dialogue / sfx
//! level and each track's measures (placed.rs); the tracks summed into the master bus (bus.rs); the stems
//! written through the master's gain (stems.rs). Each track lives on disk once rendered (tape.rs) and the later
//! stages read it in blocks, so memory holds a few tracks and the master bus, never every track: it does not
//! grow with the track count. Jobs run in parallel, combined in a fixed order: the result does not depend on
//! the thread count. Every stage after the panner works on the bed's channels (bed/).

mod clip;
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

/// Tracks measured at once: each measure holds a mono copy of its track (f64) while its five bands run on
/// their own cores, so a few at a time keep a long soundtrack's peak memory near the sequential one's.
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
    // The tracks summed into the master bus in schedule order (the same sum every run), block by block from disk.
    let mut bus = vec![vec![0.0f32; buf]; s.layout.channels()];
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
        let direct = crate::mix::buses::direct(s, track);
        if direct {
            out.add_into(&mut bus)?;
        }
        if crate::mix::buses::feeds_buses(track) {
            routed[k] = Some(out);
        }
    }
    let keep_stems = keep.iter().any(|&k| k);
    let (bus_stats, bus_stems) = crate::mix::buses::mix(s, routed, &rendered.pres, &mut bus, keep_stems)?;
    let t3 = std::time::Instant::now();
    let mut mix = crate::mix::bus::master(s, bus)?;
    prof("master", t3);
    mix.buses = bus_stats;
    mix.ducks = ducks;
    mix.tracks = stats;
    mix.stems = stems;
    mix.bus_stems = bus_stems;
    Ok(mix)
}
