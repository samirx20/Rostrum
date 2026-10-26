//! The plain names resolved (names_instruments.rs): `{"builtIn": "piano"}` and `{"kit": "drums"}` become the
//! recorded files under the assets folder (ROSTRUM_ASSETS_DIR, else %USERPROFILE%\.rostrum\assets, as
//! settings.py assets_dir), a synth preset or a classic voice. A pack that is not there is a loud error
//! naming the instrument, the pack and how to install it: never silence, never a quiet synth instead.

use super::error::Error;
use super::instrument::{Inst, Zone};
use super::names::{art_family, named_family};
use super::names_instruments::{self as cat, Plays, Recorded, KITS};
use super::pitch::name as key_name;
use serde_json::{json, Value};
use std::path::PathBuf;

pub fn assets_dir() -> PathBuf {
    match std::env::var_os("ROSTRUM_ASSETS_DIR").filter(|v| !v.is_empty()) {
        Some(p) => PathBuf::from(p),
        None => PathBuf::from(std::env::var_os("USERPROFILE").or_else(|| std::env::var_os("HOME")).unwrap_or_default()).join(".rostrum").join("assets"),
    }
}

/// A pack's file as an absolute path, or the loud error.
fn file(what: &str, pack: &str, rel: &str, at: &str) -> Result<String, Error> {
    file_in(&assets_dir(), what, pack, rel, at)
}

pub(super) fn file_in(root: &std::path::Path, what: &str, pack: &str, rel: &str, at: &str) -> Result<String, Error> {
    let dir = root.join("sounds").join(pack);
    let p = dir.join(rel);
    if p.is_file() {
        return Ok(p.to_string_lossy().into_owned());
    }
    let problem = if dir.is_dir() { format!("needs {} from the sound pack \"{pack}\", which is incomplete", p.display()) } else { format!("needs the sound pack \"{pack}\", which is not installed ({} is missing)", dir.display()) };
    Err(Error::not_found(at, &format!("\"{what}\""), problem).hint(format!("Install it: python -m rostrum_sound.packs install {pack} (an agent: run_model_install with \"{pack}\")")))
}

/// What a resolved name plays, its performance family and its credit line.
pub struct Resolved {
    pub inst: Inst,
    pub family: &'static str,
    pub credit: Option<&'static str>,
}

/// `builtIn`: a plain name or `classic.<voice>`; anything else lists the names.
pub fn built_in(name: &str, at: &str) -> Result<Resolved, Error> {
    if let Some(voice) = name.strip_prefix("classic.").filter(|v| cat::CLASSIC.contains(v)) {
        return Ok(Resolved { inst: Inst::BuiltIn(voice.to_string()), family: named_family(voice), credit: None });
    }
    match cat::plain(name) {
        Some(Plays::Rec(id, art)) => recorded(name, cat::recorded(id).expect("an entry the table names"), *art, at),
        Some(Plays::Synth(p)) => Ok(Resolved { inst: Inst::Synth(serde_json::from_str(cat::preset(p).2).expect("a preset is JSON")), family: "synth", credit: None }),
        Some(Plays::Classic(voice)) => Ok(Resolved { inst: Inst::BuiltIn(voice.to_string()), family: named_family(voice), credit: None }),
        None => {
            let names = cat::built_in_names();
            Err(Error::unknown(at, name, &names.iter().map(String::as_str).collect::<Vec<_>>()))
        }
    }
}

fn recorded(name: &str, e: &Recorded, art: Option<&'static str>, at: &str) -> Result<Resolved, Error> {
    let entries: Vec<(u8, &Recorded)> = if e.zones.is_empty() { vec![(127, e)] } else { e.zones.iter().map(|(k, id)| (*k, cat::recorded(id).expect("a zone the table names"))).collect() };
    let first = art.unwrap_or(entries[0].1.arts[0].0);
    let mut zones = vec![];
    for (hikey, z) in entries {
        let (sf2, rel) = (z.arts[0].1.ends_with(".sf2"), z.arts[0].1);
        if sf2 {
            let font = file(name, z.pack, rel, at)?;
            return Ok(Resolved { inst: Inst::Sampler(json!({ "font": font, "program": 0, "bank": 0, "drums": false, "humanize": true })), family: art_family(z.arts[0].0), credit: e.credit });
        }
        let spec = |file: Value, legato: bool, swell: bool| {
            let mut s = json!({ "file": file, "legato": legato, "swell": swell });
            if z.key_offset != 0 {
                s["keyOffset"] = json!(z.key_offset);
            }
            s
        };
        let mut arts: Vec<(String, Value)> = vec![];
        for (a, rel) in z.arts {
            arts.push((a.to_string(), spec(json!(file(name, z.pack, rel, at)?), false, false)));
        }
        if let Some(sus) = arts.iter().find(|(a, _)| a == "sustain").map(|(_, s)| s["file"].clone()) {
            arts.push(("legato".into(), spec(sus.clone(), true, false)));
            arts.push(("swell".into(), spec(sus, false, true)));
        }
        let main = arts.iter().find(|(a, _)| a == first).unwrap_or(&arts[0]).1.clone();
        zones.push(Zone { hikey, main, arts });
    }
    Ok(Resolved { inst: Inst::Sfz(zones), family: art_family(first), credit: e.credit })
}

/// `kit`: a recorded kit (its files and the keys each plays) or the synthesized one. `even`: its transients held in
/// reach and each piece at its starting level (instruments/sfz/tame.rs, kit_levels).
pub fn kit(name: &str, even: bool, at: &str) -> Result<Resolved, Error> {
    let Some(k) = KITS.iter().find(|k| k.name == name) else { return Err(Error::unknown(at, name, &cat::kit_names())) };
    let Some((pack, rel)) = k.file else { return Ok(Resolved { inst: Inst::Kit, family: "drums", credit: None }) };
    let mut files = vec![];
    for (pack, rel) in std::iter::once((pack, rel)).chain(k.fill) {
        let (mut spec, keys) = kit_file(&file(&format!("kit {name}"), pack, rel, at)?, at)?;
        if even {
            spec["even"] = json!(true);
            spec["gains"] = json!(kit_levels(name));
        }
        files.push((spec, keys));
    }
    Ok(Resolved { inst: Inst::KitSfz(files), family: "drums", credit: k.credit })
}

/// A recorded kit's starting level per key (dB; engine/data/kit_levels.json, measured by devtools/kit_levels.py).
pub fn kit_levels(kit: &str) -> Vec<(u8, f64)> {
    kit_table(kit).iter().filter_map(|(d, db)| Some((super::names::gm_drum(d)?, db.as_f64()?))).collect()
}

/// The same by drum name, as the file holds it.
fn kit_table(kit: &str) -> serde_json::Map<String, Value> {
    static TABLE: std::sync::OnceLock<Value> = std::sync::OnceLock::new();
    let t = TABLE.get_or_init(|| serde_json::from_str(include_str!("../../data/kit_levels.json")).expect("kit_levels.json is JSON"));
    t["kits"][kit].as_object().cloned().unwrap_or_default()
}

/// An SFZ kit file's spec and the MIDI keys it plays.
pub fn kit_file(path: &str, at: &str) -> Result<(Value, Vec<u8>), Error> {
    let regions = crate::instruments::sfz::instrument(path).map_err(|e| Error::new("BAD_ARGUMENT", at, format!("\"{path}\""), e))?;
    let keys: Vec<u8> = (0..=127u8).filter(|&k| regions.iter().any(|r| !r.cc_only && !r.on_release && r.lokey <= k && k <= r.hikey)).collect();
    Ok((json!({ "file": path, "legato": false, "swell": false }), keys))
}

fn installed(pack: &str, rel: &str) -> bool {
    assets_dir().join("sounds").join(pack).join(rel).is_file()
}

/// The plain names as `describe` answers them: what each plays, its articulations, range and family.
pub fn describe() -> Vec<Value> {
    let mut out: Vec<Value> = cat::PLAIN.iter().map(|(n, p)| match p {
        Plays::Rec(id, art) => {
            let e = cat::recorded(id).expect("an entry the table names");
            let parts: Vec<&Recorded> = if e.zones.is_empty() { vec![e] } else { e.zones.iter().filter_map(|(_, z)| cat::recorded(z)).collect() };
            let mut arts: Vec<&str> = parts[0].arts.iter().map(|a| a.0).filter(|a| parts.iter().all(|p| p.arts.iter().any(|b| b.0 == *a))).collect();
            let first = art.unwrap_or(arts[0]);
            arts.retain(|a| *a != first);
            arts.insert(0, first);
            if arts.contains(&"sustain") { arts.extend(["legato", "swell"]); }
            json!({ "name": n, "plays": "recorded", "instrument": id, "about": e.about, "pack": e.pack, "range": [key_name(e.range.0), key_name(e.range.1)],
                    "articulations": arts, "family": art_family(first), "credit": e.credit,
                    "installed": parts.iter().all(|p| p.arts.iter().all(|(_, f)| installed(p.pack, f))) })
        }
        Plays::Synth(p) => json!({ "name": n, "plays": "synth", "instrument": p, "about": cat::preset(p).1, "family": "synth", "installed": true }),
        Plays::Classic(v) => json!({ "name": n, "plays": "classic", "instrument": v, "about": format!("the synthesized {v}"), "family": named_family(v), "installed": true }),
    }).collect();
    out.extend(cat::CLASSIC.iter().map(|v| json!({ "name": format!("classic.{v}"), "plays": "classic", "instrument": v, "about": format!("the synthesized {v}"), "family": named_family(v), "installed": true })));
    out
}

pub fn describe_kits() -> Vec<Value> {
    KITS.iter().map(|k| json!({ "name": k.name, "about": k.about, "packs": k.file.iter().chain(&k.fill).map(|f| f.0).collect::<Vec<_>>(), "credit": k.credit,
        "family": "drums", "installed": k.file.iter().chain(&k.fill).all(|(p, f)| installed(p, f)),
        "evenLevelsDb": kit_table(k.name) })).collect()
}
