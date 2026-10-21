//! The mix, offline: each clip into its own buffer (content, speed, reverse, glitch, filter sweep,
//! tone, fades and gain, reverb), clips summed into their track (tone, inserts), the track placed in
//! the bed (stereo: the pan law; surround or an object: the panner, panner.rs; a bed track: as it is),
//! its reverb send, ducking under the dialogue / sfx level, then the master bus (bus.rs). Clips render
//! in parallel (each is independent), so the result does not depend on the thread count. Every stage
//! after the panner works on the bed's channels (bed/); stereo renders as it always did.

mod clip;
pub mod stats;
#[cfg(test)]
pub(crate) mod tests;
mod track;

use crate::mix::duck;
use crate::mix::schedule::Schedule;
use clip::render_clips;
use stats::{track_stats, Mix};
use track::track_out;

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
/// (after its effects, fader and ducks), cut to the mix's length.
pub fn render_keep(s: &Schedule, cache: Option<&crate::mix::trackcache::TrackCache>, keep: &[bool]) -> Result<Mix, String> {
    let sr = s.sample_rate as f64;
    let total = s.total_samples;
    let buf = total + s.tail_samples;
    let t0 = std::time::Instant::now();
    let cache = cache.filter(|_| s.track_keys.len() == s.tracks.len());
    let mut done: Vec<Option<Vec<Vec<f32>>>> = match cache {
        // A track that sends from before its fader renders (its tap is not cached).
        Some(c) => crate::mix::par::map_n((0..s.tracks.len()).collect(), MEASURE_THREADS, |k| if crate::mix::buses::has_pre(&s.tracks[k]) { None } else { c.load(&s.track_keys[k], buf) }),
        None => (0..s.tracks.len()).map(|_| None).collect(),
    };
    let want: Vec<bool> = done.iter().map(Option::is_none).collect();
    prof(&format!("cached tracks read ({} of {})", want.iter().filter(|w| !**w).count(), want.len()), t0);
    let clips = render_clips(s, &want)?;
    prof("clips", t0);
    // Feeders first, then the buses they feed (one level of grouping: a layered instrument's layers);
    // the tracks of a level on all cores (each track is independent of the others in its level).
    let t1 = std::time::Instant::now();
    let feeds = |k: usize| s.tracks.iter().any(|t| t.into == Some(k));
    let mut rendered_clips: Vec<Option<Vec<Vec<Vec<f32>>>>> = clips.into_iter().map(Some).collect();
    let mut pres: Vec<Option<Vec<Vec<f32>>>> = s.tracks.iter().map(|_| None).collect();
    for buses in [false, true] {
        let level: Vec<(usize, Vec<Vec<Vec<f32>>>)> = (0..s.tracks.len()).filter(|&k| want[k] && feeds(k) == buses).map(|k| (k, rendered_clips[k].take().unwrap_or_default())).collect();
        let done_ref = &done;
        let outs = crate::mix::par::map(level, |(k, clips)| {
            let feeders: Vec<&Vec<Vec<f32>>> = s.tracks.iter().enumerate().filter(|(_, t)| t.into == Some(k)).filter_map(|(j, _)| done_ref[j].as_ref()).collect();
            let out = track_out(s, &s.tracks[k], clips, feeders, buf);
            if let (Some(c), Ok((out, _))) = (cache, &out) {
                c.store(&s.track_keys[k], out);
            }
            (k, out)
        });
        for (k, out) in outs {
            let (out, pre) = out?;
            done[k] = Some(out);
            pres[k] = pre;
        }
    }
    prof("tracks", t1);
    let tracks: Vec<Vec<Vec<f32>>> = done.into_iter().map(|t| t.expect("every track rendered")).collect();
    // Each source's level (before anything ducks), read by the ducks that name it.
    let level = |from: &[usize]| -> Vec<f32> {
        let mut t = vec![0.0f32; buf];
        for &k in from.iter().filter(|&&k| k < tracks.len()) {
            for c in &tracks[k] {
                for i in 0..buf {
                    t[i] = t[i].max(c[i].abs());
                }
            }
        }
        t
    };
    let t2 = std::time::Instant::now();
    let duck_jobs: Vec<(usize, &crate::mix::schedule::Duck)> = s.tracks.iter().enumerate().flat_map(|(k, t)| t.ducks.iter().map(move |d| (k, d))).collect();
    let mut triggers = crate::mix::par::map(duck_jobs, |(k, d)| (k, level(&d.from), d)).into_iter().peekable();
    let jobs: Vec<_> = s.tracks.iter().zip(tracks).enumerate().map(|(k, (track, chs))| {
        let mut own = vec![];
        while let Some((_, trigger, d)) = triggers.next_if(|(j, ..)| *j == k) {
            own.push((trigger, d));
        }
        (track, chs, own)
    }).collect();
    // Ducking and each track's measures, on all cores.
    let placed = crate::mix::par::map_n(jobs, MEASURE_THREADS, |(track, mut chs, track_ducks)| {
        let mut dips: Vec<duck::DuckSpan> = vec![];
        let mut report = false;
        for (trigger, d) in &track_ducks {
            let spans = duck::duck_n(&mut crate::bed::slices(&mut chs), trigger, sr, d);
            if d.report {
                report = true;
                dips.extend(spans);
            }
        }
        let duck = report.then(|| {
            dips.sort_by(|a, b| a.0.total_cmp(&b.0));
            (track.name.clone(), dips)
        });
        let stats = track.mix.then(|| track_stats(&track.name, &chs, total, sr, s.layout));
        (track, chs, duck, stats)
    });
    prof("ducks and track stats", t2);
    // The tracks summed into the master bus in schedule order (the same sum every run).
    let mut bus = vec![vec![0.0f32; buf]; s.layout.channels()];
    let (mut ducks, mut stats, mut stems) = (vec![], vec![], vec![]);
    // What the buses take (buses.rs): the outputs of the tracks that route or send to one.
    let mut routed: Vec<Option<Vec<Vec<f32>>>> = s.tracks.iter().map(|_| None).collect();
    for (k, (track, chs, duck, st)) in placed.into_iter().enumerate() {
        ducks.extend(duck);
        if keep.get(k).copied().unwrap_or(false) {
            stems.push((track.name.clone(), chs.iter().map(|c| c[..total.min(c.len())].to_vec()).collect()));
        }
        let Some(st) = st else { continue };
        stats.push(st);
        // A feeder reaches the master through its bus.
        if track.into.is_some() {
            continue;
        }
        if crate::mix::buses::feeds_buses(track) {
            if crate::mix::buses::direct(s, track) {
                crate::mix::buses::add_into(&mut bus, &chs);
            }
            routed[k] = Some(chs);
            continue;
        }
        if !crate::mix::buses::direct(s, track) {
            continue;
        }
        for (dst, src) in bus.iter_mut().zip(&chs) {
            for i in 0..buf {
                dst[i] += src[i];
            }
        }
    }
    let (bus_stats, bus_stems) = crate::mix::buses::mix(s, routed, &pres, &mut bus, keep.iter().any(|&k| k))?;
    let t3 = std::time::Instant::now();
    let mut mix = crate::mix::bus::master(s, bus)?;
    mix.buses = bus_stats;
    prof("master", t3);
    mix.ducks = ducks;
    mix.tracks = stats;
    mix.stems = stems;
    mix.bus_stems = bus_stems;
    Ok(mix)
}
