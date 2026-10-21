//! The 2D camera (apps/2d/CAMERA.md): a `camera` layer in a comp's own layers, not drawn. The one showing at t (the
//! last showing one in the list, so the one higher in the stack wins) moves, zooms and rolls every top-level layer
//! by its `depth`; `screenLock` layers stay put. Each top-level layer is wrapped in one div with one 2D matrix
//! (stage.rs calls `place`), always when the comp has a camera so the page keeps its shape (keep.rs), never when not.
//! `check` refuses a broken camera when the scene loads or is edited.

use crate::rig::math::Aff;
use crate::scene::eval::Item;
use crate::scene::fields::Field;
use crate::scene::fields::Kind::Number;
use crate::scene::{KeyValue, Node};

pub const FIELDS: &[Field] = &[("x", Number), ("y", Number), ("zoom", Number), ("rotation", Number), ("start", Number), ("end", Number)];

type R<T> = Result<T, String>;

/// The camera showing in a comp at its time. `lens` None: the comp has no camera (markup left exactly as it was).
pub struct View {
    lens: Option<Lens>,
}

struct Lens {
    /// The comp's centre: a camera looking at it, zoom 1, roll 0 shows every layer as placed.
    centre: (f64, f64),
    /// (x, y, zoom, roll) of the camera showing; None between cameras (layers as placed).
    shot: Option<(f64, f64, f64, f64)>,
}

impl View {
    /// Refuses a zoom at or below 0 or a depth at or below −1 at this time (keys whose ease swings past a limit).
    pub fn of(comp: &Item) -> R<View> {
        if !comp.node.layers.iter().any(|l| l.kind == "camera") {
            return Ok(View { lens: None });
        }
        let t = comp.t;
        let showing = |l: &&Item| l.kind == "camera" && l.num("start") <= t && t < l.num("end");
        let shot = comp.layers.iter().rev().find(showing).map(|c| (c.id, (c.num("x"), c.num("y"), c.num("zoom"), c.num("rotation"))));
        if let Some((id, (_, _, zoom, _))) = shot {
            if !(zoom > 0.0) {
                return Err(format!("{id}.zoom: {zoom} at {t} s; a camera's zoom must be above 0"));
            }
        }
        if let Some(l) = comp.layers.iter().find(|l| l.kind != "camera" && !(l.num("depth") > -1.0)) {
            return Err(format!("{}.depth: {} at {t} s; a depth must be above -1", l.id, l.num("depth")));
        }
        let centre = (comp.num("width") / 2.0, comp.num("height") / 2.0);
        Ok(View { lens: Some(Lens { centre, shot: shot.map(|s| s.1) }) })
    }

    /// Where a top-level layer's comp px land on screen: screen = C + R(−roll)·zoomˢ·(p − C − s·(cam − C)),
    /// s = 1/(1 + depth). The identity with no camera showing, for a screen-locked layer, or a camera at rest.
    pub fn map(&self, layer: &Item) -> Aff {
        let Some(Lens { centre: (cx, cy), shot: Some((x, y, zoom, roll)) }) = self.lens else { return Aff::ID };
        if layer.on("screenLock") {
            return Aff::ID;
        }
        let s = 1.0 / (1.0 + layer.num("depth"));
        let z = zoom.powf(s);
        Aff::translate(cx, cy) * Aff::rotate(-roll) * Aff::scale(z, z) * Aff::translate(-(cx + s * (x - cx)), -(cy + s * (y - cy)))
    }

    /// One top-level layer's markup, seen through the camera. The wrapper carries the layer's blend so the layer
    /// still blends with the layers under it (a transformed div holds what is inside it apart).
    pub fn place(&self, layer: &Item, markup: String) -> String {
        if self.lens.is_none() {
            return markup;
        }
        let m = self.map(layer);
        let blend = crate::scene::blends::style(layer.str("blend"));
        format!(
            "<div id=\"cam~{}\" style=\"position:absolute;left:0;top:0;width:100%;height:100%;transform-origin:0 0;transform:matrix({:.6}, {:.6}, {:.6}, {:.6}, {:.3}, {:.3});{blend}\">{markup}</div>",
            escape(layer.id), m.a, m.b, m.c, m.d, m.e, m.f
        )
    }
}

/// Every camera in the scene, when it loads or is edited: only in the comp's own layers, no effects or masks, a zoom
/// above 0 (still and every key); every top-level layer's depth above −1.
pub fn check(comp: &Node) -> R<()> {
    for l in &comp.layers {
        if l.kind == "camera" {
            if let Some(x) = l.effects.first().or(l.masks.first()) {
                return Err(format!("{}: a camera holds no effects or masks ({} is a {})", l.id, x.id, x.kind));
            }
            if let Some(z) = values(l, "zoom").find(|z| !(*z > 0.0)) {
                return Err(format!("{}.zoom: {z} is not above 0 (a camera's zoom must be above 0)", l.id));
            }
        } else if let Some(d) = values(l, "depth").find(|d| !(*d > -1.0)) {
            return Err(format!("{}.depth: {d} is not above -1", l.id));
        }
        l.layers.iter().try_for_each(nested)?;
    }
    Ok(())
}

fn nested(n: &Node) -> R<()> {
    if n.kind == "camera" {
        return Err(format!("{}: a camera goes in a composition's own layers, not inside a group or rig", n.id));
    }
    n.layers.iter().try_for_each(nested)
}

/// A number field's still value and every key's value.
fn values<'a>(n: &'a Node, f: &'a str) -> impl Iterator<Item = f64> + 'a {
    let keys = n.anim.iter().filter(move |(p, _)| p == f).flat_map(|(_, ks)| ks.iter());
    std::iter::once(n.props[f].as_f64().unwrap_or(f64::NAN)).chain(keys.filter_map(|k| match k.value {
        KeyValue::Number(v) => Some(v),
        KeyValue::Color(..) | KeyValue::Path(..) => None,
    }))
}

/// As stage.rs `escape` (Python's `html.escape`).
fn escape(s: &str) -> String {
    s.chars()
        .map(|c| match c {
            '&' => "&amp;".to_string(),
            '<' => "&lt;".to_string(),
            '>' => "&gt;".to_string(),
            '"' => "&quot;".to_string(),
            '\'' => "&#x27;".to_string(),
            c => c.to_string(),
        })
        .collect()
}
