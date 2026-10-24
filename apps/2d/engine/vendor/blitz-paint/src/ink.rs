//! Rostrum patch (H27): where an element's subtree can paint (its "ink"), in the element's own space (its border box at
//! the origin), for the opacity / filter layer that holds it.
//!
//! An element whose children may overflow it (overflow: visible) used to get an unbounded layer: Skia then sized the
//! layer to the whole frame, so a 1080p frame of 200 half-transparent layers cleared and composited 200 full frames
//! (≈30 ms of GPU a frame on the laptop, more than the frame's time). The layer now covers the boxes of the subtree, grown
//! by what draws outside a box (box and text shadows, CSS filters, outlines, glyph overhang).
//! Export speed (2026-10-25): a 2D-transformed descendant's ink is mapped through its transform (as render.rs places
//! it: its location, then its own transform), and an inline `<svg>` drawn at its own size reaches as far as its
//! drawing's layer bounds (strokes, filters). Night Bloom's petal and flower layers (a rotated child, a path's svg)
//! were all unbounded: ~600 frame-sized layers a motion-blur sample, ~70 % of the card's time. What still can't be
//! bounded (a 3D or fixed descendant, an SVG scaled to its box, a filter by url(#id)) keeps the unbounded layer, as
//! before: never a cut picture.

use blitz_dom::{BaseDocument, Node};
use kurbo::{Affine, Rect, Vec2};
use style::values::computed::{BorderStyle, OutlineStyle};

/// `px` device pixels in the space `transform` maps from (its smaller scale; unbounded when it collapses).
pub(crate) fn device_px(transform: kurbo::Affine, px: f64) -> f64 {
    let [a, b, c, d, _, _] = transform.as_coeffs();
    let s = (a * a + b * b).sqrt().min((c * c + d * d).sqrt());
    if s > 1e-6 { px / s } else { 1e7 }
}

/// The ink of `node`'s subtree in its own border-box space (scaled by `scale`), None when it can't be bounded. `follow`:
/// through transformed descendants and inline SVGs too (a layer without a filter; a filtered layer's picture depends on
/// where its layer starts, so its bound stays as it was).
pub(crate) fn subtree_ink(dom: &BaseDocument, node: &Node, scale: f64, follow: bool) -> Option<Rect> {
    let mut ink = Rect::ZERO;
    for &child in node.layout_children.borrow().as_deref()? {
        let child = dom.get_node(child)?;
        ink = ink.union(descend(dom, child, placed(child, Affine::IDENTITY, scale), scale, follow)?);
    }
    Some(ink)
}

/// Where `child`'s own space lands in its parent's space (`parent` maps that to the root's): its location, then its own
/// transform, as render.rs places it.
fn placed(child: &Node, parent: Affine, scale: f64) -> Affine {
    let at = child.final_layout().location;
    parent * Affine::translate(Vec2::new(at.x as f64, at.y as f64) * scale) * child.transform().as_deref().copied().unwrap_or_default()
}

/// `node`'s ink and its subtree's in the root's space; `m` maps `node`'s own space (its border box at the origin) there.
fn descend(dom: &BaseDocument, node: &Node, m: Affine, scale: f64, follow: bool) -> Option<Rect> {
    let size = node.final_layout().size;
    let mut ink = Rect::new(0.0, 0.0, size.width as f64 * scale, size.height as f64 * scale);
    if node.is_element() {
        let turned = node.transform().as_deref().is_some_and(|t| *t != Affine::IDENTITY);
        if !follow && (turned || node.element_data().is_some_and(|e| &*e.name.local == "svg")) {
            return None;
        }
        if crate::filters::url_filter_id(node).is_some() || node.taffy_position() == taffy::Position::Fixed || blitz_dom::node_3d_transform(node).is_some() {
            return None;
        }
        // Sprites stamped where an emitter puts them, its trails, the motion-blur sum: not bounded by any box.
        if ["data-particles", "data-trails", "data-shutter-held"].iter().any(|a| crate::particles::data_attr(node, a).is_some()) {
            return None;
        }
        if node.element_data().is_some_and(|e| &*e.name.local == "svg") {
            ink = ink.union(svg_reach(node, scale)?);
        }
        if let Some(styles) = node.primary_styles() {
            let text = node.flags.is_inline_root().then(|| inline_shadow(dom, node, &styles));
            ink = ink.union(own_reach(&styles, ink, text, scale));
            if let Some(f) = crate::filters::convert_filters(&styles.get_effects().filter.0) {
                let e = f.expansion_rect();
                ink = Rect::new(ink.x0 + e.x0, ink.y0 + e.y0, ink.x1 + e.x1, ink.y1 + e.y1);
            }
        }
    }
    // Its glows (glow.rs) spread its picture as far as their blurs reach.
    for (glow, _) in crate::glow::of(node) {
        let e = glow.expansion_rect();
        ink = ink.union(Rect::new(ink.x0 + e.x0, ink.y0 + e.y0, ink.x1 + e.x1, ink.y1 + e.y1));
    }
    let mut ink = m.transform_rect_bbox(ink);
    for &child in node.layout_children.borrow().as_deref().unwrap_or_default() {
        let child = dom.get_node(child)?;
        ink = ink.union(descend(dom, child, placed(child, m, scale), scale, follow)?);
    }
    Some(ink)
}

/// How far an inline `<svg>`'s drawing reaches in its own space: its layer bounds (strokes, filters) placed at its content
/// box, when it is drawn at its own size (render.rs `draw_svg`: the tree's px are then the box's); None when it is scaled.
fn svg_reach(node: &Node, scale: f64) -> Option<Rect> {
    let Some(blitz_dom::node::ImageData::Svg(data)) = node.element_data()?.image_data() else { return Some(Rect::ZERO) };
    let layout = node.final_layout();
    let (w, h) = (layout.content_box_width() * scale as f32, layout.content_box_height() * scale as f32);
    let tree = data.tree_for_box(w, h);
    if (tree.size().width() - w).abs() > 0.5 || (tree.size().height() - h).abs() > 0.5 {
        return None;
    }
    if !tree.root().has_children() {
        return Some(Rect::ZERO);
    }
    let b = tree.root().abs_layer_bounding_box();
    let (x, y) = ((layout.padding.left + layout.border.left) as f64 * scale, (layout.padding.top + layout.border.top) as f64 * scale);
    // A few pixels round it: anti-aliased edges, joins.
    Some(Rect::new(b.left() as f64 + x, b.top() as f64 + y, b.right() as f64 + x, b.bottom() as f64 + y).inflate(4.0, 4.0))
}

/// A text box's largest text-shadow reach (offset + blur), over its inline elements too (each may carry its own).
fn inline_shadow(dom: &BaseDocument, node: &Node, styles: &style::properties::ComputedValues) -> f64 {
    let own = styles.get_inherited_text().text_shadow.0.iter()
        .map(|s| s.horizontal.px().abs().max(s.vertical.px().abs()) as f64 + s.blur.px() as f64 * 2.5)
        .fold(0.0, f64::max);
    node.children.iter().filter_map(|&c| dom.get_node(c)).filter(|c| c.is_element())
        .map(|c| c.primary_styles().map_or(0.0, |st| inline_shadow(dom, c, &st)))
        .fold(own, f64::max)
}

/// What an element draws outside its border box `b`: outset box shadows, its outline and, for a box holding text
/// (`text`: its largest text-shadow reach), the glyphs' overhang and stroke (a font size around) and their shadows.
fn own_reach(styles: &style::properties::ComputedValues, b: Rect, text: Option<f64>, scale: f64) -> Rect {
    let mut r = b;
    for s in styles.get_effects().box_shadow.0.iter().filter(|s| !s.inset) {
        let grow = (s.spread.px() as f64 + s.base.blur.px() as f64 * 2.5) * scale;
        r = r.union(b.inflate(grow, grow) + Vec2::new(s.base.horizontal.px() as f64, s.base.vertical.px() as f64) * scale);
    }
    let outline = styles.get_outline();
    if !matches!(outline.outline_style, OutlineStyle::BorderStyle(BorderStyle::None | BorderStyle::Hidden)) {
        let grow = (outline.outline_width.0.to_f64_px() + outline.outline_offset.to_f64_px().abs()) * scale;
        r = r.union(b.inflate(grow, grow));
    }
    if let Some(shadow) = text {
        let grow = (styles.clone_font_size().used_size().px() as f64 + shadow) * scale;
        r = r.union(b.inflate(grow, grow));
    }
    r
}
