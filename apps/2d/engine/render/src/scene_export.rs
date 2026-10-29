//! serve's `export` (scene_serve.rs § export): every frame from start to end at the comp's fps, into the encoder or
//! pictures, and where the time went. The reply's `timing` holds the whole run (`totalS`, wall time; the median and
//! slowest frame) and, summed over every frame in seconds, each step serve.rs `frame` times (`evalS`, `diffS`,
//! `layoutS`, `paintS`, `gpuS`, `readS`, `encodeWaitS` …), so people and agents can see what a slow export spends its
//! time on. With several drawing workers the steps add up over all of them (so they can sum to more than `totalS`).
//! `timing.layers`: where the paint time goes per layer, the 10 costliest (render_costs.rs); `stillPieces`: how many
//! pieces were drawn once for a frame's motion-blur samples, not per sample (still_runs.rs); `repeatedFrames`: how many
//! frames had the stage of the frame before and went to the encoder as that picture again, not drawn (export_crew.rs).
//! `timingCsv`: the same per frame, one row each. What painted (`gpu`, `adapter`, `fallback`) is in the reply, and
//! `warning` says in words when that was not the computer's main graphics card; `encoder` names the MP4 encoder
//! used and whether it ran on the graphics card (sink.rs `encoder`, with where its time went); `read` how the frames
//! came back from the graphics card (painter.rs `start_read`); `workers` how many drew and `budgetMB` each
//! one's Skia budget.
//!
//! The frames are drawn by `workers` drawing workers side by side (export_crew.rs: request `workers`, else
//! ROSTRUM2D_EXPORT_WORKERS, else from the processor's cores), each with its own session and its own thread building
//! its next frames' stage markup (E7) while it lays out and paints, so the processor's cores and the graphics card
//! are kept busy. The pictures are the same whatever the count (a frame is a function of its time). A failure on any
//! worker stops the export with the frame it failed at; the encoder must then have taken exactly every frame, in order.

use std::time::Instant;

use serde_json::{json, Map, Value};

use crate::export_crew::{self, Row, Span, STEPS};
use crate::scene_serve::Held;
use crate::serve::{self, Session};
use crate::sink::Sink;

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
            s.sink = Some(Sink::start(program, &args, e["repeat"].as_bool() == Some(true))?);
        }
    }
    let warning = painting_warning(&s.painting);
    if let Some(w) = &warning {
        eprintln!("2D engine: {w}");
    }
    let workers = crate::export_workers::workers(req, n)?;
    let t0 = Instant::now();
    let span = Span { start, fps, n };
    let (rows, costs, worker_start_s) = export_crew::draw_all(held, s, req, span, workers, progress)?;
    let code = if images.is_none() { Some(serve::finish(s)?) } else { None };
    if let Some(sink) = &s.sink {
        // Every frame, once, in order (sink.rs `push` notes each frame's number as it is queued).
        if images.is_none() && (sink.pushed() != n || !sink.in_order()) {
            return Err(format!("export: the encoder took {} frames of {n}{}", sink.pushed(), if sink.in_order() { "" } else { ", out of order" }));
        }
    }
    if let Some(file) = req["file"].as_str() {
        if std::fs::metadata(file).map_or(true, |m| m.len() == 0) {
            return Err(format!("export wrote no file: {file}"));
        }
    }
    if let Some(csv) = req["timingCsv"].as_str() {
        write_csv(csv, start, fps, &rows)?;
    }
    let ms: Vec<f64> = rows.iter().map(|r| r.took).collect();
    let mut sorted = ms.clone();
    sorted.sort_by(f64::total_cmp);
    let mut timing = Map::new();
    timing.insert("totalS".into(), json!(t0.elapsed().as_secs_f64()));
    timing.insert("medianMs".into(), json!(sorted[sorted.len() / 2]));
    timing.insert("maxMs".into(), json!(sorted[sorted.len() - 1]));
    timing.insert("firstMs".into(), json!(ms[0]));
    timing.insert("samples".into(), json!(rows.iter().map(|r| r.samples).sum::<u64>()));
    for (j, k) in STEPS.iter().enumerate() {
        timing.insert(k.replace("Ms", "S"), json!(rows.iter().map(|r| r.steps[j]).sum::<f64>() / 1000.0));
    }
    timing.insert("stillPieces".into(), json!(rows.iter().map(|r| r.still).sum::<u64>()));
    timing.insert("workerStartS".into(), json!(worker_start_s));
    timing.insert("repeatedFrames".into(), json!(rows.iter().filter(|r| r.repeat).count()));
    timing.insert("layers".into(), costs.report(scene));
    let encoder = s.sink.as_ref().and_then(Sink::encoder);
    let budget_mb = crate::export_workers::budget(s.width, s.height, workers) >> 20;
    // How the frames came back from the graphics card: the encoder's bytes from its output step, or as stored.
    let read = if images.is_some() { Value::Null } else if s.painter.last_read_ready { json!("output step on the GPU") } else { json!("as stored") };
    let mut reply = json!({ "ok": true, "frames": n, "fps": fps, "code": code, "timing": timing, "warning": warning, "encoder": encoder, "read": read, "workers": workers, "budgetMB": budget_mb });
    serve::with_painting(&mut reply, &s.painting);
    Ok(reply)
}

fn write_csv(path: &str, start: f64, fps: f64, rows: &[Row]) -> Result<(), String> {
    let mut out = format!("frame,frameMs,samples,{}\n", STEPS.join(","));
    for r in rows {
        let cells: Vec<String> = r.steps.iter().map(|v| format!("{v:.2}")).collect();
        out += &format!("{},{:.2},{},{}\n", ((start + r.i as f64 / fps) * fps).round() as u64, r.took, r.samples, cells.join(","));
    }
    std::fs::write(path, out).map_err(|e| format!("writing the export's timing {path}: {e}"))
}
