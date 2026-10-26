//! The `range` request: what an instrument can play, so an agent voices before it renders. Read as a track's
//! instrument is (plain names resolved, a missing pack a loud error); SFZ ranges come from the files' regions
//! (loaded once and kept, instruments/sfz); synthesized and procedural voices play any key; a kit answers to
//! drum names.

use super::error::Error;
use super::instrument::{self, Inst};
use super::names::{self, SYNTH_DRUMS};
use super::pitch::name;
use serde_json::{json, Value};

pub fn range(v: &Value, at: &str) -> Result<Value, Error> {
    let (r, resolved) = instrument::read(Some(v), at, &super::time::Tempo::read(None, at)?.0)?;
    let any = |note: &str| json!({ "instrument": resolved, "low": name(21), "high": name(108), "lowKey": 21, "highKey": 108, "gaps": [], "layers": 1, "drums": [], "note": note });
    // Each file and the half steps its keys sit above the pitch written (keyOffset: contract/names_instruments.rs).
    let files: Vec<(String, i8)> = match &r.inst {
        Inst::Plugin(_) => return Ok(json!({ "instrument": resolved, "low": name(0), "high": name(127), "lowKey": 0, "highKey": 127, "gaps": [], "layers": 1,
                                             "drums": [], "note": "a plugin: it is sent any MIDI key; which keys sound is the plugin's own" })),
        Inst::Model { .. } | Inst::Synth(_) | Inst::BuiltIn(_) => return Ok(any("procedural / synthesized: plays any key (A0-C8 shown)")),
        Inst::Sampler(_) => return Ok(any("a SoundFont: keys outside its samples play its nearest sample (A0-C8 shown)")),
        Inst::Kit => return Ok(json!({ "instrument": resolved, "drums": SYNTH_DRUMS })),
        Inst::Sfz(zones) => zones.iter().filter_map(|z| Some((z.main["file"].as_str()?.to_string(), z.main["keyOffset"].as_i64().unwrap_or(0) as i8))).collect(),
        Inst::KitSfz(files) => files.iter().filter_map(|(s, _)| Some((s["file"].as_str()?.to_string(), 0))).collect(),
        Inst::None => return Err(Error::bad(at, v, "is not an instrument", &instrument::FORMS)),
    };
    let mut played = vec![];
    for (f, off) in &files {
        let regions = crate::instruments::sfz::instrument(f).map_err(|e| Error::new("BAD_ARGUMENT", at, format!("\"{f}\""), e))?;
        let written = |k: u8| (k as i16 - *off as i16).clamp(0, 127) as u8;
        played.extend(regions.iter().filter(|r| !r.cc_only && !r.on_release).map(|r| crate::instruments::sfz::Region { lokey: written(r.lokey), hikey: written(r.hikey), ..r.clone() }));
    }
    if played.is_empty() {
        return Err(Error::new("BAD_ARGUMENT", at, files.iter().map(|f| f.0.as_str()).collect::<Vec<_>>().join(", "), "has no playable regions"));
    }
    let lo = played.iter().map(|r| r.lokey).min().unwrap_or(0);
    let hi = played.iter().map(|r| r.hikey).max().unwrap_or(0);
    let gaps: Vec<u8> = (lo..=hi).filter(|&k| !played.iter().any(|r| r.lokey <= k && k <= r.hikey)).collect();
    let mut vel_edges: Vec<u8> = played.iter().map(|r| r.lovel).collect();
    vel_edges.sort();
    vel_edges.dedup();
    let drums: Vec<&str> = match &r.inst {
        Inst::KitSfz(files) => names::GM_DRUMS.iter().filter(|(_, k)| files.iter().any(|(_, keys)| keys.contains(k))).map(|(n, _)| *n).collect(),
        _ => vec![],
    };
    // How early its notes start so each is heard on its time (instruments/sfz/onset.rs), over its main files' samples.
    let mut attack: Option<(f64, f64)> = None;
    if let Inst::Sfz(_) = &r.inst {
        for (f, _) in &files {
            if let Some((med, most)) = crate::instruments::sfz::onset::typical_ms(f).map_err(|e| Error::new("BAD_ARGUMENT", at, format!("\"{f}\""), e))? {
                attack = Some(attack.map_or((med, most), |(a, b)| (a.max(med), b.max(most))));
            }
        }
    }
    let round = |v: f64| v.round();
    Ok(json!({ "instrument": resolved, "low": name(lo), "high": name(hi), "lowKey": lo, "highKey": hi,
               "gaps": gaps.iter().map(|&k| name(k)).collect::<Vec<_>>(), "layers": vel_edges.len(), "drums": drums,
               "attackMs": attack.map(|(med, most)| json!({ "typical": round(med), "most": round(most) })) }))
}
