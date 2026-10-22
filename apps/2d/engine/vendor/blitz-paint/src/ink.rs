//! Rostrum patch (H27): where an element's subtree can paint (its "ink"), in the element's own space (its border box at
//! the origin), for the opacity / filter layer that holds it.
//!
//! An element whose children may overflow it (overflow: visible) used to get an unbounded layer: Skia then sized the
//! layer to the whole frame, so a 1080p frame of 200 half-transparent layers cleared and composited 200 full frames
//! (≈30 ms of GPU a frame on the laptop, more than the frame's time). The layer now covers the boxes of the subtree, grown
//! by what draws outside a box (box and text shadows, CSS filters, outlines, glyph overhang). Where the subtree holds
//! something whose reach is not known from its boxes (a transformed or fixed descendant, an SVG, a filter by url(#id)),
//! there is no bound and the layer stays unbounded, as before: never a cut picture.

use blitz_dom::{BaseDocument, Node};
use kurbo::{Rect, Vec2};
use style::values::computed::{BorderStyle, OutlineStyle};

/// `px` device pixels in the space `transform` maps from (its smaller scale; unbounded when it collapses).
pub(crate) fn device_px(transform: kurbo::Affine, px: f64) -> f64 {
    let [a, b, c, d, _, _] = transform.as_coeffs();
    let s = (a * a + b * b).sqrt().min((c * c + d * d).sqrt());
    if s > 1e-6 { px / s } else { 1e7 }
}

/// The ink of `node`'s subtree in its own border-box space (scaled by `scale`), None when it can't be bounded.
pub(crate) fn subtree_ink(dom: &BaseDocument, node: &Node, scale: f64) -> Option<Rect> {
    let mut ink = Rect::ZERO;
    for &child in node.layout_children.borrow().as_deref()? {
        let child = dom.get_node(child)?;
        let at = child.final_layout().location;
        ink = ink.union(descend(dom, child, Vec2::new(at.x as f64, at.y as f64) * scale, scale)?);
    }
    Some(ink)
}

/// `node`'s ink and its subtree's, `at` its border box's origin in the root's space.
fn descend(dom: &BaseDocument, node: &Node, at: Vec2, scale: f64) -> Option<Rect> {
    let size = node.final_layout().size;
    let mut ink = Rect::from_origin_size(at.to_point(), (size.width as f64 * scale, size.height as f64 * scale));
    if node.is_element() {
        if node.transform().as_deref().is_some_and(|t| *t != kurbo::Affine::IDENTITY) || node.element_data().is_some_and(|e| &*e.name.local == "svg") {
            return None;
        }
        if crate::filters::url_filter_id(node).is_some() {
            return None;
        }
        if node.taffy_position() == taffy::Position::Fixed {
            return None;
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
    for &child in node.layout_children.borrow().as_deref().unwrap_or_default() {
        let child = dom.get_node(child)?;
        let loc = child.final_layout().location;
        ink = ink.union(descend(dom, child, at + Vec2::new(loc.x as f64, loc.y as f64) * scale, scale)?);
    }
    Some(ink)
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
