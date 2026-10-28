//! The frame (apps/2d/FRAME.md): the scene's one `camera` layer, first in the comp's own layers, never drawn. It is
//! what the export shows: it moves, zooms and rolls every top-level layer by its `depth`; `screenLock` layers are
//! pinned to it (in the frame's own px). Each top-level layer is wrapped in one div with one 2D matrix (stage.rs
//! calls `place`) when the frame ever leaves home (decided from the scene, so the page keeps its shape: keep.rs),
//! never otherwise, so a scene whose frame stays home writes byte for byte the page it wrote before frames.
//! `check` refuses a broken frame when the scene loads or is edited.
//! Depth of field (`dof`, `focus`, `focusBlur`): each top-level layer's wrapper also blurs it by how far its depth is
//! from the focus depth, one `filter: blur()` per layer per frame; with it on, every top-level layer is wrapped (at
//! home too), so the page keeps its shape.

use crate::rig::math::Aff;
use crate::scene::eval::Item;
use crate::scene::fields::Field;
use crate::scene::fields::Kind::{Number, Toggle};
use crate::scene::{KeyValue, Node};

pub const FIELDS: &[Field] = &[("x", Number), ("y", Number), ("zoom", Number), ("rotation", Number), ("homeX", Number), ("homeY", Number),
    ("dof", Toggle), ("focus", Number), ("focusBlur", Number)];
/// The frame's fields keys never drive (home is written when the scene is made).
pub const STILL: &[&str] = &["homeX", "homeY"];

type R<T> = Result<T, String>;

/// The frame at a comp's time. `lens` None: it never leaves home (markup left exactly as it was). `world`: the layers
/// are placed for the world view (the canvas outside Look through, `map`), not the export.
pub struct View {
    lens: Option<Lens>,
    world: bool,
    dof: Option<Dof>,
}

/// Depth of field at this time: the focus depth's scale (1 / (1 + focus)) and the blur, in a layer's own px.
struct Dof {
    focus: f64,
    blur: f64,
}

impl Dof {
    /// A layer's blur radius (its own px, so the frame's zoom grows it as it grows the layer): `blur` × |s / s_f − 1|,
    /// s = 1 / (1 + depth): `blur` for a layer far behind the focus (never more), and as much for one twice as near.
    fn radius(&self, depth: f64) -> f64 {
        self.blur * ((1.0 + self.focus) / (1.0 + depth) - 1.0).abs()
    }
}

struct Lens {
    /// O, the output's centre; H, home; F, the frame's centre at this time; its zoom and roll.
    o: (f64, f64),
    home: (f64, f64),
    at: (f64, f64),
    zoom: f64,
    roll: f64,
}

fn num(n: &Node, f: &str) -> f64 {
    n.props[f].as_f64().unwrap_or(f64::NAN)
}

/// Whether the frame ever shows anything but every layer as placed: a key on its move, a ride, a still value away
/// from home, or home away from the output's centre (Python: frame/view.py `leaves_home`).
pub fn leaves_home(frame: &Node, comp: &Node) -> bool {
    let keyed = frame.anim.iter().any(|(f, ks)| matches!(f.as_str(), "x" | "y" | "zoom" | "rotation") && !ks.is_empty());
    let rides = frame.props["ridePath"].as_str().is_some_and(|p| !p.is_empty());
    let moved = (num(frame, "x"), num(frame, "y"), num(frame, "zoom"), num(frame, "rotation")) != (num(frame, "homeX"), num(frame, "homeY"), 1.0, 0.0);
    keyed || rides || moved || (num(frame, "homeX"), num(frame, "homeY")) != (num(comp, "width") / 2.0, num(comp, "height") / 2.0)
}

impl View {
    /// Refuses a zoom at or below 0 or a depth at or below −1 at this time (keys whose ease swings past a limit).
    pub fn of(comp: &Item) -> R<View> {
        let Some(frame) = comp.layers.iter().find(|l| l.kind == "camera") else { return Ok(View { lens: None, world: false, dof: None }) };
        let dof = dof(comp, frame)?;
        if !leaves_home(frame.node, comp.node) {
            return Ok(View { lens: None, world: false, dof });
        }
        let (t, zoom) = (comp.t, frame.num("zoom"));
        if !(zoom > 0.0) {
            return Err(format!("{}.zoom: {zoom} at {t} s; the frame's zoom must be above 0", frame.id));
        }
        if let Some(l) = comp.layers.iter().find(|l| l.kind != "camera" && !(l.num("depth") > -1.0)) {
            return Err(format!("{}.depth: {} at {t} s; a depth must be above -1", l.id, l.num("depth")));
        }
        let lens = Lens {
            o: (comp.num("width") / 2.0, comp.num("height") / 2.0),
            home: (frame.num("homeX"), frame.num("homeY")),
            at: (frame.num("x"), frame.num("y")),
            zoom,
            roll: frame.num("rotation"),
        };
        Ok(View { lens: Some(lens), world: false, dof })
    }

    /// The frame for the world view (`map` gives § 8.3's matrix).
    pub fn world(comp: &Item) -> R<View> {
        Ok(View { world: true, ..View::of(comp)? })
    }

    /// Whether the frame shows every layer as placed at this time (no wrappers; the world view equals the export).
    pub fn at_home(&self) -> bool {
        self.lens.is_none()
    }

    /// Output px → world px through the plain frame (depth 0): world(q) = F + R(roll)·z⁻¹·(q − O). The identity at home.
    pub fn out_to_world(&self) -> Aff {
        let Some(Lens { o: (ox, oy), at: (x, y), zoom, roll, .. }) = self.lens else { return Aff::ID };
        Aff::translate(x, y) * Aff::rotate(roll) * Aff::scale(1.0 / zoom, 1.0 / zoom) * Aff::translate(-ox, -oy)
    }

    /// Where a top-level layer's world px land in the export: out = O + R(−roll)·zoomˢ·(p − H − s·(F − H)),
    /// s = 1/(1 + depth). The identity for a frame that stays home or a pinned (screenLock) layer.
    /// In the world view (spec § 8.3) that point carried back through the plain frame:
    /// world = F + z^(s−1)·(p − H − s·(F − H)); a pinned layer is turned and sized with the frame's box.
    pub fn map(&self, layer: &Item) -> Aff {
        let Some(Lens { o: (ox, oy), home: (hx, hy), at: (x, y), zoom, roll }) = self.lens else { return Aff::ID };
        if layer.on("screenLock") {
            return if self.world { self.out_to_world() } else { Aff::ID };
        }
        let s = 1.0 / (1.0 + layer.num("depth"));
        let z = zoom.powf(s);
        let from = Aff::translate(-(hx + s * (x - hx)), -(hy + s * (y - hy)));
        if self.world {
            let k = z / zoom;
            return Aff::translate(x, y) * Aff::scale(k, k) * from;
        }
        Aff::translate(ox, oy) * Aff::rotate(-roll) * Aff::scale(z, z) * from
    }

    /// The matrix `place` writes on this layer's wrapper (`matrix(…)`); None when the frame never leaves home.
    pub fn matrix_of(&self, layer: &Item) -> Option<String> {
        self.lens.as_ref().map(|_| matrix(&self.map(layer)))
    }

    /// One top-level layer's markup, seen through the frame. The wrapper carries the layer's blend so the layer
    /// still blends with the layers under it (a transformed div holds what is inside it apart).
    pub fn place(&self, layer: &Item, markup: String) -> String {
        if self.lens.is_none() && self.dof.is_none() {
            return markup;
        }
        let blend = crate::scene::blends::style(layer.str("blend"));
        let blur = match &self.dof {
            Some(d) if !layer.on("screenLock") => format!("filter:blur({:.3}px);", d.radius(layer.num("depth"))),
            _ => String::new(),
        };
        let m = if self.lens.is_some() { format!("transform-origin:0 0;transform:{};", matrix(&self.map(layer))) } else { String::new() };
        format!("<div id=\"cam~{}\" style=\"position:absolute;left:0;top:0;width:100%;height:100%;{m}{blur}{blend}\">{markup}</div>", escape(layer.id))
    }
}

fn matrix(m: &Aff) -> String {
    format!("matrix({:.6}, {:.6}, {:.6}, {:.6}, {:.3}, {:.3})", m.a, m.b, m.c, m.d, m.e, m.f)
}

/// Depth of field at this time, when it is on; refuses a focus at or below −1 (as a depth) and a blur below 0.
fn dof(comp: &Item, frame: &Item) -> R<Option<Dof>> {
    if !frame.on("dof") {
        return Ok(None);
    }
    let (t, focus, blur) = (comp.t, frame.num("focus"), frame.num("focusBlur"));
    if !(focus > -1.0) {
        return Err(format!("{}.focus: {focus} at {t} s; the focus is a depth, above -1", frame.id));
    }
    if !(blur >= 0.0) {
        return Err(format!("{}.focusBlur: {blur} at {t} s; the blur is 0 or more", frame.id));
    }
    Ok(Some(Dof { focus, blur }))
}

/// The frame, when the scene loads or is edited: at most one, first in the comp's own layers (never inside a group or
/// rig), no effects or masks, a zoom above 0 (still and every key); every top-level layer's depth above −1.
pub fn check(comp: &Node) -> R<()> {
    let frames: Vec<&Node> = comp.layers.iter().filter(|l| l.kind == "camera").collect();
    if frames.len() > 1 {
        let ids: Vec<&str> = frames.iter().map(|f| f.id.as_str()).collect();
        return Err(format!("{}: a scene has one frame; this one has {} ({})", comp.id, frames.len(), ids.join(", ")));
    }
    if let Some(i) = comp.layers.iter().position(|l| l.kind == "camera").filter(|i| *i != 0) {
        return Err(format!("{}: the frame goes first in the scene's layers (it is at {i})", comp.layers[i].id));
    }
    for l in &comp.layers {
        if l.kind == "camera" {
            if let Some(x) = l.effects.first().or(l.masks.first()) {
                return Err(format!("{}: the frame holds no effects or masks ({} is a {})", l.id, x.id, x.kind));
            }
            if let Some(z) = values(l, "zoom").find(|z| !(*z > 0.0)) {
                return Err(format!("{}.zoom: {z} is not above 0 (the frame's zoom must be above 0)", l.id));
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
        return Err(format!("{}: the frame goes in a scene's own layers, not inside a group or rig", n.id));
    }
    n.layers.iter().try_for_each(nested)
}

/// A number field's still value and every key's value.
fn values<'a>(n: &'a Node, f: &'a str) -> impl Iterator<Item = f64> + 'a {
    let keys = n.anim.iter().filter(move |(p, _)| p == f).flat_map(|(_, ks)| ks.iter());
    std::iter::once(n.props[f].as_f64().unwrap_or(f64::NAN)).chain(keys.filter_map(|k| match k.value {
        KeyValue::Number(v) => Some(v),
        KeyValue::Color(..) | KeyValue::Path(..) | KeyValue::Profile(..) => None,
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
