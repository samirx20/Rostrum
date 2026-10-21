//! serve's scene requests (ENGINE_CONTRACT.md § 1): the engine holds the scene and evaluates every frame itself.
//!
//! - `{"scene": {…scene…}, "cpu"?: bool}` → `{"ok": true, "items": n, "width", "height", "fps", "duration"}`: load or
//!   replace the scene, checked whole (scene/mod.rs; every layer's stage is written once, so a frame never meets
//!   something it can't draw). Opens a session the comp's size if none is open at that size.
//! - `{"frame": {"t": 1.25, "image"? | "rgba"? | "boxes"? …}}`: the scene at `t` seconds, drawn as any frame is
//!   (serve.rs `frame`; `index` defaults to the frame number round(t·fps), so a still equals the exported frame).
//!   Adds `timing.evalMs` (keys, easing and the stage markup).
//! - `{"export": {"start"?, "end"?, "encode": {"program", "args"}, "file"?}}` → `{"ok", "frames", "timing"}`: every
//!   frame from start (default 0) to end (default the comp's duration) at the comp's fps into the encoder; `file`
//!   is checked to exist and not be empty after. Or `"images": "C:\\…\\f-{frame}.png"`: each frame to a picture.
//!   With `"progress": true`, a line `{"progress": i, "of": n}` after each frame, before the reply.
//! - `{"edit": [{"id", "props"?: {…}, "anim"?: {field: [keys] | null}}, …]}` → `{"ok": true, "edits": n}`: small
//!   changes to the held scene (a drag), checked as a load is; the next frame shows them.

use std::time::Instant;

use serde_json::{json, Value};

use crate::painter::Gl;
use crate::scene::{eval, stage, Scene};
use crate::serve::{self, Session};
use crate::sink::Sink;

/// The scene the engine holds, and whether the open page is its shell.
#[derive(Default)]
pub struct Held {
    scene: Option<Scene>,
    /// The session's page is the scene shell at this size (an `open` / `page` request clears it).
    pub shell: Option<(u32, u32)>,
}

impl Held {
    fn scene(&self) -> Result<&Scene, String> {
        self.scene.as_ref().ok_or_else(|| "no scene loaded (send {\"scene\": …} first)".to_string())
    }
}

/// Every layer's stage written once (showing or not), so what can't be drawn is refused now.
fn check(scene: &Scene) -> Result<(), String> {
    stage::stage(&eval::whole(&scene.comp, 0.0)).map(|_| ())
}

fn count(n: &crate::scene::Node) -> usize {
    1 + n.effects.iter().chain(&n.masks).chain(&n.layers).map(count).sum::<usize>()
}

pub fn load(held: &mut Held, session: &mut Option<Session>, warm: &mut Option<Result<Gl, String>>, req: &Value) -> Result<Value, String> {
    let scene = Scene::load(&req["scene"])?;
    check(&scene)?;
    let (w, h) = (scene.width(), scene.height());
    let same_size = session.as_ref().is_some_and(|s| (s.width, s.height) == (w, h));
    if !same_size {
        let open = json!({ "width": w, "height": h, "html": stage::shell(w, h), "cpu": req["cpu"].as_bool() == Some(true) });
        *session = Some(serve::open(&open, warm)?.0);
    } else if held.shell != Some((w, h)) {
        serve::page(session.as_mut().unwrap(), &json!({ "html": stage::shell(w, h) }))?;
    }
    held.shell = Some((w, h));
    let reply = json!({ "ok": true, "items": count(&scene.comp), "width": w, "height": h, "fps": scene.fps(), "duration": scene.duration() });
    held.scene = Some(scene);
    Ok(reply)
}

pub fn edit(held: &mut Held, edits: &Value) -> Result<Value, String> {
    let mut next = held.scene()?.clone();
    let n = next.edit(edits)?;
    check(&next)?;
    held.scene = Some(next);
    Ok(json!({ "ok": true, "edits": n }))
}

/// The stage markup at `t`, and the ms it took.
fn markup(scene: &Scene, t: f64) -> Result<(String, f64), String> {
    let t0 = Instant::now();
    let comp = eval::at(&scene.comp, t).expect("the comp always shows");
    let m = stage::stage(&comp)?;
    Ok((m, t0.elapsed().as_secs_f64() * 1000.0))
}

/// `frame` with `t`: the request with the scene's stage at t filled in, drawn by serve.rs `frame`.
pub fn frame(held: &Held, s: &mut Session, req: &Value) -> Result<(Value, Option<Vec<u8>>), String> {
    let scene = held.scene()?;
    let t = req["t"].as_f64().ok_or("frame needs t (seconds) or stage")?;
    if held.shell != Some((s.width, s.height)) {
        return Err("the open page is not the scene's (an open or page came after the scene); send the scene again".into());
    }
    let (m, eval_ms) = markup(scene, t)?;
    let mut f = req.clone();
    f["stage"] = Value::String(m);
    if f.get("index").is_none() {
        f["index"] = json!((t * scene.fps()).round() as u64);
    }
    let (mut reply, px) = serve::frame(s, &f)?;
    if let Some(timing) = reply.get_mut("timing") {
        timing["evalMs"] = json!(eval_ms);
    }
    Ok((reply, px))
}

/// `progress(i, n)` after each frame when the request asks for it (`"progress": true`).
pub fn export(held: &Held, s: &mut Session, req: &Value, progress: &mut dyn FnMut(u64, u64)) -> Result<Value, String> {
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
    let t0 = Instant::now();
    let mut ms = vec![];
    for i in 0..n {
        let t = start + i as f64 / fps;
        let tf = Instant::now();
        let mut f = json!({ "t": t, "index": (t * fps).round() as u64 });
        match images {
            Some(p) => f["image"] = json!(p.replace("{frame}", &format!("{:04}", (t * fps).round() as u64))),
            None => f["encode"] = json!(true),
        }
        frame(held, s, &f).map_err(|e| format!("export frame {i} (t={t:.3} s): {e}"))?;
        ms.push(tf.elapsed().as_secs_f64() * 1000.0);
        if req["progress"].as_bool() == Some(true) {
            progress(i + 1, n);
        }
    }
    let code = if images.is_none() { Some(serve::finish(s)?) } else { None };
    if let Some(file) = req["file"].as_str() {
        if std::fs::metadata(file).map_or(true, |m| m.len() == 0) {
            return Err(format!("export wrote no file: {file}"));
        }
    }
    let mut sorted = ms.clone();
    sorted.sort_by(f64::total_cmp);
    let timing = json!({ "totalS": t0.elapsed().as_secs_f64(), "medianMs": sorted[sorted.len() / 2], "maxMs": sorted[sorted.len() - 1], "firstMs": ms[0] });
    Ok(json!({ "ok": true, "frames": n, "fps": fps, "code": code, "timing": timing }))
}
