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
//!   With `"progress": true`, a line `{"progress": i, "of": n, "elapsedS", "leftS"}` after each frame, before the reply.
//!   The reply's `timing` sums where the time went (scene_export.rs); `"timingCsv": path` writes it per frame too.
//! - `{"edit": [{"id", "props"?: {…}, "anim"?: {field: [keys] | null}}, …]}` → `{"ok": true, "edits": n}`: small
//!   changes to the held scene (a drag), checked as a load is; the next frame shows them.
//! - `{"bones": {"t": 1.25}}` → `{"ok": true, "rigs": {…}}`: every rig's posed bones and IK targets in comp px (rig/bones.rs, RIG.md).
//! - `{"outline": {"id", "t"}}` → `{"ok": true, "d": "…"|null}`: a path layer's varied (tapered / width-profile) stroke as filled-outline
//!   path data in the layer's box px, at `t`; `d` null when the stroke is even (scene/outline_cmd.rs; the Lottie export's source).
//! - `{"place": {"t", "ids": [id, …]}}` → `{"ok": true, "layers": {id: {"m": [9], "w", "h", "edge": "M… L… Z"}}}`: where each layer
//!   is drawn at t, from the laid-out page (through its groups, the camera and tilt): `m` its own px -> comp px (3×3
//!   projective, row-major), `w` × `h` its own box, `edge` its true outline in comp px (place.rs). A `frame` with
//!   `"place": [id, …]` adds the same as its reply's `place`, for the picture it drew (a layer it doesn't draw left out).
//! - `{"measure": {"items": [{"id", "body", "font", "size", "weight", "stretch", "tracking", "lineHeight", "align", "boxWidth", …}]}}`
//!   → `{"ok": true, "sizes": {id: [w, h]}}`: each text's laid-out box in its own px, by the path that draws it (scene/measure.rs);
//!   with the loaded scene's fonts, else the app's. Needs no scene and no open page.
//! - `{"shapes": {"items": [{"id", "shape", "w", "h", …}]}}` → `{"ok": true, "paths": {id: {"d", …path look}}}`: each
//!   parametric shape as the path it is drawn as (scene/shape_cmd.rs; Convert to path's source). Needs no scene.

use std::time::Instant;

use serde_json::{json, Value};

use crate::painter::Gl;
use crate::scene::{eval, fonts, stage, Scene};
use crate::serve::{self, Session};

/// The scene the engine holds, and whether the open page is its shell.
#[derive(Default)]
pub struct Held {
    scene: Option<Scene>,
    /// The session's page is the scene shell at this size (an `open` / `page` request clears it).
    pub shell: Option<(u32, u32)>,
}

impl Held {
    pub(crate) fn scene(&self) -> Result<&Scene, String> {
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
        serve::reopen(session, &open, warm)?;
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

pub fn shapes(req: &Value) -> Result<Value, String> {
    crate::scene::shape_cmd::shapes(req)
}

pub fn bones(held: &Held, req: &Value) -> Result<Value, String> {
    let t = req["t"].as_f64().ok_or("bones needs t (seconds)")?;
    Ok(crate::rig::bones(&held.scene()?.comp, t))
}

pub fn outline(held: &Held, req: &Value) -> Result<Value, String> {
    crate::scene::outline_cmd::outline(&held.scene()?.comp, req)
}

/// `place {t, ids}` (place.rs): where those layers are drawn at `t` and their edges, from the page laid out at t (no paint).
pub fn place(held: &Held, s: &mut Session, req: &Value) -> Result<Value, String> {
    let t = req["t"].as_f64().ok_or("place needs t (seconds)")?;
    Ok(json!({ "ok": true, "layers": placed(held, s, t, &req["ids"], true)? }))
}

/// The layers `ids` (a list of layer ids) as the page shows them at `t`: the page is laid out at t first (a no-op
/// after that frame's own layout, but a motion-blurred frame leaves its last sub-frame laid out).
fn placed(held: &Held, s: &mut Session, t: f64, ids: &Value, strict: bool) -> Result<Value, String> {
    let scene = held.scene()?;
    let ids: Vec<&str> = ids.as_array().ok_or("place needs ids (a list of layer ids)")?.iter().map(|v| v.as_str().ok_or("place: ids are layer ids (text)")).collect::<Result<_, _>>()?;
    if held.shell != Some((s.width, s.height)) {
        return Err("the open page is not the scene's (an open or page came after the scene); send the scene again".into());
    }
    let pieces = markup(scene, t, false)?.0;
    let whole = pieces.concat();
    s.next_pieces = Some(pieces);
    serve::apply(s, &whole)?;
    crate::place::places(&s.doc, s.width, s.height, &eval::whole(&scene.comp, t), &ids, strict)
}

/// The stage markup at `t`, one piece per top-level element (restage.rs), and the ms it took.
/// `alpha`: the comp's background left out (an export with transparency).
pub(crate) fn markup(scene: &Scene, t: f64, alpha: bool) -> Result<(Vec<String>, f64), String> {
    let t0 = Instant::now();
    let plan = crate::motion::Plan::of(&scene.comp)?;
    let mut comp = eval::at(&scene.comp, t).expect("the comp always shows");
    plan.apply(&scene.comp, &mut comp);
    if alpha {
        comp.props.insert("background".into(), Value::String("transparent".into()));
    }
    let m = stage::parts(&comp)?;
    Ok((m, t0.elapsed().as_secs_f64() * 1000.0))
}

/// A frame's stage markup, built before it is drawn (scene_export.rs builds the next frames' on another thread):
/// the frame's own pieces (empty when motion-blurred and not drawn: `stage_at`) and, motion-blurred, each sub-frame's
/// (empty when nothing moves while the shutter is open).
pub(crate) struct Staged {
    pub t: f64,
    pieces: Vec<String>,
    samples: Vec<Vec<String>>,
    eval_ms: f64,
}

/// The stage markup of the frame `req` asks for at `t` (keys, easing, motion-blur sub-frames): no page, no paint.
/// A motion-blurred frame's own stage is built only when it is drawn (serve.rs `frame`: `held` paints it over the
/// sum, `boxes` lays it out); otherwise the picture is the sub-frames' sum alone and its stage is left empty.
pub(crate) fn stage_at(scene: &Scene, t: f64, req: &Value) -> Result<Staged, String> {
    let alpha = req["alpha"].as_bool() == Some(true);
    // Motion blur (crate::motion, MOTION.md): the stage at each sub-frame of the open shutter, averaged by serve.rs.
    let (angle, n) = crate::motion::shutter(&scene.comp, req)?;
    let (mut samples, mut eval_ms) = (vec![], 0.0);
    if angle > 0.0 && n > 1 {
        for ts in crate::motion::sample_times(t, scene.fps(), angle, n) {
            let (mk, ms) = crate::scene::eval::shutter_at(t, || markup(scene, ts, alpha))?;
            eval_ms += ms;
            samples.push(mk);
        }
    }
    // Nothing moves while the shutter is open: every sub-frame is the same picture, so their average is that one
    // picture, drawn once (the same pixels, within the sum's rounding).
    if samples.windows(2).all(|w| w[0] == w[1]) {
        if let Some(only) = samples.pop() {
            return Ok(Staged { t, pieces: only, samples: vec![], eval_ms });
        }
    }
    let own_drawn = samples.is_empty() || req["held"].as_bool() == Some(true) || req["boxes"].as_bool() == Some(true);
    let pieces = if own_drawn {
        let (pieces, ms) = markup(scene, t, alpha)?;
        eval_ms += ms;
        pieces
    } else {
        vec![]
    };
    Ok(Staged { t, pieces, samples, eval_ms })
}

/// `frame` with `t`: the request with the scene's stage at t filled in, drawn by serve.rs `frame`.
pub fn frame(held: &Held, s: &mut Session, req: &Value) -> Result<(Value, Option<Vec<u8>>), String> {
    let t = req["t"].as_f64().ok_or("frame needs t (seconds) or stage")?;
    let staged = stage_at(held.scene()?, t, req)?;
    draw(held, s, req, staged)
}

/// Draws a frame from its built stage (serve.rs `frame`): the one path stills, the canvas and exports take.
pub(crate) fn draw(held: &Held, s: &mut Session, req: &Value, staged: Staged) -> Result<(Value, Option<Vec<u8>>), String> {
    let scene = held.scene()?;
    if held.shell != Some((s.width, s.height)) {
        return Err("the open page is not the scene's (an open or page came after the scene); send the scene again".into());
    }
    let Staged { t, pieces, samples, eval_ms } = staged;
    let mut f = req.clone();
    if let Some(o) = f.as_object_mut() {
        o.remove("alpha");
        o.remove("shutter");
        o.remove("shutterSamples");
    }
    f["stage"] = Value::String(pieces.concat());
    if !samples.is_empty() {
        f["samples"] = Value::Array(samples.iter().map(|p| Value::String(p.concat())).collect());
    }
    if f.get("index").is_none() {
        f["index"] = json!((t * scene.fps()).round() as u64);
    }
    s.next_pieces = Some(pieces);              // for the frame's own stage (serve.rs `apply`, restage.rs)
    s.sample_pieces = samples;                 // each sub-frame staged by its changed pieces too
    let (mut reply, px) = serve::frame(s, &f)?;
    if let Some(timing) = reply.get_mut("timing") {
        timing["evalMs"] = json!(eval_ms);
    }
    if !req["place"].is_null() {
        reply["place"] = placed(held, s, t, &req["place"], false)?;
    }
    Ok((reply, px))
}
