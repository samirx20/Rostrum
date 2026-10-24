//! The world picture (camera spec § 8.4, FRAME.md › The world view): `frame {t, pixels: true, world: {x, y, w, h,
//! scale}}` draws the world rectangle x..x+w, y..y+h (world px, anywhere on the endless canvas) at `scale`, the
//! canvas's picture outside Look through. Layers are placed by the world view's maths (§ 8.3, frame/mod.rs `map`), so
//! page px are world px; what lies wholly outside the rectangle is not drawn (blitz-paint `set_viewport`). The frame's
//! quad is filled with the export's own picture of the same time (whole-picture effects, motion blur), drawn in a
//! second set of surfaces (painter.rs `swap_aside`) and laid in, so the inside of the outline is the export.
//! The reply is a `pixels` frame's, with `quad`: the frame's corners in world px (top-left, top-right, bottom-right,
//! bottom-left) and `pass`: how it was drawn ("world", "export" or "both").
//!
//! Three ways, cheapest first, the same pixels: a frame at home and not blurred is the world page alone (inside the
//! frame it equals the export); a rectangle inside an upright frame is the export's crop alone (the `view` crop);
//! else both. Writes nothing to the comp cache beyond what any frame does.

use std::time::Instant;

use serde_json::{json, Value};

use crate::rig::math::{Aff, Pt};
use crate::scene::{eval, stage, Scene};
use crate::scene_serve::{self, Held, Staged};
use crate::serve::Session;

type R<T> = Result<T, String>;

/// The largest picture side and scale (as `view`, serve.rs).
const MOST_PX: f64 = 8192.0;
const MOST_SCALE: f64 = 64.0;

struct Rect {
    x: f64,
    y: f64,
    w: f64,
    h: f64,
    k: f64,
}

impl Rect {
    fn parse(v: &Value) -> R<Rect> {
        let n = |f: &str| v[f].as_f64().filter(|x| x.is_finite()).ok_or_else(|| format!("world needs x, y, w, h, scale (numbers); {f} is {}", v[f]));
        let r = Rect { x: n("x")?, y: n("y")?, w: n("w")?, h: n("h")?, k: n("scale")? };
        if r.w <= 0.0 || r.h <= 0.0 || !(r.k > 0.0 && r.k <= MOST_SCALE) || (r.w * r.k).round() > MOST_PX || (r.h * r.k).round() > MOST_PX {
            return Err(format!("world {} × {} at scale {}: the size is above 0, the scale above 0 and at most {MOST_SCALE}, the picture at most {MOST_PX} px a side", r.w, r.h, r.k));
        }
        Ok(r)
    }

    /// A world point in the picture's device px.
    fn dev(&self, p: Pt) -> Pt {
        ((p.0 - self.x) * self.k, (p.1 - self.y) * self.k)
    }

    fn corners(&self) -> [Pt; 4] {
        [(self.x, self.y), (self.x + self.w, self.y), (self.x + self.w, self.y + self.h), (self.x, self.y + self.h)]
    }

    fn json(&self) -> Value {
        json!({ "x": self.x, "y": self.y, "w": self.w, "h": self.h, "scale": self.k })
    }
}

/// The frame at t: whether it is at home, output px → world px (plain frame), and its quad in world px.
struct Lens {
    home: bool,
    to_world: Aff,
    quad: [Pt; 4],
}

fn lens(scene: &Scene, t: f64) -> R<Lens> {
    let comp = eval::at(&scene.comp, t).expect("the comp always shows");
    let view = crate::frame::View::of(&comp)?;
    let (w, h) = (scene.width() as f64, scene.height() as f64);
    let to_world = view.out_to_world();
    let quad = [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)].map(|p| to_world.apply(p));
    Ok(Lens { home: view.at_home(), to_world, quad })
}

/// The world view's stage pieces at t (as scene_serve `markup`, through the world maths), the background over `r`.
fn pieces(scene: &Scene, t: f64, r: &Rect) -> R<Vec<String>> {
    let plan = crate::motion::Plan::of(&scene.comp)?;
    let mut comp = eval::at(&scene.comp, t).expect("the comp always shows");
    plan.apply(&scene.comp, &mut comp);
    stage::world_parts(&comp, [r.x, r.y, r.w, r.h])
}

/// Whether `p` is inside the convex polygon `q` (either winding).
fn inside(q: &[Pt; 4], p: Pt) -> bool {
    let side = |a: Pt, b: Pt| (b.0 - a.0) * (p.1 - a.1) - (b.1 - a.1) * (p.0 - a.0);
    let s: Vec<f64> = (0..4).map(|i| side(q[i], q[(i + 1) % 4])).collect();
    s.iter().all(|v| *v >= -1e-9) || s.iter().all(|v| *v <= 1e-9)
}

fn bbox(ps: &[Pt]) -> (f64, f64, f64, f64) {
    ps.iter().fold((f64::MAX, f64::MAX, f64::MIN, f64::MIN), |b, p| (b.0.min(p.0), b.1.min(p.1), b.2.max(p.0), b.3.max(p.1)))
}

fn path(ps: &[Pt]) -> skia_safe::Path {
    let pts: Vec<skia_safe::Point> = ps.iter().map(|p| skia_safe::Point::new(p.0 as f32, p.1 as f32)).collect();
    skia_safe::Path::polygon(&pts, true, None, None)
}

fn matrix(m: Aff) -> skia_safe::Matrix {
    skia_safe::Matrix::new_all(m.a as f32, m.c as f32, m.e as f32, m.b as f32, m.d as f32, m.f as f32, 0.0, 0.0, 1.0)
}

/// The request as forwarded to a frame: without what this file answers itself.
fn forward(req: &Value) -> Value {
    let mut f = req.clone();
    if let Some(o) = f.as_object_mut() {
        for k in ["world", "place", "boxes"] {
            o.remove(k);
        }
    }
    f
}

pub fn world(held: &Held, s: &mut Session, req: &Value) -> R<(Value, Option<Vec<u8>>)> {
    let scene = held.scene()?;
    let t = req["t"].as_f64().ok_or("frame needs t (seconds)")?;
    let r = Rect::parse(&req["world"])?;
    let lens = lens(scene, t)?;
    let (angle, n) = crate::motion::shutter(&scene.comp, req)?;
    let blurred = angle > 0.0 && n > 1;
    let (w, h) = (scene.width() as f64, scene.height() as f64);
    let zoom = 1.0 / (lens.to_world.a.hypot(lens.to_world.b));
    let upright = lens.to_world.b.abs() < 1e-9 && lens.to_world.c.abs() < 1e-9;
    let from_world = lens.to_world.inverse().ok_or("the frame's zoom must be above 0")?;
    let all_in = r.corners().iter().all(|p| inside(&lens.quad, *p));
    let (qx0, qy0, qx1, qy1) = bbox(&lens.quad);
    let meets = qx0 < r.x + r.w && qx1 > r.x && qy0 < r.y + r.h && qy1 > r.y;
    let mut f = forward(req);
    let t0 = Instant::now();
    let (mut reply, px, pass) = if all_in && upright && r.k / zoom <= MOST_SCALE {
        // Inside an upright frame: the export's own crop is the picture (its size is the world picture's).
        let o = r.corners().map(|p| from_world.apply(p));
        let (x0, y0, x1, y1) = bbox(&o);
        let (x0, y0, x1, y1) = (x0.max(0.0), y0.max(0.0), x1.min(w), y1.min(h));
        f["view"] = json!({ "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "scale": r.k / zoom });
        let (reply, px) = scene_serve::frame(held, s, &f)?;
        (reply, px, "export")
    } else {
        let mut over = None;
        if !(lens.home && !blurred) && meets {
            over = Some(export_into_quad(held, s, &f, &r, &lens, zoom, upright, (w, h))?);
        }
        f.as_object_mut().map(|o| o.remove("shutter"));
        f["pageView"] = r.json();
        let staged = Staged::of(t, pieces(scene, t, &r)?);
        let quad_dev = path(&lens.quad.map(|p| r.dev(p)));
        let pass = if over.is_some() { "both" } else { "world" };
        if let Some((image, m)) = over {
            s.painter.clip_out = Some(quad_dev.clone());
            s.over = Some((image, m, quad_dev));
        }
        blitz_paint::set_viewport(Some(kurbo::Rect::new(r.x, r.y, r.x + r.w, r.y + r.h)));
        let drawn = scene_serve::draw(held, s, &f, staged);
        blitz_paint::set_viewport(None);
        s.painter.clip_out = None;
        s.over = None;
        let (reply, px) = drawn?;
        (reply, px, pass)
    };
    reply["world"] = r.json();
    reply["quad"] = json!(lens.quad.map(|p| [p.0, p.1]));
    reply["pass"] = json!(pass);
    if let Some(timing) = reply.get_mut("timing") {
        timing["worldMs"] = json!(t0.elapsed().as_secs_f64() * 1000.0);
    }
    if req["boxes"].as_bool() == Some(true) {
        let page = if pass == "export" { lens.to_world } else { Aff::ID };
        reply["boxes"] = crate::boxes::in_world(&s.doc, s.width, s.height, page);
    }
    if !req["place"].is_null() {
        reply["place"] = scene_serve::placed_world(held, s, t, &req["place"], [r.x, r.y, r.w, r.h])?;
    }
    Ok((reply, px))
}

/// The export at t drawn in the second set of surfaces, cropped to the part of the frame the rectangle shows and at
/// the size shown: (the picture, its px → the world picture's device px). Upright, the crop starts on a whole device
/// px, so the picture lands on the world picture's pixels without resampling.
#[allow(clippy::too_many_arguments)]
fn export_into_quad(held: &Held, s: &mut Session, f: &Value, r: &Rect, lens: &Lens, zoom: f64, upright: bool, (w, h): (f64, f64)) -> R<(skia_safe::Image, skia_safe::Matrix)> {
    let from_world = lens.to_world.inverse().ok_or("the frame's zoom must be above 0")?;
    // The part of the frame inside the rectangle, in output px.
    let (qx0, qy0, qx1, qy1) = bbox(&lens.quad);
    let seen = [(qx0.max(r.x), qy0.max(r.y)), (qx1.min(r.x + r.w), qy0.max(r.y)), (qx1.min(r.x + r.w), qy1.min(r.y + r.h)), (qx0.max(r.x), qy1.min(r.y + r.h))];
    let (mut x0, mut y0, mut x1, mut y1) = bbox(&seen.map(|p| from_world.apply(p)));
    let ke = (r.k / zoom).min(MOST_SCALE);
    if upright {
        // device = c + q·ke: whole device px at both ends.
        let c = r.dev(lens.to_world.apply((0.0, 0.0)));
        x0 = (((c.0 + x0 * ke).floor()) - c.0) / ke;
        y0 = (((c.1 + y0 * ke).floor()) - c.1) / ke;
        x1 = (((c.0 + x1 * ke).ceil()) - c.0) / ke;
        y1 = (((c.1 + y1 * ke).ceil()) - c.1) / ke;
    }
    let (x0, y0, x1, y1) = (x0.max(0.0), y0.max(0.0), x1.min(w), y1.min(h));
    let ke = ke.min(MOST_PX / (x1 - x0).max(y1 - y0).max(1e-6));
    let mut e = f.clone();
    e["view"] = json!({ "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "scale": ke });
    e["noRead"] = json!(true);
    s.painter.swap_aside()?;
    let drawn = scene_serve::frame(held, s, &e);
    let image = s.painter.last_image();
    s.painter.swap_aside()?;
    drawn?;
    // image px → output px → world px → device px.
    let m = Aff::scale(r.k, r.k) * Aff::translate(-r.x, -r.y) * lens.to_world * Aff::translate(x0, y0) * Aff::scale(1.0 / ke, 1.0 / ke);
    Ok((image, matrix(m)))
}

/// The world picture's request on the canvas (serve.rs dispatch): a `frame` with `t` and `world`.
pub fn wants(f: &Value) -> bool {
    f.get("world").is_some_and(|w| !w.is_null()) && f.get("t").is_some()
}

/// Output px → world px at t (the plain frame): where the world view draws what the export shows (export boxes'
/// `world`, scene_serve.rs).
pub(crate) fn to_world(scene: &Scene, t: f64) -> R<Aff> {
    Ok(lens(scene, t)?.to_world)
}
