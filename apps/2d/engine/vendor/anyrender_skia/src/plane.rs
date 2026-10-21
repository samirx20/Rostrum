//! Rostrum patch (round 14, H5): a drawing plane under a 3D (perspective) matrix. Skia projects whatever it is
//! given: a rect that reaches behind the viewer (w ≤ 0) folds over the horizon (a huge "overflow: visible" layer
//! clip drawn as a sliver), and image filters run under perspective are wrong and slow. These are the plane
//! questions the painter asks before drawing: what part of the plane is on screen, what part is in front of the
//! viewer, and how much the plane is magnified there.

use skia_safe::M44;

/// Below this w a point is treated as behind the viewer (its projection is unbounded).
const MIN_W: f64 = 1.0 / 64.0;

/// The matrix as row-major f64 (column vectors), as the painter's 4×4s are written.
fn rows(m: &M44) -> [f64; 16] {
    let mut r = [0.0f64; 16];
    for (i, v) in r.iter_mut().enumerate() {
        *v = m.rc(i / 4, i % 4) as f64;
    }
    r
}

/// Whether the matrix divides by w (perspective) on the z = 0 plane.
pub(crate) fn has_perspective(m: &M44) -> bool {
    let r = rows(m);
    r[12] != 0.0 || r[13] != 0.0 || r[15] != 1.0
}

/// w of a plane point (x, y, 0, 1) under `r`.
fn w_at(r: &[f64; 16], x: f64, y: f64) -> f64 {
    r[12] * x + r[13] * y + r[15]
}

/// A plane point projected to the device; None when it is behind the viewer.
fn project(r: &[f64; 16], x: f64, y: f64) -> Option<(f64, f64)> {
    let w = w_at(r, x, y);
    (w > MIN_W).then(|| ((r[0] * x + r[1] * y + r[3]) / w, (r[4] * x + r[5] * y + r[7]) / w))
}

/// The bounding box, in plane coordinates, of the plane seen through the device rect `device`: its corners
/// mapped back through the plane's homography. None when a corner's ray misses the plane in front of the viewer
/// (the visible plane then runs to the horizon, unbounded).
pub(crate) fn visible_in_plane(m: &M44, device: kurbo::Rect) -> Option<kurbo::Rect> {
    let r = rows(m);
    // The z = 0 plane's homography (rows and columns x, y, w) and its inverse by the adjugate.
    let h = [r[0], r[1], r[3], r[4], r[5], r[7], r[12], r[13], r[15]];
    let det = h[0] * (h[4] * h[8] - h[5] * h[7]) - h[1] * (h[3] * h[8] - h[5] * h[6]) + h[2] * (h[3] * h[7] - h[4] * h[6]);
    if det.abs() < 1e-12 {
        return None;
    }
    let inv = [
        h[4] * h[8] - h[5] * h[7], h[2] * h[7] - h[1] * h[8], h[1] * h[5] - h[2] * h[4],
        h[5] * h[6] - h[3] * h[8], h[0] * h[8] - h[2] * h[6], h[2] * h[3] - h[0] * h[5],
        h[3] * h[7] - h[4] * h[6], h[1] * h[6] - h[0] * h[7], h[0] * h[4] - h[1] * h[3],
    ];
    let mut out = kurbo::Rect::new(f64::INFINITY, f64::INFINITY, f64::NEG_INFINITY, f64::NEG_INFINITY);
    for (dx, dy) in [(device.x0, device.y0), (device.x1, device.y0), (device.x0, device.y1), (device.x1, device.y1)] {
        let w = inv[6] * dx + inv[7] * dy + inv[8];
        if w.abs() < 1e-12 {
            return None;
        }
        let (x, y) = ((inv[0] * dx + inv[1] * dy + inv[2]) / w, (inv[3] * dx + inv[4] * dy + inv[5]) / w);
        if w_at(&r, x, y) <= MIN_W {
            return None;
        }
        out = kurbo::Rect::new(out.x0.min(x), out.y0.min(y), out.x1.max(x), out.y1.max(y));
    }
    Some(out)
}

/// `rect` (plane coordinates) limited to what can be projected: cut to the visible plane when that is bounded,
/// then to the half-plane in front of the viewer. None when nothing needs cutting (no perspective, or every
/// corner in front and on a bounded plane); else the polygon to use instead (possibly empty).
pub(crate) fn in_front(m: &M44, rect: kurbo::Rect, device: Option<kurbo::Rect>) -> Option<kurbo::BezPath> {
    if !has_perspective(m) {
        return None;
    }
    let r = rows(m);
    let corners = [(rect.x0, rect.y0), (rect.x1, rect.y0), (rect.x1, rect.y1), (rect.x0, rect.y1)];
    let visible = device.and_then(|d| visible_in_plane(m, d));
    let all_in_front = corners.iter().all(|&(x, y)| w_at(&r, x, y) > MIN_W);
    let inside_visible = visible.map_or(true, |v| v.x0 <= rect.x0 && v.y0 <= rect.y0 && v.x1 >= rect.x1 && v.y1 >= rect.y1);
    if all_in_front && inside_visible {
        return None;
    }
    let rect = visible.map_or(rect, |v| rect.intersect(v));
    // Sutherland–Hodgman against w ≥ MIN_W (w is linear on the plane).
    let pts = [(rect.x0, rect.y0), (rect.x1, rect.y0), (rect.x1, rect.y1), (rect.x0, rect.y1)];
    let mut poly: Vec<(f64, f64)> = Vec::with_capacity(5);
    for i in 0..4 {
        let (a, b) = (pts[i], pts[(i + 1) % 4]);
        let (wa, wb) = (w_at(&r, a.0, a.1) - MIN_W, w_at(&r, b.0, b.1) - MIN_W);
        if wa >= 0.0 {
            poly.push(a);
        }
        if (wa >= 0.0) != (wb >= 0.0) {
            let t = wa / (wa - wb);
            poly.push((a.0 + (b.0 - a.0) * t, a.1 + (b.1 - a.1) * t));
        }
    }
    let mut path = kurbo::BezPath::new();
    for (i, &(x, y)) in poly.iter().enumerate() {
        if i == 0 {
            path.move_to((x, y));
        } else {
            path.line_to((x, y));
        }
    }
    if !poly.is_empty() {
        path.close_path();
    }
    Some(path)
}

/// How many device pixels one plane unit covers at most along `rect`'s edges (the near edge of a tilted plane
/// is magnified, the far one shrunk); None when a corner is behind the viewer.
pub(crate) fn magnification(m: &M44, rect: kurbo::Rect) -> Option<f64> {
    let r = rows(m);
    let c = [(rect.x0, rect.y0), (rect.x1, rect.y0), (rect.x1, rect.y1), (rect.x0, rect.y1)];
    let p: Vec<(f64, f64)> = c.iter().map(|&(x, y)| project(&r, x, y)).collect::<Option<_>>()?;
    let mut k: f64 = 0.0;
    for i in 0..4 {
        let j = (i + 1) % 4;
        let local = ((c[j].0 - c[i].0).powi(2) + (c[j].1 - c[i].1).powi(2)).sqrt();
        if local > 1e-9 {
            k = k.max(((p[j].0 - p[i].0).powi(2) + (p[j].1 - p[i].1).powi(2)).sqrt() / local);
        }
    }
    Some(k)
}
