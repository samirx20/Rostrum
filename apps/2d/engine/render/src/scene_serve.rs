//! serve's scene requests (ENGINE_CONTRACT.md § 1): the engine holds the scene and evaluates every frame itself.
//!
//! - `{"scene": {…scene…}, "cpu"?: bool, "depth"?: 8 | 16}` → `{"ok": true, "items": n, "width", "height", "fps", "duration"}`: load or
//!   replace the scene, checked whole (`depth` 16: frames to an encoder are RGBA64LE, else RGBA8; both straight alpha) (scene/mod.rs; every layer's stage is written once, so a frame never meets
//!   something it can't draw). Opens a session the comp's size if none is open at that size.
//! - `{"change": {…scene…}, "cpu"?, "depth"?}` → as `scene`, plus `"kept": n`: a scene where any child may be the id of
//!   an item of the held scene, kept as it is (scene/change.rs); only what is given anew is checked (and staged once).
//!   Both replies carry `timing: {parseMs, checkMs, totalMs}`.
//! - `{"frame": {"t": 1.25, "image"? | "rgba"? | "boxes"? …}}`: the scene at `t` seconds, drawn as any frame is
//!   (serve.rs `frame`; `index` defaults to the frame number round(t·fps), so a still equals the exported frame).
//!   Adds `timing.evalMs` (keys, easing and the stage markup). With the comp's `shutter` > 0 the frame is motion
//!   blurred: `samples` are the stages at sub-frame times centred on t, at least `shutterSamples` and more on fast moves (crate::motion, MOTION.md);
//!   the request's own `shutter` / `shutterSamples` override the comp's (its `shutterSamples` is then the exact count, e.g. 1 for a fast preview).
//! - `{"export": {"start"?, "end"?, "encode": {"program", "args"}, "file"?}}` → `{"ok", "frames", "timing"}`: every
//!   frame from start (default 0) to end (default the comp's duration) at the comp's fps into the encoder; `file`
//!   is checked to exist and not be empty after. Or `"images": "C:\\…\\f-{frame}.png"`: each frame to a picture.
//!   With `"alpha": true` the comp's background is left out, so the frames are transparent where nothing is drawn.
//!   With `"progress": true`, a line `{"progress": i, "of": n, "elapsedS", "leftS"}` after each frame, before the reply.
//!   The reply's `timing` sums where the time went (scene_export.rs); `"timingCsv": path` writes it per frame too.
//!   `"workers": n` (1–4): frames drawn side by side by n drawing workers (export_crew.rs); the same pictures.
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
//! - `{"layout": {"trees": [{"id", "kind": "box" | "text" | "leaf", "style": {…}, "children" | "text" | "w", "h"}, …]}}`
//!   → `{"ok": true, "boxes": [{id: [x, y, w, h]}, …]}`: each tree laid out as CSS flex / grid with its texts wrapped by
//!   the code that draws them, one pass for all; each node's border box in its parent's (scene/layout_cmd.rs). Needs no scene.
//! - `{"shapes": {"items": [{"id", "shape", "w", "h", …}]}}` → `{"ok": true, "paths": {id: {"d", …path look}}}`: each
//!   parametric shape as the path it is drawn as (scene/shape_cmd.rs; Convert to path's source). Needs no scene.

use std::time::Instant;

use serde_json::{json, Value};

use crate::painter::Gl;
use crate::scene::{change::Refs, eval, fonts, stage, Scene};
use crate::serve::{self, Session};

#[cfg(test)]
#[path = "change_tests.rs"]
mod tests;

/// The scene the engine holds, and whether the open page is its shell.
#[derive(Default)]
pub struct Held {
    scene: Option<Scene>,
    /// The session's page is the scene shell at this size (an `open` / `page` request clears it).
    pub shell: Option<(u32, u32)>,
    /// The font families whose faces the shell carries (the scene's texts' fonts).
    faces: Vec<String>,
}

impl Held {
    pub(crate) fn scene(&self) -> Result<&Scene, String> {
        self.scene.as_ref().ok_or_else(|| "no scene loaded (send {\"scene\": …} first)".to_string())
    }
}

/// Every layer's stage written once (showing or not), so what can't be drawn is refused now.
pub(crate) fn check(scene: &Scene) -> Result<(), String> {
    check_part(scene, None)
}

/// `check`, staging only `part` (a comp of some of the scene's layers: scene/change.rs `part`) when given.
fn check_part(scene: &Scene, part: Option<&crate::scene::Node>) -> Result<(), String> {
    scene.comp.walk(&mut |n| match n.kind {
        "text" => fonts::pick(&scene.fonts, n.props["font"].as_str().unwrap_or(""), 400.0, n.props["italic"].as_bool() == Some(true))
            .map(|_| ()).map_err(|e| format!("{}: {e}", n.id)),
        _ => Ok(()),
    })?;
    crate::motion::check(&scene.comp)?;
    stage::stage(&eval::whole(part.unwrap_or(&scene.comp), 0.0)).map(|_| ())
}

/// The page shell of the scene: its size, and the faces of the fonts its texts use (only those are embedded).
pub(crate) fn shell_of(scene: &Scene, w: u32, h: u32) -> Result<String, String> {
    stage::shell(w, h, &fonts::faces_of(&scene.fonts, &fonts::used(&scene.comp)))
}

/// `{"fonts": {}}`: every family a text can name (scene/font_list.rs), the loaded scene's own fonts included.
pub fn font_list(held: &Held) -> Result<Value, String> {
    match held.scene.as_ref() {
        Some(s) => Ok(crate::scene::font_list::list(&s.fonts)),
        None => Ok(crate::scene::font_list::list(&fonts::list(&Value::Null)?)),
    }
}

fn count(n: &crate::scene::Node) -> usize {
    1 + n.effects.iter().chain(&n.masks).chain(&n.layers).chain(&n.rig).map(count).sum::<usize>()
}

fn ms(since: Instant) -> f64 {
    since.elapsed().as_secs_f64() * 1000.0
}

/// `scene`, or `change` (the held scene's items kept where it names them by id): read, checked, then held; all or
/// nothing (a refused load leaves the held scene, and the fonts the stage reads, as they were).
pub fn load(held: &mut Held, session: &mut Option<Session>, warm: &mut Option<Result<Gl, String>>, req: &Value) -> Result<Value, String> {
    let r = load_in(held, session, warm, req);
    if let (Err(_), Some(s)) = (&r, &held.scene) {
        crate::scene::type_font::register(&s.fonts);
    }
    r
}

fn load_in(held: &mut Held, session: &mut Option<Session>, warm: &mut Option<Result<Gl, String>>, req: &Value) -> Result<Value, String> {
    let t0 = Instant::now();
    let deep = match req["depth"].as_u64() {
        None | Some(8) => false,
        Some(16) => true,
        Some(d) => return Err(format!("depth is 8 or 16; got {d}")),
    };
    let (scene, kept, parse_ms, check_ms) = read(held, req)?;
    let (w, h) = (scene.width(), scene.height());
    let same = session.as_ref().is_some_and(|s| (s.width, s.height, s.deep) == (w, h, deep));
    let faces = fonts::used(&scene.comp);
    if !same {
        let open = json!({ "width": w, "height": h, "html": shell_of(&scene, w, h)?, "cpu": req["cpu"].as_bool() == Some(true), "depth": if deep { 16 } else { 8 } });
        serve::reopen(session, &open, warm)?;
    } else if held.shell != Some((w, h)) || held.faces != faces {
        serve::page(session.as_mut().unwrap(), &json!({ "html": shell_of(&scene, w, h)? }))?;
    }
    held.shell = Some((w, h));
    let mut reply = json!({ "ok": true, "items": count(&scene.comp), "width": w, "height": h, "fps": scene.fps(), "duration": scene.duration(), "fonts": faces });
    if let Some(n) = kept {
        reply["kept"] = json!(n);
    }
    serve::with_painting(&mut reply, &session.as_ref().unwrap().painting);
    held.faces = faces;
    held.scene = Some(scene);
    reply["timing"] = json!({ "parseMs": parse_ms, "checkMs": check_ms, "totalMs": ms(t0) });
    Ok(reply)
}

/// The scene a `scene` or `change` request gives, checked; with a change, how many items it kept.
fn read(held: &Held, req: &Value) -> Result<(Scene, Option<usize>, f64, f64), String> {
    let t0 = Instant::now();
    let (v, change) = match req.get("change") {
        Some(v) => (v, Some(held.scene().map_err(|_| "change: no scene is held (send {\"scene\": …} first)".to_string())?)),
        None => (&req["scene"], None),
    };
    let mut refs = change.map_or_else(Refs::none, Refs::of);
    let scene = Scene::read(v, &mut refs, held.scene.as_ref())?;
    let parse_ms = ms(t0);
    let t1 = Instant::now();
    let part = change.and_then(|h| crate::scene::change::part(&scene, h, &crate::scene::change::kept_top(v)));
    check_part(&scene, part.as_ref())?;
    Ok((scene, change.map(|_| refs.kept), parse_ms, ms(t1)))
}

/// An edit; one that changes which fonts the texts use puts the page shell up again with those fonts' faces.
pub fn edit(held: &mut Held, session: &mut Option<Session>, edits: &Value) -> Result<Value, String> {
    let mut next = held.scene()?.clone();
    let n = next.edit(edits)?;
    check(&next)?;
    let faces = fonts::used(&next.comp);
    if faces != held.faces {
        if let (Some(s), Some((w, h))) = (session.as_mut(), held.shell) {
            serve::page(s, &json!({ "html": shell_of(&next, w, h)? }))?;
        }
        held.faces = faces;
    }
    held.scene = Some(next);
    Ok(json!({ "ok": true, "edits": n }))
}

pub fn measure(held: &Held, req: &Value) -> Result<Value, String> {
    crate::scene::measure::measure(req, held.scene.as_ref().map(|s| s.fonts.as_slice()))
}

pub fn layout(held: &Held, req: &Value) -> Result<Value, String> {
    crate::scene::layout_cmd::layout(req, held.scene.as_ref().map(|s| s.fonts.as_slice()))
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
    if let Some(w) = req.get("world").filter(|w| w.is_object()) {
        let n = |f: &str| w[f].as_f64().ok_or_else(|| format!("place world needs x, y, w, h; {f} is {}", w[f]));
        return Ok(json!({ "ok": true, "layers": placed_world(held, s, t, &req["ids"], [n("x")?, n("y")?, n("w")?, n("h")?])? }));
    }
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
    markup_seen(scene, t, None, alpha)
}

/// `markup`, the frame (camera) taken at `frame_at` when given: the layers as at `t`, seen through the frame as it
/// is at that other time (its move, zoom and roll; its focus stays as at `t`). A grouped motion-blur sub-frame
/// (crate::motion `sub_frames_grouped`), called inside `eval::shutter_at` for `t`.
fn markup_seen(scene: &Scene, t: f64, frame_at: Option<(f64, f64)>, alpha: bool) -> Result<(Vec<String>, f64), String> {
    let t0 = Instant::now();
    let plan = crate::motion::Plan::of(&scene.comp)?;
    let mut comp = eval::at(&scene.comp, t).expect("the comp always shows");
    if let Some((centre, at)) = frame_at {
        let moved = eval::shutter_at(centre, at, || eval::at(&scene.comp, at));
        let cam = moved.and_then(|m| m.layers.into_iter().find(|l| l.kind == "camera"));
        if let (Some(mut cam), Some(own)) = (cam, comp.layers.iter_mut().find(|l| l.kind == "camera")) {
            for f in ["dof", "focus", "focusBlur"] {
                match own.props.get(f) {
                    Some(v) => cam.props.insert(f.into(), v.clone()),
                    None => cam.props.remove(f),
                };
            }
            *own = cam;
        }
    }
    plan.apply(&scene.comp, &mut comp);
    if alpha {
        comp.props.insert("background".into(), Value::String("transparent".into()));
    }
    let m = stage::parts(&comp)?;
    Ok((m, t0.elapsed().as_secs_f64() * 1000.0))
}

/// The comp evaluated at `t` with its motion effects (crate::motion `Plan`), and its stage pieces.
fn content<'a>(scene: &'a Scene, plan: &'a crate::motion::Plan, t: f64, alpha: bool) -> Result<(eval::Item<'a>, Vec<String>), String> {
    let mut comp = eval::at(&scene.comp, t).expect("the comp always shows");
    plan.apply(&scene.comp, &mut comp);
    if alpha {
        comp.props.insert("background".into(), Value::String("transparent".into()));
    }
    let pieces = stage::parts(&comp)?;
    Ok((comp, pieces))
}

/// `pieces` (`comp`'s stage) seen through the frame as it is at sub-frame `at` of the frame at `centre`, its focus
/// kept: each top-level wrapper's matrix written anew (what `markup_seen` writes, without staging every layer again).
/// None when a piece holds more than one wrapper or names no top-level layer; `comp` is left as it was.
fn reframed<'a>(scene: &'a Scene, comp: &mut eval::Item<'a>, pieces: &[String], centre: f64, at: f64) -> Option<Vec<String>> {
    let moved = eval::shutter_at(centre, at, || eval::at(&scene.comp, at))?;
    let mut cam = moved.layers.into_iter().find(|l| l.kind == "camera")?;
    let slot = comp.layers.iter().position(|l| l.kind == "camera")?;
    for f in ["dof", "focus", "focusBlur"] {
        match comp.layers[slot].props.get(f) {
            Some(v) => cam.props.insert(f.into(), v.clone()),
            None => cam.props.remove(f),
        };
    }
    let kept = std::mem::replace(&mut comp.layers[slot], cam);
    let out = (|| {
        let view = crate::frame::View::of(comp).ok()?;
        pieces.iter().map(|p| match p.starts_with("<div id=\"cam~") {
            false => Some(p.clone()),
            true => {
                let id = crate::still_runs::wrapper_id(p)?;
                let layer = comp.layers.iter().find(|l| l.id == id && l.kind != "camera")?;
                crate::still_runs::with_matrix(p, &view.matrix_of(layer)?)
            }
        }).collect::<Option<Vec<String>>>()
    })();
    comp.layers[slot] = kept;
    out
}

/// A frame's stage markup, built before it is drawn (scene_export.rs builds the next frames' on another thread):
/// the frame's own pieces (empty when motion-blurred and not drawn: `stage_at`) and, motion-blurred, each sub-frame's
/// (empty when nothing moves while the shutter is open).
pub(crate) struct Staged {
    pub t: f64,
    pieces: Vec<String>,
    samples: Vec<Vec<String>>,
    /// Grouped sub-frames (crate::motion `sub_frames_grouped`): each sample's group's middle sample, whose stage has the
    /// same layers, only the frame elsewhere. Empty when not grouped.
    bases: Vec<usize>,
    eval_ms: f64,
}

impl Staged {
    /// What the frame's picture is made from, as a 128-bit hash of its stage, motion-blur samples and their grouping: a
    /// frame is a function of these alone (its time enters only through them: keys, grain's frame, a video's picture),
    /// so two frames with the same print are the same picture (export_crew.rs repeats it).
    pub(crate) fn print(&self) -> u128 {
        use std::hash::{Hash, Hasher};
        let half = |salt: u8| {
            let mut h = std::collections::hash_map::DefaultHasher::new();
            salt.hash(&mut h);
            (&self.pieces, &self.samples, &self.bases).hash(&mut h);
            h.finish() as u128
        };
        half(0) << 64 | half(1)
    }

    /// A frame's own pieces, not motion-blurred (the world picture's page, scene_world.rs).
    pub(crate) fn of(t: f64, pieces: Vec<String>) -> Staged {
        Staged { t, pieces, samples: vec![], bases: vec![], eval_ms: 0.0 }
    }

    /// Tests: each motion-blur sub-frame's stage pieces.
    #[cfg(test)]
    pub(crate) fn sample_pieces(&self) -> &[Vec<String>] {
        &self.samples
    }
}

/// `place` in world px (`place {…, world: {x, y, w, h}}` or a world picture's `place`): the layers as the world view
/// draws them at t (scene_world.rs), from the world page laid out at t.
pub(crate) fn placed_world(held: &Held, s: &mut Session, t: f64, ids: &Value, rect: [f64; 4]) -> Result<Value, String> {
    let scene = held.scene()?;
    let ids: Vec<&str> = ids.as_array().ok_or("place needs ids (a list of layer ids)")?.iter().map(|v| v.as_str().ok_or("place: ids are layer ids (text)")).collect::<Result<_, _>>()?;
    if held.shell != Some((s.width, s.height)) {
        return Err("the open page is not the scene's (an open or page came after the scene); send the scene again".into());
    }
    let plan = crate::motion::Plan::of(&scene.comp)?;
    let mut comp = eval::at(&scene.comp, t).expect("the comp always shows");
    plan.apply(&scene.comp, &mut comp);
    let pieces = stage::world_parts(&comp, rect)?;
    let whole = pieces.concat();
    s.next_pieces = Some(pieces);
    serve::apply(s, &whole)?;
    crate::place::places(&s.doc, s.width, s.height, &eval::whole(&scene.comp, t), &ids, false)
}

/// The stage markup of the frame `req` asks for at `t` (keys, easing, motion-blur sub-frames): no page, no paint.
/// A motion-blurred frame's own stage is built only when it is drawn (serve.rs `frame`: `held` paints it over the
/// sum, `boxes` lays it out); otherwise the picture is the sub-frames' sum alone and its stage is left empty.
pub(crate) fn stage_at(scene: &Scene, t: f64, req: &Value) -> Result<Staged, String> {
    let alpha = req["alpha"].as_bool() == Some(true);
    // Motion blur (crate::motion, MOTION.md): the stage at each sub-frame of the open shutter (as many as the motion on
    // screen needs), averaged by serve.rs.
    // Grouped (the frame moves faster than the layers): within a group the layers are as at its middle sub-frame and
    // only the frame moves, so serve.rs draws each layer once per group and moves its picture.
    let (mut samples, mut eval_ms) = (vec![], 0.0);
    let (times, groups) = crate::motion::sub_frames_grouped(&scene.comp, req, t)?;
    let n = times.len();
    let grouped = groups >= 1 && groups * 2 <= n;
    let mut bases = vec![];
    if grouped {
        let plan = crate::motion::Plan::of(&scene.comp)?;
        for g in 0..groups {
            let (lo, hi) = ((g * n).div_ceil(groups), ((g + 1) * n).div_ceil(groups));
            let base = (lo + hi) / 2;
            let tc = times[base];
            let t0 = Instant::now();
            let (mut comp, own) = crate::scene::eval::shutter_at(t, tc, || content(scene, &plan, tc, alpha))?;
            eval_ms += ms(t0);
            for (j, &ts) in times.iter().enumerate().take(hi).skip(lo) {
                bases.push(base);
                if j == base {
                    samples.push(own.clone());
                    continue;
                }
                // The group's stage with each wrapper's frame matrix written anew; staged whole where that can't be.
                let t0 = Instant::now();
                let mk = match reframed(scene, &mut comp, &own, t, ts) {
                    Some(mk) => mk,
                    None => crate::scene::eval::shutter_at(t, tc, || markup_seen(scene, tc, Some((t, ts)), alpha))?.0,
                };
                eval_ms += ms(t0);
                samples.push(mk);
            }
        }
    } else if !times.is_empty() {
        // Each sub-frame's stage and comp; then the layers that barely move while the shutter is open are drawn as at the
        // frame's own time in every one (motion/hold.rs), so still_runs.rs paints them once.
        let t0 = Instant::now();
        let plan = crate::motion::Plan::of(&scene.comp)?;
        let (centre, centre_pieces) = crate::scene::eval::shutter_at(t, t, || content(scene, &plan, t, alpha))?;
        let mut items = Vec::with_capacity(n);
        for &ts in &times {
            let (comp, mk) = crate::scene::eval::shutter_at(t, ts, || content(scene, &plan, ts, alpha))?;
            items.push(comp);
            samples.push(mk);
        }
        crate::motion::hold_still(&centre, &centre_pieces, &items, &mut samples);
        eval_ms += ms(t0);
    }
    // Nothing moves while the shutter is open: every sub-frame is the same picture, so their average is that one
    // picture, drawn once (the same pixels, within the sum's rounding).
    if samples.windows(2).all(|w| w[0] == w[1]) {
        if let Some(only) = samples.pop() {
            return Ok(Staged { t, pieces: only, samples: vec![], bases: vec![], eval_ms });
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
    Ok(Staged { t, pieces, samples, bases, eval_ms })
}

/// `frame` with `t`: the request with the scene's stage at t filled in, drawn by serve.rs `frame`.
pub fn frame(held: &Held, s: &mut Session, req: &Value) -> Result<(Value, Option<Vec<u8>>), String> {
    if crate::scene_world::wants(req) {
        return crate::scene_world::world(held, s, req);
    }
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
    let Staged { t, pieces, samples, bases, eval_ms } = staged;
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
    s.sample_bases = bases;                    // grouped sub-frames: each one's group's middle sample
    let (mut reply, px) = serve::frame(s, &f)?;
    if let Some(timing) = reply.get_mut("timing") {
        timing["evalMs"] = json!(eval_ms);
    }
    if !req["place"].is_null() {
        reply["place"] = placed(held, s, t, &req["place"], false)?;
    }
    if reply["boxes"].is_array() && req.get("pageView").is_none() {
        crate::boxes::add_world(&mut reply["boxes"], crate::scene_world::to_world(scene, t)?);
    }
    Ok((reply, px))
}
