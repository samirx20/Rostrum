//! The `range` request: what an instrument can play, so an agent voices before it renders. An SFZ file's
//! range comes from its regions (loaded once and kept, instruments/sfz); built-ins are synthesized and
//! play any key; a kit answers to drum names.

use super::error::Error;
use super::names::{self, SYNTH_DRUMS};
use super::pitch::name;
use super::read::Obj;
use serde_json::{json, Value};

pub fn range(v: &Value, at: &str) -> Result<Value, Error> {
    if v.get("plugin").is_some() {
        let (_, resolved) = super::instrument::read(Some(v), at, &super::time::Tempo::read(None, at)?.0)?;
        return Ok(json!({ "instrument": resolved, "low": name(0), "high": name(127), "lowKey": 0, "highKey": 127, "gaps": [], "layers": 1,
                          "drums": [], "note": "a plugin: it is sent any MIDI key; which keys sound is the plugin's own" }));
    }
    if v.get("model").is_some() || v.get("synth").is_some() {
        let (_, resolved) = super::instrument::read(Some(v), at, &super::time::Tempo::read(None, at)?.0)?;
        return Ok(json!({ "instrument": resolved, "low": name(21), "high": name(108), "lowKey": 21, "highKey": 108, "gaps": [], "layers": 1,
                          "drums": [], "note": "procedural / synthesized: plays any key (A0-C8 shown)" }));
    }
    let mut o = Obj::new(v, at)?;
    let out = if o.has("builtIn") {
        let n = o.name("builtIn", names::BUILT_INS, None)?;
        json!({ "instrument": n, "low": name(21), "high": name(108), "lowKey": 21, "highKey": 108, "gaps": [], "layers": 1,
                "drums": [], "note": "synthesized: plays any key (A0-C8 shown)" })
    } else if o.has("kit") {
        o.name("kit", &["synth"], None)?;
        json!({ "instrument": "kit synth", "drums": SYNTH_DRUMS })
    } else if o.has("sfz") || o.has("kitSfz") {
        let kit = o.has("kitSfz");
        let file = o.str(if kit { "kitSfz" } else { "sfz" }, None)?;
        let _ = (o.raw("legato"), o.raw("swell"));
        let regions = crate::instruments::sfz::instrument(&file).map_err(|e| Error::new("BAD_ARGUMENT", &o.at(if kit { "kitSfz" } else { "sfz" }), format!("\"{file}\""), e))?;
        let played: Vec<_> = regions.iter().filter(|r| !r.cc_only && !r.on_release).collect();
        if played.is_empty() {
            return Err(Error::new("BAD_ARGUMENT", at, format!("\"{file}\""), "has no playable regions"));
        }
        let lo = played.iter().map(|r| r.lokey).min().unwrap_or(0);
        let hi = played.iter().map(|r| r.hikey).max().unwrap_or(0);
        let gaps: Vec<u8> = (lo..=hi).filter(|&k| !played.iter().any(|r| r.lokey <= k && k <= r.hikey)).collect();
        let mut vel_edges: Vec<u8> = played.iter().map(|r| r.lovel).collect();
        vel_edges.sort();
        vel_edges.dedup();
        let drums: Vec<&str> = if kit { names::GM_DRUMS.iter().filter(|(_, k)| played.iter().any(|r| r.lokey <= *k && *k <= r.hikey)).map(|(n, _)| *n).collect() } else { vec![] };
        json!({ "instrument": file, "low": name(lo), "high": name(hi), "lowKey": lo, "highKey": hi,
                "gaps": gaps.iter().map(|&k| name(k)).collect::<Vec<_>>(), "layers": vel_edges.len(), "drums": drums })
    } else {
        return Err(Error::bad(at, v, "is not an instrument", &super::instrument::FORMS));
    };
    o.done()?;
    Ok(out)
}
