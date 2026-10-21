//! Where each stage layer was laid out and painted this frame (`frame` with `"boxes": true`): the host's
//! checks (overflow, clipped text, collisions, contrast; src/engine/perception/renderedChecks.ts) measure
//! the one layout the renderer draws, never an estimate. The walk mirrors blitz-paint's `render_element`
//! (same transforms, hoisted z-index children, opacity and overflow clips), in paint order. `glyphs` is the
//! union of the glyph runs drawn inside a layer (font ascent to descent over each run's advance): the text
//! itself, without the empty struts and inline boxes an overflow box also counts (KaTeX has many), and
//! without runs of spaces.

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
}

struct Walk<'a> {
    doc: &'a BaseDocument,
    out: Vec<Value>,
    glyphs: Vec<Option<Rect>>,
}

fn r(v: f64) -> f64 {
    (v * 10.0).round() / 10.0
}

fn rect(b: Rect) -> Value {
    json!([r(b.x0), r(b.y0), r(b.x1), r(b.y1)])
}

fn layer_id(node: &Node) -> Option<&str> {
    let el = node.element_data()?;
    el.attrs().iter().find(|a| &*a.name.local == LAYER_ATTR).map(|a| a.value.as_str())
}

impl Walk<'_> {
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
        let overflow = *node.scrollable_overflow();
        let own = layer_id(node).map(|lid| {
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
    let mut w = Walk { doc, out: vec![], glyphs: vec![] };
    {
        let root = doc.root_element().id;
        w.element(root, Affine::IDENTITY, None, Rect::new(0.0, 0.0, width as f64, height as f64), 1.0, None);
    }
    for (b, g) in w.out.iter_mut().zip(&w.glyphs) {
        b["glyphs"] = g.map_or(Value::Null, rect);
    }
    Value::Array(w.out)
}
