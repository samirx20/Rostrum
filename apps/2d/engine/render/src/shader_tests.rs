//! A shader that does not compile fails the frame (AGENTS.md rule 6): the paint returns an error naming the
//! effect and Skia's message, never a frame drawn without it.

use crate::painter::Painter;
use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};

/// Paints a red square under an SVG filter whose one primitive is the given SkSL, on the CPU.
fn paint_with(effect: &str, program: &str) -> Result<(), String> {
    let html = format!(
        "<!DOCTYPE html><html><body style=\"margin:0;background:#000\"><svg width=\"0\" height=\"0\" style=\"position:absolute\"><filter id=\"f\" x=\"0\" y=\"0\" width=\"100%\" height=\"100%\">\
         <feshader effect=\"{effect}\" in=\"SourceGraphic\" result=\"o\" radius=\"0\" grow=\"0\" uniforms=\"\">{program}</feshader></filter></svg>\
         <div style=\"width:20px;height:20px;background:#f00;filter:url(#f)\"></div></body></html>"
    );
    let mut doc = HtmlDocument::from_html(&html, DocumentConfig { viewport: Some(Viewport::new(40, 40, 1.0, ColorScheme::Light)), ..Default::default() });
    doc.resolve(0.0);
    let mut painter = Painter::cpu(40, 40, None).unwrap();
    painter.paint(false, |scene| blitz_paint::paint_scene(scene, &mut doc, 1.0, 40, 40, 0, 0))
}

#[test]
fn a_shader_that_links_paints() {
    paint_with("passthrough", "uniform shader src; half4 main(float2 p) { return src.eval(p); }").unwrap();
    paint_with("tint", "half4 main(half4 c) { return c; }").unwrap();
}

#[test]
fn a_shader_that_does_not_compile_fails_the_frame_naming_the_effect_and_skia_s_message() {
    let err = paint_with("halftone", "uniform shader src; half4 main(float2 p) { return no_such_function(src.eval(p)); }").unwrap_err();
    assert!(err.contains("the halftone effect's shader failed to compile: "), "{err}");
    assert!(err.contains("no_such_function"), "Skia's own message is kept: {err}");
    // A colour program (`half4 main(half4 …)`: a LUT, a grade) takes the other path and fails the same way.
    let err = paint_with("grade", "half4 main(half4 c) { return missing(c); }").unwrap_err();
    assert!(err.contains("the grade effect's shader failed to compile: "), "{err}");
    assert!(err.contains("missing"), "{err}");
    // The error is taken with the frame: the next, healthy one paints.
    paint_with("passthrough", "uniform shader src; half4 main(float2 p) { return src.eval(p); }").unwrap();
}

#[test]
fn the_grain_effect_s_shader_links() {
    paint_with("grain", crate::scene::grain::PROGRAM).unwrap();
}

#[test]
fn the_rough_effect_s_shader_links() {
    paint_with("rough", crate::scene::rough::PROGRAM).unwrap();
}
