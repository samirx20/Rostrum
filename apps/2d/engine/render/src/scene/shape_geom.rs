//! The parametric shape kinds (ENGINE_CONTRACT.md § 4 shape; design v2 SPEC § 5): arc / ring, triangle, polygon,
//! star, line, arrow and spiral, each worked out from its numbers at this frame as path data in the layer's w × h box
//! and drawn as a path (stage_path.rs), so they take fills, gradients, pictures, outlines and shadows as a path does.
//! Angles: 0° = up, clockwise. Closed outlines run clockwise on screen (arrow pieces join by the nonzero rule).
//! Line and spiral are open: drawn as a line `lineWidth` wide in the fill's paint.

use std::f64::consts::{PI, TAU};
use std::fmt::Write;

use serde_json::Value;

use super::eval::Item;

type R<T> = Result<T, String>;
type P = (f64, f64);

/// Path data written as stage_path reads it (absolute M L C Z).
#[derive(Default)]
struct D(String);

impl D {
    fn m(&mut self, p: P) { let _ = write!(self.0, "M{:.3} {:.3} ", p.0, p.1); }
    fn l(&mut self, p: P) { let _ = write!(self.0, "L{:.3} {:.3} ", p.0, p.1); }
    fn c(&mut self, a: P, b: P, p: P) { let _ = write!(self.0, "C{:.3} {:.3} {:.3} {:.3} {:.3} {:.3} ", a.0, a.1, b.0, b.1, p.0, p.1); }
    fn z(&mut self) { self.0 += "Z "; }
}

/// Drawn by stage.rs as a CSS box (rect, ellipse), or as a path from `as_path`.
pub fn is_path(it: &Item) -> bool {
    it.kind == "shape" && !matches!(it.str("shape"), "rect" | "ellipse")
}

/// The shape as a path layer: its outline in `d`, its look carried over, the path's other fields at their defaults.
pub fn as_path<'a>(it: &Item<'a>) -> R<Item<'a>> {
    let (d, open) = outline(it)?;
    let mut p = it.clone();
    p.kind = "path";
    let mut set = |f: &str, v: Value| { p.props.insert(f.into(), v); };
    set("d", d.0.trim_end().into());
    for (f, v) in [("fillRule", "nonzero"), ("cap", "butt"), ("join", "miter"), ("widthProfile", ""), ("taperAlong", "line")] {
        set(f, v.into());
    }
    for (f, v) in [("miter", 4.0), ("dash", 0.0), ("gap", 0.0), ("dashOffset", 0.0), ("trimStart", 0.0), ("trimEnd", 1.0), ("taperStart", 0.0), ("taperEnd", 0.0)] {
        set(f, v.into());
    }
    if open {
        // A line is its stroke: the fill's paint (gradient and picture too, as on an unfilled path) at `lineWidth`.
        set("stroke", it.on("filled").into());
        set("strokeColor", it.props["fill"].clone());
        set("strokeWidth", it.props["lineWidth"].clone());
        set("cap", it.props["lineCap"].clone());
        set("filled", false.into());
    }
    Ok(p)
}

/// (path data, open) of a parametric shape.
fn outline(it: &Item) -> R<(D, bool)> {
    let (w, h) = (it.num("w"), it.num("h"));
    let (cx, cy, rx, ry) = (w / 2.0, h / 2.0, w / 2.0, h / 2.0);
    let on = |a: f64, k: f64| (cx + rx * k * a.sin(), cy - ry * k * a.cos());
    let count = |f: &str| -> R<usize> {
        let n = it.num(f).round();
        if (3.0..=60.0).contains(&n) { Ok(n as usize) } else { Err(format!("{}.{f}: {n} must be 3 to 60", it.id)) }
    };
    let r = it.num("radius").max(0.0);
    let mut d = D::default();
    match it.str("shape") {
        "polygon" => {
            let n = count("sides")?;
            rounded(&mut d, &(0..n).map(|i| on(TAU * i as f64 / n as f64, 1.0)).collect::<Vec<_>>(), &vec![r; n]);
        }
        "star" => {
            let n = count("points")?;
            let inner = it.num("innerRadius").clamp(0.0, 1.0);
            let pts: Vec<P> = (0..2 * n).map(|i| on(PI * i as f64 / n as f64, if i % 2 == 0 { 1.0 } else { inner })).collect();
            let radii: Vec<f64> = (0..2 * n).map(|i| if i % 2 == 0 { r } else { it.num("innerCorner").max(0.0) }).collect();
            rounded(&mut d, &pts, &radii);
        }
        "triangle" => rounded(&mut d, &[(it.num("tip").clamp(0.0, 1.0) * w, 0.0), (w, h), (0.0, h)], &[r; 3]),
        "arc" => {
            let (a0, sweep) = (it.num("startAngle").to_radians(), it.num("sweep").clamp(-360.0, 360.0).to_radians());
            let hole = it.num("hole").clamp(0.0, 1.0);
            d.m(on(a0, 1.0));
            arc(&mut d, (cx, cy, rx, ry), 1.0, a0, a0 + sweep);
            if hole > 0.0 {
                d.l(on(a0 + sweep, hole));
                arc(&mut d, (cx, cy, rx, ry), hole, a0 + sweep, a0);
            } else {
                d.l((cx, cy));
            }
            d.z();
        }
        "line" => {
            d.m((0.0, cy));
            d.l((w, cy));
            return Ok((d, true));
        }
        "spiral" => {
            spiral(&mut d, (cx, cy, rx, ry), it.num("turns").clamp(0.05, 100.0), it.num("hole").clamp(0.0, 1.0));
            return Ok((d, true));
        }
        "arrow" => arrow(&mut d, it, w, cy),
        k => return Err(format!("{}: a {k} shape is not drawn by this engine yet", it.id)),
    }
    Ok((d, false))
}

/// A closed outline through `pts`, each corner rounded by its radius (a circular fillet, shrunk to fit the edges).
fn rounded(d: &mut D, pts: &[P], radii: &[f64]) {
    let n = pts.len();
    for i in 0..n {
        let (a, v, b) = (pts[(i + n - 1) % n], pts[i], pts[(i + 1) % n]);
        let unit = |p: P| { let l = (p.0 - v.0).hypot(p.1 - v.1).max(1e-9); ((p.0 - v.0) / l, (p.1 - v.1) / l, l) };
        let ((ua0, ua1, la), (ub0, ub1, lb)) = (unit(a), unit(b));
        let theta = (ua0 * ub0 + ua1 * ub1).clamp(-1.0, 1.0).acos();
        let cut = if radii[i] > 0.0 && theta > 1e-6 && theta < PI - 1e-6 { (radii[i] / (theta / 2.0).tan()).min(la.min(lb) / 2.0) } else { 0.0 };
        let p_in = (v.0 + ua0 * cut, v.1 + ua1 * cut);
        if i == 0 { d.m(p_in) } else { d.l(p_in) }
        if cut > 0.0 {
            // The arc turns by π − θ; its radius is the fillet's, shrunk with the cut.
            let k = 4.0 / 3.0 * ((PI - theta) / 4.0).tan() * cut * (theta / 2.0).tan();
            d.c((p_in.0 - ua0 * k, p_in.1 - ua1 * k), (v.0 + ub0 * (cut - k), v.1 + ub1 * (cut - k)), (v.0 + ub0 * cut, v.1 + ub1 * cut));
        }
    }
    d.z();
}

/// An elliptical arc (the box's ellipse scaled by `k`) from angle a0 to a1, as cubics of at most 90°; the pen is at a0.
fn arc(d: &mut D, (cx, cy, rx, ry): (f64, f64, f64, f64), k: f64, a0: f64, a1: f64) {
    let n = ((a1 - a0).abs() / (PI / 2.0)).ceil().max(1.0) as usize;
    let step = (a1 - a0) / n as f64;
    let h = 4.0 / 3.0 * (step / 4.0).tan();
    let at = |a: f64| (cx + rx * k * a.sin(), cy - ry * k * a.cos());
    let tan = |a: f64| (rx * k * a.cos(), ry * k * a.sin());
    for i in 0..n {
        let (s, e) = (a0 + step * i as f64, a0 + step * (i + 1) as f64);
        let (p0, p1, t0, t1) = (at(s), at(e), tan(s), tan(e));
        d.c((p0.0 + t0.0 * h, p0.1 + t0.1 * h), (p1.0 - t1.0 * h, p1.1 - t1.1 * h), p1);
    }
}

/// An Archimedean spiral out from `hole` × the box's ellipse to its edge over `turns` turns, 16 cubics a turn.
fn spiral(d: &mut D, (cx, cy, rx, ry): (f64, f64, f64, f64), turns: f64, hole: f64) {
    let end = turns * TAU;
    let rho = |a: f64| hole + (1.0 - hole) * a / end;
    let at = |a: f64| (cx + rx * rho(a) * a.sin(), cy - ry * rho(a) * a.cos());
    let tan = |a: f64| {
        let dr = (1.0 - hole) / end;
        (rx * (dr * a.sin() + rho(a) * a.cos()), ry * (-dr * a.cos() + rho(a) * a.sin()))
    };
    let n = (turns * 16.0).ceil().max(2.0) as usize;
    let step = end / n as f64;
    d.m(at(0.0));
    for i in 0..n {
        let (s, e) = (step * i as f64, step * (i + 1) as f64);
        let (p0, p1, t0, t1) = (at(s), at(e), tan(s), tan(e));
        d.c((p0.0 + t0.0 * step / 3.0, p0.1 + t0.1 * step / 3.0), (p1.0 - t1.0 * step / 3.0, p1.1 - t1.1 * step / 3.0), p1);
    }
}

/// A closed polygon, turned clockwise on screen so overlapping pieces join (nonzero).
fn poly(d: &mut D, pts: &[P]) {
    let area: f64 = (0..pts.len()).map(|i| { let (a, b) = (pts[i], pts[(i + 1) % pts.len()]); a.0 * b.1 - b.0 * a.1 }).sum();
    let mut pts = pts.to_vec();
    if area < 0.0 {
        pts.reverse();
    }
    d.m(pts[0]);
    pts[1..].iter().for_each(|&p| d.l(p));
    d.z();
}

/// A bar `t` thick from a to b.
fn bar(d: &mut D, a: P, b: P, t: f64) {
    let l = (b.0 - a.0).hypot(b.1 - a.1).max(1e-9);
    let (nx, ny) = (-(b.1 - a.1) / l * t / 2.0, (b.0 - a.0) / l * t / 2.0);
    poly(d, &[(a.0 + nx, a.1 + ny), (b.0 + nx, b.1 + ny), (b.0 - nx, b.1 - ny), (a.0 - nx, a.1 - ny)]);
}

/// An arrow along the box's middle from x = 0 to x = w: a shaft `lineWidth` thick and a head at each end.
fn arrow(d: &mut D, it: &Item, w: f64, cy: f64) {
    let (t, s) = (it.num("lineWidth").max(0.0), it.num("headSize").max(0.0));
    // Each head drawn at its tip x, pointing along `dir`; returns how far the shaft stops short of the tip.
    let mut head = |kind: &str, tip: f64, dir: f64| -> f64 {
        let back = |k: f64| tip - dir * k;
        match kind {
            "triangle" => { poly(d, &[(tip, cy), (back(s), cy - s / 2.0), (back(s), cy + s / 2.0)]); s * 0.9 }
            "open" => {
                bar(d, (tip, cy), (back(s * 0.7), cy - s / 2.0), t);
                bar(d, (tip, cy), (back(s * 0.7), cy + s / 2.0), t);
                t / 2.0
            }
            "circle" => {
                let c = back(s / 2.0);
                d.m((c, cy - s / 2.0));
                arc(d, (c, cy, s / 2.0, s / 2.0), 1.0, 0.0, TAU);
                d.z();
                s / 2.0
            }
            "square" => { poly(d, &[(tip, cy - s / 2.0), (back(s), cy - s / 2.0), (back(s), cy + s / 2.0), (tip, cy + s / 2.0)]); s / 2.0 }
            "bar" => { poly(d, &[(tip, cy - s / 2.0), (back(t), cy - s / 2.0), (back(t), cy + s / 2.0), (tip, cy + s / 2.0)]); t / 2.0 }
            _ => 0.0,
        }
    };
    let start = head(it.str("headStart"), 0.0, -1.0);
    let end = head(it.str("headEnd"), w, 1.0);
    if w - end > start && t > 0.0 {
        bar(d, (start, cy), (w - end, cy), t);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use kurbo::Shape;

    /// The outlines are path data stage_path reads (M L C Z only), and a rounded corner stays inside its corner.
    #[test]
    fn outlines_are_readable_path_data() {
        let b = (100.0, 100.0, 100.0, 100.0);
        let mut d = D::default();
        rounded(&mut d, &[(100.0, 0.0), (200.0, 200.0), (0.0, 200.0)], &[30.0; 3]);
        d.m((100.0, 0.0));
        arc(&mut d, b, 1.0, 0.0, 1.5 * PI);
        d.z();
        spiral(&mut d, b, 2.5, 0.1);
        bar(&mut d, (0.0, 100.0), (200.0, 100.0), 8.0);
        let subs = crate::scene::path_data::read("s", d.0.trim_end()).unwrap();
        assert_eq!(subs.len(), 4);
        let r = subs[0].bounding_box();
        assert!(r.x0 >= 0.0 && r.x1 <= 200.0 && r.y0 > 0.0 && r.y1 <= 200.0, "{r:?}");
    }
}
