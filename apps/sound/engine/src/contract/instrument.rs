//! A track's instrument (exactly one key), read strictly, and how each of its notes becomes an engine voice:
//! sampled (with named articulations), built-in, procedural model (with its touch), synth, a CLAP / VST3
//! plugin (contract/plugin.rs; one instance plays the track's notes), or a drum kit.

use super::error::Error;
use super::names::{self, Def, Field, Kind, BUILT_INS, MODEL_FIELDS, PLUCKED, SYNTH_FIELDS, WAVES};
use super::read::Obj;
use super::time::Tempo;
use serde_json::{json, Map, Value};

pub const FORMS: [&str; 7] = ["builtIn", "sfz", "model", "synth", "plugin", "kit", "kitSfz"];
const TOUCH: [&str; 3] = ["position", "damping", "hardness"];

pub enum Inst {
    None,
    BuiltIn(String),
    /// The main file's spec and each named articulation's.
    Sfz { main: Value, arts: Vec<(String, Value)> },
    /// The contract's name, the engine's, and the track's touch (position, damping, hardness).
    Model { name: String, engine: &'static str, touch: [Option<f64>; 3] },
    /// The engine's synth spec.
    Synth(Value),
    /// The job's PluginSpec (song time 0: the notes are one clip over the whole mix).
    Plugin(Value),
    Kit,
    KitSfz(Value),
}

/// The instrument and its resolved form (every default written in).
pub fn read(v: Option<&Value>, at: &str, tempo: &Tempo) -> Result<(Inst, Value), Error> {
    let Some(v) = v else { return Ok((Inst::None, Value::Null)) };
    let key = v.as_object().and_then(|m| FORMS.iter().find(|f| m.contains_key(**f)).copied())
        .ok_or_else(|| Error::bad(at, v, "is not an instrument", &FORMS))?;
    let mut o = Obj::new(v, at)?;
    let inst = match key {
        "builtIn" => Inst::BuiltIn(o.name("builtIn", BUILT_INS, None)?),
        "kit" => { o.name("kit", &["synth"], None)?; Inst::Kit }
        "sfz" => {
            let file = file_arg(&mut o, "sfz")?;
            let (legato, swell) = (o.bool("legato", false)?, o.bool("swell", false)?);
            let spec = |f: &str| json!({ "file": f, "legato": legato, "swell": swell });
            let arts = articulations(&mut o)?;
            Inst::Sfz { main: spec(&file), arts: arts.iter().map(|(n, f)| (n.clone(), spec(f))).collect() }
        }
        "model" => {
            let name = o.name("model", &names::model_names(), None)?;
            let engine = names::MODELS.iter().find(|(n, _)| *n == name).map(|(_, e)| *e).unwrap_or("");
            let touch = touch(&mut o, &name, None)?;
            Inst::Model { name, engine, touch }
        }
        "synth" => synth(&mut o)?,
        "plugin" => {
            let pa = o.at("plugin");
            let p = super::plugin::read(Obj::new(o.required("plugin")?, pa)?, tempo, Some("instrument"))?;
            let job = super::plugin::spec(&p.resolved, 0.0);
            o.put("plugin", Value::Object(p.resolved));
            Inst::Plugin(job)
        }
        _ => Inst::KitSfz(json!({ "file": file_arg(&mut o, "kitSfz")?, "legato": false, "swell": false })),
    };
    Ok((inst, Value::Object(o.done()?)))
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
    /// Fills a note's voice with what plays it, reading the note's own instrument fields (`art`, the touch).
    pub fn note(&self, no: &mut Obj, voice: &mut Value) -> Result<(), Error> {
        if !matches!(self, Inst::Model { .. }) {
            if let Some(f) = TOUCH.iter().find(|f| no.has(f)) {
                return Err(Error::new("BAD_ARGUMENT", &no.at(f), *f, "needs a model instrument on its track").hint("Touch (position, damping, hardness) is how a procedural instrument is played: {\"model\": \"guitar\"}."));
            }
        }
        if matches!(self, Inst::Plugin(_)) && no.has("pan") {
            return Err(Error::new("BAD_ARGUMENT", &no.at("pan"), "pan", "is not sent to a plugin instrument (it plays in its own stereo)").hint("Pan the track instead."));
        }
        if !matches!(self, Inst::Sfz { .. }) && no.has("art") {
            return Err(Error::new("BAD_ARGUMENT", &no.at("art"), "art", "needs an sfz track with articulations"));
        }
        match self {
            Inst::BuiltIn(name) => voice["instrument"] = json!(name),
            Inst::Sfz { main, arts } => {
                let at = no.at("art");
                let spec = match no.raw("art") {
                    None => main,
                    Some(a) => {
                        let s = a.as_str().unwrap_or("");
                        let known: Vec<&str> = arts.iter().map(|(n, _)| n.as_str()).collect();
                        let found = arts.iter().find(|(n, _)| n == s).ok_or_else(|| Error::unknown(&at, s, &known))?;
                        no.put("art", json!(s));
                        &found.1
                    }
                };
                voice["instrument"] = json!("sampled");
                voice["sfz"] = spec.clone();
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
        Ok(())
    }
}
