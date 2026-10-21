//! A contract track: instrument, notes, hits, recorded clips, fader, inserts, automation and ducks, read
//! strictly (read.rs) and written as the engine's job track (schedule/mod.rs Track, Clip, Voice).

use super::error::Error;
use super::instrument::{self, Inst};
use super::names::{self, SYNTH_DRUMS, TONES};
use super::pitch;
use super::read::{Obj, number};
use super::time::Tempo;
use super::{buses, designed, effects, expression, media};
use serde_json::{json, Map, Value};

pub struct Track {
    pub resolved: Value,
    /// Where its last sound ends (seconds), for the default length.
    pub end: f64,
    head: Value,
    voices: Vec<Value>,
    clips: Vec<Value>,
}

/// Every track's (or bus') id, checked (pattern, unique), before the tracks are read.
pub fn ids(v: &Value, at: &str, what: &str) -> Result<Vec<String>, Error> {
    let Some(a) = v.as_array() else {
        return Err(Error::bad(at, v, &format!("is not a list of {what}s"), &["[{\"id\": \"strings\", …}]"]));
    };
    let mut out: Vec<String> = vec![];
    for (i, t) in a.iter().enumerate() {
        let p = format!("{at}[{i}].id");
        let id = t.get("id").and_then(Value::as_str).ok_or_else(|| Error::missing(&p))?;
        if id.is_empty() || id.len() > 64 || !id.chars().all(|c| c.is_ascii_alphanumeric() || "_.-".contains(c)) {
            return Err(Error::new("BAD_ARGUMENT", &p, format!("\"{id}\""), format!("is not a {what} id (1–64 letters, digits, _ . -)")));
        }
        if out.iter().any(|o| o == id) {
            return Err(Error::new("BAD_ARGUMENT", &p, format!("\"{id}\""), format!("is used by two {what}s")));
        }
        out.push(id.to_string());
    }
    Ok(out)
}

pub fn read(v: &Value, at: &str, tempo: &Tempo, sr: u32, ids: &[String], bus_ids: &[String]) -> Result<Track, Error> {
    let mut o = Obj::new(v, at)?;
    let id = o.str("id", None)?;
    let inst_at = o.at("instrument");
    let (inst, inst_resolved) = instrument::read(o.raw("instrument"), &inst_at)?;
    o.put("instrument", inst_resolved);
    let volume = o.num("volume", 0.0, 4.0, Some(0.85))?;
    let pan = o.num("pan", -1.0, 1.0, Some(0.0))?;
    let reverb = o.num("reverb", 0.0, 1.0, Some(0.0))?;
    let tone = o.name("tone", TONES, Some("neutral"))?;
    let mute = o.bool("mute", false)?;
    let fx_at = o.at("effects");
    let fx = effects::list(o.raw("effects"), &fx_at, tempo)?;
    o.put("effects", json!(fx));
    let auto = automation(&mut o, tempo, true)?;
    let ducks = o.list("ducks", |d, p| duck(d, &p, ids))?;
    let lanes = expression::lanes(&mut o, tempo)?;
    let (output, sends) = buses::route(&mut o, tempo, bus_ids)?;
    o.put("ducks", json!(ducks.iter().map(|d| d.0.clone()).collect::<Vec<_>>()));

    let sri = |t: f64| (t * sr as f64).round() as usize;
    let mut end: f64 = 0.0;
    let mut voices = vec![];
    let notes = o.list("notes", |n, p| {
        let mut no = Obj::new(n, p)?;
        let pa = no.at("pitch");
        let keys = pitch::keys(no.required("pitch")?, &pa)?;
        no.put("pitch", json!(keys));
        let at_s = tempo.time(no.required("at")?, &no.at("at"))?;
        no.put("at", json!(at_s));
        let dur = tempo.length(no.required("dur")?, &no.at("dur"), at_s)?;
        if dur <= 0.0 {
            return Err(Error::new("BAD_ARGUMENT", &no.at("dur"), "dur", "must be more than 0 s"));
        }
        no.put("dur", json!(dur));
        let vel = no.num("vel", 0.0, 1.0, Some(0.8))?;
        let npan = no.num("pan", -1.0, 1.0, Some(0.0))?;
        let freqs: Vec<f64> = keys.iter().map(|&k| pitch::freq(k)).collect();
        let mut voice = json!({ "kind": "note", "freqs": freqs, "startIdx": sri(at_s), "duration": dur, "velocity": vel, "pan": npan });
        inst.note(&mut no, &mut voice)?;
        if let Some(e) = expression::note(&mut no, &lanes, at_s, dur)? {
            voice["expression"] = e;
        }
        end = end.max(at_s + dur);
        voices.push(voice);
        Ok(Value::Object(no.done()?))
    })?;
    o.put("notes", json!(notes));
    let hits = o.list("hits", |h, p| {
        let (resolved, voice, t) = hit(h, &p, &inst, tempo, sr)?;
        end = end.max(t + 0.5);
        voices.push(voice);
        Ok(resolved)
    })?;
    o.put("hits", json!(hits));
    let mut clips = vec![];
    let clip_list = o.list("clips", |c, p| {
        let (resolved, job, t) = clip(c, &p, tempo, sr)?;
        end = end.max(t);
        clips.push(job);
        Ok(resolved)
    })?;
    o.put("clips", json!(clip_list));
    let sound_list = o.list("sounds", |c, p| {
        let (resolved, job, t) = designed::read(c, &p, tempo, sr)?;
        end = end.max(t);
        clips.push(job);
        Ok(resolved)
    })?;
    o.put("sounds", json!(sound_list));
    let resolved = Value::Object(o.done()?);
    let head = json!({ "name": id, "tone": tone, "volume": volume, "pan": pan, "reverb": reverb, "mix": !mute,
        "ducks": ducks.into_iter().map(|d| d.1).collect::<Vec<_>>(), "effects": fx, "automation": auto,
        "output": output, "sends": sends });
    Ok(Track { resolved, end, head, voices, clips })
}

impl Track {
    /// The job's track: the notes and hits as one score clip over the whole mix, then each recorded clip.
    pub fn job(self, total: usize) -> Value {
        let mut head = self.head;
        let mut clips = vec![];
        if !self.voices.is_empty() {
            clips.push(clip_job(json!({ "kind": "score", "voices": self.voices }), 0, total, total as f64, 1.0, 0.0, 0.0, 0.0, vec![]));
        }
        clips.extend(self.clips);
        head["clips"] = Value::Array(clips);
        head
    }
}

fn hit(v: &Value, at: &str, inst: &Inst, tempo: &Tempo, sr: u32) -> Result<(Value, Value, f64), Error> {
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
        Inst::KitSfz(spec) => {
            let key = match drum {
                Value::String(s) => names::gm_drum(s).ok_or_else(|| Error::unknown(&da, s, &names::gm_names()))? as f64,
                v => number(v, &da, 27.0, 87.0)?.round(),
            };
            o.put("drum", drum.clone());
            json!({ "kind": "note", "instrument": "sampled", "sfz": spec, "freqs": [pitch::freq(key)], "startIdx": idx, "duration": 0.2 * decay, "velocity": vel, "pan": pan })
        }
        _ => return Err(Error::new("BAD_ARGUMENT", at, "a hit", "needs a drum kit on its track").hint("Give the track {\"kit\": \"synth\"} or {\"kitSfz\": …}.")),
    };
    Ok((Value::Object(o.done()?), voice, t))
}

/// A recorded clip; returns (resolved, job clip, where it ends).
fn clip(v: &Value, at: &str, tempo: &Tempo, sr: u32) -> Result<(Value, Value, f64), Error> {
    let mut o = Obj::new(v, at)?;
    let path = o.str("media", None)?;
    let start = o.num("in", 0.0, 86400.0, Some(0.0))?;
    let t = tempo.time(o.required("at")?, &o.at("at"))?;
    o.put("at", json!(t));
    let length = match o.raw("length") { Some(l) => Some(tempo.length(l, &o.at("length"), t)?), None => None };
    let volume = o.num("volume", 0.0, 4.0, Some(1.0))?;
    let semis = o.num("pitch", -24.0, 24.0, Some(0.0))?;
    let pan = o.num("pan", -1.0, 1.0, Some(0.0))?;
    let pan_to = o.num("panTo", -1.0, 1.0, Some(pan))?;
    let fade_in = o.num("fadeIn", 0.0, 600.0, Some(0.0))?;
    let fade_out = o.num("fadeOut", 0.0, 600.0, Some(0.0))?;
    let reverb = o.num("reverb", 0.0, 1.0, Some(0.0))?;
    let fx_at = o.at("effects");
    let fx = effects::list(o.raw("effects"), &fx_at, tempo)?;
    o.put("effects", json!(fx));
    let slice = media::slice(&path, sr, start, length, &o.at("media"))?;
    o.put("length", json!(slice.seconds));
    let dur = slice.seconds / 2f64.powf(semis / 12.0);
    let content = json!({ "kind": "sample", "pcm": slice.pcm, "duration": dur, "volume": 1.0, "pitch": semis, "panFrom": pan, "panTo": pan_to });
    let samples = ((dur * sr as f64).ceil() as usize).max(16);
    let job = clip_job(content, (t * sr as f64).round() as usize, samples, dur, volume, fade_in, fade_out, reverb, fx);
    Ok((Value::Object(o.done()?), job, t + dur))
}

#[allow(clippy::too_many_arguments)]
pub(super) fn clip_job(content: Value, start: usize, samples: usize, dur: f64, volume: f64, fade_in: f64, fade_out: f64, reverb: f64, fx: Vec<Value>) -> Value {
    json!({ "startSample": start, "samples": samples, "duration": dur, "content": content, "rate": null, "reverse": null,
            "glitch": null, "filterSweep": null, "tone": "neutral", "fadeIn": fade_in, "fadeOut": fade_out, "volume": volume,
            "pan": 0.0, "reverb": reverb, "effects": fx })
}

/// `automation`: volume (and pan, on tracks) lanes, points through the tempo map.
pub fn automation(o: &mut Obj, tempo: &Tempo, pan: bool) -> Result<Map<String, Value>, Error> {
    let at = o.at("automation");
    let empty = json!({});
    let v = o.raw("automation").unwrap_or(&empty);
    let mut a = Obj::new(v, &at)?;
    let mut out = Map::new();
    if let Some(p) = a.raw("volume") {
        out.insert("volume".into(), json!(effects::points(p, &a.at("volume"), 0.0, 4.0, tempo)?));
    }
    if pan {
        if let Some(p) = a.raw("pan") {
            out.insert("pan".into(), json!(effects::points(p, &a.at("pan"), -1.0, 1.0, tempo)?));
        }
    }
    a.done()?;
    o.put("automation", Value::Object(out.clone()));
    Ok(out)
}

/// A duck: (resolved, job form with track indices).
fn duck(v: &Value, at: &str, ids: &[String]) -> Result<(Value, Value), Error> {
    let mut o = Obj::new(v, at)?;
    let ua = o.at("under");
    let under: Vec<usize> = o.list("under", |u, p| {
        let name = u.as_str().ok_or_else(|| Error::bad(&p, u, "is not a track id", &[]))?;
        ids.iter().position(|i| i == name).ok_or_else(|| Error::unknown(&p, name, &ids.iter().map(String::as_str).collect::<Vec<_>>()))
    })?;
    if under.is_empty() {
        return Err(Error::new("BAD_ARGUMENT", &ua, "under", "needs at least one track id"));
    }
    o.put("under", json!(under.iter().map(|&k| &ids[k]).collect::<Vec<_>>()));
    let depth = o.num("depth", 0.0, 1.0, Some(0.5))?;
    let attack = o.num("attack", 0.0005, 2.0, Some(0.02))?;
    let release = o.num("release", 0.005, 10.0, Some(0.3))?;
    let lookahead = o.num("lookahead", 0.0, 0.5, Some(0.01))?;
    let hold = o.num("hold", 0.0, 10.0, Some(0.0))?;
    let voice = o.bool("voice", false)?;
    let job = json!({ "from": under, "depth": depth, "attack": attack, "release": release, "lookahead": lookahead, "hold": hold, "voice": voice, "report": true });
    Ok((Value::Object(o.done()?), job))
}
