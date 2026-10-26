//! Every name the contract accepts, in one place: what `describe` answers, what the reader checks, and so
//! what the Python side reads instead of copying lists. When a DSP module learns a new name, add it here
//! (the module's own match arms fall back silently, which is why the contract gates them).

/// Track and clip tones (fx/dsp.rs ToneFilter).
pub const TONES: &[&str] = &["neutral", "muffled", "warm", "sub-boost", "bright", "voice-clarity", "radio"];
/// Reverb spaces (fx/reverb.rs: the comb spaces and the Freeverb ones).
pub const SPACES: &[&str] = &["dry", "room", "hall", "cathedral", "shimmer", "freeverb.room", "freeverb.hall", "freeverb.cathedral"];
/// EQ band shapes (fx/eq.rs biquad).
pub const EQ_SHAPES: &[&str] = &["lowshelf", "highshelf", "peak", "lowpass", "highpass", "notch"];
pub use super::names_instruments::{built_in_names, kit_names};
/// The synthesized drum kit (instruments/voices/tones.rs drum voices).
pub const SYNTH_DRUMS: &[&str] = &["kick", "snare", "clap", "hat", "openHat", "cymbal", "tom", "rim"];
/// General MIDI percussion keys the recorded kits (and an SFZ kit on GM keys) answer to: one list on every kit.
pub const GM_DRUMS: &[(&str, u8)] = &[
    ("kick", 36), ("kick2", 35), ("rim", 37), ("snare", 38), ("clap", 39), ("snare2", 40), ("hat", 42), ("pedalHat", 44), ("openHat", 46),
    ("lowTom", 41), ("floorTom", 43), ("tomLow", 45), ("tom", 47), ("midTom", 47), ("tomHigh", 50), ("highTom", 50), ("crash", 49),
    ("cymbal", 49), ("ride", 51), ("china", 52), ("rideBell", 53), ("splash", 55), ("crash2", 57), ("ride2", 59), ("stir", 60), ("shaker", 70),
];
/// The performance layer's families and their defaults (ENGINE_CONTRACT.md § Perform; the experiment's
/// performDefaults.ts, Sam 2026-10-15): timing ms, velocity spread, accent, strum, articulation.
pub const PERFORM_DEFAULTS: &[(&str, &str)] = &[
    ("plucked", r#"{"timing":8,"velocity":0.12,"accent":0.07,"strum":0.6}"#),
    ("mallets", r#"{"timing":6,"velocity":0.12,"accent":0.08}"#),
    ("drums", r#"{"timing":4,"velocity":0.1,"accent":0.06}"#),
    ("sustained", r#"{"timing":10,"velocity":0.08,"accent":0.04,"articulation":"legato"}"#),
    ("detached", r#"{"timing":6,"velocity":0.1,"accent":0.06}"#),
    ("keys", r#"{"timing":6,"velocity":0.1,"accent":0.05}"#),
    ("synth", r#"{"velocity":0.05}"#),
];
/// A recorded articulation's family (any other, sustain, soft, vibrato …, is sustained).
pub const ART_FAMILY: &[(&str, &str)] = &[("keys", "keys"), ("pedal", "keys"), ("spiccato", "detached"), ("staccato", "detached"), ("tremolo", "detached"),
    ("pizzicato", "plucked"), ("pluck", "plucked"), ("fingerstyle", "plucked"), ("hit", "drums"), ("roll", "drums"), ("mallet", "mallets")];
/// A classic voice's or a model's family (any other classic voice is synth).
pub const NAMED_FAMILY: &[(&str, &str)] = &[("feltPiano", "keys"), ("grandPiano", "keys"), ("glassMarimba", "mallets"), ("spiccatoStrings", "detached"),
    ("guitar", "plucked"), ("nylonGuitar", "plucked"), ("marimba", "mallets"), ("vibraphone", "mallets"), ("glockenspiel", "mallets"), ("tubularBell", "mallets"), ("violin", "sustained")];

pub fn art_family(art: &str) -> &'static str {
    ART_FAMILY.iter().find(|(a, _)| *a == art).map_or("sustained", |(_, f)| *f)
}

pub fn named_family(name: &str) -> &'static str {
    NAMED_FAMILY.iter().find(|(n, _)| *n == name).map_or("synth", |(_, f)| *f)
}

pub fn perform_defaults(family: &str) -> serde_json::Value {
    PERFORM_DEFAULTS.iter().find(|(f, _)| *f == family).map_or(serde_json::json!({}), |(_, d)| serde_json::from_str(d).expect("the defaults table is JSON"))
}
/// Procedural instruments (instruments/model/): the contract's name -> the engine's.
pub const MODELS: &[(&str, &str)] = &[("guitar", "model.guitar"), ("nylonGuitar", "model.nylonGuitar"), ("marimba", "model.marimba"),
    ("vibraphone", "model.vibraphone"), ("glockenspiel", "model.glockenspiel"), ("tubularBell", "model.tubularBell"), ("violin", "ddsp.violin")];
/// Plucked strings (they take `damping`); the bowed violin takes no touch at all.
pub const PLUCKED: &[&str] = &["guitar", "nylonGuitar"];
/// The synth's oscillator waves (instruments/synth/mod.rs osc).
pub const WAVES: &[&str] = &["saw", "square", "triangle", "sine"];
/// A model's touch fields (default None: the instrument's own, `model_default`).
pub const MODEL_FIELDS: &[Field] = &[Field("position", Num(0.0, 0.5), Def::None), Field("damping", Num(0.0, 1.0), N(0.0)), Field("hardness", Num(0.0, 1.0), N(0.5))];
/// The synth's settings, contract names (`brightness` is the engine's `cutoff`).
pub const SYNTH_FIELDS: &[Field] = &[Field("voices", Int(1.0, 16.0), N(3.0)), Field("detune", Num(0.0, 100.0), N(12.0)),
    Field("brightness", Num(40.0, 20000.0), N(2400.0)), Field("resonance", Num(0.0, 1.0), N(0.2)), Field("envAmount", Num(0.0, 8.0), N(0.0)),
    Field("attack", Num(0.001, 20.0), N(0.3)), Field("decay", Num(0.001, 20.0), N(0.5)), Field("sustain", Num(0.0, 1.0), N(0.8)),
    Field("release", Num(0.001, 20.0), N(0.8)), Field("octave", Int(-3.0, 3.0), N(0.0)), Field("drive", Num(0.0, 10.0), N(0.0)),
    Field("width", Num(0.0, 1.0), N(1.0)), Field("drift", Num(0.0, 30.0), N(0.0)), Field("noise", Num(0.0, 1.0), N(0.0)), Field("sub", Num(0.0, 1.0), N(0.0))];

/// Where a model is plucked or struck when the track does not say (guitar.rs, mallet.rs).
pub fn model_position(model: &str) -> f64 {
    match model { "guitar" => 0.13, "nylonGuitar" => 0.2, "marimba" => 0.42, "tubularBell" => 0.05, _ => 0.4 }
}

pub fn model_names() -> Vec<&'static str> {
    MODELS.iter().map(|(n, _)| *n).collect()
}

pub const MEDIA_FORMATS: &[&str] = &["wav", "flac", "ogg", "mp3", "mp4", "m4a", "mov"];
/// Plugin formats the engine hosts (plugins/clap, plugins/vst3), each its file extension.
pub const PLUGIN_FORMATS: &[&str] = &["clap", "vst3"];

/// How one effect field is read.
#[derive(Clone, Copy)]
pub enum Kind {
    /// A number in a range.
    Num(f64, f64),
    /// A whole number in a range.
    Int(f64, f64),
    /// A number in a range, or an envelope [[time, value], …].
    Env(f64, f64),
    Bool,
    /// One of a closed list.
    Name(&'static [&'static str]),
    /// A number, or absent (null): the engine decides.
    OptNum(f64, f64),
}

/// A field: its name (the same in the contract and the engine's job), how it is read, its default.
pub struct Field(pub &'static str, pub Kind, pub Def);

#[derive(Clone, Copy)]
pub enum Def {
    N(f64),
    B(bool),
    S(&'static str),
    None,
}

use Def::{B, N, S};
use Kind::{Bool, Env, Int, Name, Num, OptNum};

/// The insert effects (schedule/effect.rs), with the defaults the engine fills in. `eq` reads its bands apart,
/// `plugin` its fields (contract/plugin.rs).
pub const EFFECTS: &[(&str, &[Field])] = &[
    ("eq", &[]),
    ("plugin", &[]),
    ("compressor", &[Field("threshold", Env(-80.0, 0.0), N(-18.0)), Field("ratio", Env(1.0, 50.0), N(3.0)), Field("attack", Num(0.0001, 1.0), N(0.01)),
        Field("release", Num(0.001, 5.0), N(0.15)), Field("makeup", Env(-24.0, 48.0), N(0.0)), Field("knee", Num(0.0, 24.0), N(6.0))]),
    ("reverb", &[Field("space", Name(SPACES), S("hall")), Field("mix", Env(0.0, 1.0), N(0.25)), Field("decay", OptNum(0.1, 30.0), Def::None),
        Field("damping", OptNum(0.0, 1.0), Def::None), Field("size", OptNum(0.0, 1.0), Def::None)]),
    ("delay", &[Field("time", Num(0.001, 4.0), N(0.375)), Field("feedback", Env(0.0, 0.98), N(0.35)), Field("mix", Env(0.0, 1.0), N(0.2)),
        Field("pingPong", Bool, B(false)), Field("damp", Num(0.0, 1.0), N(0.3))]),
    ("saturate", &[Field("drive", Env(0.0, 1.0), N(0.3)), Field("mix", Env(0.0, 1.0), N(1.0))]),
    ("tape", &[Field("wow", Env(0.0, 1.0), N(0.2)), Field("flutter", Env(0.0, 1.0), N(0.2)), Field("age", Env(0.0, 1.0), N(0.2))]),
    ("limiter", &[Field("ceiling", Num(-24.0, 0.0), N(-1.0)), Field("release", Num(0.001, 2.0), N(0.1))]),
    ("width", &[Field("width", Env(0.0, 2.0), N(1.0)), Field("monoBelow", Num(0.0, 1000.0), N(120.0))]),
    ("gate", &[Field("threshold", Num(-100.0, 0.0), N(-45.0)), Field("ratio", Num(1.0, 100.0), N(4.0)), Field("range", Num(0.0, 100.0), N(30.0)),
        Field("attack", Num(0.0001, 1.0), N(0.002)), Field("hold", Num(0.0, 2.0), N(0.05)), Field("release", Num(0.001, 5.0), N(0.12))]),
    ("deess", &[Field("freq", Num(2000.0, 16000.0), N(6000.0)), Field("threshold", Num(-80.0, 0.0), N(-30.0)), Field("range", Num(0.0, 40.0), N(8.0))]),
    ("dehum", &[Field("freq", Num(0.0, 400.0), N(0.0)), Field("harmonics", Int(1.0, 32.0), N(6.0)), Field("width", Num(1.0, 400.0), N(40.0))]),
    ("dereverb", &[Field("amount", Num(0.0, 1.0), N(0.5)), Field("reduction", Num(0.0, 60.0), N(18.0)), Field("time", Num(0.0, 20.0), N(0.0))]),
];

/// An EQ band's fields.
pub const EQ_BAND: &[Field] = &[Field("shape", Name(EQ_SHAPES), Def::None), Field("freq", Env(10.0, 24000.0), Def::None),
    Field("gain", Env(-48.0, 48.0), N(0.0)), Field("q", Env(0.05, 40.0), N(0.707))];

pub fn effect_names() -> Vec<&'static str> {
    EFFECTS.iter().map(|(n, _)| *n).collect()
}

pub fn gm_drum(name: &str) -> Option<u8> {
    GM_DRUMS.iter().find(|(n, _)| *n == name).map(|(_, k)| *k)
}

/// The names as `describe` answers them.
pub fn describe() -> serde_json::Value {
    use serde_json::{json, Value};
    let field = |f: &Field| {
        let (kind, range) = match f.1 {
            Num(a, b) => ("number", json!([a, b])),
            Int(a, b) => ("whole number", json!([a, b])),
            Env(a, b) => ("number or envelope", json!([a, b])),
            OptNum(a, b) => ("number or null", json!([a, b])),
            Bool => ("bool", Value::Null),
            Name(n) => ("name", json!(n)),
        };
        let default = match f.2 { N(x) => json!(x), B(b) => json!(b), S(s) => json!(s), Def::None => Value::Null };
        json!({ "name": f.0, "kind": kind, "accepts": range, "default": default })
    };
    let fields = |fs: &[Field]| fs.iter().map(field).collect::<Vec<_>>();
    let instrument_fields = json!({ "model": fields(MODEL_FIELDS), "synth": fields(SYNTH_FIELDS), "plucked": PLUCKED,
        "modelPositions": MODELS.iter().filter(|(n, _)| *n != "violin").map(|(n, _)| (n.to_string(), json!(model_position(n)))).collect::<serde_json::Map<_, _>>() });
    let effects: serde_json::Map<String, Value> = EFFECTS.iter().map(|(n, fs)| {
        let fields: Vec<Value> = match *n {
            "eq" => vec![json!({ "name": "bands", "kind": "list", "of": EQ_BAND.iter().map(field).collect::<Vec<_>>() })],
            "plugin" => plugin_fields(),
            _ => fs.iter().map(field).collect(),
        };
        (n.to_string(), Value::Array(fields))
    }).collect();
    json!({ "tones": TONES, "spaces": SPACES, "eqShapes": EQ_SHAPES, "builtIns": built_in_names(), "synthDrums": SYNTH_DRUMS,
            "instruments": super::plain::describe(), "kits": super::plain::describe_kits(), "kitNames": kit_names(),
            "perform": { "families": PERFORM_DEFAULTS.iter().map(|(f, _)| (f.to_string(), perform_defaults(f))).collect::<serde_json::Map<_, _>>(),
                         "articulations": ART_FAMILY.iter().map(|(a, f)| (a.to_string(), json!(f))).collect::<serde_json::Map<_, _>>() },
            "gmDrums": GM_DRUMS.iter().map(|(n, k)| json!({ "name": n, "key": k })).collect::<Vec<_>>(),
            "mediaFormats": MEDIA_FORMATS, "pluginFormats": PLUGIN_FORMATS, "effects": effects, "models": model_names(), "waves": WAVES,
            "instrumentFields": instrument_fields })
}

/// A plugin's fields (an effect's, and an instrument's `plugin` object), as `describe` answers them.
fn plugin_fields() -> Vec<serde_json::Value> {
    use serde_json::json;
    vec![json!({ "name": "format", "kind": "name", "accepts": PLUGIN_FORMATS, "default": null }),
         json!({ "name": "path", "kind": "absolute path to a .clap / .vst3", "accepts": null, "default": null }),
         json!({ "name": "id", "kind": "text (the plugin's id in the file)", "accepts": null, "default": null }),
         json!({ "name": "params", "kind": "map of parameter id or name to number or envelope", "accepts": null, "default": {} }),
         json!({ "name": "state", "kind": "base64 text or null", "accepts": null, "default": null })]
}
