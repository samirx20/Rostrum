//! 2D affine maps for rigs (RIG.md): p' = (a·x + c·y + e, b·x + d·y + f), y down, angles in degrees clockwise on
//! screen. A bone's frame and its delta are similarities (move, turn, uniform scale); a layer's own map may stretch.

use serde_json::{Map, Value};

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Aff {
    pub a: f64,
    pub b: f64,
    pub c: f64,
    pub d: f64,
    pub e: f64,
    pub f: f64,
}

pub type Pt = (f64, f64);

impl Aff {
    pub const ID: Aff = Aff { a: 1.0, b: 0.0, c: 0.0, d: 1.0, e: 0.0, f: 0.0 };

    pub fn translate(x: f64, y: f64) -> Aff {
        Aff { e: x, f: y, ..Aff::ID }
    }

    /// A turn by `deg` about the origin (90: the x axis points down).
    pub fn rotate(deg: f64) -> Aff {
        let (s, c) = deg.to_radians().sin_cos();
        Aff { a: c, b: s, c: -s, d: c, e: 0.0, f: 0.0 }
    }

    pub fn scale(sx: f64, sy: f64) -> Aff {
        Aff { a: sx, d: sy, ..Aff::ID }
    }

    /// A turn by `deg` about the point `p`.
    pub fn rotate_about(deg: f64, p: Pt) -> Aff {
        Aff::translate(p.0, p.1) * Aff::rotate(deg) * Aff::translate(-p.0, -p.1)
    }

    pub fn apply(&self, p: Pt) -> Pt {
        (self.a * p.0 + self.c * p.1 + self.e, self.b * p.0 + self.d * p.1 + self.f)
    }

    /// The image of the origin (a bone's pivot, when this is its frame).
    pub fn origin(&self) -> Pt {
        (self.e, self.f)
    }

    pub fn inverse(&self) -> Option<Aff> {
        let det = self.a * self.d - self.b * self.c;
        if det.abs() < 1e-12 || !det.is_finite() {
            return None;
        }
        Some(Aff {
            a: self.d / det,
            b: -self.b / det,
            c: -self.c / det,
            d: self.a / det,
            e: (self.c * self.f - self.d * self.e) / det,
            f: (self.b * self.e - self.a * self.f) / det,
        })
    }

    /// The turn of the x axis, degrees.
    pub fn turn(&self) -> f64 {
        self.b.atan2(self.a).to_degrees()
    }

    /// The uniform scale of a similarity.
    pub fn uniform_scale(&self) -> f64 {
        (self.a * self.d - self.b * self.c).abs().sqrt()
    }
}

impl std::ops::Mul for Aff {
    type Output = Aff;

    /// `self * o`: o first, then self.
    fn mul(self, o: Aff) -> Aff {
        Aff {
            a: self.a * o.a + self.c * o.b,
            b: self.b * o.a + self.d * o.b,
            c: self.a * o.c + self.c * o.d,
            d: self.b * o.c + self.d * o.d,
            e: self.a * o.e + self.c * o.f + self.e,
            f: self.b * o.e + self.d * o.f + self.f,
        }
    }
}

pub fn dist(p: Pt, q: Pt) -> f64 {
    (q.0 - p.0).hypot(q.1 - p.1)
}

/// Direction of p → q, radians.
pub fn heading(p: Pt, q: Pt) -> f64 {
    (q.1 - p.1).atan2(q.0 - p.0)
}

/// An angle (radians) brought into (−π, π]: the shortest way round.
pub fn wrap(a: f64) -> f64 {
    let t = std::f64::consts::TAU;
    let r = a.rem_euclid(t);
    if r > std::f64::consts::PI { r - t } else { r }
}

/// A layer's own map from its px (its box's top-left) to its parent's px, tilt left out: the anchor point
/// (anchorX·w, anchorY·h) sits at (x, y), turned and scaled about it (stage.rs `transform`).
pub fn layer_map(p: &Map<String, Value>) -> Aff {
    let n = |f: &str| p.get(f).and_then(Value::as_f64).unwrap_or(0.0);
    let (s, sx, sy) = (n("scale"), n("scaleX"), n("scaleY"));
    Aff::translate(n("x"), n("y")) * Aff::rotate(n("rotation")) * Aff::scale(s * sx, s * sy) * Aff::translate(-n("anchorX") * n("w"), -n("anchorY") * n("h"))
}
