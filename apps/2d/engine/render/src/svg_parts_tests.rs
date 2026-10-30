//! The parts of an inline `<svg>` named by the layer attribute are measured where they are painted (boxes.rs
//! `svg_parts`): through the viewBox, a part's own transform and the svg's place; an SVG `<text>` has `glyphs`.

use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};
use serde_json::Value;

const W: u32 = 800;
const H: u32 = 400;

fn boxes(body: &str) -> Value {
    let html = format!("<!DOCTYPE html><html><head></head><body style=\"margin:0\">{body}</body></html>");
    let mut doc = HtmlDocument::from_html(&html, DocumentConfig { viewport: Some(Viewport::new(W, H, 1.0, ColorScheme::Light)), ..Default::default() });
    doc.resolve(0.0);
    crate::boxes::boxes(&doc, W, H)
}

fn find<'a>(b: &'a Value, id: &str) -> &'a Value {
    b.as_array().unwrap().iter().find(|x| x["id"] == id).unwrap_or_else(|| panic!("no box for {id}: {b}"))
}

fn rect(v: &Value) -> [f64; 4] {
    let r: Vec<f64> = v.as_array().unwrap().iter().map(|x| x.as_f64().unwrap()).collect();
    [r[0], r[1], r[2], r[3]]
}

#[test]
fn svg_parts_are_measured_where_painted() {
    // A 400 × 200 svg at (100, 50) with a viewBox at half size: user units × 2.
    let b = boxes(
        "<svg data-layer-id=\"pic\" style=\"position:absolute;left:100px;top:50px\" width=\"400\" height=\"200\" viewBox=\"0 0 200 100\">\
         <g data-layer-id=\"arm\" id=\"arm\" transform=\"translate(150 0)\"><rect data-layer-id=\"hand\" id=\"hand\" x=\"0\" y=\"10\" width=\"80\" height=\"20\"/></g>\
         <text data-layer-id=\"label\" id=\"label\" x=\"10\" y=\"80\" font-size=\"20\">Hi</text>\
         <circle id=\"plain\" cx=\"10\" cy=\"10\" r=\"5\"/></svg>",
    );
    let hand = rect(&find(&b, "hand")["box"]);
    // x: 100 + 150 * 2 = 400 .. 100 + 230 * 2 = 560; y: 50 + 10 * 2 = 70 .. 50 + 30 * 2 = 110
    assert!((hand[0] - 400.0).abs() < 1.0 && (hand[2] - 560.0).abs() < 1.0, "{hand:?}");
    assert!((hand[1] - 70.0).abs() < 1.0 && (hand[3] - 110.0).abs() < 1.0, "{hand:?}");
    assert_eq!(find(&b, "hand")["parent"], "arm");
    assert_eq!(find(&b, "arm")["parent"], "pic");
    assert!(find(&b, "label")["glyphs"].is_array(), "an svg <text> has glyphs");
    assert!(b.as_array().unwrap().iter().all(|x| x["id"] != "plain"), "a part without the layer attribute is not listed");
}
