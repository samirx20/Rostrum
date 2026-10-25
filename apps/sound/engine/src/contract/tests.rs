//! The contract's guards: unknown names fail loudly, and a render request comes back whole (mix, stems,
//! meters), with recorded media decoded by the engine.

use super::answer;
use serde_json::{json, Value};

fn error_of(req: Value) -> Value {
    let a = answer(&req);
    assert_eq!(a["ok"], json!(false), "expected a refusal, got {a}");
    a["error"].clone()
}

fn check(schedule: Value) -> Value {
    json!({ "do": "check", "schedule": schedule })
}

#[test]
fn unknown_names_fail_loudly() {
    let base = || json!({ "contract": "rostrum-sound-schedule/1", "tracks": [{ "id": "keys", "instrument": { "builtIn": "classic.grandPiano" },
        "notes": [{ "pitch": "C4", "at": 0, "dur": 1 }] }] });
    let cases: Vec<(Value, &str, &str)> = vec![
        ({ let mut s = base(); s["tracks"][0]["tone"] = json!("warmm"); s }, "schedule.tracks[0].tone", "warm"),
        ({ let mut s = base(); s["tracks"][0]["volumee"] = json!(1); s }, "schedule.tracks[0].volumee", "volume"),
        ({ let mut s = base(); s["tracks"][0]["effects"] = json!([{ "type": "reverbb" }]); s }, "schedule.tracks[0].effects[0].type", "reverb"),
        ({ let mut s = base(); s["tracks"][0]["effects"] = json!([{ "type": "eq", "bands": [{ "shape": "peek", "freq": 100 }] }]); s }, "schedule.tracks[0].effects[0].bands[0].shape", "peak"),
        ({ let mut s = base(); s["tracks"][0]["instrument"] = json!({ "builtIn": "grandpiano" }); s }, "schedule.tracks[0].instrument.builtIn", "grandPiano"),
        ({ let mut s = base(); s["tracks"][0]["notes"][0]["pitch"] = json!("H4"); s }, "schedule.tracks[0].notes[0].pitch", ""),
        ({ let mut s = base(); s["master"] = json!({ "reverb": "hal" }); s }, "schedule.master.reverb", "hall"),
        ({ let mut s = base(); s["tracks"][0]["instrument"] = json!({ "model": "guitarr" }); s }, "schedule.tracks[0].instrument.model", "guitar"),
        ({ let mut s = base(); s["tracks"][0]["instrument"] = json!({ "synth": "saww" }); s }, "schedule.tracks[0].instrument.synth", "saw"),
        ({ let mut s = base(); s["tracks"][0]["expression"] = json!({ "vibratoo": [[0, 1]] }); s }, "schedule.tracks[0].expression.vibratoo", "vibrato"),
    ];
    // A touch the instrument doesn't play is refused, never ignored (a marimba isn't damped; only model tracks take touch).
    let e = error_of(check({ let mut s = base(); s["tracks"][0]["instrument"] = json!({ "model": "marimba", "damping": 0.5 }); s }));
    assert_eq!(e["where"], json!("schedule.tracks[0].instrument.damping"), "{e}");
    let e = error_of(check({ let mut s = base(); s["tracks"][0]["notes"][0]["position"] = json!(0.2); s }));
    assert_eq!(e["where"], json!("schedule.tracks[0].notes[0].position"), "{e}");
    for (s, at, hint) in cases {
        let e = error_of(check(s));
        assert_eq!(e["where"], json!(at), "{e}");
        assert!(e["hint"].as_str().unwrap().contains(hint), "{e}");
    }
    let e = error_of(check({ let mut s = base(); s["contract"] = json!("rostrum-sound-schedule/2"); s }));
    assert!(e["hint"].as_str().unwrap().contains("rostrum-sound-schedule/1"), "{e}");
    assert_eq!(error_of(json!({ "do": "rendr" }))["hint"], json!("Did you mean render?"));
}

#[test]
fn defaults_are_filled_and_beats_become_seconds() {
    let a = answer(&check(json!({ "contract": "rostrum-sound-schedule/1", "tempo": 120, "tracks": [{ "id": "keys",
        "instrument": { "builtIn": "warmPad" }, "notes": [{ "pitch": ["C4", "E4"], "at": { "beat": 4 }, "dur": { "beats": 2 } }] }] })));
    let r = &a["result"]["resolved"];
    let n = &r["tracks"][0]["notes"][0];
    assert_eq!((n["at"].clone(), n["dur"].clone(), n["vel"].clone(), n["pitch"].clone()), (json!(2.0), json!(1.0), json!(0.8), json!([60.0, 64.0])));
    assert_eq!(r["tracks"][0]["volume"], json!(0.85));
    assert_eq!(a["result"]["length"], json!(5.0)); // last note ends at 3 s, plus 2 s
}

#[test]
fn render_request_round_trip() {
    let dir = std::env::temp_dir().join(format!("rostrum-sound-contract-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    // A recorded take for the engine to decode: a 0.5 s 440 Hz tone.
    let tone: Vec<f32> = (0..24000).map(|i| (i as f32 * 440.0 * std::f32::consts::TAU / 48000.0).sin() * 0.3).collect();
    let take = dir.join("take.wav");
    std::fs::write(&take, crate::mix::wavio::write(&[tone.clone(), tone], crate::bed::Layout::Stereo, 48000)).unwrap();
    let out = dir.join("mix.wav");
    let req = json!({ "id": 7, "do": "render", "out": out, "stems": "all", "schedule": {
        "contract": "rostrum-sound-schedule/1", "length": 2.0, "tempo": 120, "master": { "loudness": -18 },
        "tracks": [
            { "id": "drums", "instrument": { "kit": "classic" }, "hits": [{ "drum": "kick", "at": 0 }, { "drum": "snare", "at": { "beat": 1 } }] },
            { "id": "pad", "instrument": { "builtIn": "warmPad" }, "notes": [{ "pitch": "A3", "at": 0, "dur": 1.5 }], "effects": [{ "type": "reverb", "mix": 0.2 }] },
            { "id": "take", "clips": [{ "media": take, "in": 0.1, "at": 1.0 }] }
        ] } });
    let a = answer(&req);
    assert_eq!(a["ok"], json!(true), "{a}");
    assert_eq!(a["id"], json!(7));
    let r = &a["result"];
    assert!(out.is_file() && !dir.join("mix.wav.partial").exists());
    let ids: Vec<&str> = r["tracks"].as_array().unwrap().iter().map(|t| t["id"].as_str().unwrap()).collect();
    assert_eq!(ids, ["drums", "pad", "take"]);
    for id in ids {
        assert!(std::path::Path::new(r["stems"][id].as_str().unwrap()).is_file(), "stem {id}");
    }
    let take_span = r["tracks"][2]["span"][0].as_f64().unwrap();
    assert!((take_span - 1.0).abs() < 0.02, "the take starts at 1 s: {take_span}");
    assert!(r["lufs"].as_f64().unwrap() > -30.0, "{r}");
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn buses_and_sends_route_or_fail_loudly() {
    let s = || json!({ "contract": "rostrum-sound-schedule/1", "length": 1.0,
        "buses": [{ "id": "music", "output": "verb" }, { "id": "verb", "effects": [{ "type": "reverb", "mix": 1.0 }] }],
        "tracks": [{ "id": "pad", "instrument": { "builtIn": "warmPad" }, "notes": [{ "pitch": "A3", "at": 0, "dur": 0.5 }],
            "output": "music", "sends": [{ "bus": "verb", "level": [[0, 0.2], [0.5, 0.8]] }] }] });
    let e = error_of(check({ let mut x = s(); x["tracks"][0]["sends"][0]["bus"] = json!("verbb"); x }));
    assert_eq!(e["where"], json!("schedule.tracks[0].sends[0].bus"), "{e}");
    let e = error_of(check({ let mut x = s(); x["buses"][1]["output"] = json!("music"); x }));
    assert_eq!(e["where"], json!("schedule.buses[0].output"), "{e}");
    let dir = std::env::temp_dir().join(format!("rostrum-sound-buses-{}", std::process::id()));
    let a = answer(&json!({ "do": "render", "out": dir.join("mix.wav"), "schedule": s() }));
    assert_eq!(a["ok"], json!(true), "{a}");
    let ids: Vec<&str> = a["result"]["buses"].as_array().unwrap().iter().map(|b| b["id"].as_str().unwrap()).collect();
    assert_eq!(ids, ["music", "verb"]);
    assert!(a["result"]["buses"][1]["peak"].as_f64().unwrap() > 0.01, "the pad reaches the reverb bus: {a}");
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn plugin_names_fail_loudly_before_the_plugin_loads() {
    let dir = std::env::temp_dir().join(format!("rostrum-sound-plugin-names-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let fake = dir.join("fake.clap");
    std::fs::write(&fake, b"not a plugin").unwrap();
    let s = |fx: Value| json!({ "contract": "rostrum-sound-schedule/1", "length": 1.0, "tracks": [{ "id": "fx", "effects": [fx] }] });
    let e = error_of(check(s(json!({ "type": "plugin", "format": "clapp", "path": fake, "id": "x" }))));
    assert_eq!((e["where"].clone(), e["hint"].clone()), (json!("schedule.tracks[0].effects[0].format"), json!("Did you mean clap?")), "{e}");
    let e = error_of(check(s(json!({ "type": "plugin", "format": "clap", "path": fake, "id": "x", "preset": "warm" }))));
    assert_eq!(e["where"], json!("schedule.tracks[0].effects[0].preset"), "{e}");
    let e = error_of(check(s(json!({ "type": "plugin", "format": "vst3", "path": fake, "id": "x" }))));
    assert_eq!(e["where"], json!("schedule.tracks[0].effects[0].path"), "a .clap file is not a VST3: {e}");
    let inst = json!({ "contract": "rostrum-sound-schedule/1", "tracks": [{ "id": "keys", "instrument": { "plugin": { "format": "clap", "path": fake, "id": "x", "volume": 1 } },
        "notes": [{ "pitch": "C4", "at": 0, "dur": 1 }] }] });
    assert_eq!(error_of(check(inst))["where"], json!("schedule.tracks[0].instrument.plugin.volume"));
    assert_eq!(error_of(json!({ "do": "plugins", "path": "relative/folder" }))["where"], json!("path"));
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn stretch_keeps_the_pitch_and_shift_keeps_the_length() {
    let dir = std::env::temp_dir().join(format!("rostrum-sound-stretch-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let tone: Vec<f32> = (0..24000).map(|i| (i as f32 * 440.0 * std::f32::consts::TAU / 48000.0).sin() * 0.3).collect();
    let take = dir.join("take.wav");
    std::fs::write(&take, crate::mix::wavio::write(&[tone.clone(), tone], crate::bed::Layout::Stereo, 48000)).unwrap();
    // (stretch, shift) → (seconds on the timeline, Hz)
    for (k, (stretch, shift, secs, hz)) in [(json!(2.0), json!(null), 1.0, 440.0), (json!(null), json!(12.0), 0.5, 880.0)].into_iter().enumerate() {
        let out = dir.join(format!("mix{k}.wav"));
        let a = answer(&json!({ "do": "render", "out": out, "stems": "all", "master": false, "schedule": { "contract": "rostrum-sound-schedule/1", "length": 1.5,
            "tracks": [{ "id": "take", "volume": 1.0, "clips": [{ "media": take, "at": 0, "stretch": stretch, "shift": shift }] }] } }));
        assert_eq!(a["ok"], json!(true), "{a}");
        let span = &a["result"]["tracks"][0]["span"];
        let len = span[1].as_f64().unwrap() - span[0].as_f64().unwrap();
        assert!((len - secs).abs() < 0.06, "stretch {stretch} shift {shift}: lasts {len} s, expected {secs}");
        let w = crate::instruments::sfz::read_wav(std::path::Path::new(a["result"]["stems"]["take"].as_str().unwrap())).unwrap();
        let mid: Vec<f32> = w.frames[(0.1 * w.rate) as usize..(0.4 * w.rate) as usize].iter().map(|f| f[0]).collect();
        let crossings = mid.windows(2).filter(|p| (p[0] < 0.0) != (p[1] < 0.0)).count() as f64;
        let measured = crossings / 2.0 / 0.3;
        assert!((measured - hz).abs() < hz * 0.03, "stretch {stretch} shift {shift}: {measured} Hz, expected {hz}");
    }
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn a_missing_pack_or_an_unknown_name_is_a_loud_error() {
    let root = std::env::temp_dir().join(format!("rostrum-sound-no-packs-{}", std::process::id()));
    let e = super::plain::file_in(&root, "piano", "salamander-piano", "Salamander.sfz", "instrument.builtIn").unwrap_err().to_json();
    assert_eq!((e["code"].clone(), e["subject"].clone()), (json!("NOT_FOUND"), json!("\"piano\"")), "{e}");
    assert!(e["problem"].as_str().unwrap().contains("salamander-piano") && e["hint"].as_str().unwrap().contains("rostrum_sound.packs install salamander-piano"), "{e}");
    let e = error_of(check(json!({ "contract": "rostrum-sound-schedule/1", "tracks": [{ "id": "k", "instrument": { "builtIn": "kazoo" } }], "length": 1 })));
    let accepted: Vec<&str> = e["accepted"].as_array().unwrap().iter().filter_map(Value::as_str).collect();
    assert!(accepted.contains(&"piano") && accepted.contains(&"classic.choirPad"), "{e}");
    let e = error_of(check(json!({ "contract": "rostrum-sound-schedule/1", "tracks": [{ "id": "d", "instrument": { "kit": "synth" } }], "length": 1 })));
    assert!(e["accepted"].as_array().unwrap().contains(&json!("drums")), "{e}");
}

/// The voices the engine is handed for a schedule of chords and hits, performed as `perform` says.
fn voices(perform: Value) -> Vec<Value> {
    let notes: Vec<Value> = (0..8).map(|i| json!({ "pitch": ["C4", "E4", "G4"], "at": { "beat": i as f64 * 0.5 }, "dur": 0.4, "vel": 0.7, "strum": 20 })).collect();
    let hits: Vec<Value> = (0..8).map(|i| json!({ "drum": "hat", "at": { "beat": i as f64 * 0.5 }, "vel": 0.6 })).collect();
    let mut s = json!({ "contract": "rostrum-sound-schedule/1", "tempo": 100, "tracks": [
        { "id": "keys", "instrument": { "builtIn": "classic.feltPiano" }, "notes": notes },
        { "id": "drums", "instrument": { "kit": "classic" }, "hits": hits }] });
    for t in s["tracks"].as_array_mut().unwrap() { if !perform.is_null() { t["perform"] = perform.clone() } }
    let c = super::schedule::compile(&s, "schedule").unwrap();
    c.job["tracks"].as_array().unwrap().iter().flat_map(|t| t["clips"][0]["content"]["voices"].as_array().unwrap().clone()).collect()
}

#[test]
fn perform_false_plays_as_written_and_performing_is_the_same_every_time() {
    let written = voices(json!(false));
    let sr = 48000.0;
    for (i, v) in written.iter().enumerate() {
        let (n, k) = (i / 3, i % 3);    // 8 strummed chords (3 tones, 20 ms apart), then 8 hats
        let (at, vel) = if i < 24 { (n as f64 * 0.3 + k as f64 * 0.02, 0.7) } else { ((i - 24) as f64 * 0.3, 0.6) };
        assert_eq!(v["startIdx"], json!((at * sr).round() as u64), "voice {i}: {v}");
        assert_eq!(v["velocity"], json!(vel), "voice {i}");
        if i < 24 { assert_eq!(v["duration"], json!(0.4 - k as f64 * 0.02), "voice {i}") }
    }
    let (a, b) = (voices(Value::Null), voices(json!({})));
    assert_eq!(a, b, "the same performance every render");
    assert_ne!(a, written, "on by default");
    assert!(a.iter().all(|v| v["startIdx"].as_u64().is_some()));
    assert_ne!(voices(json!({ "seed": 7 })), a, "another seed, another performance");
}

#[test]
fn person_false_keeps_swing_and_drops_the_family_looseness() {
    // Swing 1 on 8ths at 100 bpm: every off-beat 8th (odd chord, odd hat) lands 1/6 beat = 0.1 s late; no velocity or length changes.
    let (written, swung) = (voices(json!(false)), voices(json!({ "person": false, "swing": 1 })));
    assert_eq!(written.len(), swung.len());
    for (i, (w, s)) in written.iter().zip(&swung).enumerate() {
        let (n, root) = if i < 24 { (i / 3, i % 3 == 0) } else { (i - 24, true) };
        let late = if n % 2 == 1 { (0.1f64 * 48000.0).round() as u64 } else { 0 };
        // A strum's later tones (40 ms off the grid) are past the engine's swing window (0.08 of a cell): roots and hats only.
        if root { assert_eq!(s["startIdx"].as_u64().unwrap(), w["startIdx"].as_u64().unwrap() + late, "voice {i}") }
        assert_eq!(s["velocity"], w["velocity"], "voice {i}: no velocity spread or accent");
        assert_eq!(s["duration"], w["duration"], "voice {i}: no articulation");
    }
}

#[test]
fn stems_carry_the_limiter_so_they_add_up_to_the_mix_and_never_clip() {
    // Two tracks of the same loud tone, mastered loud: the limiter works. The stems take its gain too (the critic's piano
    // stem took the master's gain but not its limiter and clipped), so they stay under full scale and add up to the mix.
    let dir = std::env::temp_dir().join(format!("rostrum-sound-stems-sum-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let tone: Vec<f32> = (0..48000).map(|i| (i as f32 * 220.0 * std::f32::consts::TAU / 48000.0).sin() * 0.6).collect();
    let take = dir.join("tone.wav");
    std::fs::write(&take, crate::mix::wavio::write(&[tone.clone(), tone], crate::bed::Layout::Stereo, 48000)).unwrap();
    let out = dir.join("mix.wav");
    let a = answer(&json!({ "do": "render", "out": out, "stems": "all", "schedule": { "contract": "rostrum-sound-schedule/1", "length": 1.0,
        "master": { "loudness": -1, "truePeak": -1 },
        "tracks": [{ "id": "a", "clips": [{ "media": take, "at": 0 }] }, { "id": "b", "clips": [{ "media": take, "at": 0 }] }] } }));
    assert_eq!(a["ok"], json!(true), "{a}");
    let r = &a["result"];
    assert!(r["master"]["limiterMaxReductionDb"].as_f64().unwrap() > 1.0, "the limiter must work for this test: {}", r["master"]);
    assert_eq!(r["master"]["onMixOnly"], json!([]), "{}", r["master"]);
    assert!(r["master"]["stemsMaxDifference"].as_f64().unwrap() < 1e-4, "{}", r["master"]);
    let read = |p: &str| crate::instruments::sfz::read_wav(std::path::Path::new(p)).unwrap().frames;
    let mix = read(out.to_str().unwrap());
    let (sa, sb) = (read(r["stems"]["a"].as_str().unwrap()), read(r["stems"]["b"].as_str().unwrap()));
    let mut worst = 0.0f32;
    for i in 0..mix.len() {
        for c in 0..2 {
            assert!(sa[i][c].abs() <= 1.0 && sb[i][c].abs() <= 1.0, "a stem past full scale at frame {i}");
            worst = worst.max((sa[i][c] + sb[i][c] - mix[i][c]).abs());
        }
    }
    assert!(worst < 1e-4, "the stems miss the mix by {worst}");
    assert_eq!(r["stemMeters"]["a"]["overFullScale"], json!(0), "{}", r["stemMeters"]);
    let _ = std::fs::remove_dir_all(&dir);
}
