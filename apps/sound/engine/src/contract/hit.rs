//! A drum hit, read strictly and written as the engine's voice. One list of hit names (names.rs GM_DRUMS) works
//! on every recorded kit: a name is a General MIDI key, played by the first of the kit's files that has a
//! sample on it (a kit's fill-in file supplies the keys its main one lacks). A name or key the kit cannot play
//! is an error listing what it can. The synthesized kit (`classic`) plays its own names.

use super::error::Error;
use super::instrument::Inst;
use super::names::{self, SYNTH_DRUMS};
use super::pitch;
use super::read::{number, Obj};
use super::time::Tempo;
use serde_json::{json, Value};

pub fn read(v: &Value, at: &str, inst: &Inst, tempo: &Tempo, sr: u32) -> Result<(Value, Value, f64), Error> {
    let mut o = Obj::new(v, at)?;
    let drum = o.required("drum")?;
    let t = tempo.time(o.required("at")?, &o.at("at"))?;
    o.put("at", json!(t));
    let vel = o.num("vel", 0.0, 1.0, Some(0.85))?;
    let pan = o.num("pan", -1.0, 1.0, Some(0.0))?;
    let tune = o.num("tune", 0.25, 4.0, Some(1.0))?;
    let decay = o.num("decay", 0.1, 4.0, Some(1.0))?;
    let idx = (t * sr as f64).round() as usize;
    let da = o.at("drum");
    let voice = match inst {
        Inst::Kit => {
            let name = drum.as_str().ok_or_else(|| Error::bad(&da, drum, "is not a drum name", SYNTH_DRUMS))?;
            super::read::one_of(name, &da, SYNTH_DRUMS)?;
            o.put("drum", json!(name));
            json!({ "kind": "drum", "voice": name, "startIdx": idx, "velocity": vel, "pan": pan, "tune": tune, "decay": decay })
        }
        Inst::KitSfz(files) => {
            let plays = |k: u8| files.iter().find(|(_, keys)| keys.contains(&k));
            let can: Vec<&str> = names::GM_DRUMS.iter().filter(|(_, k)| plays(*k).is_some()).map(|(n, _)| *n).collect();
            let key = match drum {
                Value::String(s) => match names::gm_drum(s) {
                    Some(k) if plays(k).is_some() => k,
                    Some(_) => return Err(Error::unknown(&da, s, &can).hint(format!("This kit has no {s}; it plays the names listed."))),
                    None => return Err(Error::unknown(&da, s, &can)),
                },
                v => number(v, &da, 0.0, 127.0)?.round() as u8,
            };
            let (spec, _) = plays(key).ok_or_else(|| Error::new("BAD_ARGUMENT", &da, format!("key {key}"), "has no sample in this kit").hint(format!("It plays: {}.", can.join(", "))))?;
            o.put("drum", drum.clone());
            json!({ "kind": "note", "instrument": "sampled", "sfz": spec, "freqs": [pitch::freq(key as f64)], "startIdx": idx, "duration": 0.2 * decay, "velocity": vel, "pan": pan })
        }
        _ => return Err(Error::new("BAD_ARGUMENT", at, "a hit", "needs a drum kit on its track").hint("Give the track {\"kit\": \"drums\"} or {\"kitSfz\": …}.")),
    };
    Ok((Value::Object(o.done()?), voice, t))
}
