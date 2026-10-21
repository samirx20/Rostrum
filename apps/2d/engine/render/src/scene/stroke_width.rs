//! A varied-width stroke (ENGINE_CONTRACT.md § 4 path, taper and widthProfile) drawn as a filled outline: each
//! visible piece of a subpath is sampled along its length, offset ± half the width there along the normal, and
//! closed as one loop (left side forward, the end cap, the right side back, the start cap). Every loop and every
//! join disc winds the same way, so filled nonzero they make one shape with no holes where they overlap.

use std::f64::consts::PI;
use std::fmt::Write;

use kurbo::{BezPath, CubicBez, ParamCurve, ParamCurveArclen, ParamCurveDeriv, PathEl, PathSeg, Point, Vec2};

/// At most this many px between two samples (a long subpath spreads `MAX_SAMPLES` over its length instead).
const STEP: f64 = 2.0;
const MAX_SAMPLES: f64 = 4000.0;
/// At most this much turn (rad, ~4°) between two samples, so a tight curve gets more; at most `MAX_PER_SEG`.
const TURN: f64 = 0.07;
const MAX_PER_SEG: f64 = 1024.0;
/// A corner turning more than this (rad, ~10°) gets a round join: a disc as wide as the stroke there.
const JOIN: f64 = 0.17;
const ACC: f64 = 1e-3;

/// One point on the line: where, its unit tangent, half the width there.
struct Sample {
    p: Point,
    t: Vec2,
    h: f64,
}

fn cubic(seg: PathSeg) -> CubicBez {
    match seg {
        PathSeg::Line(l) => CubicBez::new(l.p0, l.p0.lerp(l.p1, 1.0 / 3.0), l.p0.lerp(l.p1, 2.0 / 3.0), l.p1),
        PathSeg::Quad(q) => q.raise(),
        PathSeg::Cubic(c) => c,
    }
}

/// The unit tangent at t; where the derivative vanishes (a control point on its end) the nearby chord, else `prev`.
fn tangent(c: &CubicBez, t: f64, prev: Vec2) -> Vec2 {
    let mut d = c.deriv().eval(t).to_vec2();
    if d.hypot() < 1e-9 {
        d = c.eval((t + 1e-3).min(1.0)) - c.eval((t - 1e-3).max(0.0));
    }
    if d.hypot() > 1e-12 { d / d.hypot() } else { prev }
}

fn turn(a: Vec2, b: Vec2) -> f64 {
    a.cross(b).atan2(a.dot(b)).abs()
}

fn normal(t: Vec2) -> Vec2 {
    Vec2::new(-t.y, t.x)
}

/// Samples of the piece `[a, b]` (px along the subpath) of the segments `(curve, start px, length px)`.
fn samples(segs: &[(CubicBez, f64, f64)], (a, b): (f64, f64), step: f64, width: &dyn Fn(f64) -> f64) -> Vec<Sample> {
    let mut out: Vec<Sample> = vec![];
    for &(c, s0, len) in segs {
        let (sa, sb) = ((a - s0).max(0.0), (b - s0).min(len));
        if sb - sa <= 1e-9 {
            continue;
        }
        let (t0, t1) = (c.inv_arclen(sa, ACC), c.inv_arclen(sb, ACC));
        let mut prev = out.last().map_or(Vec2::new(1.0, 0.0), |s| s.t);
        let probe: Vec<Vec2> = (0..=8).map(|i| tangent(&c, t0 + (t1 - t0) * i as f64 / 8.0, prev)).collect();
        let turned: f64 = probe.windows(2).map(|w| turn(w[0], w[1])).sum();
        let n = ((sb - sa) / step).max(turned / TURN).ceil().clamp(1.0, MAX_PER_SEG) as usize;
        let ts: Vec<f64> = (0..=n).map(|i| t0 + (t1 - t0) * i as f64 / n as f64).collect();
        let pts: Vec<Point> = ts.iter().map(|&t| c.eval(t)).collect();
        // Arclength between samples by their chords, scaled to the piece's true length (exact at both ends).
        let mut along = vec![0.0];
        for w in pts.windows(2) {
            along.push(along[along.len() - 1] + w[0].distance(w[1]));
        }
        let chord = along[n].max(1e-12);
        for i in 0..=n {
            prev = tangent(&c, ts[i], prev);
            // f64::max drops a NaN, so a width that can't be worked out is 0, never a NaN point.
            out.push(Sample { p: pts[i], t: prev, h: (width(s0 + sa + (sb - sa) * along[i] / chord) / 2.0).max(0.0) });
        }
    }
    out
}

fn pt(d: &mut String, cmd: char, p: Point) {
    let _ = write!(d, "{cmd}{:.2} {:.2} ", p.x, p.y);
}

/// The cap at sample `s`, from `p + m·h` round to `p − m·h`, bulging along `f` (no points for butt or width 0).
fn cap(d: &mut String, s: &Sample, m: Vec2, f: Vec2, kind: &str) {
    if s.h <= 1e-6 {
        return;
    }
    match kind {
        "round" => {
            let k = ((s.h * PI / 2.0).ceil() as usize).clamp(4, 32);
            for i in 1..k {
                let a = PI * i as f64 / k as f64;
                pt(d, 'L', s.p + (m * a.cos() + f * a.sin()) * s.h);
            }
        }
        "square" => {
            pt(d, 'L', s.p + (m + f) * s.h);
            pt(d, 'L', s.p + (f - m) * s.h);
        }
        _ => {}
    }
}

/// A round join: a disc of radius `h` wound the same way as the loops (angle decreasing).
fn disc(d: &mut String, c: Point, h: f64) {
    if h <= 1e-6 {
        return;
    }
    let k = ((h * PI).ceil() as usize).clamp(8, 64);
    for i in 0..k {
        let a = -2.0 * PI * i as f64 / k as f64;
        pt(d, if i == 0 { 'M' } else { 'L' }, c + Vec2::new(a.cos(), a.sin()) * h);
    }
    d.push_str("Z ");
}

/// Path data (absolute M L Z, to fill nonzero) of the visible `pieces` `[a, b]` (px from the subpath's start) of
/// `sub`, `width(s)` px wide at s px along it, with `cap` (butt, round, square) at each piece's ends. A closed
/// subpath shown whole is a ring (its two sides as two loops), with no caps.
pub fn outline(sub: &BezPath, pieces: &[(f64, f64)], cap_kind: &str, width: &dyn Fn(f64) -> f64) -> String {
    let mut segs = vec![];
    let mut total = 0.0;
    for seg in sub.segments() {
        let c = cubic(seg);
        let len = c.arclen(ACC);
        segs.push((c, total, len));
        total += len;
    }
    let closed = matches!(sub.elements().last(), Some(PathEl::ClosePath));
    let step = (total / MAX_SAMPLES).max(STEP);
    let mut d = String::new();
    for &(a, b) in pieces {
        let ss = samples(&segs, (a, b), step, width);
        if ss.len() < 2 || ss.iter().all(|s| s.h <= 1e-6) {
            continue;
        }
        let left = |s: &Sample| s.p + normal(s.t) * s.h;
        let right = |s: &Sample| s.p - normal(s.t) * s.h;
        let (first, last) = (&ss[0], &ss[ss.len() - 1]);
        let ring = closed && a <= 1e-6 && b >= total * (1.0 - 1e-4) - 1e-2;
        for (i, s) in ss.iter().enumerate() {
            pt(&mut d, if i == 0 { 'M' } else { 'L' }, left(s));
        }
        if ring {
            d.push_str("Z ");
        } else {
            cap(&mut d, last, normal(last.t), last.t, cap_kind);
        }
        for (i, s) in ss.iter().rev().enumerate() {
            pt(&mut d, if ring && i == 0 { 'M' } else { 'L' }, right(s));
        }
        if !ring {
            cap(&mut d, first, -normal(first.t), -first.t, cap_kind);
        }
        d.push_str("Z ");
        // Corners: two samples on one point (where segments meet) whose directions differ.
        for w in ss.windows(2) {
            if w[0].p.distance(w[1].p) < 1e-6 && turn(w[0].t, w[1].t) > JOIN {
                disc(&mut d, w[1].p, w[0].h.max(w[1].h));
            }
        }
        if ring && turn(last.t, first.t) > JOIN {
            disc(&mut d, first.p, first.h.max(last.h));
        }
    }
    d
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::scene::width_profile;
    use kurbo::Shape;

    fn draw(d: &str, cap: &str, width: &dyn Fn(f64) -> f64) -> BezPath {
        let sub = BezPath::from_svg(d).unwrap();
        let len: f64 = sub.segments().map(|s| s.arclen(ACC)).sum();
        let out = outline(&sub, &[(0.0, len)], cap, width);
        assert!(!out.contains("NaN") && !out.contains("inf"), "{out}");
        BezPath::from_svg(&out).unwrap()
    }

    /// The width the profile asks for is the width drawn: 20 px (10 × 2) at the middle of a 200 px line.
    #[test]
    fn the_outline_is_as_wide_as_the_profile_says() {
        let profile = width_profile::read("p", "0,0.5 0.5,2 1,0.5").unwrap();
        let out = draw("M0 0 L200 0", "butt", &|s| 10.0 * width_profile::at(&profile, s / 200.0));
        let mid = out.elements().iter().filter_map(|e| e.end_point()).filter(|p| (p.x - 100.0).abs() < 1.5).map(|p| p.y.abs());
        let half = mid.fold(0.0, f64::max);
        assert!((half - 10.0).abs() < 0.5, "half width at the middle {half}");
    }

    /// Tips tapered to 0 and a sharp corner give finite points and nothing poking out past the stroke.
    #[test]
    fn tapered_tips_and_corners_stay_inside_the_stroke() {
        let out = draw("M0 0 L100 0 L100 100", "round", &|s| 10.0 * width_profile::taper(s / 200.0, 0.3, 0.3));
        let b = out.bounding_box();
        assert!(b.x0 > -0.5 && b.y0 > -5.5 && b.x1 < 105.5 && b.y1 < 100.5, "{b:?}");
    }
}
