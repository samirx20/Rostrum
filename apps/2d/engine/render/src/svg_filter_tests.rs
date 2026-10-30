//! SVG filters are drawn (2D SVG filters, 2026-10-30): `filter=` on shapes, groups and text inside an `<svg>` (the SVG
//! painter drew none), each primitive in its `color-interpolation-filters` space (linearRGB unless sRGB, as Chrome; both
//! the SVG painter and HTML's `filter: url(#id)`), feDropShadow and feBlend (HTML's url filters skipped them), the
//! filter region and subregions, and a blur's two σ.

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

/// An `<svg>` filling the stage with `defs` and `body`.
fn svg(defs: &str, body: &str) -> Vec<u8> {
    paint(&format!(
        "<svg width=\"{W}\" height=\"{H}\" viewBox=\"0 0 {W} {H}\" style=\"position:absolute;left:0;top:0\"><defs>{defs}</defs>{body}</svg>"
    ))
}

fn at(px: &[u8], x: u32, y: u32) -> [u8; 3] {
    let i = ((y * W + x) * 4) as usize;
    [px[i], px[i + 1], px[i + 2]]
}

fn near(v: u8, want: u8, what: &str) {
    assert!((v as i32 - want as i32).abs() <= 10, "{what}: {v}, want {want}");
}

#[test]
fn a_blur_on_a_shape_inside_an_svg_spreads_it() {
    let px = svg("<filter id=\"f\"><feGaussianBlur stdDeviation=\"6\"/></filter>", "<rect x=\"60\" y=\"20\" width=\"80\" height=\"60\" fill=\"#fff\" filter=\"url(#f)\"/>");
    assert!(at(&px, 56, 50)[0] > 40, "4 px outside the blurred rectangle: {:?}", at(&px, 56, 50));
    assert!(at(&px, 100, 50)[0] > 245, "its middle stays white: {:?}", at(&px, 100, 50));
    assert!(at(&px, 20, 50)[0] < 3, "far outside: {:?}", at(&px, 20, 50));
}

#[test]
fn primitives_work_in_linear_rgb_unless_told_srgb() {
    // Pure red desaturated: luminance 0.213 in linear light (≈ 127 once encoded), 0.213 × 255 ≈ 54 in sRGB values.
    let grey = |space: &str| {
        let px = svg(
            &format!("<filter id=\"f\" {space}><feColorMatrix type=\"saturate\" values=\"0\"/></filter>"),
            "<rect width=\"200\" height=\"100\" fill=\"#ff0000\" filter=\"url(#f)\"/>",
        );
        at(&px, 100, 50)
    };
    near(grey("")[1], 127, "linearRGB (the default)");
    near(grey("color-interpolation-filters=\"sRGB\"")[1], 54, "sRGB");
}

#[test]
fn an_html_url_filter_works_in_linear_rgb_too() {
    let px = paint(
        "<svg width=\"0\" height=\"0\" style=\"position:absolute\"><defs><filter id=\"f\"><feColorMatrix type=\"saturate\" values=\"0\"/></filter></defs></svg>\
         <div style=\"position:absolute;left:0;top:0;width:200px;height:100px;background:#ff0000;filter:url(#f)\"></div>",
    );
    near(at(&px, 100, 50)[1], 127, "desaturated red");
}

#[test]
fn a_drop_shadow_falls_where_offset_inside_an_svg_and_on_html() {
    let shadow = "<filter id=\"f\" x=\"-50%\" y=\"-50%\" width=\"200%\" height=\"200%\"><feDropShadow dx=\"20\" dy=\"0\" stdDeviation=\"1\" flood-color=\"#00ff00\"/></filter>";
    let px = svg(shadow, "<rect x=\"40\" y=\"30\" width=\"60\" height=\"40\" fill=\"#ff0000\" filter=\"url(#f)\"/>");
    near(at(&px, 70, 50)[0], 255, "the shape on top");
    near(at(&px, 110, 50)[1], 255, "its green shadow 20 px right");
    let px = paint(&format!(
        "<svg width=\"0\" height=\"0\" style=\"position:absolute\"><defs>{shadow}</defs></svg>\
         <div style=\"position:absolute;left:40px;top:30px;width:60px;height:40px;background:#ff0000;filter:url(#f)\"></div>"
    ));
    near(at(&px, 110, 50)[1], 255, "an HTML element's feDropShadow");
}

#[test]
fn the_filter_region_cuts_what_the_filter_makes() {
    // A flood under the shape, inside a user-space region on the left half only.
    let px = svg(
        "<filter id=\"f\" filterUnits=\"userSpaceOnUse\" x=\"0\" y=\"0\" width=\"100\" height=\"100\"><feFlood flood-color=\"#0000ff\"/>\
         <feMerge><feMergeNode/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter>",
        "<g filter=\"url(#f)\"><rect x=\"80\" y=\"40\" width=\"40\" height=\"20\" fill=\"#ff0000\"/></g>",
    );
    near(at(&px, 20, 20)[2], 255, "the flood inside the region");
    near(at(&px, 150, 20)[2], 0, "nothing past the region");
    near(at(&px, 90, 50)[0], 255, "the shape inside the region");
    near(at(&px, 110, 50)[0], 0, "the shape cut at the region's edge");
}

#[test]
fn fe_blend_multiplies_two_inputs() {
    let px = svg(
        "<filter id=\"f\" color-interpolation-filters=\"sRGB\"><feFlood flood-color=\"#808080\" result=\"g\"/><feBlend in=\"SourceGraphic\" in2=\"g\" mode=\"multiply\"/></filter>",
        "<rect width=\"200\" height=\"100\" fill=\"#ffffff\" filter=\"url(#f)\"/>",
    );
    near(at(&px, 100, 50)[0], 128, "white times mid grey");
}

#[test]
fn a_blur_with_two_deviations_spreads_only_down() {
    let px = svg("<filter id=\"f\"><feGaussianBlur stdDeviation=\"0 8\"/></filter>", "<rect x=\"60\" y=\"30\" width=\"80\" height=\"40\" fill=\"#fff\" filter=\"url(#f)\"/>");
    assert!(at(&px, 100, 25)[0] > 40, "above the shape: {:?}", at(&px, 100, 25));
    assert!(at(&px, 55, 50)[0] < 3, "beside the shape: {:?}", at(&px, 55, 50));
}

#[test]
fn turbulence_fills_its_region_with_noise() {
    let px = svg(
        "<filter id=\"f\" x=\"0\" y=\"0\" width=\"100%\" height=\"100%\"><feTurbulence type=\"fractalNoise\" baseFrequency=\"0.05\" numOctaves=\"2\"/></filter>",
        "<rect width=\"200\" height=\"100\" filter=\"url(#f)\"/>",
    );
    let reds: Vec<u8> = (0..20).map(|i| at(&px, 10 + i * 9, 50)[0]).collect();
    let (lo, hi) = (reds.iter().min().unwrap(), reds.iter().max().unwrap());
    assert!(hi - lo > 30, "noise varies across the row: {reds:?}");
}
