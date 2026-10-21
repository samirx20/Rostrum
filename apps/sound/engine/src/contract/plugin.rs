//! A CLAP / VST3 plugin as the contract names it (an effect, or an instrument's `plugin`): its format, its file,
//! its id in that file, its saved state and its parameters, read strictly. The plugin is loaded once to read
//! what it is and its parameters (plugins/clap, plugins/vst3; kept per file and modified time), so an id the
//! file does not hold, a parameter it does not have or a value outside its range fails here, naming it.
//! A parameter is named by its id or its name; its value is a number or an envelope through the tempo map.
//! The resolved form keys parameters by id, so it turns into the job's PluginSpec without loading again.

use super::effects;
use super::error::Error;
use super::names::PLUGIN_FORMATS;
use super::read::Obj;
use super::time::Tempo;
use serde_json::{json, Map, Value};
use std::collections::HashMap;
use std::path::Path;
use std::sync::{Mutex, OnceLock};

pub struct Plugin {
    /// The contract form, every default written in, `params` keyed by parameter id.
    pub resolved: Map<String, Value>,
    /// "effect" or "instrument" (what the plugin says it is).
    pub kind: String,
    pub name: String,
}

/// Reads the plugin's fields of `o` and ends it (an unknown field fails before the plugin is loaded).
/// `want`: the kind the place needs (an effect slot, an instrument), None for either.
pub fn read(mut o: Obj, tempo: &Tempo, want: Option<&str>) -> Result<Plugin, Error> {
    let format = o.name("format", PLUGIN_FORMATS, None)?;
    let path = o.str("path", None)?;
    let pa = o.at("path");
    let file = Path::new(&path);
    if !file.is_absolute() || !file.extension().is_some_and(|e| e.eq_ignore_ascii_case(&format)) {
        return Err(Error::new("BAD_ARGUMENT", &pa, format!("\"{path}\""), format!("is not an absolute path to a .{format} plugin")));
    }
    if !file.exists() {
        return Err(Error::not_found(&pa, &format!("\"{path}\""), "does not exist"));
    }
    let id = o.str("id", None)?;
    let ia = o.at("id");
    let state = match o.raw("state") {
        None => Value::Null,
        Some(Value::String(s)) => {
            crate::plugins::params::unbase64(s).map_err(|e| Error::new("BAD_ARGUMENT", &o.at("state"), "state", e))?;
            json!(s)
        }
        Some(v) => return Err(Error::bad(&o.at("state"), v, "is not a saved state (base64 text)", &[])),
    };
    o.put("state", state);
    let params_at = o.at("params");
    let params = o.raw("params");
    let mut resolved = o.done()?;

    let list = described(&format, file).map_err(|e| Error::new("BAD_ARGUMENT", &pa, format!("\"{path}\""), e))?;
    let ids: Vec<&str> = list.iter().filter_map(|p| p["id"].as_str()).collect();
    let found = list.iter().find(|p| p["id"].as_str() == Some(id.as_str())).ok_or_else(|| Error::unknown(&ia, &id, &ids))?;
    let kind = found["kind"].as_str().unwrap_or("effect").to_string();
    if let Some(w) = want.filter(|w| *w != kind) {
        let place = if w == "effect" { "an effect (it plays notes: give it to a track's instrument)" } else { "an instrument (it processes sound: put it in effects)" };
        return Err(Error::new("BAD_ARGUMENT", &ia, format!("\"{id}\""), format!("is an {kind} plugin, not {place}")));
    }
    let empty = vec![];
    let known = found["params"].as_array().unwrap_or(&empty);
    resolved.insert("params".into(), Value::Object(values(params, &params_at, known, tempo)?));
    let name = found["name"].as_str().unwrap_or(&id).to_string();
    Ok(Plugin { resolved, kind, name })
}

/// `params`: {id or name: number or envelope}, checked against the plugin's own list, keyed by id.
fn values(v: Option<&Value>, at: &str, known: &[Value], tempo: &Tempo) -> Result<Map<String, Value>, Error> {
    let mut out = Map::new();
    let Some(v) = v else { return Ok(out) };
    let m = v.as_object().ok_or_else(|| Error::bad(at, v, "is not a map of parameter ids or names to values", &["{\"Cutoff\": 0.5}", "{\"12\": [[0, 0.2], [4, 0.8]]}"]))?;
    let names: Vec<&str> = known.iter().filter_map(|p| p["name"].as_str()).collect();
    for (key, val) in m {
        let pa = format!("{at}.{key}");
        let by_id = key.parse::<u64>().ok().and_then(|n| known.iter().find(|p| p["id"].as_u64() == Some(n)));
        let p = match by_id {
            Some(p) => p,
            None => {
                let named: Vec<&Value> = known.iter().filter(|p| p["name"].as_str() == Some(key.as_str())).collect();
                match named.len() {
                    0 => return Err(Error::unknown(&pa, key, &names)),
                    1 => named[0],
                    n => return Err(Error::new("BAD_ARGUMENT", &pa, format!("\"{key}\""), format!("names {n} parameters of this plugin")).hint("Name it by its id (the plugins request lists them).")),
                }
            }
        };
        let id = p["id"].as_u64().unwrap_or(0).to_string();
        let x = effects::envelope(val, &pa, p["min"].as_f64().unwrap_or(0.0), p["max"].as_f64().unwrap_or(1.0), tempo)?;
        if out.insert(id.clone(), x).is_some() {
            return Err(Error::new("BAD_ARGUMENT", &pa, format!("\"{key}\""), format!("is parameter {id}, which another key already sets")));
        }
    }
    Ok(out)
}

/// The job's PluginSpec (plugins/clap PluginSpec) of a resolved plugin, its envelopes read from song second `at`.
pub fn spec(m: &Map<String, Value>, at: f64) -> Value {
    let get = |k: &str| m.get(k).cloned().unwrap_or(Value::Null);
    let params: Vec<Value> = m.get("params").and_then(Value::as_object)
        .map(|p| p.iter().map(|(id, v)| json!([id.parse::<u32>().unwrap_or(0), v])).collect()).unwrap_or_default();
    json!({ "format": get("format"), "path": get("path"), "id": get("id"), "params": params, "state": get("state"), "at": at })
}

/// The plugins in one file (or VST3 bundle), as plugins/clap and plugins/vst3 describe them; loaded once per
/// file and modified time, then kept for the process (a plugin's DLL stays loaded anyway).
pub fn described(format: &str, path: &Path) -> Result<Vec<Value>, String> {
    static KEPT: OnceLock<Mutex<HashMap<String, Vec<Value>>>> = OnceLock::new();
    let stamp = std::fs::metadata(path).and_then(|m| m.modified()).ok().and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok()).map_or(0, |d| d.as_nanos());
    let key = format!("{format}|{}|{stamp}", path.display());
    let kept = KEPT.get_or_init(Default::default);
    if let Some(list) = kept.lock().unwrap_or_else(|e| e.into_inner()).get(&key) {
        return Ok(list.clone());
    }
    let list = match format {
        "clap" => crate::plugins::clap::describe(path)?,
        #[cfg(windows)]
        "vst3" => crate::plugins::vst3::describe(path)?,
        f => return Err(format!("{f} plugins are not hosted by this engine on this system")),
    };
    if list.is_empty() {
        return Err("holds no plugins this engine can load".into());
    }
    kept.lock().unwrap_or_else(|e| e.into_inner()).insert(key, list.clone());
    Ok(list)
}
