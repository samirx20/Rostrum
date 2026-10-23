use super::stats::track_stats;
use super::*;
use crate::bed::Layout;

#[test]
fn a_track_reports_where_its_hits_start() {
    // Silence, then a decaying hit every 0.25 s from 0.5 s: each hit is an onset on its own track.
    let sr = 44100.0;
    let total = (sr * 1.5) as usize;
    let l: Vec<f32> = (0..total)
        .map(|i| {
            let t = i as f64 / sr;
            if t < 0.5 { 0.0 } else { (0.6 * (-((t - 0.5) % 0.25) * 40.0).exp() * (t * 900.0).sin()) as f32 }
        })
        .collect();
    let s = track_stats("drums", &[l.clone(), l], total, sr, Layout::Stereo);
    assert_eq!(s.onsets, vec![0.5, 0.75, 1.0, 1.25]);
}

pub(crate) const SCHEDULE: &str = r#"{"version":6,"sampleRate":44100,"totalSamples":66150,"tailSamples":0,"fadeInSamples":128,"fadeOutSamples":1543,
      "masterVolume":0.9,"masterReverb":"hall","trackReverbSpace":"hall","timeWarps":[{"start":0.5,"duration":0.6,"rateTo":0.4,"subDrop":true}],"tracks":[
      {"name":"keys","tone":"warm","volume":0.85,"pan":0.2,"reverb":0.4,"ducks":[{"from":[1],"depth":0.78,"attack":0.012,"release":0.26,"lookahead":0.018,"voice":true,"report":true}],"clips":[
        {"startSample":2205,"samples":60000,"duration":1.2,"content":{"kind":"score","voices":[{"kind":"note","instrument":"warmPad","freqs":[261.63,329.63,392],"startIdx":0,"duration":1.2,"velocity":0.8,"pan":0}]},
         "rate":null,"reverse":null,"glitch":null,"filterSweep":{"fromHz":400,"toHz":9000,"linear":false},"tone":"neutral","fadeIn":0.1,"fadeOut":0.2,"volume":1,"pan":0,"reverb":0.3}]},
      {"name":"fx","tone":"neutral","volume":0.9,"pan":0,"reverb":0.2,"ducks":[],"clips":[
        {"startSample":11025,"samples":20000,"duration":0.4,"content":{"kind":"sfx","preset":"riser","material":null,"duration":0.4,"volume":0.9,"pitch":0,"panFrom":-0.8,"panTo":0.8},
         "rate":{"from":0.8,"to":null,"preservePitch":false},"reverse":null,"glitch":{"stutterRate":20,"repeats":4},"filterSweep":null,"tone":"bright","fadeIn":0,"fadeOut":0,"volume":1,"pan":0,"reverb":0},
        {"startSample":30000,"samples":30000,"duration":0.6,"content":{"kind":"sfx","preset":"impact","material":{"baseFreq":1820,"ratios":[1,2.32,4.18],"decay":8.5,"noiseMix":0.12},"duration":0.6,"volume":0.9,"pitch":0,"panFrom":0,"panTo":0},
         "rate":null,"reverse":0.65,"glitch":null,"filterSweep":null,"tone":"neutral","fadeIn":0.27,"fadeOut":0.015,"volume":1,"pan":0,"reverb":0}]}]}"#;

#[test]
fn renders_the_same_every_time() {
    let s = Schedule::parse(SCHEDULE).unwrap();
    let a = render(&s).unwrap();
    let b = render(&s).unwrap();
    let (ac, bc) = (a.channels().unwrap(), b.channels().unwrap());
    assert_eq!(ac[0].len(), 66150);
    assert!(a.peak > 0.05, "silent render");
    assert_eq!(ac, bc);
    assert_eq!(a.ducks.len(), 1, "the keys track reports its ducking");
    assert!(!a.ducks[0].1.is_empty(), "the keys dip under the fx");
}

#[test]
fn a_missing_pcm_file_is_an_error_naming_it() {
    let s = SCHEDULE.replace(r#"{"kind":"sfx","preset":"riser","material":null,"duration":0.4,"volume":0.9,"pitch":0,"panFrom":-0.8,"panTo":0.8}"#, r#"{"kind":"media","pcm":{"file":"nowhere/take.f32","channels":2,"frames":100}}"#);
    let err = render(&Schedule::parse(&s).unwrap()).err().expect("an error");
    assert!(err.contains("nowhere/take.f32"), "{err}");
}

#[test]
fn a_surround_schedule_renders_its_bed_with_every_stage_on_every_channel() {
    // The same schedule in 5.1: keys placed wide, the fx flying from Ls to Rs with an LFE send, the
    // master reverb, ducks, time warps and a mastering stage — all on six channels, deterministic.
    let s = SCHEDULE
        .replace(r#""version":6,"#, r#""version":7,"layout":"5.1","master":{"loudness":-23,"truePeak":-1,"glue":0.3},"effects":[{"type":"compressor","threshold":-20,"ratio":2,"attack":10,"release":100,"makeup":0,"knee":6},{"type":"delay","time":0.2,"feedback":0.3,"mix":0.2,"pingPong":true,"damp":6000}],"#)
        .replace(r#"{"name":"keys","tone":"warm","volume":0.85,"pan":0.2,"reverb":0.4,"#, r#"{"name":"keys","tone":"warm","volume":0.85,"pan":0.2,"reverb":0.4,"surround":{"az":0,"el":0,"dist":1,"spread":0.5,"lfe":0,"centre":0},"#)
        .replace(r#"{"name":"fx","tone":"neutral","volume":0.9,"pan":0,"reverb":0.2,"#, r#"{"name":"fx","tone":"neutral","volume":0.9,"pan":0,"reverb":0.2,"surround":{"az":[[0,-110],[1.5,110]],"el":0,"dist":1,"spread":0,"lfe":0.5,"centre":1},"#);
    let sched = Schedule::parse(&s).unwrap();
    let a = render(&sched).unwrap();
    let b = render(&sched).unwrap();
    let (ac, bc) = (a.channels().unwrap(), b.channels().unwrap());
    assert_eq!(ac.len(), 6);
    assert_eq!(ac, bc);
    assert!((a.lufs - -23.0).abs() < 0.3, "BS.1770 with channel weights: {}", a.lufs);
    assert!(a.true_peak <= -1.0, "{}", a.true_peak);
    let energy = |c: usize| ac[c].iter().map(|v| (*v as f64).powi(2)).sum::<f64>();
    assert!((0..6).all(|c| energy(c) > 0.0), "every channel sounds");
    assert!(a.tracks.iter().all(|t| t.shares.as_ref().is_some_and(|s| s.len() == 6)));
    let report = crate::mix::bus::surround_report(a.layout, &ac, a.lufs, 44100.0);
    assert_eq!(report["channels"].as_array().unwrap().len(), 6);
}

// ---- The transparent path (Phase 0 K4: generated test signals through the engine) ----------------------------
// A file placed on a track and rendered with nothing added: no master reverb, no master effects, no fades, a
// neutral track at unity. What comes out is what went in (to float rounding), and nothing rings on after it.
// The defaults a soundtrack gets from the front (the master "hall" reverb at 0.18, the "balanced" production EQ)
// are deliberate and live in the schedule it sends, not in the engine: these tests keep the engine itself honest.

/// One stereo f32 file: a sine of `hz` at `amp` for `secs` seconds, written under the per-run test folder.
fn sine_file(name: &str, sr: u32, hz: f64, amp: f64, secs: f64) -> (String, usize) {
    let n = (sr as f64 * secs) as usize;
    let dir = std::env::temp_dir().join(format!("rostrum-transparent-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let file = dir.join(format!("{name}-{sr}.f32"));
    let bytes: Vec<u8> = (0..n).flat_map(|i| { let v = (amp * (2.0 * std::f64::consts::PI * hz * i as f64 / sr as f64).sin()) as f32; [v, v] }).flat_map(|v| v.to_le_bytes()).collect();
    std::fs::write(&file, bytes).unwrap();
    (file.to_string_lossy().replace('\\', "\\\\"), n)
}

/// A schedule of one media clip at 0.5 s in a 3 s mix, with the master reverb `space`.
fn clip_schedule(file: &str, frames: usize, sr: u32, space: &str) -> Schedule {
    let (start, total) = (sr as usize / 2, sr as usize * 3);
    Schedule::parse(&format!(
        r#"{{"version":7,"layout":"stereo","sampleRate":{sr},"totalSamples":{total},"tailSamples":0,"fadeInSamples":0,"fadeOutSamples":0,"masterVolume":1,"masterReverb":"{space}","trackReverbSpace":"room","effects":[],"master":null,"timeWarps":[],"tracks":[
        {{"name":"sig","tone":"neutral","volume":1,"pan":0,"reverb":0,"mix":true,"ducks":[],"effects":[],"automation":{{}},"into":null,"surround":null,"bed":false,"clips":[
        {{"startSample":{start},"samples":{frames},"duration":{},"content":{{"kind":"media","pcm":{{"file":"{file}","channels":2,"frames":{frames}}}}},"rate":null,"reverse":null,"glitch":null,"filterSweep":null,"tone":"neutral","fadeIn":0,"fadeOut":0,"volume":1,"pan":0,"reverb":0,"repair":[],"effects":[],"matchEq":null}}]}}]}}"#,
        frames as f64 / sr as f64
    ))
    .unwrap()
}

fn db(x: f64) -> f64 {
    20.0 * x.max(1e-12).log10()
}

#[test]
fn a_file_through_a_dry_unprocessed_mix_comes_out_as_it_went_in() {
    for sr in [44100u32, 48000] {
        for (hz, name) in [(1000.0, "k1"), (18000.0, "k18")] {
            let (file, n) = sine_file(name, sr, hz, 0.125, 2.0); // -18 dBFS
            let s = clip_schedule(&file, n, sr, "dry");
            let mix = render_with(&s, None).unwrap().channels().unwrap();
            let start = sr as usize / 2;
            let (mut worst, mut tail) = (0.0f64, 0.0f64);
            for i in 0..mix[0].len() {
                let want = if i >= start && i < start + n { (0.125 * (2.0 * std::f64::consts::PI * hz * (i - start) as f64 / sr as f64).sin()) as f32 as f64 } else { 0.0 };
                worst = worst.max((mix[0][i] as f64 - want).abs());
                if i >= start + n {
                    tail = tail.max((mix[0][i] as f64).abs());
                }
            }
            assert!(worst < 1e-6, "{hz} Hz at {sr}: the engine changed the signal by {} dB re full scale", db(worst));
            assert!(tail == 0.0, "{hz} Hz at {sr}: {} dBFS still sounds after the file ends", db(tail));
        }
    }
}

#[test]
fn the_master_hall_reverb_is_what_costs_a_sine_its_level_and_gives_it_a_tail() {
    // The measured, deliberate cost of the default master reverb (schedule "hall", 0.18 wet): the dry path is scaled by
    // 1 - 0.18 * 0.35 (-0.56 dB) and the combs ring on after the file: a few tenths of a second to -60 dB.
    let sr = 48000u32;
    let (file, n) = sine_file("hall", sr, 1000.0, 0.125, 2.0);
    let dry = render_with(&clip_schedule(&file, n, sr, "dry"), None).unwrap();
    let hall = render_with(&clip_schedule(&file, n, sr, "hall"), None).unwrap();
    let (a, b) = (sr as usize, sr as usize + 4800);
    let peak = |m: &Mix| m.channels().unwrap()[0][a..b].iter().fold(0.0f64, |p, v| p.max((*v as f64).abs()));
    let loss = db(peak(&hall)) - db(peak(&dry));
    assert!((-0.9..=-0.1).contains(&loss), "a 1 kHz sine through the hall: {loss:.2} dB");
    let end = sr as usize / 2 + n;
    let ring = |m: &Mix| { let c = m.channels().unwrap(); (end..c[0].len()).rev().find(|&i| db((c[0][i] as f64).abs() / 0.125) > -60.0).map_or(0.0, |i| (i - end) as f64 / sr as f64) };
    assert_eq!(ring(&dry), 0.0);
    assert!((0.15..=0.8).contains(&ring(&hall)), "the hall's tail: {:.2} s", ring(&hall));
}
