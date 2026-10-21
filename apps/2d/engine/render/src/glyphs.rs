//! Text as outlines, laid out by the renderer itself (`rostrum2d-render glyphs`): the host's one source of glyph
//! positions for text it bends, morphs, masks or emits particles from (src/engine/typography/rendererGlyphs.ts).
//! Reads `{ html, width, height, layers: [id, …] }` on stdin (a page: the stage's shell with the layers' own
//! markup) and writes `{ id: { w, h, d } }`: each `[data-layer-id]` element's glyphs as one SVG path in its
//! border box's px (its own transform left out, its descendants' kept), from the same Blitz layout (Stylo +
//! Taffy + Parley shaping, line breaking, variable-font instances) and the same font files the renderer paints.

use std::fmt::Write as _;
use std::io::Read as _;
use std::sync::Arc;

use blitz_dom::{BaseDocument, NodeData, NodeId};
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};
use kurbo::{Affine, Point, Vec2};
use parley::PositionedLayoutItem;
use serde_json::{json, Map, Value};
use skrifa::instance::{LocationRef, NormalizedCoord, Size};
use skrifa::outline::{DrawSettings, OutlinePen};
use skrifa::{FontRef, GlyphId, MetadataProvider};

/// An SVG path in layer px: each glyph's outline through `t` (font units are y-up at the glyph's origin).
struct Pen<'a> {
    d: &'a mut String,
    t: Affine,
}

impl Pen<'_> {
    fn pt(&self, x: f32, y: f32) -> Point {
        self.t * Point::new(x as f64, -y as f64)
    }
}

impl OutlinePen for Pen<'_> {
    fn move_to(&mut self, x: f32, y: f32) {
        let p = self.pt(x, y);
        let _ = write!(self.d, "M{:.2} {:.2}", p.x, p.y);
    }
    fn line_to(&mut self, x: f32, y: f32) {
        let p = self.pt(x, y);
        let _ = write!(self.d, "L{:.2} {:.2}", p.x, p.y);
    }
    fn quad_to(&mut self, cx: f32, cy: f32, x: f32, y: f32) {
        let (c, p) = (self.pt(cx, cy), self.pt(x, y));
        let _ = write!(self.d, "Q{:.2} {:.2} {:.2} {:.2}", c.x, c.y, p.x, p.y);
    }
    fn curve_to(&mut self, c0x: f32, c0y: f32, c1x: f32, c1y: f32, x: f32, y: f32) {
        let (a, b, p) = (self.pt(c0x, c0y), self.pt(c1x, c1y), self.pt(x, y));
        let _ = write!(self.d, "C{:.2} {:.2} {:.2} {:.2} {:.2} {:.2}", a.x, a.y, b.x, b.y, p.x, p.y);
    }
    fn close(&mut self) {
        self.d.push('Z');
    }
}

/// The glyphs drawn inside node `id` (and its painted descendants), `parent` mapping its parent's space to layer px.
fn walk(doc: &BaseDocument, id: NodeId, parent: Affine, own: bool, d: &mut String) {
    let node = &doc.tree()[id];
    if !matches!(node.data, NodeData::Element(_) | NodeData::AnonymousBlock(_)) || format!("{:?}", node.taffy_display()) == "None" {
        return;
    }
    let layout = *node.final_layout();
    // The layer element itself sits at the origin with no transform; below it, as painted.
    let t = if own { Affine::IDENTITY } else { parent * Affine::translate(Vec2::new(layout.location.x as f64, layout.location.y as f64)) * node.transform().as_deref().copied().unwrap_or_default() };
    if node.flags.is_inline_root() {
        if let Some(text) = node.element_data().and_then(|e| e.inline_layout_data.as_ref()) {
            let origin = Vec2::new((layout.padding.left + layout.border.left) as f64, (layout.padding.top + layout.border.top + text.block_offset) as f64);
            for line in text.layout.lines() {
                for item in line.items() {
                    let PositionedLayoutItem::GlyphRun(glyph_run) = item else { continue };
                    let run = glyph_run.run();
                    let data = run.font();
                    let Ok(font) = FontRef::from_index(data.data.data(), data.index) else { continue };
                    let outlines = font.outline_glyphs();
                    let coords: Vec<NormalizedCoord> = run.normalized_coords().iter().map(|c| NormalizedCoord::from_bits(c.to_bits())).collect();
                    let size = Size::new(run.font_size());
                    let skew = run.synthesis().skew().map(|a| Affine::skew(a.to_radians().tan() as f64, 0.0)).unwrap_or_default();
                    for g in glyph_run.positioned_glyphs() {
                        let Some(glyph) = outlines.get(GlyphId::new(g.id)) else { continue };
                        let mut pen = Pen { d, t: t * Affine::translate(origin + Vec2::new(g.x as f64, g.y as f64)) * skew };
                        let _ = glyph.draw(DrawSettings::unhinted(size, LocationRef::new(&coords)), &mut pen);
                    }
                }
            }
        }
    }
    if let Some(children) = &*node.paint_children.borrow() {
        for c in children.iter() {
            walk(doc, *c, t, false, d);
        }
    }
}

pub fn run() {
    let mut input = String::new();
    std::io::stdin().read_to_string(&mut input).expect("stdin");
    let req: Value = serde_json::from_str(&input).expect("glyphs: a JSON request on stdin");
    let (w, h) = (req["width"].as_u64().unwrap_or(1920) as u32, req["height"].as_u64().unwrap_or(1080) as u32);
    let config = blitz_dom::DocumentConfig { viewport: Some(Viewport::new(w, h, 1.0, ColorScheme::Light)), base_url: Some(crate::assets::BASE_URL.into()), net_provider: Some(Arc::new(crate::assets::Assets::default())), ..Default::default() };
    let mut doc = HtmlDocument::from_html(req["html"].as_str().unwrap_or(""), config);
    doc.handle_messages();
    doc.resolve(0.0);
    let mut out = Map::new();
    for id in req["layers"].as_array().into_iter().flatten().filter_map(Value::as_str) {
        let Ok(Some(node_id)) = doc.query_selector(&format!("[data-layer-id=\"{id}\"]")) else { continue };
        let size = doc.get_node(node_id).unwrap().final_layout().size;
        let mut d = String::new();
        walk(&doc, node_id, Affine::IDENTITY, true, &mut d);
        out.insert(id.to_string(), json!({ "w": size.width, "h": size.height, "d": d }));
    }
    println!("{}", Value::Object(out));
}
