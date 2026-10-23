//! A 3D-tilted, clipping panel (perspective + rotateY + overflow: hidden, the saas-launch panel) draws its
//! children where the tilt puts them, and `boxes` reports them there. Its children's untilted boxes lie past
//! the frame's right edge: the painter used to cull them against the frame in that untilted plane (round 12).

use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};

const W: u32 = 1200;
const H: u32 = 600;
// The panel: left 700, top 300 (its centre after translate(-50%, -50%)), 600 × 300, rotateY(-25deg) in perspective(900px).
const PX: f64 = 700.0;
const PY: f64 = 300.0;
const PW: f64 = 600.0;
const PH: f64 = 300.0;
const D: f64 = 900.0;
const DEG: f64 = -25.0;

fn page() -> String {
    let child = |id: &str, x: u32, y: u32, color: &str| format!("<div data-layer-id=\"{id}\" style=\"position:absolute;left:{x}px;top:{y}px;width:60px;height:60px;background:{color}\"></div>");
    format!(
        "<!DOCTYPE html><html><head></head><body style=\"margin:0;background:#000\"><div id=\"rostrum-stage\">\
         <div data-layer-id=\"panel\" style=\"position:absolute;left:{PX}px;top:{PY}px;width:{PW}px;height:{PH}px;transform:translateX(-50%) translateY(-50%) perspective({D}px) rotateY({DEG}deg);transform-style:preserve-3d;overflow:hidden;background:#202020\">{}{}{}</div>\
         </div></body></html>",
        child("left", 20, 20, "#00ff00"),
        child("right", 520, 120, "#ff0000"),
        child("cut", 570, 220, "#0000ff"), // half past the panel's right edge: clipped by it
    )
}

/// Where a point of the panel lands (CSS: rotateY about the centre, then perspective, centre at (PX, PY)).
fn project(x: f64, y: f64) -> (f64, f64) {
    let (cx, cy) = (PW / 2.0, PH / 2.0);
    let a = DEG.to_radians();
    let (dx, dz) = ((x - cx) * a.cos(), -(x - cx) * a.sin());
    let s = D / (D - dz);
    (PX + dx * s, PY + (y - cy) * s)
}

fn expected(x0: f64, y0: f64, x1: f64, y1: f64) -> [f64; 4] {
    let pts = [project(x0, y0), project(x1, y0), project(x0, y1), project(x1, y1)];
    let (xs, ys) = (pts.map(|p| p.0), pts.map(|p| p.1));
    [xs.iter().cloned().fold(f64::INFINITY, f64::min), ys.iter().cloned().fold(f64::INFINITY, f64::min), xs.iter().cloned().fold(f64::NEG_INFINITY, f64::max), ys.iter().cloned().fold(f64::NEG_INFINITY, f64::max)]
}

#[test]
fn a_tilted_clipping_panel_draws_and_reports_its_children_where_the_tilt_puts_them() {
    let mut doc = HtmlDocument::from_html(&page(), DocumentConfig { viewport: Some(Viewport::new(W, H, 1.0, ColorScheme::Light)), ..Default::default() });
    doc.resolve(0.0);

    // Boxes: projected through the tilt, within a pixel of the CSS geometry.
    let boxes = crate::boxes::boxes(&doc, W, H);
    let get = |id: &str| -> [f64; 4] {
        let b = boxes.as_array().unwrap().iter().find(|b| b["id"] == id).unwrap_or_else(|| panic!("no box for #{id}"));
        let v: Vec<f64> = b["box"].as_array().unwrap().iter().map(|v| v.as_f64().unwrap()).collect();
        [v[0], v[1], v[2], v[3]]
    };
    for (id, want) in [("panel", expected(0.0, 0.0, PW, PH)), ("left", expected(20.0, 20.0, 80.0, 80.0)), ("right", expected(520.0, 120.0, 580.0, 180.0))] {
        let got = get(id);
        assert!(got.iter().zip(want).all(|(g, w)| (g - w).abs() < 1.0), "#{id}: box {got:?}, CSS puts it at {want:?}");
    }
    assert!(expected(520.0, 0.0, 580.0, 0.0)[2] < W as f64 && 700.0 + 520.0 > W as f64, "the scene must have the right child's untilted box past the frame");

    // Pixels: each child's colour at the centre of where it lands; the clipped one only inside the panel.
    let mut painter = crate::painter::Painter::cpu(W, H, None).unwrap();
    painter.paint(false, |scene| blitz_paint::paint_scene(scene, &mut doc, 1.0, W, H, 0, 0)).unwrap();
    let mut px = vec![];
    crate::color::output(&crate::color::Spec::default(), &painter.read().unwrap(), W, false, false, 0, &mut px);
    let at = |(x, y): (f64, f64)| {
        let i = (y.round() as usize * W as usize + x.round() as usize) * 4;
        [px[i], px[i + 1], px[i + 2]]
    };
    let near = |c: [u8; 3], want: [u8; 3]| c.iter().zip(want).all(|(a, b)| (*a as i32 - b as i32).abs() < 24);
    for (name, p, want) in [
        ("left", project(50.0, 50.0), [0, 255, 0]),
        ("right", project(550.0, 150.0), [255, 0, 0]),
        ("cut (inside the panel)", project(585.0, 250.0), [0, 0, 255]),
        ("cut (past the panel's edge, clipped)", project(615.0, 250.0), [0, 0, 0]),
    ] {
        assert!(near(at(p), want), "{name} at {p:?}: {:?}, want {want:?}", at(p));
    }
}
