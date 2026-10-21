//! Shape morphing (ENGINE_CONTRACT.md § 3): a path's `d` keyed at two times is blended point by point. Both
//! shapes become cubic segments (a line is a straight cubic); subpaths pair up in order and must be as many; the
//! one with fewer segments has its longest segment halved until the counts match; a closed pair starts at the
//! points nearest each other. Anything that can't be paired is an error, never a jump.

use kurbo::{BezPath, CubicBez, ParamCurve, ParamCurveArclen, PathEl, Point};

use super::path_data;

/// One subpath as cubic segments from `start` (a closed one ends where it starts).
struct Sub {
    start: Point,
    segs: Vec<CubicBez>,
    closed: bool,
}

fn line(a: Point, b: Point) -> CubicBez {
    CubicBez::new(a, a.lerp(b, 1.0 / 3.0), a.lerp(b, 2.0 / 3.0), b)
}

fn subs(id: &str, d: &str) -> Result<Vec<Sub>, String> {
    let paths = path_data::read(id, d)?;
    Ok(paths.iter().map(|p| {
        let mut s = Sub { start: Point::ZERO, segs: vec![], closed: false };
        let mut at = Point::ZERO;
        for el in p.elements() {
            let seg = match *el {
                PathEl::MoveTo(q) => {
                    (s.start, at) = (q, q);
                    continue;
                }
                PathEl::LineTo(q) => line(at, q),
                PathEl::QuadTo(c, q) => kurbo::QuadBez::new(at, c, q).raise(),
                PathEl::CurveTo(a, b, q) => CubicBez::new(at, a, b, q),
                PathEl::ClosePath => {
                    s.closed = true;
                    if at.distance(s.start) <= 1e-9 {
                        continue;
                    }
                    line(at, s.start)
                }
            };
            at = seg.p3;
            s.segs.push(seg);
        }
        s
    }).collect())
}

/// Halve the longest segment.
fn split_longest(s: &mut Sub) {
    let lens: Vec<f64> = s.segs.iter().map(|c| c.arclen(1e-2)).collect();
    let i = (0..lens.len()).max_by(|&a, &b| lens[a].total_cmp(&lens[b])).unwrap();
    let (a, b) = s.segs[i].subdivide();
    s.segs.splice(i..=i, [a, b]);
}

/// Make `b` pair with `a` segment for segment: equal counts, and a closed pair turned to start nearest each other.
fn pair(a: &mut Sub, b: &mut Sub, n: usize) -> Result<(), String> {
    if a.segs.is_empty() != b.segs.is_empty() {
        return Err(format!("piece {n} is a single point in one shape and a line in the other"));
    }
    while a.segs.len() < b.segs.len() {
        split_longest(a);
    }
    while b.segs.len() < a.segs.len() {
        split_longest(b);
    }
    if a.closed && b.closed && !b.segs.is_empty() {
        let len = b.segs.len();
        let cost = |r: usize| (0..len).map(|i| (a.segs[i].p0 - b.segs[(i + r) % len].p0).hypot2()).sum::<f64>();
        let best = (0..len).min_by(|&x, &y| cost(x).total_cmp(&cost(y))).unwrap();
        b.segs.rotate_left(best);
        b.start = b.segs[0].p0;
    }
    Ok(())
}

/// The shape `p` of the way from path data `a` to path data `b` (p = 0 is `a`, 1 is `b`; outside 0..1 it
/// carries on), written as absolute path data. Errors name `id.d`.
pub fn blend(id: &str, a: &str, b: &str, p: f64) -> Result<String, String> {
    let (mut sa, mut sb) = (subs(id, a)?, subs(id, b)?);
    if sa.len() != sb.len() {
        return Err(format!("{id}.d: the shapes have {} and {} pieces (subpaths); a morph needs the same number in both", sa.len(), sb.len()));
    }
    let mut out = BezPath::new();
    for (n, (x, y)) in sa.iter_mut().zip(sb.iter_mut()).enumerate() {
        pair(x, y, n + 1).map_err(|e| format!("{id}.d: {e}"))?;
        out.move_to(x.start.lerp(y.start, p));
        for (c, e) in x.segs.iter().zip(&y.segs) {
            out.curve_to(c.p1.lerp(e.p1, p), c.p2.lerp(e.p2, p), c.p3.lerp(e.p3, p));
        }
        if if p < 0.5 { x.closed } else { y.closed } {
            out.close_path();
        }
    }
    Ok(out.to_svg())
}

#[cfg(test)]
mod tests {
    use super::*;
    use kurbo::Shape;

    fn shape(d: &str) -> (f64, kurbo::Rect) {
        let p = BezPath::from_svg(d).unwrap();
        (p.area().abs(), p.bounding_box())
    }

    fn near(a: (f64, kurbo::Rect), b: (f64, kurbo::Rect)) -> bool {
        let r = |x: kurbo::Rect, y: kurbo::Rect| (x.x0 - y.x0).abs() + (x.y0 - y.y0).abs() + (x.x1 - y.x1).abs() + (x.y1 - y.y1).abs();
        (a.0 - b.0).abs() < 1e-6 * a.0.max(1.0) && r(a.1, b.1) < 1e-6
    }

    #[test]
    fn ends_are_the_keyed_shapes_and_counts_are_matched() {
        let tri = "M50 0 L100 100 L0 100 Z";
        let circle = BezPath::from_vec(kurbo::Circle::new((50.0, 50.0), 50.0).path_elements(1e-3).collect()).to_svg();
        assert!(near(shape(&blend("p", tri, &circle, 0.0).unwrap()), shape(tri)));
        assert!(near(shape(&blend("p", tri, &circle, 1.0).unwrap()), shape(&circle)));
        let mid = blend("p", tri, &circle, 0.5).unwrap();
        assert_eq!(subs("p", &mid).unwrap()[0].segs.len(), subs("p", &circle).unwrap()[0].segs.len());
        let e = blend("p", tri, "M0 0 L1 1 Z M5 5 L6 6 Z", 0.5).unwrap_err();
        assert!(e.starts_with("p.d: the shapes have 1 and 2 pieces"), "{e}");
    }
}
