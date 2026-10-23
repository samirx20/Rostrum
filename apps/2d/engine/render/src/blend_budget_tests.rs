//! H41: a blend layer drawn after more than 1024 other layers in one frame still blends. Upstream Blitz refused every
//! layer past the 1024th and drew on without it (vendor/PATCHES.md › H41), so Night Bloom's multiply vignette, drawn
//! last at the drop, came out as a plain white oval over the whole frame, with no error, in look and export alike.

use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};

const S: u32 = 64;

#[test]
fn a_multiply_layer_after_many_layers_still_multiplies() {
    // 1200 faded dots (one opacity layer each), then a white full-frame multiply layer over a red backdrop: white ×
    // red is red. Without the layer it would draw as plain white.
    let dots: String = (0..1200).map(|i| format!("<div style=\"position:absolute;left:{}px;top:0;width:1px;height:1px;\
        background:#00f;opacity:0.5\"></div>", i % 4)).collect();
    let html = format!("<!DOCTYPE html><html><body style=\"margin:0;background:#ff0000\">{dots}<div style=\"position:absolute;\
        left:0;top:0;width:{S}px;height:{S}px;background:#ffffff;mix-blend-mode:multiply\"></div></body></html>");
    let spec = crate::color::Spec::parse(&serde_json::Value::Null).unwrap();
    let mut doc = HtmlDocument::from_html(&html, DocumentConfig { viewport: Some(Viewport::new(S, S, 1.0, ColorScheme::Light)), ..Default::default() });
    doc.resolve(0.0);
    let mut painter = crate::painter::Painter::cpu(S, S, spec.surface_space()).unwrap();
    painter.paint(false, |scene| blitz_paint::paint_scene(scene, &mut doc, 1.0, S, S, 0, 0)).unwrap();
    let mut px = vec![];
    crate::color::output(&spec, &painter.read().unwrap(), S, false, false, 0, &mut px);
    let at = |x: u32, y: u32| &px[((y * S + x) * 4) as usize..((y * S + x) * 4 + 3) as usize];
    for (x, y) in [(32, 32), (60, 60), (10, 50)] {
        let p = at(x, y);
        assert!(p[0] > 245 && p[1] < 10 && p[2] < 10, "({x}, {y}) should stay red under a white multiply layer, got {p:?}");
    }
}
