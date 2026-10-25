//! A `rostrum-sound-schedule/1` read whole: the top level and the master here, tracks in track.rs. It
//! comes out twice: `resolved` (the contract form with every default filled and times in seconds, what
//! `check` answers) and `job` (the engine's internal job, schedule/mod.rs, which the renderer reads).

use super::error::Error;
use super::names::SPACES;
use super::read::Obj;
use super::time::Tempo;
use super::{buses, effects, ending, track};
use serde_json::{json, Value};

pub const CONTRACT: &str = "rostrum-sound-schedule/1";
/// The engine's internal job version the compiler writes (schedule/mod.rs reads 5 to 9).
const JOB_VERSION: u32 = 9;

pub struct Compiled {
    pub resolved: Value,
    pub job: Value,
    pub seconds: f64,
    /// Track ids, in schedule order.
    pub ids: Vec<String>,
    /// The distinct credit lines of the CC-BY instruments the tracks play (every export carries them).
    pub credits: Vec<&'static str>,
    /// A given length (ending.rs): its frame, whether the song rings out past it, and the notes and clips held past it.
    pub ending: Option<(usize, bool, usize)>,
}

pub fn compile(v: &Value, at: &str) -> Result<Compiled, Error> {
    let mut o = Obj::new(v, at)?;
    let contract = o.str("contract", None)?;
    if contract != CONTRACT {
        return Err(Error::new("BAD_ARGUMENT", &o.at("contract"), format!("\"{contract}\""), "is a contract version this engine does not read").hint(format!("This engine reads \"{CONTRACT}\".")));
    }
    let sr = o.num("sampleRate", 22050.0, 192000.0, Some(48000.0))? as u32;
    let tempo_at = o.at("tempo");
    let (mut tempo, tempo_resolved) = Tempo::read(o.raw("tempo"), &tempo_at)?;
    o.put("tempo", tempo_resolved);
    let (meter, meter_resolved) = super::meter::Meter::read(o.raw("meter"), &o.at("meter"))?;
    tempo.meter = meter;
    o.put("meter", meter_resolved);
    let length_given = match o.raw("length") {
        Some(l) => Some(tempo.time(l, &o.at("length"))?),
        None => None,
    };

    // Track ids first, so ducks can name tracks that come later.
    let raw_tracks = o.required("tracks")?;
    let ids = track::ids(raw_tracks, &o.at("tracks"), "track")?;
    let bus_ids = buses::ids(o.raw("buses"), &o.at("buses"), &ids)?;
    let (buses_resolved, buses_job) = buses::read(&mut o, &tempo, &bus_ids)?;
    let ring = o.bool("ringOut", false)?;
    let tracks_at = o.at("tracks");
    let mut tracks: Vec<track::Track> = o.list("tracks", |t, p| track::read(t, &p, &tempo, sr, length_given, &ids, &bus_ids))?;
    let end = tracks.iter().map(|t| t.end).fold(0.0, f64::max);
    let mut credits: Vec<&'static str> = vec![];
    for c in tracks.iter().filter_map(|t| t.credit) {
        if !credits.contains(&c) { credits.push(c) }
    }
    let seconds = match length_given {
        Some(l) if l > 0.0 => l,
        Some(_) => return Err(Error::new("BAD_ARGUMENT", &o.at("length"), "length", "must be more than 0 s")),
        None if end > 0.0 => end + 2.0,
        None => return Err(Error::new("BAD_ARGUMENT", &tracks_at, "the schedule", "has no sound and no length").hint("Add notes, hits or clips, or give a length.")),
    };
    o.put("length", json!(seconds));
    let song = (seconds * sr as f64).round() as usize;
    let ending = length_given.map(|_| (song, ring, tracks.iter_mut().map(|t| ending::hold_to(&mut t.voices, &mut t.clips, song, sr as f64, ring)).sum()));
    // A song that rings out renders on past its length (the file is cut where the ring dies away: ending.rs).
    let total = if ring && length_given.is_some() { song + (ending::RING_MAX * sr as f64).round() as usize } else { song };

    let master_at = o.at("master");
    let empty = json!({});
    let master = master(o.raw("master").unwrap_or(&empty), &master_at, &tempo, sr)?;
    o.put("master", master.resolved);
    o.put("tracks", Value::Array(tracks.iter().map(|t| t.resolved.clone()).collect()));
    if !bus_ids.is_empty() {
        o.put("buses", Value::Array(buses_resolved));
    }
    let resolved = Value::Object(o.done()?);

    let mut job = master.job;
    job["version"] = json!(JOB_VERSION);
    job["sampleRate"] = json!(sr);
    job["totalSamples"] = json!(total);
    if total > song {
        job["songSamples"] = json!(song);
    }
    job["tailSamples"] = json!(0);
    job["timeWarps"] = json!([]);
    job["tracks"] = Value::Array(tracks.into_iter().map(|t| t.job(total)).collect());
    job["buses"] = Value::Array(buses_job);
    Ok(Compiled { resolved, job, seconds, ids, credits, ending })
}

struct Master {
    resolved: Value,
    job: Value,
}

fn master(v: &Value, at: &str, tempo: &Tempo, sr: u32) -> Result<Master, Error> {
    let mut o = Obj::new(v, at)?;
    let volume = o.num("volume", 0.0, 4.0, Some(1.0))?;
    let reverb = o.name("reverb", SPACES, Some("dry"))?;
    let track_space = o.name("trackReverbSpace", SPACES, Some("hall"))?;
    let fade_in = o.num("fadeIn", 0.0, 600.0, Some(0.0))?;
    let fade_out = o.num("fadeOut", 0.0, 600.0, Some(0.0))?;
    let fx_at = o.at("effects");
    let fx = effects::list(o.raw("effects"), &fx_at, tempo)?;
    o.put("effects", json!(fx));
    let loudness = o.opt_num("loudness", -60.0, 0.0)?;
    let true_peak = o.num("truePeak", -12.0, 0.0, Some(-1.0))?;
    let glue = o.num("glue", 0.0, 1.0, Some(0.0))?;
    let max_limit = o.opt_num("maxLimit", 0.0, 24.0)?;
    let safety = o.bool("safetyClip", true)?;
    let auto = track::automation(&mut o, tempo, false)?;
    let sr = sr as f64;
    let job = json!({
        "masterVolume": volume, "masterReverb": reverb, "trackReverbSpace": track_space,
        "fadeInSamples": (fade_in * sr) as usize, "fadeOutSamples": (fade_out * sr) as usize,
        "effects": effects::job(&fx, 0.0), "master": { "loudness": loudness, "truePeak": true_peak, "glue": glue, "maxLimit": max_limit }, "safetyClip": safety,
        "masterAutomation": auto.get("volume").cloned().unwrap_or(Value::Null),
    });
    Ok(Master { resolved: Value::Object(o.done()?), job })
}
