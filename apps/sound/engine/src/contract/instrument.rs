//! A track's instrument (exactly one key), read strictly, and how each of its notes becomes engine voices:
//! sampled (with named articulations, split by pitch into zones for a section), a SoundFont, a plain name
//! (plain.rs: recorded, an analog preset or a classic voice), procedural model (with its touch), synth, a
//! CLAP / VST3 plugin (contract/plugin.rs; one instance plays the track's notes), or a drum kit.

use super::error::Error;
use super::names::{self, Def, Field, Kind, MODEL_FIELDS, PLUCKED, SYNTH_FIELDS, WAVES};
use super::plain::{self, Resolved};
use super::read::Obj;
use super::time::Tempo;
use serde_json::{json, Map, Value};

pub const FORMS: [&str; 7] = ["builtIn", "sfz", "model", "synth", "plugin", "kit", "kitSfz"];
const TOUCH: [&str; 3] = ["position", "damping", "hardness"];

/// SFZ files for the keys up to `hikey`: the main file's spec and each named articulation's.
pub struct Zone {
    pub hikey: u8,
    pub main: Value,
    pub arts: Vec<(String, Value)>,
}

pub enum Inst {
    None,
    /// A classic synthesized voice (instruments/voices/tones.rs).
    BuiltIn(String),
    /// SFZ zones, lowest first (a single file is one zone up to key 127).
    Sfz(Vec<Zone>),
    /// A SoundFont's preset (instruments/sampler.rs SamplerSpec).
    Sampler(Value),
    /// The contract's name, the engine's, and the track's touch (position, damping, hardness).
    Model { name: String, engine: &'static str, touch: [Option<f64>; 3] },
    /// The engine's synth spec.
    Synth(Value),
    /// The job's PluginSpec (song time 0: the notes are one clip over the whole mix).
    Plugin(Value),
    /// The synthesized kit.
    Kit,
    /// SFZ kit files on GM keys, each with the keys it plays (the first file that plays a key plays it).
    KitSfz(Vec<(Value, Vec<u8>)>),
}

/// The instrument (with its performance family, "" for none, and credit line) and its resolved form.
pub fn read(v: Option<&Value>, at: &str, tempo: &Tempo) -> Result<(Resolved, Value), Error> {
    let Some(v) = v else { return Ok((Resolved { inst: Inst::None, family: "", credit: None }, Value::Null)) };
    let key = v.as_object().and_then(|m| FORMS.iter().find(|f| m.contains_key(**f)).copied())
        .ok_or_else(|| Error::bad(at, v, "is not an instrument", &FORMS))?;
    let mut o = Obj::new(v, at)?;
    let own = |inst, family| Resolved { inst, family, credit: None };
    let r = match key {
        "builtIn" => { let n = o.str("builtIn", None)?; plain::built_in(&n, &o.at("builtIn"))? }
        "kit" => { let n = o.str("kit", None)?; plain::kit(&n, &o.at("kit"))? }
        "sfz" => {
            let file = file_arg(&mut o, "sfz")?;
            let (legato, swell) = (o.bool("legato", false)?, o.bool("swell", false)?);
            let spec = |f: &str| json!({ "file": f, "legato": legato, "swell": swell });
            let arts = articulations(&mut o)?;
            own(Inst::Sfz(vec![Zone { hikey: 127, main: spec(&file), arts: arts.iter().map(|(n, f)| (n.clone(), spec(f))).collect() }]), "keys")
        }
        "model" => {
            let name = o.name("model", &names::model_names(), None)?;
            let engine = names::MODELS.iter().find(|(n, _)| *n == name).map(|(_, e)| *e).unwrap_or("");
            let touch = touch(&mut o, &name, None)?;
            let family = names::named_family(&name);
            own(Inst::Model { name, engine, touch }, family)
        }
        "synth" => own(synth(&mut o)?, "synth"),
        "plugin" => {
            let pa = o.at("plugin");
            let p = super::plugin::read(Obj::new(o.required("plugin")?, pa)?, tempo, Some("instrument"))?;
            let job = super::plugin::spec(&p.resolved, 0.0);
            o.put("plugin", Value::Object(p.resolved));
            own(Inst::Plugin(job), "keys")
        }
        _ => {
            let file = file_arg(&mut o, "kitSfz")?;
            own(Inst::KitSfz(vec![plain::kit_file(&file, &o.at("kitSfz"))?]), "drums")
        }
    };
    Ok((r, Value::Object(o.done()?)))
}

pub fn file_arg(o: &mut Obj, key: &'static str) -> Result<String, Error> {
    let f = o.str(key, None)?;
    if !std::path::Path::new(&f).is_file() {
        return Err(Error::not_found(&o.at(key), &format!("\"{f}\""), "is not a file"));
    }
    Ok(f)
}

/// `articulations`: {name: sfz path}, each a file.
fn articulations(o: &mut Obj) -> Result<Vec<(String, String)>, Error> {
    let at = o.at("articulations");
    let mut out = vec![];
    if let Some(v) = o.raw("articulations") {
        let m = v.as_object().ok_or_else(|| Error::bad(&at, v, "is not a map of articulation names to SFZ files", &["{\"spiccato\": \"C:\\\\…\\\\spic.sfz\"}"]))?;
        for (name, f) in m {
            let p = format!("{at}.{name}");
            let f = f.as_str().ok_or_else(|| Error::bad(&p, f, "is not a file path", &[]))?;
            if !std::path::Path::new(f).is_file() {
                return Err(Error::not_found(&p, &format!("\"{f}\""), "is not a file"));
            }
            out.push((name.clone(), f.to_string()));
        }
    }
    o.put("articulations", Value::Object(out.iter().map(|(n, f)| (n.clone(), json!(f))).collect()));
    Ok(out)
}

/// The touch fields `model` plays (none for the violin, damping only on plucked strings). A track's
/// (`track` None) default to the model's own; a note's (`track` Some) to its track's.
fn touch(o: &mut Obj, model: &str, track: Option<[Option<f64>; 3]>) -> Result<[Option<f64>; 3], Error> {
    let mut out = [None; 3];
    for (i, f) in MODEL_FIELDS.iter().enumerate() {
        let plays = model != "violin" && (f.0 != "damping" || PLUCKED.contains(&model));
        if !plays {
            if o.has(f.0) {
                return Err(Error::new("BAD_ARGUMENT", &o.at(f.0), f.0, format!("is not played by the {model}")));
            }
            continue;
        }
        let Kind::Num(lo, hi) = f.1 else { continue };
        let default = match (track, f.2) { (Some(t), _) => t[i].unwrap_or(0.0), (None, Def::N(x)) => x, _ => names::model_position(model) };
        out[i] = Some(o.num(f.0, lo, hi, Some(default))?);
    }
    Ok(out)
}

fn synth(o: &mut Obj) -> Result<Inst, Error> {
    let mut spec = Map::new();
    spec.insert("wave".into(), json!(o.name("synth", WAVES, None)?));
    for Field(name, kind, def) in SYNTH_FIELDS {
        let (lo, hi, whole) = match kind { Kind::Num(a, b) => (*a, *b, false), Kind::Int(a, b) => (*a, *b, true), _ => continue };
        let x = o.num(name, lo, hi, match def { Def::N(x) => Some(*x), _ => None })?;
        if whole && x.fract() != 0.0 {
            return Err(Error::new("BAD_ARGUMENT", &o.at(name), *name, "must be a whole number"));
        }
        let key = if *name == "brightness" { "cutoff" } else { name };
        spec.insert(key.into(), if whole { json!(x as i64) } else { json!(x) });
    }
    spec.insert("curve".into(), json!("analog"));
    Ok(Inst::Synth(Value::Object(spec)))
}

impl Inst {
    /// A note's voices (one, or one per zone its chord spans), reading the note's own instrument fields
    /// (`art`, the touch).
    pub fn note(&self, no: &mut Obj, mut voice: Value) -> Result<Vec<Value>, Error> {
        if !matches!(self, Inst::Model { .. }) {
            if let Some(f) = TOUCH.iter().find(|f| no.has(f)) {
                return Err(Error::new("BAD_ARGUMENT", &no.at(f), *f, "needs a model instrument on its track").hint("Touch (position, damping, hardness) is how a procedural instrument is played: {\"model\": \"guitar\"}."));
            }
        }
        if matches!(self, Inst::Plugin(_)) && no.has("pan") {
            return Err(Error::new("BAD_ARGUMENT", &no.at("pan"), "pan", "is not sent to a plugin instrument (it plays in its own stereo)").hint("Pan the track instead."));
        }
        if !matches!(self, Inst::Sfz(_)) && no.has("art") {
            return Err(Error::new("BAD_ARGUMENT", &no.at("art"), "art", "needs a recorded instrument with articulations (or an sfz track with articulations)"));
        }
        match self {
            Inst::BuiltIn(name) => voice["instrument"] = json!(name),
            Inst::Sfz(zones) => return sfz_voices(zones, no, voice),
            Inst::Sampler(spec) => {
                voice["instrument"] = json!("sampled");
                voice["sampler"] = spec.clone();
            }
            Inst::Model { name, engine, touch: t } => {
                let n = touch(no, name, Some(*t))?;
                voice["instrument"] = json!(engine);
                voice["touch"] = json!({ "position": n[0], "damping": n[1], "hardness": n[2] });
            }
            Inst::Synth(spec) => {
                voice["instrument"] = json!("synth");
                voice["synth"] = spec.clone();
            }
            Inst::Plugin(spec) => {
                voice["instrument"] = json!("plugin");
                voice["plugin"] = spec.clone();
            }
            _ => return Err(Error::new("BAD_ARGUMENT", &no.path, "a note", "needs a pitched instrument on its track").hint("Give the track {\"builtIn\": …}, {\"sfz\": …}, {\"model\": …}, {\"synth\": …} or {\"plugin\": …}; drum kits take hits.")),
        }
        Ok(vec![voice])
    }
}

/// A note on SFZ zones: its articulation's file in each zone its keys fall in, one voice per zone.
fn sfz_voices(zones: &[Zone], no: &mut Obj, voice: Value) -> Result<Vec<Value>, Error> {
    let at = no.at("art");
    let art = match no.raw("art") {
        None => None,
        Some(a) => Some(a.as_str().ok_or_else(|| Error::bad(&at, a, "is not an articulation name", &[]))?.to_string()),
    };
    let freqs: Vec<f64> = voice["freqs"].as_array().map(|a| a.iter().filter_map(Value::as_f64).collect()).unwrap_or_default();
    let key = |f: f64| (69.0 + 12.0 * (f / 440.0).log2()).round().clamp(0.0, 127.0) as u8;
    let (mut out, mut lo) = (vec![], 0u8);
    for z in zones {
        let mine: Vec<f64> = freqs.iter().copied().filter(|&f| (lo..=z.hikey).contains(&key(f))).collect();
        lo = z.hikey.saturating_add(1);
        if mine.is_empty() {
            continue;
        }
        let spec = match &art {
            None => &z.main,
            Some(s) => {
                let known: Vec<&str> = z.arts.iter().map(|(n, _)| n.as_str()).collect();
                &z.arts.iter().find(|(n, _)| n == s).ok_or_else(|| Error::unknown(&at, s, &known))?.1
            }
        };
        let mut v = voice.clone();
        v["freqs"] = json!(mine);
        v["instrument"] = json!("sampled");
        v["sfz"] = spec.clone();
        out.push(v);
    }
    if let Some(a) = art {
        no.put("art", json!(a));
    }
    Ok(out)
}
