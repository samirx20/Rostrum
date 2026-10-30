//! Where each stage layer was laid out and painted this frame (`frame` with `"boxes": true`): the host's
//! checks (overflow, clipped text, collisions, contrast; src/engine/perception/renderedChecks.ts) measure
//! the one layout the renderer draws, never an estimate. The walk mirrors blitz-paint's `render_element`
//! (same transforms, hoisted z-index children, opacity and overflow clips), in paint order. `glyphs` is the
//! union of the glyph runs drawn inside a layer (font ascent to descent over each run's advance): the text
//! itself, without the empty struts and inline boxes an overflow box also counts (KaTeX has many), and
//! without runs of spaces. The parts of an inline `<svg>` that carry the layer attribute (shapes, `<g>`, `<text>`)
//! are measured too, from the SVG tree the painter draws (`svg_parts`): an SVG `<text>`'s box is its `glyphs`.

use blitz_dom::{BaseDocument, Node, NodeData, NodeId};
use kurbo::{Affine, Rect, Vec2};
use parley::PositionedLayoutItem;
use serde_json::{json, Value};

const LAYER_ATTR: &str = "data-layer-id";

/// An element's 2D placement in page pixels, under the 3D base matrix of its tilted ancestors (if any).
struct Placed {
    transform: Affine,
    base: Option<[f64; 16]>,
}

impl Placed {
    /// A rect in the element's own space as the bounding box of where it is painted, projected through any
    /// 3D tilt as the painter draws it (blitz_paint::project_rect_bbox).
    fn bbox(&self, r: Rect) -> Rect {
        let Some(b) = &self.base else { return self.transform.transform_rect_bbox(r) };
        let [a, bb, c, d, e, f] = self.transform.as_coeffs();
        let p = [a, c, 0.0, e, bb, d, 0.0, f, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0];
        blitz_paint::project_rect_bbox(&blitz_dom::mul4(b, &p), r)
    }

    /// Element px -> page px as a 3×3 projective matrix, row-major (x', y', w') = M (x, y, 1), then x'/w', y'/w': the
    /// 2D placement under any 3D tilt, as the painter draws it.
    fn matrix(&self) -> [f64; 9] {
        let [a, b, c, d, e, f] = self.transform.as_coeffs();
        let Some(base) = &self.base else { return [a, c, e, b, d, f, 0.0, 0.0, 1.0] };
        let p = [a, c, 0.0, e, b, d, 0.0, f, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0];
        let m = blitz_dom::mul4(base, &p);
        [m[0], m[1], m[3], m[4], m[5], m[7], m[12], m[13], m[15]]
    }
}

/// A layer element as `places` finds it: its node, border box size and element px -> page px matrix.
pub struct Place {
    pub node: NodeId,
    pub w: f64,
    pub h: f64,
    pub matrix: [f64; 9],
}

struct Walk<'a> {
    doc: &'a BaseDocument,
    out: Vec<Value>,
    glyphs: Vec<Option<Rect>>,
    /// The attribute naming a layer element (`data-layer-id` on a page; a scene's stage uses `id`).
    attr: &'static str,
    /// `places`: only these layers are recorded, with their node and matrix.
    want: &'a [&'a str],
    places: Vec<(String, Place)>,
}

fn r(v: f64) -> f64 {
    (v * 10.0).round() / 10.0
}

fn rect(b: Rect) -> Value {
    json!([r(b.x0), r(b.y0), r(b.x1), r(b.y1)])
}

fn layer_id<'n>(node: &'n Node, attr: &str) -> Option<&'n str> {
    let el = node.element_data()?;
    el.attrs().iter().find(|a| &*a.name.local == attr).map(|a| a.value.as_str())
}

impl Walk<'_> {
    /// The parts of an inline `<svg>` named by the layer attribute, after the svg in paint order, each as painted: the
    /// SVG tree parsed for the svg's content box (draw_svg's mapping: object-fit contain, centred), its parts'
    /// stroke boxes through the svg's placement. A part's `parent` is its nearest named `<g>`, else the svg's owner.
    fn svg_parts(&mut self, node: &Node, placed: &Placed, clip: Rect, alpha: f32, owner: Option<usize>) {
        if !self.want.is_empty() {
            return;
        }
        let Some(blitz_dom::node::ImageData::Svg(data)) = node.element_data().and_then(|e| e.image_data()) else { return };
        let mut named = std::collections::HashSet::new();
        self.named_below(node, &mut named);
        if named.is_empty() {
            return;
        }
        let layout = node.final_layout();
        let (x, y) = ((layout.padding.left + layout.border.left) as f64, (layout.padding.top + layout.border.top) as f64);
        let w = layout.size.width - layout.padding.left - layout.padding.right - layout.border.left - layout.border.right;
        let h = layout.size.height - layout.padding.top - layout.padding.bottom - layout.border.top - layout.border.bottom;
        if w <= 0.0 || h <= 0.0 {
            return;
        }
        let tree = data.tree_for_box(w, h);
        let size = tree.size();
        let (sw, sh) = (size.width() as f64, size.height() as f64);
        let k = (w as f64 / sw).min(h as f64 / sh);
        let m = Affine::translate(Vec2::new(x + (w as f64 - sw * k) / 2.0, y + (h as f64 - sh * k) / 2.0)) * Affine::scale(k);
        let parent = owner.and_then(|i| self.out[i]["id"].as_str().map(str::to_string));
        self.svg_group(tree.root(), m, placed, clip, alpha, parent, &named);
    }

    fn named_below(&self, node: &Node, out: &mut std::collections::HashSet<String>) {
        for &c in &node.children {
            let child = &self.doc.tree()[c];
            if let Some(l) = layer_id(child, self.attr) {
                out.insert(l.to_string());
            }
            self.named_below(child, out);
        }
    }

    #[allow(clippy::too_many_arguments)]
    fn svg_group(&mut self, g: &usvg::Group, m: Affine, placed: &Placed, clip: Rect, alpha: f32, parent: Option<String>,
                 named: &std::collections::HashSet<String>) {
        for n in g.children() {
            let a = match n { usvg::Node::Group(cg) => alpha * cg.opacity().get(), _ => alpha };
            let mut next = parent.clone();
            if named.contains(n.id()) && a > 0.0 {
                let b = n.abs_stroke_bounding_box();
                let bx = placed.bbox(m.transform_rect_bbox(Rect::new(b.left() as f64, b.top() as f64, b.right() as f64, b.bottom() as f64)));
                self.out.push(json!({ "id": n.id(), "parent": parent, "box": rect(bx), "ink": rect(bx), "clip": rect(clip),
                                      "opacity": r(a as f64 * 1000.0) / 1000.0, "svg": true }));
                self.glyphs.push(matches!(n, usvg::Node::Text(_)).then_some(bx));
                next = Some(n.id().to_string());
            }
            if let usvg::Node::Group(cg) = n {
                self.svg_group(cg, m, placed, clip, a, next, named);
            }
        }
    }

    /// The glyph runs of an inline root, in page pixels.
    fn runs(node: &Node, transform: &Placed) -> Option<Rect> {
        if !node.flags.is_inline_root() {
            return None;
        }
        let text = node.element_data()?.inline_layout_data.as_ref()?;
        let l = node.final_layout();
        let origin = Vec2::new((l.padding.left + l.border.left) as f64, (l.padding.top + l.border.top + text.block_offset) as f64);
        let mut all: Option<Rect> = None;
        for line in text.layout.lines() {
            for item in line.items() {
                let PositionedLayoutItem::GlyphRun(run) = item else { continue };
                // A run of spaces draws nothing (the gap between split words, letters faded out around it).
                if run.glyphs().next().is_none() || text.text.get(run.run().text_range()).is_some_and(|t| t.chars().all(char::is_whitespace)) {
                    continue;
                }
                let m = run.run().font_metrics();
                let (x, b) = (run.offset() as f64, run.baseline() as f64);
                let r = Rect::new(x, b - m.ascent as f64, x + run.advance() as f64, b + m.descent as f64) + origin;
                let r = transform.bbox(r);
                all = Some(all.map_or(r, |a| a.union(r)));
            }
        }
        all
    }

    fn element(&mut self, id: NodeId, parent: Affine, base: Option<[f64; 16]>, clip: Rect, opacity: f32, owner: Option<usize>) {
        let node = &self.doc.tree()[id];
        if !matches!(node.data, NodeData::Element(_) | NodeData::AnonymousBlock(_)) || format!("{:?}", node.taffy_display()) == "None" {
            return;
        }
        let Some(styles) = node.primary_styles() else { return };
        if format!("{:?}", styles.get_inherited_box().visibility) != "Visible" {
            return;
        }
        let alpha = opacity * styles.get_effects().opacity;
        if alpha <= 0.0 {
            return;
        }
        let layout = *node.final_layout();
        let border = Rect::from_origin_size((layout.location.x as f64, layout.location.y as f64), (layout.size.width as f64, layout.size.height as f64));
        let transform = parent * Affine::translate(Vec2::new(border.x0, border.y0)) * node.transform().as_deref().copied().unwrap_or_default();
        // Its own 3D transform and its 3D ancestors' (the painter's base matrix, outer · inner).
        let base = match (base, blitz_paint::element_3d(node, transform, 1.0)) {
            (Some(b), Some(m)) => Some(blitz_dom::mul4(&b, &m)),
            (b, m) => m.or(b),
        };
        let placed = Placed { transform, base };
        let local = Rect::new(0.0, 0.0, border.width(), border.height());
        // Its own CSS clip-path clips it and what it holds, as the painter draws it.
        let clip = blitz_paint::clip_path_bbox(node).map_or(clip, |c| clip.intersect(placed.bbox(c)));
        let overflow = *node.scrollable_overflow();
        if let Some(lid) = layer_id(node, self.attr).filter(|l| self.want.contains(l)) {
            self.places.push((lid.to_string(), Place { node: id, w: local.width(), h: local.height(), matrix: placed.matrix() }));
        }
        let own = layer_id(node, self.attr).filter(|_| self.want.is_empty()).map(|lid| {
            let parent = owner.and_then(|i| self.out[i]["id"].as_str().map(str::to_string));
            self.out.push(json!({
                "id": lid,
                "parent": parent,
                "box": rect(placed.bbox(local)),
                "ink": rect(placed.bbox(overflow.union(local))),
                "clip": rect(clip),
                "opacity": r(alpha as f64 * 1000.0) / 1000.0,
            }));
            self.glyphs.push(None);
            self.out.len() - 1
        });
        let owner = own.or(owner);
        self.svg_parts(node, &placed, clip, alpha, owner);
        if let (Some(i), Some(g)) = (owner, Self::runs(node, &placed)) {
            self.glyphs[i] = Some(self.glyphs[i].map_or(g, |a| a.union(g)));
        }
        let clips = format!("{:?}", styles.get_box().overflow_x) != "Visible" || format!("{:?}", styles.get_box().overflow_y) != "Visible";
        let child_clip = if clips { clip.intersect(placed.bbox(local)) } else { clip };
        let child_alpha = alpha;
        drop(styles);
        if let Some(sc) = &node.stacking_context {
            for h in sc.neg_z_hoisted_children() {
                let p = h.position(node.tree(), node.id);
                self.element(h.node_id, transform.pre_translate(Vec2::new(p.x as f64, p.y as f64)), base, child_clip, child_alpha, owner);
            }
        }
        if let Some(children) = &*node.paint_children.borrow() {
            for c in children.iter() {
                self.element(*c, transform, base, child_clip, child_alpha, owner);
            }
        }
        if let Some(sc) = &node.stacking_context {
            for h in sc.pos_z_hoisted_children() {
                let p = h.position(node.tree(), node.id);
                self.element(h.node_id, transform.pre_translate(Vec2::new(p.x as f64, p.y as f64)), base, child_clip, child_alpha, owner);
            }
        }
    }
}

/// Every `[data-layer-id]` element painted this frame, in paint order (later is on top): its border box and
/// ink (border box ∪ overflowing content: text past its box) in page pixels, the clip its ancestors apply,
/// and its opacity with its ancestors'.
pub fn boxes(doc: &BaseDocument, width: u32, height: u32) -> Value {
    let mut w = Walk { doc, out: vec![], glyphs: vec![], attr: LAYER_ATTR, want: &[], places: vec![] };
    {
        let root = doc.root_element().id;
        w.element(root, Affine::IDENTITY, None, Rect::new(0.0, 0.0, width as f64, height as f64), 1.0, None);
    }
    for (b, g) in w.out.iter_mut().zip(&w.glyphs) {
        b["glyphs"] = g.map_or(Value::Null, rect);
    }
    Value::Array(w.out)
}

/// The layers `ids` (elements whose `attr` is one of them) as painted this frame, in paint order: what `place`
/// (place.rs) maps pointer and outline through. A layer not painted (hidden, opacity 0, out of its time) is absent.
pub fn places(doc: &BaseDocument, width: u32, height: u32, attr: &'static str, ids: &[&str]) -> Vec<(String, Place)> {
    let mut w = Walk { doc, out: vec![], glyphs: vec![], attr, want: ids, places: vec![] };
    let root = doc.root_element().id;
    w.element(root, Affine::IDENTITY, None, Rect::new(0.0, 0.0, width as f64, height as f64), 1.0, None);
    w.places
}

/// `boxes`, carried by `m` (page px → world px; the identity when the page is the world view's): a world picture's
/// boxes (scene_world.rs), every rect in world px.
pub fn in_world(doc: &BaseDocument, width: u32, height: u32, m: crate::rig::math::Aff) -> Value {
    let mut out = boxes(doc, width, height);
    if m != crate::rig::math::Aff::ID {
        for b in out.as_array_mut().into_iter().flatten() {
            for k in ["box", "ink", "clip", "glyphs"] {
                if let Some(w) = carried(&b[k], m) {
                    b[k] = w;
                }
            }
        }
    }
    out
}

/// Adds `world` to each box: its `box` carried by `m` (output px → world px, the plain frame), where the world view
/// draws the layer (camera spec § 8.3).
pub fn add_world(boxes: &mut Value, m: crate::rig::math::Aff) {
    for b in boxes.as_array_mut().into_iter().flatten() {
        b["world"] = carried(&b["box"], m).unwrap_or(Value::Null);
    }
}

/// A rect [x0, y0, x1, y1] carried by `m`: the bounding box of its corners.
fn carried(v: &Value, m: crate::rig::math::Aff) -> Option<Value> {
    let r: Vec<f64> = v.as_array()?.iter().filter_map(Value::as_f64).collect();
    let [x0, y0, x1, y1] = r[..] else { return None };
    let ps = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)].map(|p| m.apply(p));
    let b = ps.iter().fold(Rect::new(f64::MAX, f64::MAX, f64::MIN, f64::MIN), |b, p| Rect::new(b.x0.min(p.0), b.y0.min(p.1), b.x1.max(p.0), b.y1.max(p.1)));
    Some(rect(b))
}
