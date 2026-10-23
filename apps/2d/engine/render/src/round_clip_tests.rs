//! H17: a rounded rect mask (`clip-path: inset(… round r)`, stage_fx.rs `mask`) cuts its corners. Upstream Blitz drew
//! every rounded inset as a square (vendor/PATCHES.md › H17), so the H16 phone's screen corners stuck out.

use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};

const S: u32 = 100;

#[test]
fn rounded_inset_clip_cuts_the_corners() {
    let html = format!("<!DOCTYPE html><html><body style=\"margin:0;background:#000\"><div style=\"position:absolute;left:0;top:0;\
        width:{S}px;height:{S}px;background:#ff0000;clip-path:inset(0px 0px 0px 0px round 30px)\"></div></body></html>");
    let spec = crate::color::Spec::parse(&serde_json::Value::Null).unwrap();
    let mut doc = HtmlDocument::from_html(&html, DocumentConfig { viewport: Some(Viewport::new(S, S, 1.0, ColorScheme::Light)), ..Default::default() });
    doc.resolve(0.0);
    let mut painter = crate::painter::Painter::cpu(S, S, spec.surface_space()).unwrap();
    painter.paint(false, |scene| blitz_paint::paint_scene(scene, &mut doc, 1.0, S, S, 0, 0)).unwrap();
    let mut px = vec![];
    crate::color::output(&spec, &painter.read().unwrap(), S, false, false, 0, &mut px);
    let red = |x: u32, y: u32| px[((y * S + x) * 4) as usize];
    for (x, y) in [(2, 2), (97, 2), (2, 97), (97, 97)] {
        assert!(red(x, y) < 10, "corner ({x}, {y}) should be cut away, red = {}", red(x, y));
    }
    for (x, y) in [(50, 50), (50, 1), (1, 50), (12, 12)] {
        assert!(red(x, y) > 245, "({x}, {y}) is inside the rounded box, red = {}", red(x, y));
    }
}
