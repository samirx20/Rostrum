//! Where layers are drawn and the edge their paint stays inside (`place`, scene_serve.rs; ENGINE_CONTRACT.md § 1):
//! from the laid-out page the frame paints (boxes.rs `places`: the walk the painter makes, through parent groups, the
//! camera and 3D tilt), never from a second copy of the maths. Each layer: `m`, its own px -> comp px as a 3×3
//! projective matrix (row-major; (x', y', w') = m (x, y, 1), then x'/w', y'/w'), its own box `w` × `h` (the box its
//! paint is stretched over), and `edge`, its true outline in comp px as path data (M / L / Z, flattened): a shape's
//! rounded corners or ellipse, a picture's rounded box, a path's fill and stroke, a text's letters; any other layer
//! its box. The screen draws `edge` while painting and turns the pointer back through `m`; agents' strokes too.

use blitz_dom::BaseDocument;
use kurbo::{BezPath, Cap, Ellipse, Join, PathEl, Point, Rect, RoundedRect, Shape, Stroke, StrokeOpts};
use serde_json::{json, Map, Value};

use crate::scene::eval::Item;

/// How far a flattened edge may stray from the true curve (own px).
const TOLERANCE: f64 = 0.05;

fn find<'b, 'a>(it: &'b Item<'a>, id: &str) -> Option<&'b Item<'a>> {
    if it.id == id {
        return Some(it);
    }
    it.layers.iter().find_map(|c| find(c, id))
}

/// A path layer's edge: its fill, and its stroke's outline (a varied stroke's own outline, stage_path.rs).
fn path_edge(it: &Item) -> Result<BezPath, String> {
    let mut out = BezPath::new();
    let subs = crate::scene::path_data::read(it.id, it.str("d"))?;
    if it.on("filled") {
        subs.iter().for_each(|s| out.extend(s.elements().iter().copied()));
    }
    let w = it.num("strokeWidth");
    if it.on("stroke") && w > 0.0 {
        match crate::scene::stage::outline_d(it)? {
            Some(d) => crate::scene::path_data::read(it.id, &d)?.iter().for_each(|s| out.extend(s.elements().iter().copied())),
            None => {
                let cap = match it.str("cap") { "round" => Cap::Round, "square" => Cap::Square, _ => Cap::Butt };
                let join = match it.str("join") { "round" => Join::Round, "bevel" => Join::Bevel, _ => Join::Miter };
                let style = Stroke::new(w).with_caps(cap).with_join(join).with_miter_limit(it.num("miter").max(1.0));
                for s in &subs {
                    out.extend(kurbo::stroke(s.elements().iter().copied(), &style, &StrokeOpts::default(), TOLERANCE).elements().iter().copied());
                }
            }
        }
    }
    Ok(out)
}

/// The layer's edge in its own px (`w` × `h`: its laid-out box): what its paint is kept inside (stage_paint.rs).
fn own_edge(it: &Item, doc: &BaseDocument, node: blitz_dom::NodeId, w: f64, h: f64) -> Result<BezPath, String> {
    let r = Rect::new(0.0, 0.0, w, h);
    Ok(match it.kind {
        "shape" if it.str("shape") == "ellipse" => Ellipse::from_rect(r).to_path(TOLERANCE),
        "shape" | "image" | "video" => RoundedRect::from_rect(r, it.num("radius").clamp(0.0, w.min(h) / 2.0)).to_path(TOLERANCE),
        "text" => crate::glyphs::outlines(doc, node),
        "path" => path_edge(it)?,
        _ => r.to_path(TOLERANCE),
    })
}

fn project(m: &[f64; 9], p: Point) -> Option<(f64, f64)> {
    let w = m[6] * p.x + m[7] * p.y + m[8];
    (w > 1e-9).then(|| ((m[0] * p.x + m[1] * p.y + m[2]) / w, (m[3] * p.x + m[4] * p.y + m[5]) / w))
}

/// `own` flattened and mapped through `m` to comp px, as path data (a point behind the viewer is left out).
fn to_comp(own: &BezPath, m: &[f64; 9]) -> String {
    let mut d = String::new();
    kurbo::flatten(own.elements().iter().copied(), TOLERANCE, |el| {
        let (c, p) = match el {
            PathEl::MoveTo(p) => ('M', p),
            PathEl::LineTo(p) => ('L', p),
            PathEl::ClosePath => return d.push('Z'),
            _ => return,
        };
        if let Some((x, y)) = project(m, p) {
            d += &format!("{c}{:.1} {:.1}", x, y);
        }
    });
    d
}

/// `{id: {m, w, h, edge}}` for each of `ids` drawn on the laid-out page (`comp`: the scene evaluated at the same t).
/// A layer the frame does not draw (hidden, out of its time, opacity 0, unknown) is an error naming it when `strict`
/// (a `place` request), else left out (a frame's `place`: the frame is still drawn).
pub fn places(doc: &BaseDocument, width: u32, height: u32, comp: &Item, ids: &[&str], strict: bool) -> Result<Value, String> {
    let found = crate::boxes::places(doc, width, height, "id", ids);
    let mut out = Map::new();
    for id in ids {
        let (Some((_, p)), Some(it)) = (found.iter().find(|(l, _)| l == id), find(comp, id)) else {
            if !strict {
                continue;
            }
            return Err(format!("place: \"{id}\" is not drawn at this time (no such layer, hidden, out of its time or fully see-through)"));
        };
        let edge = to_comp(&own_edge(it, doc, p.node, p.w, p.h)?, &p.matrix);
        out.insert(id.to_string(), json!({ "m": p.matrix, "w": p.w, "h": p.h, "edge": edge }));
    }
    Ok(Value::Object(out))
}
