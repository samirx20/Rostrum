//! A frame is a function of its time alone (rule 5, H7): the same page drawn by a fresh GPU painter (cold) and by
//! one that drew other frames first (warm) gives the same bytes. Before H7, big text drawn from Skia's glyph atlas
//! differed by 1–2 levels at letter edges depending on what the atlas held (painter.rs `gl_context`).

use std::sync::Arc;

use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};
use parley::fontique::Blob;

use crate::painter::Painter;

/// Roboto Flex (SIL OFL 1.1, tests/fonts/RobotoFlex-OFL.txt), a variable font: each weight is its own glyph set.
const FONT: &[u8] = include_bytes!("../tests/fonts/RobotoFlex.ttf");
const W: u32 = 1280;
const H: u32 = 720;

/// Lines of text from small (atlas) to title size (outlines), at one weight, shifted down by `dy` px.
fn page(weight: u32, dy: f32) -> HtmlDocument {
    let mut font_ctx = parley::FontContext::new();
    font_ctx.collection.register_fonts(Blob::new(Arc::new(FONT) as _), None);
    let lines: String = [14, 20, 28, 40, 72, 160, 230]
        .iter()
        .map(|px| format!("<div style=\"font-size:{px}px;line-height:1\">Meridian {px}</div>"))
        .collect();
    let html = format!(
        "<!DOCTYPE html><html><head></head><body style=\"margin:0;background:#101018\">\
         <div style=\"position:absolute;left:10.3px;top:{dy}px;white-space:nowrap;color:#f4f6fb;font-family:'Roboto Flex';font-weight:{weight};letter-spacing:-0.02em\">{lines}</div>\
         </body></html>"
    );
    let config = DocumentConfig { viewport: Some(Viewport::new(W, H, 1.0, ColorScheme::Light)), font_ctx: Some(font_ctx), ..Default::default() };
    let mut doc = HtmlDocument::from_html(&html, config);
    doc.resolve(0.0);
    doc
}

fn draw(painter: &mut Painter, weight: u32, dy: f32) -> Vec<u8> {
    let mut doc = page(weight, dy);
    painter.paint(false, |scene| blitz_paint::paint_scene(scene, &mut doc, 1.0, W, H, 0, 0)).unwrap();
    painter.read()
}

#[test]
fn a_frame_is_the_same_whatever_was_drawn_before() {
    let cold = draw(&mut Painter::gpu(W, H, None).expect("a GPU painter"), 680, 4.0);
    let mut warm = Painter::gpu(W, H, None).expect("a GPU painter");
    for (k, weight) in [400, 450, 520, 600, 640, 700].into_iter().enumerate() {
        draw(&mut warm, weight, k as f32 * 3.7);
    }
    let again = draw(&mut warm, 680, 4.0);
    let differ = cold.iter().zip(&again).filter(|(a, b)| a != b).count();
    assert_eq!(differ, 0, "{differ} bytes differ between the frame drawn cold and after other frames");
}
