//! serve's `export` (scene_serve.rs § export): every frame from start to end at the comp's fps, into the encoder or
//! pictures, and where the time went. The reply's `timing` holds the whole run (`totalS`, wall time; the median and
//! slowest frame) and, summed over every frame in seconds, each step serve.rs `frame` times (`evalS`, `diffS`,
//! `layoutS`, `paintS`, `gpuS`, `readS`, `encodeWaitS` …), so people and agents can see what a slow export spends its
//! time on. With several drawing workers the steps add up over all of them (so they can sum to more than `totalS`).
//! `timing.layers`: where the paint time goes per layer, the 10 costliest (render_costs.rs); `stillPieces`: how many
//! pieces were drawn once for a frame's motion-blur samples, not per sample (still_runs.rs); `repeatedFrames`: how many
//! frames had the stage of the frame before and went to the encoder as that picture again, not drawn (export_crew.rs);
//! `workerStartS` the seconds the extra workers took to be ready and `workersMade` how many made their session now (the
//! others were kept from an earlier export: export_pool.rs).
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
//!
//! `saves` (a held encoder, `encode.keep`): [{end, file}], the export cut into files as it goes: the frames before
//! `end` (counted from the export's first) since the cut before are saved as `file`, each finished and renamed into
//! place by the encoder while the frames after it are drawn (encode_mp4.rs `--keep`). The last `end` is the export's
//! frame count. A stop or a crash keeps every file saved before it whole, and nothing of the one it was in. The reply's
//! `saved` counts the files and `saveWaitS` is how long the end waited for the encoder to finish the last ones.

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
            // `keep` (encode_mp4.rs --keep): the session's held encoder takes the frames when its settings match (its
            // file aside: each export names its own), else a new one is started and kept; its 2-4 s start is paid once.
            let file = req["file"].as_str();
            let key = (e["keep"].as_bool() == Some(true)).then(|| {
                let same: Vec<&str> = args.iter().map(String::as_str).filter(|a| Some(*a) != file).collect();
                format!("{program}|{}", same.join("|"))
            });
            if key.is_some() && file.is_none() {
                return Err("export encode keep needs file (the file each export is saved as)".into());
            }
            s.sink = match (key, s.kept_encoder.take()) {
                (Some(k), Some((held, mut sink))) if k == held => {
                    sink.begin_file();
                    s.kept_key = Some(k);
                    Some(sink)
                }
                (k, _) => {
                    s.kept_key = k;
                    Some(Sink::start(program, &args, e["repeat"].as_bool() == Some(true), e["nv12"].as_bool() == Some(true))?)
                }
            };
        }
    }
    let saves = saves_of(req, n, s.sink.as_ref().is_some_and(Sink::is_kept))?;
    let warning = painting_warning(&s.painting);
    if let Some(w) = &warning {
        eprintln!("2D engine: {w}");
    }
    let workers = crate::export_workers::workers(req, n)?;
    let t0 = Instant::now();
    let span = Span { start, fps, n };
    let (rows, costs, worker_start_s, workers_made, turn_s, card) = export_crew::draw_all(held, s, req, span, workers, saves.iter().map(|(e, f, _)| (*e, f.clone())).collect(), progress)?;
    let kept = s.sink.as_ref().is_some_and(Sink::is_kept);
    if kept {
        serve::drain(s)?;
    }
    let code = if images.is_some() { None } else if kept { Some(0) } else { Some(serve::finish(s)?) };
    if let Some(sink) = &s.sink {
        // Every frame, once, in order (sink.rs `push` notes each frame's number as it is queued).
        if images.is_none() && (sink.pushed() != n || !sink.in_order()) {
            return Err(format!("export: the encoder took {} frames of {n}{}", sink.pushed(), if sink.in_order() { "" } else { ", out of order" }));
        }
    }
    let mut save_wait_s = 0.0;
    if kept && saves.is_empty() {
        // a held encoder saves this export's frames as its file and goes on running (a wrong count above is never saved)
        let file = req["file"].as_str().ok_or("export encode keep needs file")?;
        s.sink.as_mut().unwrap().save(file)?;
    } else if kept {
        // the save marks went in with the frames (sink_turn.rs); the last files are being finished
        let files: Vec<(u32, String)> = saves.iter().map(|(_, f, k)| (*k, f.clone())).collect();
        save_wait_s = s.sink.as_mut().unwrap().wait_saved(&files)?;
    }
    for file in req["file"].as_str().into_iter().chain(saves.iter().map(|(_, f, _)| f.as_str())) {
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
    timing.insert("workersMade".into(), json!(workers_made));
    timing.insert("turn".into(), json!({ "convertS": turn_s[0], "waitS": turn_s[1], "handS": turn_s[2] }));
    timing.insert("saveWaitS".into(), json!(save_wait_s));
    // The card thread's share (export_crew.rs `own`): frames it played from the workers' paint calls, and its time.
    timing.insert("card".into(), card);
    timing.insert("repeatedFrames".into(), json!(rows.iter().filter(|r| r.repeat).count()));
    timing.insert("layers".into(), costs.report(scene));
    let encoder = s.sink.as_ref().and_then(Sink::encoder);
    let budget_mb = crate::export_workers::budget(s.width, s.height, workers) >> 20;
    // How the frames came back from the graphics card: the encoder's bytes from its output step, or as stored.
    let read = if images.is_some() { Value::Null } else if s.painter.last_read_ready { json!("output step on the GPU") } else { json!("as stored") };
    if kept {
        // held for the next export, under the settings it was started with
        s.kept_encoder = s.sink.take().zip(s.kept_key.take()).map(|(sink, k)| (k, sink));
    }
    let mut reply = json!({ "ok": true, "frames": n, "saved": saves.len(), "fps": fps, "code": code, "timing": timing, "warning": warning, "encoder": encoder, "read": read, "workers": workers, "budgetMB": budget_mb });
    serve::with_painting(&mut reply, &s.painting);
    Ok(reply)
}

/// The request's `saves` as (end, file, frames in it), checked: a held encoder's, ends rising to the frame count.
fn saves_of(req: &Value, n: u64, kept: bool) -> Result<Vec<(usize, String, u32)>, String> {
    let Some(list) = req["saves"].as_array() else { return Ok(vec![]) };
    if !kept {
        return Err("export saves needs a held MP4 encoder (encode keep, encode-mp4 --keep)".into());
    }
    let mut out: Vec<(usize, String, u32)> = vec![];
    for s in list {
        let (end, file) = (s["end"].as_u64().unwrap_or(0), s["file"].as_str().unwrap_or(""));
        let before = out.last().map_or(0, |l| l.0 as u64);
        if end <= before || end > n || file.is_empty() {
            return Err(format!("export saves: each is {{end, file}}, ends rising from above 0 to the export's {n} frames; got {s}"));
        }
        out.push((end as usize, file.to_string(), (end - before) as u32));
    }
    if out.last().map(|l| l.0 as u64) != Some(n) {
        return Err(format!("export saves: the last end must be the export's {n} frames (the frames after it would go in no file)"));
    }
    Ok(out)
}

fn write_csv(path: &str, start: f64, fps: f64, rows: &[Row]) -> Result<(), String> {
    let mut out = format!("frame,frameMs,samples,{}\n", STEPS.join(","));
    for r in rows {
        let cells: Vec<String> = r.steps.iter().map(|v| format!("{v:.2}")).collect();
        out += &format!("{},{:.2},{},{}\n", ((start + r.i as f64 / fps) * fps).round() as u64, r.took, r.samples, cells.join(","));
    }
    std::fs::write(path, out).map_err(|e| format!("writing the export's timing {path}: {e}"))
}
