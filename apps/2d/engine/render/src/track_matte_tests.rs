//! Track mattes are drawn (H15): a red layer seen through a matte square shows red only inside it (alpha, luma) or
//! only outside it (inverted); a dark matte read by luma lets little through. Without this a matte silently drew the
//! layer whole (H14's KNOWN OPEN).

use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};

const W: u32 = 120;
const H: u32 = 60;

/// Red over the whole frame, seen through a 40 × 40 square of `colour` at (10, 10), on black.
fn frame(mode: &str, colour: &str) -> Vec<u8> {
    let full = "position:absolute;left:0;top:0;width:100%;height:100%;";
    let html = format!(
        "<!DOCTYPE html><html><head></head><body style=\"margin:0;background:#000\"><div id=\"rostrum-stage\" style=\"position:relative;width:{W}px;height:{H}px\">\
         <div data-track-matte=\"{mode}\" style=\"{full}\"><div style=\"{full}\"><div style=\"position:absolute;left:10px;top:10px;width:40px;height:40px;background:{colour}\"></div></div>\
         <div style=\"{full}\"><div style=\"{full}background:#ff0000\"></div></div></div></div></body></html>"
    );
    let mut doc = HtmlDocument::from_html(&html, DocumentConfig { viewport: Some(Viewport::new(W, H, 1.0, ColorScheme::Light)), ..Default::default() });
    doc.resolve(0.0);
    let mut painter = crate::painter::Painter::cpu(W, H, None).unwrap();
    painter.paint(false, |scene| blitz_paint::paint_scene(scene, &mut doc, 1.0, W, H, 0, 0)).unwrap();
    let mut px = vec![];
    crate::color::output(&crate::color::Spec::default(), &painter.read(), W, false, false, 0, &mut px);
    px
}

fn red(px: &[u8], x: usize, y: usize) -> u8 {
    px[(y * W as usize + x) * 4]
}

#[test]
fn a_layer_shows_only_through_its_matte() {
    for (mode, colour, inside, outside) in [
        ("alpha", "#0000ff", 255, 0),
        ("alphaInverted", "#0000ff", 0, 255),
        ("luma", "#ffffff", 255, 0),
        ("lumaInverted", "#ffffff", 0, 255),
    ] {
        let px = frame(mode, colour);
        let (i, o) = (red(&px, 30, 30), red(&px, 90, 30));
        assert!((i as i32 - inside).abs() < 24 && (o as i32 - outside).abs() < 24, "{mode} {colour}: inside {i}, outside {o}; want {inside}, {outside}");
    }
    // Luma reads brightness, not coverage: an opaque dark-blue matte lets little through.
    let i = red(&frame("luma", "#0000ff"), 30, 30);
    assert!(i < 128, "luma through blue: {i}");
}
