//! Variable-font axes reach layout as Chrome sets them (H5): `font-optical-sizing: auto` (the initial value) sets
//! `opsz` to the font size in CSS px unless `font-variation-settings` names `opsz` itself; `none` leaves the font's
//! default (Roboto Flex: 14). Big titles used to lay out at opsz 14, lighter and narrower than in Chrome. And the
//! glyphs are drawn at the instance they were shaped at: below an axis's default (`font-stretch: 88%`) Skia was
//! handed a value lerped from the axis minimum, so the letters drew far narrower than their advances.

use std::sync::Arc;

use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};
use parley::fontique::Blob;

/// Roboto Flex (SIL OFL 1.1, apps/2d/engine/fonts/RobotoFlex-OFL.txt): `opsz` 8–144 (default 14), `wdth` 25–151.
const FONT: &[u8] = include_bytes!("../../fonts/RobotoFlex.ttf");

/// The laid-out width of one word in Roboto Flex at 140 px under `style`.
fn width(style: &str) -> f32 {
    let mut font_ctx = parley::FontContext::new();
    font_ctx.collection.register_fonts(Blob::new(Arc::new(FONT) as _), None);
    let html = format!(
        "<!DOCTYPE html><html><head></head><body style=\"margin:0\">\
         <div id=\"t\" style=\"position:absolute;white-space:nowrap;font-family:'Roboto Flex';font-size:140px;{style}\">Hamburgefonts</div>\
         </body></html>"
    );
    let config = DocumentConfig { viewport: Some(Viewport::new(3000, 400, 1.0, ColorScheme::Light)), font_ctx: Some(font_ctx), ..Default::default() };
    let mut doc = HtmlDocument::from_html(&html, config);
    doc.resolve(0.0);
    let id = doc.query_selector("#t").unwrap().expect("#t");
    doc.get_node(id).unwrap().final_layout().size.width
}

#[test]
fn optical_size_follows_the_font_size_unless_set() {
    let auto = width("");
    let (at_140, at_14, at_8) = (width("font-variation-settings:'opsz' 140"), width("font-variation-settings:'opsz' 14"), width("font-variation-settings:'opsz' 8"));
    assert!((auto - at_140).abs() < 0.5, "auto lays out at opsz 140 (the font size): {auto} vs {at_140}");
    assert!((auto - at_8).abs() > 2.0, "an explicit opsz wins over auto: {auto} vs opsz 8 {at_8}");
    let none = width("font-optical-sizing:none");
    assert!((none - at_14).abs() < 0.5 && (none - auto).abs() > 2.0, "none keeps the default opsz 14: {none} vs {at_14} (auto {auto})");
    let narrow = width("font-variation-settings:'wdth' 25");
    assert!(narrow < auto - 50.0, "other axes reach layout too: wdth 25 {narrow} vs {auto}");
}

/// How far the ink of one word reaches across a CPU paint, at `font-stretch: {stretch}`, as a share of its laid-out width.
fn ink_share(stretch: &str) -> f64 {
    const W: u32 = 1600;
    const H: u32 = 200;
    let mut font_ctx = parley::FontContext::new();
    font_ctx.collection.register_fonts(Blob::new(Arc::new(FONT) as _), None);
    let html = format!(
        "<!DOCTYPE html><html><head></head><body style=\"margin:0;background:#000\">         <div id=\"t\" style=\"position:absolute;left:0;top:0;white-space:nowrap;font-family:'Roboto Flex';font-size:140px;line-height:200px;color:#fff;font-stretch:{stretch}\">HHHHHH</div>         </body></html>"
    );
    let config = DocumentConfig { viewport: Some(Viewport::new(W, H, 1.0, ColorScheme::Light)), font_ctx: Some(font_ctx), ..Default::default() };
    let mut doc = HtmlDocument::from_html(&html, config);
    doc.resolve(0.0);
    let id = doc.query_selector("#t").unwrap().expect("#t");
    let laid_out = doc.get_node(id).unwrap().final_layout().size.width as f64;
    let mut painter = crate::painter::Painter::cpu(W, H, None).unwrap();
    painter.paint(false, |scene| blitz_paint::paint_scene(scene, &mut doc, 1.0, W, H, 0, 0)).unwrap();
    let mut px = vec![];
    crate::color::output(&crate::color::Spec::default(), &painter.read(), W, false, false, 0, &mut px);
    let lit = |x: u32| (0..H).any(|y| px[((y * W + x) * 4) as usize] > 128);
    let (first, last) = ((0..W).find(|x| lit(*x)).unwrap(), (0..W).rev().find(|x| lit(*x)).unwrap());
    (last - first) as f64 / laid_out
}

#[test]
fn glyphs_are_drawn_at_the_width_they_were_shaped_at() {
    let (normal, narrow, wide) = (ink_share("100%"), ink_share("88%"), ink_share("120%"));
    for (name, share) in [("88%", narrow), ("120%", wide)] {
        assert!((share - normal).abs() < 0.03, "ink / advance at stretch {name} is {share:.3}, at 100% {normal:.3}");
    }
}
