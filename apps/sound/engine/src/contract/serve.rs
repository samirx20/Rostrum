//! The ways in: `serve` (a long-lived process: one JSON request per stdin line, one answer per stdout line;
//! instruments, samples and decoded media stay loaded, unchanged tracks come from the render cache),
//! `request <file>` (one request, one answer) and `render <schedule> <out.wav>` (a render request).

use serde_json::{json, Value};
use std::io::{BufRead, Write};

pub fn serve() -> Result<(), String> {
    let stdin = std::io::stdin();
    let mut out = std::io::stdout().lock();
    for line in stdin.lock().lines() {
        let line = line.map_err(|e| format!("stdin: {e}"))?;
        if line.trim().is_empty() {
            continue;
        }
        let (reply, quit) = match serde_json::from_str::<Value>(&line) {
            Ok(req) => {
                let quit = req.get("do").and_then(Value::as_str) == Some("quit");
                // A panic in one request is that request's error, not the end of the process.
                let reply = std::panic::catch_unwind(|| super::answer(&req)).unwrap_or_else(|p| {
                    let what = p.downcast_ref::<String>().cloned().or_else(|| p.downcast_ref::<&str>().map(|s| s.to_string())).unwrap_or_default();
                    json!({ "id": req.get("id"), "ok": false, "error": super::Error::new("INTERNAL", "engine", "the request", format!("crashed the engine: {what}")).to_json() })
                });
                (reply, quit)
            }
            Err(e) => (json!({ "id": null, "ok": false, "error": super::Error::new("BAD_ARGUMENT", "request", "the line", format!("is not JSON ({e})")).to_json() }), false),
        };
        writeln!(out, "{reply}").and_then(|_| out.flush()).map_err(|e| format!("stdout: {e}"))?;
        if quit {
            break;
        }
    }
    Ok(())
}

/// `request <file>`: the answer on stdout; exit 1 when it failed.
pub fn request(path: &str) -> Result<(), String> {
    let text = std::fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?;
    let req: Value = serde_json::from_str(&text).map_err(|e| format!("{path}: not JSON ({e})"))?;
    finish(super::answer(&req))
}

/// `render <schedule.json> <out.wav>`: a render request with every track's meters, no stems.
pub fn render(schedule: &str, out: &str) -> Result<(), String> {
    let text = std::fs::read_to_string(schedule).map_err(|e| format!("{schedule}: {e}"))?;
    let s: Value = serde_json::from_str(&text).map_err(|e| format!("{schedule}: not JSON ({e})"))?;
    let abs = std::path::absolute(out).map_err(|e| format!("{out}: {e}"))?;
    finish(super::answer(&json!({ "do": "render", "schedule": s, "out": abs })))
}

fn finish(reply: Value) -> Result<(), String> {
    println!("{reply}");
    if reply["ok"] == json!(true) { Ok(()) } else { Err(reply["error"]["line"].as_str().unwrap_or("failed").to_string()) }
}
