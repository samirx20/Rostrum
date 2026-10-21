//! The plugin requests: `plugins` (every CLAP / VST3 plugin in a file or folder, or in the standard folders
//! and the user's `.rostrum\assets\plugins`, with its parameters) and `pluginWindow` (the plugin's own window
//! opened for a person; the answer, when they close it, is its saved state and the values of the parameters
//! the request named, for the front end to store in the document). The window runs in a child process
//! (`rostrum-sound plugin <session.json> --gui`, plugins/session.rs), so a plugin that crashes takes only
//! that process down and the `serve` stdin stays the request channel.

use super::error::Error;
use super::plugin::{self, described};
use super::read::Obj;
use super::time::Tempo;
use serde_json::{json, Map, Value};
use std::io::{BufRead, Read};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

/// How deep a folder is searched (vendors put their plugins in sub-folders).
const DEPTH: usize = 4;

/// `plugins`: the folders to search (`path`, or the default ones).
pub fn read_paths(o: &mut Obj) -> Result<Vec<PathBuf>, Error> {
    let at = o.at("path");
    let Some(v) = o.raw("path") else { return Ok(default_folders()) };
    let s = v.as_str().ok_or_else(|| Error::bad(&at, v, "is not a file or folder path", &[]))?;
    let p = PathBuf::from(s);
    if !p.is_absolute() {
        return Err(Error::new("BAD_ARGUMENT", &at, format!("\"{s}\""), "is not an absolute path"));
    }
    if !p.exists() {
        return Err(Error::not_found(&at, &format!("\"{s}\""), "does not exist"));
    }
    if p.is_file() && format_of(&p).is_none() {
        return Err(Error::new("BAD_ARGUMENT", &at, format!("\"{s}\""), "is not a .clap or .vst3 plugin, nor a folder"));
    }
    o.put("path", json!(s));
    Ok(vec![p])
}

/// The standard CLAP and VST3 folders (CLAP_PATH / VST3_PATH first) and `%USERPROFILE%\.rostrum\assets\plugins`.
pub fn default_folders() -> Vec<PathBuf> {
    let mut out = crate::plugins::clap::folders();
    #[cfg(windows)]
    out.extend(crate::plugins::vst3::folders());
    if let Some(home) = std::env::var_os("USERPROFILE").or_else(|| std::env::var_os("HOME")) {
        out.push(Path::new(&home).join(".rostrum").join("assets").join("plugins"));
    }
    out.dedup();
    out
}

/// Every plugin found: `{folders, plugins, failed}` (a file that would not load is listed with why).
pub fn list(paths: &[PathBuf]) -> Value {
    let mut files = vec![];
    for p in paths {
        find(p, DEPTH, &mut files);
    }
    let (mut plugins, mut failed) = (vec![], vec![]);
    for (format, f) in files {
        match described(format, &f) {
            Ok(list) => plugins.extend(list.iter().map(entry)),
            Err(e) => failed.push(json!({ "format": format, "path": f.to_string_lossy(), "error": e })),
        }
    }
    json!({ "folders": paths.iter().map(|p| p.to_string_lossy()).collect::<Vec<_>>(), "plugins": plugins, "failed": failed })
}

fn format_of(p: &Path) -> Option<&'static str> {
    let ext = p.extension()?.to_string_lossy().to_ascii_lowercase();
    super::names::PLUGIN_FORMATS.iter().copied().find(|f| *f == ext)
}

/// Plugin files under `p` (a .vst3 bundle is a folder: it is one plugin file, never searched inside).
fn find(p: &Path, depth: usize, out: &mut Vec<(&'static str, PathBuf)>) {
    if let Some(f) = format_of(p) {
        out.push((f, p.to_path_buf()));
        return;
    }
    let Ok(items) = std::fs::read_dir(p) else { return };
    if depth == 0 {
        return;
    }
    let mut items: Vec<PathBuf> = items.flatten().map(|e| e.path()).collect();
    items.sort();
    for i in items {
        find(&i, depth - 1, out);
    }
}

/// One plugin as the request answers it; a stepped parameter gets its number of steps.
fn entry(d: &Value) -> Value {
    let params: Vec<Value> = d["params"].as_array().map(|a| a.iter().map(|p| {
        let mut q = json!({ "id": p["id"], "name": p["name"], "min": p["min"], "max": p["max"], "default": p["default"] });
        if let Some(steps) = p.get("steps").cloned().or_else(|| (p["stepped"] == json!(true)).then(|| json!((p["max"].as_f64().unwrap_or(1.0) - p["min"].as_f64().unwrap_or(0.0)).round() as i64))) {
            q["steps"] = steps;
        }
        for k in ["unit", "plainMin", "plainMax"] {
            if let Some(v) = p.get(k) {
                q[k] = v.clone();
            }
        }
        q
    }).collect()).unwrap_or_default();
    json!({ "format": d["format"], "path": d["path"], "id": d["id"], "name": d["name"], "vendor": d["vendor"], "kind": d["kind"],
            "hasWindow": d["hasWindow"], "params": params })
}

/// `pluginWindow`: the plugin read (and checked) before anything opens.
pub fn read_window(o: &mut Obj) -> Result<plugin::Plugin, Error> {
    let at = o.at("plugin");
    let tempo = Tempo::read(None, &at)?.0;
    plugin::read(Obj::new(o.required("plugin")?, at)?, &tempo, None)
}

/// Opens the window and waits for the person to close it: `{"state", "params": {id: value}, "errors"}`.
pub fn open(p: plugin::Plugin) -> Result<Value, Error> {
    let fail = |e: String| Error::new("JOB_FAILED", "plugin", format!("\"{}\"", p.name), e);
    let session = json!({ "plugin": plugin::spec(&p.resolved, 0.0), "effect": p.kind == "effect", "title": format!("Rostrum: {}", p.name) });
    let file = std::env::temp_dir().join(format!("rostrum-sound-window-{}-{}.json", std::process::id(), stamp()));
    std::fs::write(&file, session.to_string()).map_err(|e| fail(format!("{}: {e}", file.display())))?;
    let exe = std::env::current_exe().map_err(|e| fail(format!("the engine's own path: {e}")))?;
    let child = Command::new(exe).arg("plugin").arg(&file).arg("--gui").stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn();
    let mut child = match child {
        Ok(c) => c,
        Err(e) => {
            let _ = std::fs::remove_file(&file);
            return Err(fail(format!("the window process would not start: {e}")));
        }
    };
    // Its stdin is held open while the window is: the session closes when its stdin ends.
    let stdin = child.stdin.take();
    let mut stderr = child.stderr.take();
    let err_text = std::thread::spawn(move || {
        let mut s = String::new();
        if let Some(e) = stderr.as_mut() {
            let _ = e.read_to_string(&mut s);
        }
        s
    });
    let (mut state, mut errors) = (None, vec![]);
    if let Some(out) = child.stdout.take() {
        for line in std::io::BufReader::new(out).lines().map_while(Result::ok) {
            let Ok(v) = serde_json::from_str::<Value>(&line) else { continue };
            if let Some(s) = v.get("state") {
                state = Some(s.clone());
            }
            if let Some(e) = v.get("error").and_then(Value::as_str) {
                errors.push(e.to_string());
            }
        }
    }
    let status = child.wait();
    drop(stdin);
    let _ = std::fs::remove_file(&file);
    let err_text = err_text.join().unwrap_or_default();
    let Some(state) = state else {
        let why = errors.last().cloned().or_else(|| err_text.lines().last().map(str::to_string)).unwrap_or_else(|| format!("the window process ended ({status:?}) without its state"));
        return Err(fail(why));
    };
    let params: Map<String, Value> = state["values"].as_array().map(|a| a.iter().filter_map(|pair| Some((pair.get(0)?.as_u64()?.to_string(), pair.get(1)?.clone()))).collect()).unwrap_or_default();
    Ok(json!({ "state": state["state"], "params": params, "errors": errors }))
}

fn stamp() -> u128 {
    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map_or(0, |d| d.as_nanos())
}
