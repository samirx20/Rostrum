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
    let t0 = Instant::now();
    let plan = crate::motion::Plan::of(&scene.comp)?;
    let (_, m) = content(scene, &plan, t, alpha)?;
    Ok((m, t0.elapsed().as_secs_f64() * 1000.0))
}

/// The comp evaluated at `t` with its motion effects (crate::motion `Plan`), and its stage pieces.
fn content<'a>(scene: &'a Scene, plan: &'a crate::motion::Plan, t: f64, alpha: bool) -> Result<(eval::Item<'a>, Vec<String>), String> {
    content_focused(scene, plan, t, alpha, &[])
}

/// `content`, the frame's depth-of-field fields set to `focus` (none: as at `t`).
fn content_focused<'a>(scene: &'a Scene, plan: &'a crate::motion::Plan, t: f64, alpha: bool, focus: &[(&str, Option<Value>)]) -> Result<(eval::Item<'a>, Vec<String>), String> {
    let comp = comp_focused(scene, plan, t, alpha, focus);
    let pieces = stage::parts(&comp)?;
    Ok((comp, pieces))
}

/// The comp evaluated at `t` with its motion effects, the frame's depth-of-field fields set to `focus`: no stage.
fn comp_focused<'a>(scene: &'a Scene, plan: &'a crate::motion::Plan, t: f64, alpha: bool, focus: &[(&str, Option<Value>)]) -> eval::Item<'a> {
    let mut comp = eval::at(&scene.comp, t).expect("the comp always shows");
    if let Some(cam) = comp.layers.iter_mut().find(|l| l.kind == "camera") {
        for (f, v) in focus {
            match v {
                Some(v) => cam.props.insert((*f).into(), v.clone()),
                None => cam.props.remove(*f),
            };
        }
    }
    plan.apply(&scene.comp, &mut comp);
    if alpha {
        comp.props.insert("background".into(), Value::String("transparent".into()));
    }
    comp
}

/// A frame's stage markup, built before it is drawn (scene_export.rs builds the next frames' on another thread):
/// the frame's own pieces (empty when motion-blurred and not drawn: `stage_at`) and, motion-blurred, each sub-frame's
/// (empty when nothing moves while the shutter is open).
pub(crate) struct Staged {
    pub t: f64,
    pieces: Vec<String>,
    samples: Vec<Vec<String>>,
    /// Per piece of the frame's stage: its moves when it is drawn as one streak (motion/streak.rs), else None. Empty
    /// when no piece is.
    streaks: Vec<Option<crate::motion::streak::Streak>>,
    /// The layers staged at every sub-frame (`timing.stagedLayers`): what keeps a blurred frame from one layout.
    staged_ids: Vec<String>,
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
            (&self.pieces, &self.samples).hash(&mut h);
            for st in self.streaks.iter().flatten() {
                for m in &st.moves {
                    m.map(f64::to_bits).hash(&mut h);
                }
            }
            self.streaks.iter().map(Option::is_some).collect::<Vec<_>>().hash(&mut h);
            h.finish() as u128
        };
        half(0) << 64 | half(1)
    }

    /// A frame's own pieces, not motion-blurred (the world picture's page, scene_world.rs).
    pub(crate) fn of(t: f64, pieces: Vec<String>) -> Staged {
        Staged { t, pieces, samples: vec![], streaks: vec![], staged_ids: vec![], eval_ms: 0.0 }
    }

    /// Tests: each motion-blur sub-frame's stage pieces.
    #[cfg(test)]
    pub(crate) fn sample_pieces(&self) -> &[Vec<String>] {
        &self.samples
    }

    /// Tests: each piece's streak moves.
    #[cfg(test)]
    pub(crate) fn streaks(&self) -> &[Option<crate::motion::streak::Streak>] {
        &self.streaks
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
    // Motion blur (crate::motion, MOTION.md): the comp at each sub-frame of the open shutter (as many as the motion on
    // screen needs). A layer that only moves is one streak of its picture at the frame's time (motion/streak.rs); the
    // others are staged per sub-frame and averaged by serve.rs.
    let (mut samples, mut streaks, mut staged_ids, mut eval_ms) = (vec![], vec![], vec![], 0.0);
    let times = crate::motion::sub_frames(&scene.comp, req, t)?;
    let n = times.len();
    if n > 0 {
        // Each sub-frame's comp; then the layers that barely move while the shutter is open are drawn as at the frame's
        // own time in every one (motion/hold.rs), so still_runs.rs paints them once.
        let t0 = Instant::now();
        let plan = crate::motion::Plan::of(&scene.comp)?;
        let (centre, centre_pieces) = crate::scene::eval::shutter_at(t, t, || content(scene, &plan, t, alpha))?;
        // The frame's focus as at the frame's own time in every sub-frame: a rack focus no longer changes each depth
        // layer's blur between sub-frames, so a layer that doesn't move is one piece, painted and blurred once a frame
        // (B1). A focus pull within one shutter opening is a fraction of a px of blur.
        let focus: Vec<(&str, Option<Value>)> = centre.layers.iter().find(|l| l.kind == "camera")
            .map(|c| ["dof", "focus", "focusBlur"].into_iter().map(|f| (f, c.props.get(f).cloned())).collect())
            .unwrap_or_default();
        let eval_at = |ts: f64| crate::scene::eval::shutter_at(t, ts, || Ok::<_, String>(comp_focused(scene, &plan, ts, alpha, &focus)));
        // Where each layer is, at a few sub-frames spread over the shutter (motion/streak.rs `PROBES`); the streaks'
        // moves in between are read off them.
        let probes = crate::motion::streak::probes(n);
        let at_probes = probes.iter().map(|&j| eval_at(times[j])).collect::<Result<Vec<_>, _>>()?;
        let held = req["held"].as_bool() == Some(true);
        let reaches = |p: usize| crate::motion::streak::pad(&centre_pieces[p]);
        let (moves, staged) = if held { (vec![], vec![]) } else { crate::motion::streak::moves(&centre, &at_probes, |p| crate::still_runs::regroups(&centre_pieces[p]), reaches) };
        let moves: Vec<_> = moves.into_iter().map(|m| m.map(|mut m| {
            m.moves = crate::motion::streak::spread(&m.moves, &probes, n);
            m
        })).collect();
        let whole = moves.len() != centre_pieces.len();
        if whole || staged.iter().any(|&s| s) {
            let ids: Vec<&str> = centre.layers.iter().filter(|l| l.kind != "camera" && !crate::scene::matte::used(l, &centre)).map(|l| l.id).collect();
            staged_ids = if whole { vec!["(all)".to_string()] } else { (1..staged.len()).filter(|&p| staged[p]).filter_map(|p| ids.get(p - 1).map(|s| s.to_string())).collect() };
            // As many sub-frames as the staged layers' own moves need (the streaks keep all of theirs).
            let least = crate::motion::shutter(&scene.comp, req)?.1;
            let m = if whole { n } else { crate::motion::streak::own_steps(&at_probes, &staged_ids, least, n) };
            let times: Vec<f64> = crate::motion::streak::pick(m, n).into_iter().map(|j| times[j]).collect();
            let items = times.iter().map(|&ts| eval_at(ts)).collect::<Result<Vec<_>, _>>()?;
            // Staged per sub-frame: every piece when the sub-frames draw different layers, else only those that change.
            for (comp, &ts) in items.iter().zip(&times) {
                let mut mk = crate::scene::eval::shutter_at(t, ts, || stage::parts(comp))?;
                if !whole && mk.len() == centre_pieces.len() {
                    for (p, piece) in mk.iter_mut().enumerate().filter(|(p, _)| !staged[*p]) {
                        piece.clone_from(&centre_pieces[p]);
                    }
                }
                samples.push(mk);
            }
            crate::motion::hold_still(&centre, &centre_pieces, &items, &mut samples);
            if !whole && samples.windows(2).all(|w| w[0] == w[1]) {
                samples.clear();          // what changed stays within a quarter px: drawn as at the frame's time
            }
        }
        if !whole && moves.iter().any(Option::is_some) {
            streaks = moves;
            if samples.is_empty() {
                eval_ms += ms(t0);
                return Ok(Staged { t, pieces: centre_pieces, samples, streaks, staged_ids, eval_ms });
            }
        }
        eval_ms += ms(t0);
    }
    // Nothing moves while the shutter is open: every sub-frame is the same picture, so their average is that one
    // picture, drawn once (the same pixels, within the sum's rounding).
    if streaks.is_empty() && samples.windows(2).all(|w| w[0] == w[1]) {
        if let Some(only) = samples.pop() {
            return Ok(Staged { t, pieces: only, samples: vec![], streaks, staged_ids: vec![], eval_ms });
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
    Ok(Staged { t, pieces, samples, streaks, staged_ids, eval_ms })
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
    let Staged { t, pieces, samples, streaks, staged_ids, eval_ms } = staged;
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
    s.sample_streaks = streaks;                // each piece's streak moves (motion/streak.rs)
    let (mut reply, px) = serve::frame(s, &f)?;
    if let Some(timing) = reply.get_mut("timing") {
        timing["evalMs"] = json!(eval_ms);
        if !staged_ids.is_empty() {
            timing["stagedLayers"] = json!(staged_ids);
        }
    }
    if !req["place"].is_null() {
        reply["place"] = placed(held, s, t, &req["place"], false)?;
    }
    if reply["boxes"].is_array() && req.get("pageView").is_none() {
        crate::boxes::add_world(&mut reply["boxes"], crate::scene_world::to_world(scene, t)?);
    }
    Ok((reply, px))
}
