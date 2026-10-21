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
    let base = || json!({ "contract": "rostrum-sound-schedule/1", "tracks": [{ "id": "keys", "instrument": { "builtIn": "grandPiano" },
        "notes": [{ "pitch": "C4", "at": 0, "dur": 1 }] }] });
    let cases: Vec<(Value, &str, &str)> = vec![
        ({ let mut s = base(); s["tracks"][0]["tone"] = json!("warmm"); s }, "schedule.tracks[0].tone", "warm"),
        ({ let mut s = base(); s["tracks"][0]["volumee"] = json!(1); s }, "schedule.tracks[0].volumee", "volume"),
        ({ let mut s = base(); s["tracks"][0]["effects"] = json!([{ "type": "reverbb" }]); s }, "schedule.tracks[0].effects[0].type", "reverb"),
        ({ let mut s = base(); s["tracks"][0]["effects"] = json!([{ "type": "eq", "bands": [{ "shape": "peek", "freq": 100 }] }]); s }, "schedule.tracks[0].effects[0].bands[0].shape", "peak"),
        ({ let mut s = base(); s["tracks"][0]["instrument"] = json!({ "builtIn": "grandpiano" }); s }, "schedule.tracks[0].instrument.builtIn", "grandPiano"),
        ({ let mut s = base(); s["tracks"][0]["notes"][0]["pitch"] = json!("H4"); s }, "schedule.tracks[0].notes[0].pitch", ""),
        ({ let mut s = base(); s["master"] = json!({ "reverb": "hal" }); s }, "schedule.master.reverb", "hall"),
    ];
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
            { "id": "drums", "instrument": { "kit": "synth" }, "hits": [{ "drum": "kick", "at": 0 }, { "drum": "snare", "at": { "beat": 1 } }] },
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
