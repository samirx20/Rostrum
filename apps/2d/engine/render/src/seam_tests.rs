//! F7 rolling-shutter bands (R19): a source cut into horizontal windows (`overflow: hidden` inside a transformed box),
//! each band through its own matrix, the next band drawn over the last one's 2 px overrun. Inside each band the video
//! layer draws its dark background, then its frame over it. An anti-aliased clip edge applied to each of those draws
//! on its own let the background show through the frame at the band's top edge: a dark hairline per seam. On flat
//! colour no seam may show.

use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};

const W: u32 = 320;
const H: u32 = 240;
const N: usize = 8;

/// The picture as a video layer draws it: a dark background, the frame (flat grey here) over it.
fn media() -> String {
    format!(
        "<div style=\"position:absolute;left:0;top:0;width:{W}px;height:{H}px;overflow:hidden;background-color:#18181b\">\
         <div style=\"width:100%;height:100%;background:#808080\"></div></div>"
    )
}

fn page(three_d: bool) -> String {
    let e = W.max(H) as f64;
    let (w, h) = (W as f64, H as f64);
    let mut bands = String::new();
    for k in 0..N {
        let (y0, y1) = (k as f64 * h / N as f64, (k + 1) as f64 * h / N as f64);
        let top = if k == 0 { -e } else { y0 - 0.5 };
        let bottom = if k == N - 1 { h + e } else { y1 + 2.0 };
        // Each band a slightly different zoom, rotation and shift (a rolling-shutter correction), off the pixel grid.
        let (s, r, tx, ty) = (1.02 + 0.001 * k as f64, 0.01 + 0.0005 * k as f64, -3.37 + 0.61 * k as f64, -2.23 + 0.11 * k as f64);
        let m = if three_d { format!("matrix3d({s}, {}, 0, 0, {r}, {s}, 0, 0, 0, 0, 1, 0, {tx}, {ty}, 0, 1)", -r) } else { format!("matrix({s}, {}, {r}, {s}, {tx}, {ty})", -r) };
        bands.push_str(&format!(
            "<div style=\"position:absolute;left:0;top:0;width:{w}px;height:{h}px;transform:{m};transform-origin:0 0\">\
             <div style=\"position:absolute;left:{}px;top:{top}px;width:{}px;height:{}px;overflow:hidden\">\
             <div style=\"position:absolute;left:{e}px;top:{}px;width:{w}px;height:{h}px\">{}</div></div></div>",
            -e,
            w + 2.0 * e,
            bottom - top,
            -top,
            media()
        ));
    }
    format!("<!DOCTYPE html><html><head></head><body style=\"margin:0;background:#000\"><div id=\"rostrum-stage\"><div style=\"position:absolute;left:0;top:0;width:{W}px;height:{H}px;overflow:hidden\">{bands}</div></div></body></html>")
}

fn render(gpu: bool, three_d: bool, working: &str) -> Vec<u8> {
    let spec = crate::color::Spec::parse(&serde_json::json!({ "working": working })).unwrap();
    let mut doc = HtmlDocument::from_html(&page(three_d), DocumentConfig { viewport: Some(Viewport::new(W, H, 1.0, ColorScheme::Light)), ..Default::default() });
    doc.resolve(0.0);
    let mut painter = if gpu { crate::painter::Painter::gpu(W, H, spec.surface_space()) } else { crate::painter::Painter::cpu(W, H, spec.surface_space()) }.unwrap();
    painter.paint(false, |scene| blitz_paint::paint_scene(scene, &mut doc, 1.0, W, H, 0, 0)).unwrap();
    let mut px = vec![];
    crate::color::output(&spec, &painter.read().unwrap(), W, false, false, 0, &mut px);
    px
}

/// Columns across the middle, rows 20 .. H-20 (inside the picture): the darkest pixel and the median.
fn darkest(px: &[u8]) -> ((usize, usize), u8, u8) {
    let mut all = vec![];
    for x in (40..W as usize - 40).step_by(20) {
        for y in 20..H as usize - 20 {
            all.push(((x, y), px[(y * W as usize + x) * 4 + 1]));
        }
    }
    let (at, v) = *all.iter().min_by_key(|c| c.1).unwrap();
    all.sort_by_key(|c| c.1);
    (at, v, all[all.len() / 2].1)
}

#[test]
fn rolling_shutter_bands_leave_no_seam_on_flat_colour() {
    let gpu_ok = crate::painter::Painter::gpu(8, 8, None).is_ok();
    for gpu in [false, true] {
        if gpu && !gpu_ok {
            continue;
        }
        for three_d in [false, true] {
            for working in ["display", "acescg"] {
                let px = render(gpu, three_d, working);
                let (at, v, median) = darkest(&px);
                let name = format!("{} {} {working}", if gpu { "gpu" } else { "cpu" }, if three_d { "matrix3d" } else { "matrix" });
                eprintln!("{name}: darkest {at:?} = {v}, median {median}");
                assert!(median as i32 - v as i32 <= 2, "{name}: pixel {at:?} is {v}, the picture {median}: a seam");
            }
        }
    }
}

/// A clip on the pixel grid and one off it draw the same flat inside; off the grid the edge is still soft.
#[test]
fn a_clip_off_the_pixel_grid_keeps_its_soft_edge() {
    let html = "<!DOCTYPE html><html><head></head><body style=\"margin:0;background:#000\"><div id=\"rostrum-stage\">\
        <div style=\"position:absolute;left:10px;top:10px;width:40px;height:40px;overflow:hidden;transform:translate(0.5px, 0.5px)\"><div style=\"margin:-10px;width:60px;height:60px;background:#fff\"></div></div>\
        <div style=\"position:absolute;left:70px;top:10px;width:40px;height:40px;overflow:hidden\"><div style=\"width:60px;height:60px;background:#fff\"></div></div>\
        </div></body></html>";
    let mut doc = HtmlDocument::from_html(html, DocumentConfig { viewport: Some(Viewport::new(120, 60, 1.0, ColorScheme::Light)), ..Default::default() });
    doc.resolve(0.0);
    let mut painter = crate::painter::Painter::cpu(120, 60, None).unwrap();
    painter.paint(false, |scene| blitz_paint::paint_scene(scene, &mut doc, 1.0, 120, 60, 0, 0)).unwrap();
    let mut px = vec![];
    crate::color::output(&crate::color::Spec::default(), &painter.read().unwrap(), 120, false, false, 0, &mut px);
    let g = |x: usize, y: usize| px[(y * 120 + x) * 4 + 1];
    assert_eq!(g(30, 30), 255, "inside the soft clip");
    assert!((100..200).contains(&g(10, 30)), "the soft clip's half-covered left column: {}", g(10, 30));
    assert_eq!(g(9, 30), 0, "outside the soft clip");
    assert_eq!(g(90, 30), 255, "inside the grid clip");
    assert_eq!(g(69, 30), 0, "outside the grid clip");
    assert_eq!(g(70, 30), 255, "the grid clip's first column");
}
