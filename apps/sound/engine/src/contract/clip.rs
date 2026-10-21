//! A recorded clip: a slice of a media file (decoded by the engine, media.rs) placed in the mix. `pitch` plays
//! it like tape (speed and pitch together); `stretch` changes its length with the pitch kept and `shift` its
//! pitch with the length kept (the engine's Rate, stretch/: Signalsmith Stretch, or PSOLA when it hears a
//! voice). `length` is always how much of the file plays; on the timeline the clip lasts
//! length ÷ tape speed × stretch.

use super::effects;
use super::error::Error;
use super::media;
use super::read::Obj;
use super::time::Tempo;
use super::track::clip_job;
use serde_json::{json, Value};

/// Returns (resolved, job clip, where it ends).
pub fn read(v: &Value, at: &str, tempo: &Tempo, sr: u32) -> Result<(Value, Value, f64), Error> {
    let mut o = Obj::new(v, at)?;
    let path = o.str("media", None)?;
    let start = o.num("in", 0.0, 86400.0, Some(0.0))?;
    let t = tempo.time(o.required("at")?, &o.at("at"))?;
    o.put("at", json!(t));
    let length = match o.raw("length") { Some(l) => Some(tempo.length(l, &o.at("length"), t)?), None => None };
    let volume = o.num("volume", 0.0, 4.0, Some(1.0))?;
    let semis = o.num("pitch", -24.0, 24.0, Some(0.0))?;
    let stretch = o.opt_num("stretch", 0.25, 4.0)?;
    let shift = o.opt_num("shift", -24.0, 24.0)?;
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
    let tape = slice.seconds / 2f64.powf(semis / 12.0);
    let dur = tape * stretch.unwrap_or(1.0);
    let content = json!({ "kind": "sample", "pcm": slice.pcm, "duration": tape, "volume": 1.0, "pitch": semis, "panFrom": pan, "panTo": pan_to });
    let samples = ((dur * sr as f64).ceil() as usize).max(16);
    let mut job = clip_job(content, (t * sr as f64).round() as usize, samples, dur, volume, fade_in, fade_out, reverb, effects::job(&fx, t));
    if stretch.is_some() || shift.is_some() {
        job["rate"] = rate(stretch.unwrap_or(1.0), shift.unwrap_or(0.0));
    }
    Ok((Value::Object(o.done()?), job, t + dur))
}

/// The engine's Rate for a clip played as tape and then stretched (`from` is the read speed, source
/// seconds per clip second) and shifted, the other kept. `content` None: the engine listens for speech.
fn rate(stretch: f64, shift: f64) -> Value {
    json!({ "from": 1.0 / stretch, "to": null, "preservePitch": true, "warp": null, "semitones": shift, "formant": null, "content": null })
}
