//! Buses, sends, routing, fade shapes, lanes and invert (buses.rs, clipshape.rs): measured on small mixes.

use crate::mix::render::render_with;
use crate::mix::schedule::Schedule;
use crate::mix::trackcache::TrackCache;

const CLIP: &str = r#"{"startSample":0,"samples":22050,"duration":1,"content":{"kind":"score","voices":[{"kind":"note","instrument":"warmPad","freqs":[220],"startIdx":0,"duration":0.9,"velocity":0.8,"pan":0}]},"rate":null,"reverse":null,"glitch":null,"filterSweep":null,"tone":"neutral","fadeIn":0,"fadeOut":0,"volume":1,"pan":0,"reverb":0EXTRA}"#;

fn track(name: &str, extra: &str, clip_extra: &str) -> String {
    format!(r#"{{"name":"{name}","tone":"neutral","volume":1,"pan":0,"reverb":0{extra},"clips":[{}]}}"#, CLIP.replace("EXTRA", clip_extra))
}

fn sched(tracks: &[String], extra: &str) -> Schedule {
    let json = format!(r#"{{"version":8,"sampleRate":22050,"totalSamples":22050,"tailSamples":0,"fadeInSamples":0,"fadeOutSamples":0,"masterVolume":1,"masterReverb":"dry","trackReverbSpace":"dry","timeWarps":[],"tracks":[{}]{extra}}}"#, tracks.join(","));
    Schedule::parse(&json).unwrap()
}

fn mix(s: &Schedule) -> Vec<Vec<f32>> {
    render_with(s, None).unwrap().channels
}

fn rms(chs: &[Vec<f32>]) -> f64 {
    (chs.iter().flat_map(|c| c.iter()).map(|v| (*v as f64).powi(2)).sum::<f64>() / (chs.len() * chs[0].len()) as f64).sqrt()
}

/// The largest difference between two mixes, against the first one's peak.
fn diff(a: &[Vec<f32>], b: &[Vec<f32>]) -> f64 {
    let peak = a.iter().flat_map(|c| c.iter()).fold(0.0f64, |m, v| m.max((*v as f64).abs()));
    a.iter().zip(b).flat_map(|(x, y)| x.iter().zip(y)).fold(0.0f64, |m, (p, q)| m.max((*p as f64 - *q as f64).abs())) / peak.max(1e-12)
}

const BUS: &str = r#"{"name":"group","volume":1,"pan":0}"#;

#[test]
fn a_track_through_a_bus_sounds_as_it_does_on_the_master_and_the_bus_fader_scales_it() {
    let direct = mix(&sched(&[track("keys", "", "")], ""));
    let routed = render_with(&sched(&[track("keys", r#","output":0"#, "")], &format!(r#","buses":[{BUS}]"#)), None).unwrap();
    assert!(diff(&direct, &routed.channels) < 1e-5);
    assert_eq!(routed.buses.len(), 1);
    assert!(routed.buses[0].rms > 0.0 && routed.tracks.len() == 1);
    let half = mix(&sched(&[track("keys", r#","output":0"#, "")], r#","buses":[{"name":"group","volume":0.5,"pan":0}]"#));
    assert!((rms(&half) / rms(&direct) - 0.5).abs() < 1e-3);
    let muted = mix(&sched(&[track("keys", r#","output":0"#, "")], r#","buses":[{"name":"group","volume":1,"pan":0,"muted":true}]"#));
    assert_eq!(rms(&muted), 0.0);
}

#[test]
fn a_pre_fader_send_survives_the_track_fader_at_zero_and_a_post_fader_send_does_not() {
    let direct = mix(&sched(&[track("keys", "", "")], ""));
    let bus = format!(r#","buses":[{BUS}]"#);
    let pre = mix(&sched(&[track("keys", r#","volume":0,"sends":[{"bus":0,"level":1,"pre":true}]"#, "")], &bus));
    assert!(diff(&direct, &pre) < 1e-5, "the pre-fader send is the track before its fader");
    let post = mix(&sched(&[track("keys", r#","volume":0,"sends":[{"bus":0,"level":1}]"#, "")], &bus));
    assert_eq!(rms(&post), 0.0);
    // A post-fader send at 0.5 beside the direct track: the mix is 1.5× the track.
    let both = mix(&sched(&[track("keys", r#","sends":[{"bus":0,"level":0.5}]"#, "")], &bus));
    assert!((rms(&both) / rms(&direct) - 1.5).abs() < 1e-3);
    // A send level that moves: silent for the first half, full after.
    let lane = mix(&sched(&[track("keys", r#","volume":0,"sends":[{"bus":0,"level":[[0,0],[0.49,0],[0.5,1]],"pre":true}]"#, "")], &bus));
    let half = |c: &Vec<f32>, a: usize, b: usize| c[a..b].iter().map(|v| (*v as f64).abs()).sum::<f64>();
    assert_eq!(half(&lane[0], 0, 10000), 0.0);
    assert!(half(&lane[0], 11100, 20000) > 0.0);
}

#[test]
fn bus_effects_run_on_the_sum_and_nested_buses_feed_their_parent() {
    let lowpass = r#"{"name":"dark","volume":1,"pan":0,"effects":[{"type":"eq","bands":[{"shape":"lowpass","freq":300,"gain":0,"q":0.7}]}],"output":1}"#;
    let s = sched(&[track("keys", r#","output":0"#, r#","volume":0.5"#), track("pad", r#","output":0"#, r#","volume":0.5"#)], &format!(r#","buses":[{lowpass},{{"name":"music","volume":1,"pan":0}}]"#));
    let r = render_with(&s, None).unwrap();
    let plain = mix(&sched(&[track("keys", "", r#","volume":0.5"#), track("pad", "", r#","volume":0.5"#)], ""));
    assert!(rms(&r.channels) < rms(&plain) * 0.9, "the low-pass on the bus took the highs");
    assert_eq!(r.buses.iter().map(|b| b.name.as_str()).collect::<Vec<_>>(), ["dark", "music"]);
    assert!((r.buses[0].rms - r.buses[1].rms).abs() < 1e-6, "the parent holds what its child gave it");
}

#[test]
fn a_routing_loop_is_an_error_naming_it() {
    let s = sched(&[track("keys", r#","output":0"#, "")], r#","buses":[{"name":"a","volume":1,"pan":0,"output":1},{"name":"b","volume":1,"pan":0,"output":0}]"#);
    let err = render_with(&s, None).err().expect("a loop");
    assert!(err.contains("loops") && err.contains("\"a\"") && err.contains("\"b\""), "{err}");
    let s = sched(&[track("keys", r#","output":3"#, "")], &format!(r#","buses":[{BUS}]"#));
    assert!(render_with(&s, None).err().unwrap().contains("there are 1 buses"));
}

#[test]
fn a_bus_stem_holds_that_bus_and_the_direct_stem_the_rest() {
    let tracks = [track("keys", r#","output":0"#, ""), track("pad", "", r#","volume":0.3"#)];
    let bus = format!(r#","buses":[{BUS}]"#);
    let full = mix(&sched(&tracks, &bus));
    let one = mix(&sched(&tracks, &format!(r#"{bus},"tap":{{"bus":0}}"#)));
    let rest = mix(&sched(&tracks, &format!(r#"{bus},"tap":{{"bus":null}}"#)));
    let sum: Vec<Vec<f32>> = one.iter().zip(&rest).map(|(a, b)| a.iter().zip(b).map(|(x, y)| x + y).collect()).collect();
    assert!(diff(&full, &sum) < 1e-5, "the stems sum to the mix");
    assert!(diff(&mix(&sched(&[track("keys", "", "")], "")), &one) < 1e-5);
}

#[test]
fn invert_flips_the_track_and_the_clip_and_cancels_against_the_original() {
    let plain = mix(&sched(&[track("keys", "", "")], ""));
    for (t, c) in [(r#","invert":true"#, ""), ("", r#","invert":true"#)] {
        let flipped = mix(&sched(&[track("keys", t, c)], ""));
        assert!(diff(&plain, &flipped.iter().map(|ch| ch.iter().map(|v| -v).collect()).collect::<Vec<Vec<f32>>>()) < 1e-6);
        let both = mix(&sched(&[track("keys", "", ""), track("flip", t, c)], ""));
        assert!(rms(&both) < 1e-6, "{}", rms(&both));
    }
}

#[test]
fn fade_shapes_lanes_and_the_master_lane_shape_the_sound() {
    let fade = |shape: &str| mix(&sched(&[track("keys", "", &format!(r#","fadeIn":0.8,"fadeInCurve":"{shape}""#))], ""));
    let early = |c: &[Vec<f32>]| c[0][4000..7000].iter().map(|v| (*v as f64).powi(2)).sum::<f64>();
    let (exp, lin, log) = (fade("exponential"), fade("linear"), fade("logarithmic"));
    assert!(early(&exp) < early(&lin) && early(&lin) < early(&log));
    let eq = fade("equalPower");
    let old = mix(&sched(&[track("keys", "", r#","fadeIn":0.8"#)], ""));
    assert_eq!(eq, old, "equalPower is the old fade, bit for bit");
    // A clip's volume lane (clip seconds) and the master lane silence the first half.
    let clip_lane = mix(&sched(&[track("keys", "", r#","automation":{"volume":[[0,0],[0.49,0],[0.5,1]]}"#)], ""));
    let master_lane = mix(&sched(&[track("keys", "", "")], r#","masterAutomation":[[0,0],[0.49,0],[0.5,1]]"#));
    for m in [&clip_lane, &master_lane] {
        assert_eq!(m[0][..10000].iter().map(|v| v.abs()).sum::<f32>(), 0.0);
        assert!(m[0][11100..].iter().map(|v| v.abs()).sum::<f32>() > 0.0);
    }
    // A clip's pan lane: hard left, then hard right.
    let pan = mix(&sched(&[track("keys", "", r#","automation":{"pan":[[0,-1],[0.49,-1],[0.5,1]]}"#)], ""));
    assert!(pan[1][..10000].iter().all(|v| v.abs() < 1e-7) && pan[0][11100..].iter().all(|v| v.abs() < 1e-7));
}

#[test]
fn a_cached_mix_with_buses_and_a_pre_fader_send_is_the_uncached_mix() {
    let dir = std::env::temp_dir().join(format!("rostrum-buscache-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    let cache = TrackCache::at(dir.clone());
    let s = sched(&[track("keys", r#","output":0,"sends":[{"bus":1,"level":0.4,"pre":true}]"#, ""), track("pad", r#","sends":[{"bus":1,"level":0.2}]"#, "")], r#","buses":[{"name":"group","volume":0.8,"pan":0.3},{"name":"verb","volume":1,"pan":0,"effects":[{"type":"reverb","space":"hall","mix":1}]}]"#);
    let plain = mix(&s);
    let cold = render_with(&s, Some(&cache)).unwrap().channels;
    let warm = render_with(&s, Some(&cache)).unwrap().channels;
    assert_eq!(plain, cold);
    assert_eq!(plain, warm);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn the_safety_clip_is_on_by_default_and_a_schedule_can_bypass_it() {
    let loud = |extra: &str| mix(&sched(&[track("keys", r#","volume":8"#, "")], extra));
    let peak = |m: &[Vec<f32>]| m.iter().flat_map(|c| c.iter()).fold(0.0f64, |p, v| p.max((*v as f64).abs()));
    let (on, explicit, off) = (loud(""), loud(r#","safetyClip":true"#), loud(r#","safetyClip":false"#));
    assert!(peak(&on) < 1.0 && peak(&on) > 0.891, "default: soft-clipped under full scale, got {}", peak(&on));
    assert_eq!(on, explicit);
    assert!(peak(&off) > 1.0, "bypassed: the samples the mix holds, past full scale, got {}", peak(&off));
    // Quiet material is the same either way (the clip only acts above -1 dBFS).
    let quiet = |extra: &str| mix(&sched(&[track("keys", "", "")], extra));
    assert_eq!(quiet(""), quiet(r#","safetyClip":false"#));
}
