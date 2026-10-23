//! serve's `export` (scene_serve.rs § export): every frame from start to end at the comp's fps, into the encoder or
//! pictures, and where the time went. The reply's `timing` holds the whole run (`totalS`, the median and slowest
//! frame) and, summed over every frame in seconds, each step serve.rs `frame` times (`evalS`, `diffS`, `layoutS`,
//! `paintS`, `gpuS`, `readS`, `encodeWaitS` …), so people and agents can see what a slow export spends its time on.
//! `timingCsv`: the same per frame, one row each. What painted (`gpu`, `adapter`, `fallback`) is in the reply, and
//! `warning` says in words when that was not the computer's main graphics card.

use std::time::Instant;

use serde_json::{json, Map, Value};

use crate::scene_serve::{frame, Held};
use crate::serve::{self, Session};
use crate::sink::Sink;

/// The frame reply's timing fields summed (ms in the reply, seconds in the sum), in this order in the CSV.
const STEPS: [&str; 10] = ["evalMs", "decodeMs", "diffMs", "layoutMs", "paintMs", "recordMs", "gpuMs", "readMs", "convertMs", "encodeWaitMs"];

/// Words for an adapter that is not a main graphics card: the processor's own graphics or a software stand-in.
const NOT_MAIN: [&str; 6] = ["intel", "microsoft basic", "gdi generic", "llvmpipe", "swiftshader", "software"];

/// The warning for what painted, if it was not the main graphics card (None on a discrete or Apple GPU).
pub fn painting_warning(painting: &Value) -> Option<String> {
    let adapter = painting["adapter"].as_str().unwrap_or("");
    if painting["gpu"].as_bool() != Some(true) {
        let why = painting["fallback"].as_str().unwrap_or("asked for the CPU");
        return Some(format!("this export was drawn on the processor, not the graphics card ({why}); it is many times slower"));
    }
    let low = adapter.to_ascii_lowercase();
    NOT_MAIN.iter().any(|w| low.contains(w)).then(|| {
        format!("this export was drawn on \"{adapter}\", not the main graphics card; set Windows › Graphics settings to \
                 High performance for Rostrum2D")
    })
}

/// `progress(line)` after each frame when the request asks for it (`"progress": true`).
pub fn export(held: &Held, s: &mut Session, req: &Value, progress: &mut dyn FnMut(Value)) -> Result<Value, String> {
    let scene = held.scene()?;
    let fps = scene.fps();
    let start = req["start"].as_f64().unwrap_or(0.0);
    let end = req["end"].as_f64().unwrap_or(scene.duration());
    let n = (((end - start) * fps).round() as i64).max(1) as u64;
    let images = req["images"].as_str();
    match (&req["encode"], images) {
        (Value::Null, None) => return Err("export needs encode {program, args} or images (a path with {frame})".into()),
        (Value::Null, Some(p)) if !p.contains("{frame}") => return Err(format!("export images: the path must hold {{frame}}: {p}")),
        (Value::Null, Some(_)) => {}
        (e, _) => {
            let program = e["program"].as_str().ok_or("encode needs program")?;
            let args: Vec<String> = e["args"].as_array().ok_or("encode needs args")?.iter().filter_map(|a| a.as_str().map(String::from)).collect();
            s.sink = Some(Sink::start(program, &args)?);
        }
    }
    let warning = painting_warning(&s.painting);
    if let Some(w) = &warning {
        eprintln!("2D engine: {w}");
    }
    let t0 = Instant::now();
    let (mut ms, mut rows) = (vec![], vec![]);
    let mut sums = [0.0f64; STEPS.len()];
    for i in 0..n {
        let t = start + i as f64 / fps;
        let tf = Instant::now();
        let mut f = json!({ "t": t, "index": (t * fps).round() as u64, "alpha": req["alpha"].as_bool() == Some(true) });
        match images {
            Some(p) => f["image"] = json!(p.replace("{frame}", &format!("{:04}", (t * fps).round() as u64))),
            None => f["encode"] = json!(true),
        }
        let (reply, _) = frame(held, s, &f).map_err(|e| format!("export frame {i} (t={t:.3} s): {e}"))?;
        let took = tf.elapsed().as_secs_f64() * 1000.0;
        ms.push(took);
        let steps: Vec<f64> = STEPS.iter().map(|k| reply["timing"][*k].as_f64().unwrap_or(0.0)).collect();
        for (sum, v) in sums.iter_mut().zip(&steps) {
            *sum += v / 1000.0;
        }
        rows.push((took, steps, reply["timing"]["samples"].as_u64().unwrap_or(1)));
        if req["progress"].as_bool() == Some(true) {
            let elapsed = t0.elapsed().as_secs_f64();
            progress(json!({ "progress": i + 1, "of": n, "elapsedS": elapsed, "leftS": elapsed / (i + 1) as f64 * (n - i - 1) as f64 }));
        }
    }
    let code = if images.is_none() { Some(serve::finish(s)?) } else { None };
    if let Some(file) = req["file"].as_str() {
        if std::fs::metadata(file).map_or(true, |m| m.len() == 0) {
            return Err(format!("export wrote no file: {file}"));
        }
    }
    if let Some(csv) = req["timingCsv"].as_str() {
        write_csv(csv, start, fps, &rows)?;
    }
    let mut sorted = ms.clone();
    sorted.sort_by(f64::total_cmp);
    let mut timing = Map::new();
    timing.insert("totalS".into(), json!(t0.elapsed().as_secs_f64()));
    timing.insert("medianMs".into(), json!(sorted[sorted.len() / 2]));
    timing.insert("maxMs".into(), json!(sorted[sorted.len() - 1]));
    timing.insert("firstMs".into(), json!(ms[0]));
    timing.insert("samples".into(), json!(rows.iter().map(|r| r.2).sum::<u64>()));
    for (k, v) in STEPS.iter().zip(sums) {
        timing.insert(k.replace("Ms", "S"), json!(v));
    }
    let mut reply = json!({ "ok": true, "frames": n, "fps": fps, "code": code, "timing": timing, "warning": warning });
    serve::with_painting(&mut reply, &s.painting);
    Ok(reply)
}

fn write_csv(path: &str, start: f64, fps: f64, rows: &[(f64, Vec<f64>, u64)]) -> Result<(), String> {
    let mut out = format!("frame,frameMs,samples,{}\n", STEPS.join(","));
    for (i, (took, steps, samples)) in rows.iter().enumerate() {
        let cells: Vec<String> = steps.iter().map(|v| format!("{v:.2}")).collect();
        out += &format!("{},{took:.2},{samples},{}\n", ((start + i as f64 / fps) * fps).round() as u64, cells.join(","));
    }
    std::fs::write(path, out).map_err(|e| format!("writing the export's timing {path}: {e}"))
}
