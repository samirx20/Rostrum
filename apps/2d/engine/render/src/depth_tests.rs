//! Depth (round 14, H5): a parent's `perspective` reaches its 3D-transformed children exactly as
//! `perspective(…)` in the child's own transform does (one matrix for paint and `boxes`), and `filter: blur()`
//! on a tilted element blurs it in its own plane (no sliver, no sharp inner rectangle); any layer on a tilted
//! element (opacity, blend, isolation) is drawn.

use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};
use serde_json::Value;

const W: u32 = 600;
const H: u32 = 400;

/// A 300 × 200 card centred in a 600 × 400 parent (so the parent's perspective-origin, its centre, is the card's
/// transform-origin), on a black page.
fn page(parent_style: &str, card_style: &str) -> String {
    format!(
        "<!DOCTYPE html><html><head></head><body style=\"margin:0;background:#000\">\
         <div style=\"position:absolute;left:0;top:0;width:{W}px;height:{H}px;{parent_style}\">\
         <div data-layer-id=\"card\" style=\"position:absolute;left:150px;top:100px;width:300px;height:200px;background:#fff;{card_style}\"></div>\
         </div></body></html>"
    )
}

/// The frame's display RGBA and its boxes.
fn render(html: &str) -> (Vec<u8>, Value) {
    let mut doc = HtmlDocument::from_html(html, DocumentConfig { viewport: Some(Viewport::new(W, H, 1.0, ColorScheme::Light)), ..Default::default() });
    doc.resolve(0.0);
    let boxes = crate::boxes::boxes(&doc, W, H);
    let mut painter = crate::painter::Painter::cpu(W, H, None).unwrap();
    painter.paint(false, |scene| blitz_paint::paint_scene(scene, &mut doc, 1.0, W, H, 0, 0)).unwrap();
    let mut px = vec![];
    crate::color::output(&crate::color::Spec::default(), &painter.read().unwrap(), W, false, false, 0, &mut px);
    (px, boxes)
}

fn card_box(boxes: &Value) -> [f64; 4] {
    let b = boxes.as_array().unwrap().iter().find(|b| b["id"] == "card").expect("no box for the card");
    let v: Vec<f64> = b["box"].as_array().unwrap().iter().map(|v| v.as_f64().unwrap()).collect();
    [v[0], v[1], v[2], v[3]]
}

/// Brightness (the red channel: everything here is grey) at (x, y).
fn lum(px: &[u8], x: u32, y: u32) -> i32 {
    px[((y * W + x) * 4) as usize] as i32
}

#[test]
fn a_parents_perspective_tilts_a_child_as_the_childs_own_perspective_does() {
    let (by_parent, parent_boxes) = render(&page("perspective:800px", "transform:rotateY(40deg)"));
    let (by_child, child_boxes) = render(&page("", "transform:perspective(800px) rotateY(40deg)"));

    let (a, b) = (card_box(&parent_boxes), card_box(&child_boxes));
    assert!(a.iter().zip(b).all(|(p, c)| (p - c).abs() < 0.5), "boxes: parent's perspective {a:?}, the card's own {b:?}");
    // Really tilted in perspective: narrower than 300, its near edge taller than 200.
    assert!(a[2] - a[0] < 290.0 && a[3] - a[1] > 202.0, "the card is not tilted in perspective: {a:?}");

    let differing = by_parent.chunks(4).zip(by_child.chunks(4)).filter(|(p, c)| p.iter().zip(c.iter()).any(|(x, y)| (*x as i32 - *y as i32).abs() > 8)).count();
    assert!(differing <= 20, "{differing} pixels differ between the parent's perspective and the card's own");
}

#[test]
fn a_tilted_blurred_card_is_blurred_in_its_plane() {
    let tilt = "transform:perspective(800px) rotateY(30deg)";
    let (sharp, _) = render(&page("", tilt));
    let (blurred, _) = render(&page("", &format!("{tilt};filter:blur(8px)")));

    // No sharp edge anywhere along the middle row and column (a sharp card steps 255 in one pixel; a blur of 8 px
    // ramps over ~40, under 20 a pixel even where the perspective compresses it).
    let steepest = |px: &[u8]| {
        let row = (1..W).map(|x| (lum(px, x, H / 2) - lum(px, x - 1, H / 2)).abs());
        let col = (1..H).map(|y| (lum(px, W / 2, y) - lum(px, W / 2, y - 1)).abs());
        row.chain(col).max().unwrap()
    };
    assert!(steepest(&sharp) > 100, "the sharp card should have a hard edge (test scene broken)");
    let step = steepest(&blurred);
    assert!(step < 40, "the blurred card has a sharp edge: a {step} step between neighbouring pixels");

    // The blur spreads the card, it neither cuts it to a sliver nor loses it: about the same light overall (within
    // 20 %: the frame is display-encoded, so a blur done in linear light reads a little brighter at the ramps), and
    // its middle still white.
    let total = |px: &[u8]| px.chunks(4).map(|p| p[0] as f64).sum::<f64>();
    let (s, b) = (total(&sharp), total(&blurred));
    assert!((b / s - 1.0).abs() < 0.2, "blurred card's light {b} vs the sharp card's {s}");
    assert!(lum(&blurred, W / 2, H / 2) > 240, "the blurred card's middle is {}", lum(&blurred, W / 2, H / 2));
}

/// Any layer on a tilted element (here `opacity`) is drawn: a `saveLayer` opened under perspective came out empty,
/// so a tilted card with `opacity: .9`, `isolation` or a blending child vanished (anyrender_skia `push_layer`).
#[test]
fn a_tilted_card_with_opacity_is_drawn() {
    let tilt = "transform:perspective(800px) rotateY(30deg)";
    let (px, _) = render(&page("", &format!("{tilt};opacity:.9")));
    let mid = lum(&px, W / 2, H / 2);
    assert!((200..255).contains(&mid), "the card's middle is {mid}: not drawn at 90 % white");
}
