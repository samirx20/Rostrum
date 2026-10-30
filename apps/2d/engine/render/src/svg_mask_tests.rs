//! SVG masks and clip paths are drawn (2D SVG masks, 2026-10-30): inside an `<svg>`, `mask=` (luminance and alpha,
//! region, content units) and `clip-path=` with any content (several shapes, `<text>`,
//! clipPathUnits, a clip on the clip, the clip's transform); on HTML, CSS `mask: url(#id)` and `clip-path: url(#id)`.
//! Before, the SVG painter skipped masks (the shape drawn whole) and clipped only by a single plain path (text clips
//! drew the shape whole), and a CSS url mask took a luminance filter the SVG painter never drew.

use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};

const W: u32 = 200;
const H: u32 = 100;

/// `body` on black (inside a W × H stage), painted on the CPU: RGBA8 rows.
fn paint(body: &str) -> Vec<u8> {
    let html = format!(
        "<!DOCTYPE html><html><head></head><body style=\"margin:0;background:#000\"><div style=\"position:relative;width:{W}px;height:{H}px\">{body}</div></body></html>"
    );
    let mut doc = HtmlDocument::from_html(&html, DocumentConfig { viewport: Some(Viewport::new(W, H, 1.0, ColorScheme::Light)), ..Default::default() });
    doc.resolve(0.0);
    let mut painter = crate::painter::Painter::cpu(W, H, None).unwrap();
    painter.paint(false, |scene| blitz_paint::paint_scene(scene, &mut doc, 1.0, W, H, 0, 0)).unwrap();
    let mut px = vec![];
    crate::color::output(&crate::color::Spec::default(), &painter.read().unwrap(), W, false, false, 0, &mut px);
    px
}

/// An `<svg>` filling the stage, with `defs` and a red rectangle over everything drawn with `attrs` (a mask or clip).
fn red_through(defs: &str, attrs: &str) -> Vec<u8> {
    paint(&format!(
        "<svg width=\"{W}\" height=\"{H}\" viewBox=\"0 0 {W} {H}\" style=\"position:absolute;left:0;top:0\"><defs>{defs}</defs>\
         <rect width=\"{W}\" height=\"{H}\" fill=\"#ff0000\" {attrs}/></svg>"
    ))
}

fn red(px: &[u8], x: u32, y: u32) -> u8 {
    px[((y * W + x) * 4) as usize]
}

fn near(v: u8, want: u8, what: &str) {
    assert!((v as i32 - want as i32).abs() <= 12, "{what}: {v}, want {want}");
}

#[test]
fn a_luminance_mask_lets_through_by_brightness_and_only_inside_its_shapes() {
    let px = red_through(
        "<mask id=\"m\" maskUnits=\"userSpaceOnUse\" x=\"0\" y=\"0\" width=\"200\" height=\"100\">\
         <rect x=\"0\" y=\"0\" width=\"50\" height=\"100\" fill=\"#fff\"/><rect x=\"50\" y=\"0\" width=\"50\" height=\"100\" fill=\"#fff\" fill-opacity=\"0.5\"/>\
         <rect x=\"100\" y=\"0\" width=\"50\" height=\"100\" fill=\"#0000ff\"/></mask>",
        "mask=\"url(#m)\"",
    );
    near(red(&px, 25, 50), 255, "under white");
    near(red(&px, 75, 50), 128, "under half-transparent white");
    near(red(&px, 125, 50), 18, "under blue (luminance 0.07)");
    near(red(&px, 175, 50), 0, "outside the mask's shapes");
}

#[test]
fn an_alpha_mask_reads_coverage_not_colour() {
    let px = red_through(
        "<mask id=\"m\" mask-type=\"alpha\"><rect x=\"0\" y=\"0\" width=\"100\" height=\"100\" fill=\"#000\"/>\
         <rect x=\"100\" y=\"0\" width=\"100\" height=\"100\" fill=\"#000\" fill-opacity=\"0.5\"/></mask>",
        "mask=\"url(#m)\"",
    );
    near(red(&px, 50, 50), 255, "under opaque black");
    near(red(&px, 150, 50), 128, "under half-transparent black");
}

#[test]
fn mask_content_in_object_bounding_box_units_and_the_default_region() {
    // A white circle in the shape's own 0..1 box; the default region (−10 % … 120 %) holds it.
    let px = red_through("<mask id=\"m\" maskContentUnits=\"objectBoundingBox\"><circle cx=\"0.5\" cy=\"0.5\" r=\"0.25\" fill=\"#fff\"/></mask>", "mask=\"url(#m)\"");
    near(red(&px, 100, 50), 255, "the circle's centre");
    near(red(&px, 10, 10), 0, "the corner, outside the circle");
}

#[test]
fn a_mask_on_the_mask_is_left_out_as_in_chromium() {
    let px = red_through(
        "<mask id=\"left\" maskUnits=\"userSpaceOnUse\" x=\"0\" y=\"0\" width=\"100\" height=\"100\"><rect width=\"200\" height=\"100\" fill=\"#fff\"/></mask>\
         <mask id=\"m\" mask=\"url(#left)\"><rect width=\"200\" height=\"100\" fill=\"#fff\"/></mask>",
        "mask=\"url(#m)\"",
    );
    near(red(&px, 50, 50), 255, "left half");
    near(red(&px, 150, 50), 255, "right half: Chromium ignores mask= on a <mask>");
}

#[test]
fn a_clip_of_several_shapes_keeps_each() {
    let px = red_through("<clipPath id=\"c\"><rect x=\"0\" y=\"0\" width=\"40\" height=\"100\"/><circle cx=\"150\" cy=\"50\" r=\"30\"/></clipPath>", "clip-path=\"url(#c)\"");
    near(red(&px, 20, 50), 255, "inside the rectangle");
    near(red(&px, 150, 50), 255, "inside the circle");
    near(red(&px, 90, 50), 0, "between them");
}

#[test]
fn a_clip_of_text_shows_the_shape_only_through_the_letters() {
    let px = red_through(
        "<clipPath id=\"c\"><text x=\"100\" y=\"80\" text-anchor=\"middle\" font-family=\"sans-serif\" font-weight=\"900\" font-size=\"80\">HH</text></clipPath>",
        "clip-path=\"url(#c)\"",
    );
    let lit = (0..H).flat_map(|y| (0..W).map(move |x| (x, y))).filter(|&(x, y)| red(&px, x, y) > 128).count();
    let area = (W * H) as usize;
    assert!(lit > area / 20 && lit < area / 2, "letters only: {lit} of {area} lit (all: the clip was skipped; none: the text drew nothing)");
    near(red(&px, 3, 3), 0, "the corner, outside the letters");
}

#[test]
fn clip_units_transform_and_a_clip_on_the_clip() {
    // objectBoundingBox: a circle filling the shape's box.
    let px = red_through("<clipPath id=\"c\" clipPathUnits=\"objectBoundingBox\"><circle cx=\"0.5\" cy=\"0.5\" r=\"0.5\"/></clipPath>", "clip-path=\"url(#c)\"");
    near(red(&px, 100, 50), 255, "bbox circle centre");
    near(red(&px, 5, 5), 0, "bbox circle corner");
    // The clip's own transform moves it; its clip-path cuts it further.
    let px = red_through(
        "<clipPath id=\"half\"><rect x=\"0\" y=\"0\" width=\"150\" height=\"100\"/></clipPath>\
         <clipPath id=\"c\" clip-path=\"url(#half)\" transform=\"translate(100 0)\"><rect x=\"0\" y=\"0\" width=\"100\" height=\"100\"/></clipPath>",
        "clip-path=\"url(#c)\"",
    );
    near(red(&px, 50, 50), 0, "left of the moved clip");
    near(red(&px, 125, 50), 255, "inside the moved clip and the half");
    near(red(&px, 175, 50), 0, "inside the moved clip, cut by the clip's own clip");
}

#[test]
fn css_mask_and_clip_path_by_url_on_html() {
    let defs = "<svg width=\"0\" height=\"0\" style=\"position:absolute\"><defs>\
        <mask id=\"m\" maskContentUnits=\"objectBoundingBox\"><rect width=\"0.5\" height=\"1\" fill=\"#fff\"/><rect x=\"0.5\" width=\"0.5\" height=\"1\" fill=\"#808080\"/></mask>\
        <clipPath id=\"c\" clipPathUnits=\"objectBoundingBox\"><circle cx=\"0.5\" cy=\"0.5\" r=\"0.5\"/></clipPath></defs></svg>";
    let div = |css: &str| paint(&format!("{defs}<div style=\"position:absolute;left:0;top:0;width:{W}px;height:{H}px;background:#ff0000;{css}\"></div>"));
    let px = div("mask:url(#m)");
    near(red(&px, 50, 50), 255, "mask: white half");
    near(red(&px, 150, 50), 128, "mask: grey half (luminance, not alpha)");
    let px = div("clip-path:url(#c)");
    near(red(&px, 100, 50), 255, "clip-path: centre");
    near(red(&px, 3, 3), 0, "clip-path: corner");
}
