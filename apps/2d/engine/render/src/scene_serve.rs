//! serve's scene requests (ENGINE_CONTRACT.md § 1): the engine holds the scene and evaluates every frame itself.
//!
//! - `{"scene": {…scene…}, "cpu"?: bool, "depth"?: 8 | 16}` → `{"ok": true, "items": n, "width", "height", "fps", "duration"}`: load or
//!   replace the scene, checked whole (`depth` 16: frames to an encoder are RGBA64LE, else RGBA8; both straight alpha) (scene/mod.rs; every layer's stage is written once, so a frame never meets
//!   something it can't draw). Opens a session the comp's size if none is open at that size.
//! - `{"frame": {"t": 1.25, "image"? | "rgba"? | "boxes"? …}}`: the scene at `t` seconds, drawn as any frame is
//!   (serve.rs `frame`; `index` defaults to the frame number round(t·fps), so a still equals the exported frame).
//!   Adds `timing.evalMs` (keys, easing and the stage markup). With the comp's `shutter` > 0 the frame is motion
//!   blurred: `samples` are the stages at `shutterSamples` sub-frame times centred on t (crate::motion, MOTION.md);
//!   the request's own `shutter` / `shutterSamples` override the comp's (e.g. `shutterSamples: 1` for a fast preview).
//! - `{"export": {"start"?, "end"?, "encode": {"program", "args"}, "file"?}}` → `{"ok", "frames", "timing"}`: every
//!   frame from start (default 0) to end (default the comp's duration) at the comp's fps into the encoder; `file`
//!   is checked to exist and not be empty after. Or `"images": "C:\\…\\f-{frame}.png"`: each frame to a picture.
//!   With `"alpha": true` the comp's background is left out, so the frames are transparent where nothing is drawn.
//!   With `"progress": true`, a line `{"progress": i, "of": n}` after each frame, before the reply.
//! - `{"edit": [{"id", "props"?: {…}, "anim"?: {field: [keys] | null}}, …]}` → `{"ok": true, "edits": n}`: small
//!   changes to the held scene (a drag), checked as a load is; the next frame shows them.
//! - `{"bones": {"t": 1.25}}` → `{"ok": true, "rigs": {…}}`: every rig's posed bones and IK targets in comp px (rig/bones.rs, RIG.md).
//! - `{"outline": {"id", "t"}}` → `{"ok": true, "d": "…"|null}`: a path layer's varied (tapered / width-profile) stroke as filled-outline
//!   path data in the layer's box px, at `t`; `d` null when the stroke is even (scene/outline_cmd.rs; the Lottie export's source).
//! - `{"measure": {"items": [{"id", "body", "font", "size", "weight", "stretch", "tracking", "lineHeight", "align", "boxWidth", …}]}}`
//!   → `{"ok": true, "sizes": {id: [w, h]}}`: each text's laid-out box in its own px, by the path that draws it (scene/measure.rs);
//!   with the loaded scene's fonts, else the app's. Needs no scene and no open page.

use std::time::Instant;

use serde_json::{json, Value};

use crate::painter::Gl;
use crate::scene::{eval, fonts, stage, Scene};
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
pub(crate) fn check(scene: &Scene) -> Result<(), String> {
    scene.comp.walk(&mut |n| match n.kind {
        "text" => fonts::resolve(&scene.fonts, n.props["font"].as_str().unwrap_or("")).map(|_| ()).map_err(|e| format!("{}: {e}", n.id)),
        _ => Ok(()),
    })?;
    crate::motion::check(&scene.comp)?;
    stage::stage(&eval::whole(&scene.comp, 0.0)).map(|_| ())
}

/// The font families the scene can name (the load reply's `fonts`, for agents and the font picker).
fn fonts_of(scene: &Scene) -> Vec<&str> {
    let mut names: Vec<&str> = scene.fonts.iter().map(|f| f.family.as_str()).collect();
    names.sort();
    names.dedup();
    names
}

fn count(n: &crate::scene::Node) -> usize {
    1 + n.effects.iter().chain(&n.masks).chain(&n.layers).chain(&n.rig).map(count).sum::<usize>()
}

pub fn load(held: &mut Held, session: &mut Option<Session>, warm: &mut Option<Result<Gl, String>>, req: &Value) -> Result<Value, String> {
    let scene = Scene::load(&req["scene"])?;
    check(&scene)?;
    let (w, h) = (scene.width(), scene.height());
    let deep = match req["depth"].as_u64() {
        None | Some(8) => false,
        Some(16) => true,
        Some(d) => return Err(format!("depth is 8 or 16; got {d}")),
    };
    let same = session.as_ref().is_some_and(|s| (s.width, s.height, s.deep) == (w, h, deep));
    if !same {
        let open = json!({ "width": w, "height": h, "html": stage::shell(w, h, &scene.fonts)?, "cpu": req["cpu"].as_bool() == Some(true), "depth": if deep { 16 } else { 8 } });
        *session = Some(serve::open(&open, warm)?.0);
    } else if held.shell != Some((w, h)) {
        serve::page(session.as_mut().unwrap(), &json!({ "html": stage::shell(w, h, &scene.fonts)? }))?;
    }
    held.shell = Some((w, h));
    let mut reply = json!({ "ok": true, "items": count(&scene.comp), "width": w, "height": h, "fps": scene.fps(), "duration": scene.duration(), "fonts": fonts_of(&scene) });
    serve::with_painting(&mut reply, &session.as_ref().unwrap().painting);
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

pub fn measure(held: &Held, req: &Value) -> Result<Value, String> {
    crate::scene::measure::measure(req, held.scene.as_ref().map(|s| s.fonts.as_slice()))
}

pub fn bones(held: &Held, req: &Value) -> Result<Value, String> {
    let t = req["t"].as_f64().ok_or("bones needs t (seconds)")?;
    Ok(crate::rig::bones(&held.scene()?.comp, t))
}

pub fn outline(held: &Held, req: &Value) -> Result<Value, String> {
    crate::scene::outline_cmd::outline(&held.scene()?.comp, req)
}

/// The stage markup at `t`, and the ms it took.
/// `alpha`: the comp's background left out (an export with transparency).
fn markup(scene: &Scene, t: f64, alpha: bool) -> Result<(String, f64), String> {
    let t0 = Instant::now();
    let plan = crate::motion::Plan::of(&scene.comp)?;
    let mut comp = eval::at(&scene.comp, t).expect("the comp always shows");
    plan.apply(&scene.comp, &mut comp);
    if alpha {
        comp.props.insert("background".into(), Value::String("transparent".into()));
    }
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
    let alpha = req["alpha"].as_bool() == Some(true);
    let (m, mut eval_ms) = markup(scene, t, alpha)?;
    let mut f = req.clone();
    if let Some(o) = f.as_object_mut() {
        o.remove("alpha");
        o.remove("shutter");
        o.remove("shutterSamples");
    }
    f["stage"] = Value::String(m);
    // Motion blur (crate::motion, MOTION.md): the stage at each sub-frame of the open shutter, averaged by serve.rs.
    let (angle, n) = crate::motion::shutter(&scene.comp, req)?;
    if angle > 0.0 && n > 1 {
        let mut samples = vec![];
        for ts in crate::motion::sample_times(t, scene.fps(), angle, n) {
            let (mk, ms) = markup(scene, ts, alpha)?;
            eval_ms += ms;
            samples.push(Value::String(mk));
        }
        f["samples"] = Value::Array(samples);
    }
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
        let mut f = json!({ "t": t, "index": (t * fps).round() as u64, "alpha": req["alpha"].as_bool() == Some(true) });
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
