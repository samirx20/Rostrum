//! Properties Stylo for Servo does not parse, set from a stylesheet, reach the paint (H5, PATCHES.md round 14:
//! blitz_dom::css_shim). `background-clip: text` paints the background only through the letters (it used to fill
//! the whole box) and does not inherit; `-webkit-text-stroke` outlines the letters and inherits (it was read from
//! the inline style only, so a stylesheet rule vanished).

use std::sync::Arc;

use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};
use parley::fontique::Blob;

/// Roboto Flex (SIL OFL 1.1, apps/2d/engine/fonts/RobotoFlex-OFL.txt), so the glyphs are the same on every machine.
const FONT: &[u8] = include_bytes!("../../fonts/RobotoFlex.ttf");
const W: u32 = 400;
const H: u32 = 160;
const TEXT: &str = "font-family:'Roboto Flex';font-size:120px;font-weight:900;line-height:160px;white-space:nowrap";

/// The page, painted on the CPU: RGBA8 rows.
fn paint(css: &str, body: &str) -> Vec<u8> {
    let mut font_ctx = parley::FontContext::new();
    font_ctx.collection.register_fonts(Blob::new(Arc::new(FONT) as _), None);
    let html = format!("<!DOCTYPE html><html><head><style>{css}</style></head><body style=\"margin:0;background:#000\">{body}</body></html>");
    let config = DocumentConfig { viewport: Some(Viewport::new(W, H, 1.0, ColorScheme::Light)), font_ctx: Some(font_ctx), ..Default::default() };
    let mut doc = HtmlDocument::from_html(&html, config);
    doc.resolve(0.0);
    let mut painter = crate::painter::Painter::cpu(W, H, None).unwrap();
    painter.paint(false, |scene| blitz_paint::paint_scene(scene, &mut doc, 1.0, W, H, 0, 0)).unwrap();
    let mut px = vec![];
    crate::color::output(&crate::color::Spec::default(), &painter.read().unwrap(), W, false, false, 0, &mut px);
    px
}

fn at(px: &[u8], x: u32, y: u32) -> [u8; 3] {
    let i = ((y * W + x) * 4) as usize;
    [px[i], px[i + 1], px[i + 2]]
}

/// The lit pixels (any channel over 64) in columns x0..x1: their count and mean colour.
fn lit(px: &[u8], x0: u32, x1: u32) -> (usize, [f64; 3]) {
    let (mut n, mut sum) = (0, [0.0; 3]);
    for y in 0..H {
        for x in x0..x1 {
            let c = at(px, x, y);
            if c.iter().any(|v| *v > 64) {
                n += 1;
                (0..3).for_each(|k| sum[k] += c[k] as f64);
            }
        }
    }
    (n, sum.map(|s| s / n.max(1) as f64))
}

#[test]
fn a_stylesheet_background_clip_text_paints_the_gradient_only_through_the_letters() {
    let css = format!(
        ".g {{ position:absolute; left:0; top:0; width:{W}px; height:{H}px; {TEXT}; background: linear-gradient(90deg, #ff0000, #0000ff); \
         -webkit-background-clip: text; background-clip: text; color: transparent; }}\
         .kid {{ position:absolute; left:360px; top:120px; width:30px; height:30px; background:#00ff00; }}"
    );
    let px = paint(&css, "<div class=\"g\">HHH<div class=\"kid\"></div></div>");

    // Outside the letters the page shows (before: the gradient filled the whole box).
    assert_eq!(at(&px, 3, 3), [0, 0, 0], "the box's corner, above the letters, is the page background");
    let (n, _) = lit(&px, 0, 340);
    let area = (340 * H) as usize;
    assert!(n > area / 20 && n < area * 7 / 10, "letters only: {n} of {area} pixels lit (all lit: the box is filled; none: the text mask is empty)");
    // The gradient spans the box, through the letters: red on the left, blue towards the right.
    let (_, left) = lit(&px, 0, 100);
    let (_, right) = lit(&px, 220, 300);
    assert!(left[0] > left[2] + 60.0, "left letters are red-ish: {left:?}");
    assert!(right[2] > right[0] + 30.0, "right letters are blue-ish: {right:?}");
    // background-clip does not inherit: the child's own background fills its box.
    let kid = at(&px, 375, 135);
    assert!(kid[1] > 200 && kid[0] < 40 && kid[2] < 40, "the child keeps its box background: {kid:?}");
}

#[test]
fn a_stylesheet_text_stroke_outlines_the_letters_and_inherits() {
    let css = format!(".o {{ position:absolute; left:0; top:0; {TEXT}; color: transparent; -webkit-text-stroke: 6px #ffffff; }}");
    // The text sits in a child span: the outline reaches it by inheritance.
    let px = paint(&css, "<div class=\"o\"><span>HH</span></div>");
    let white = (0..H).flat_map(|y| (0..W).map(move |x| (x, y))).filter(|&(x, y)| at(&px, x, y).iter().all(|v| *v > 200)).count();
    assert!(white > 500, "the outline is drawn: {white} white pixels (0: the stylesheet's -webkit-text-stroke was dropped)");
}

/// The shim's copy goes after a declaration's whole value, never inside a function in it: a copy put inside
/// `blur(` broke every rule after it, so a whole stage's stylesheet silently vanished.
#[test]
fn the_shim_copy_follows_the_whole_value_and_keeps_the_rest_of_the_sheet() {
    let css = ".a{filter:blur(2px) saturate(1.5);width:10px}.b{background:linear-gradient(red,blue) text;color:red}";
    let out = blitz_dom::css_shim::rewrite_stylesheet(css);
    assert_eq!(
        out,
        ".a{filter:blur(2px) saturate(1.5);--rostrum-filter:blur(2px) saturate(1.5);width:10px}\
         .b{background:linear-gradient(red,blue) border-box;--rostrum-background-clip:text;color:red}"
    );
}
