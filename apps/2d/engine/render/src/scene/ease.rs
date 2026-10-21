//! Easing: how a value travels from one key to the next (ENGINE_CONTRACT.md § 3). A port of the reference,
//! `apps/2d/python/rostrum2d/easing.py`, step for step, so both give the same numbers (scene/tests.rs).

pub const BEZIERS: &[(&str, [f64; 4])] = &[
    ("smooth", [0.25, 0.1, 0.25, 1.0]),
    ("snappy", [0.16, 1.0, 0.3, 1.0]),
    ("natural", [0.4, 0.0, 0.2, 1.0]),
    ("heavy", [0.25, 1.0, 0.5, 1.0]),
    ("easeIn", [0.42, 0.0, 1.0, 1.0]),
    ("easeOut", [0.0, 0.0, 0.58, 1.0]),
    ("easeInOut", [0.65, 0.0, 0.35, 1.0]),
];

/// Every ease name, in easing.py's order.
pub const NAMES: &[&str] = &["linear", "hold", "smooth", "snappy", "natural", "heavy", "easeIn", "easeOut", "easeInOut", "spring", "bounce", "custom"];

/// A key's ease, checked once when the scene loads.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Ease {
    Linear,
    Hold,
    Bezier([f64; 4]),
    Spring { stiffness: f64, damping: f64 },
    Bounce,
}

impl Ease {
    /// `custom` takes `x1 y1 x2 y2`, `spring` `stiffness damping` (each with easing.py's default when absent).
    pub fn parse(name: &str, get: impl Fn(&str) -> Option<f64>) -> Result<Ease, String> {
        Ok(match name {
            "linear" => Ease::Linear,
            "hold" => Ease::Hold,
            "custom" => Ease::Bezier([get("x1").unwrap_or(0.25), get("y1").unwrap_or(0.1), get("x2").unwrap_or(0.25), get("y2").unwrap_or(1.0)]),
            "spring" => Ease::Spring { stiffness: get("stiffness").unwrap_or(170.0), damping: get("damping").unwrap_or(12.0) },
            "bounce" => Ease::Bounce,
            _ => match BEZIERS.iter().find(|(n, _)| *n == name) {
                Some((_, b)) => Ease::Bezier(*b),
                None => return Err(format!("unknown ease \"{name}\"; accepted: {}", NAMES.join(", "))),
            },
        })
    }

    /// Progress (0 at this key, 1 at the next) at time fraction `x`.
    pub fn at(&self, x: f64) -> f64 {
        if x <= 0.0 {
            return 0.0;
        }
        if x >= 1.0 {
            return 1.0;
        }
        match *self {
            Ease::Linear => x,
            Ease::Hold => 0.0,
            Ease::Bezier([x1, y1, x2, y2]) => bezier(x1, y1, x2, y2, x),
            Ease::Spring { stiffness, damping } => spring(x, stiffness, damping),
            Ease::Bounce => bounce(x),
        }
    }
}

fn bez(p1: f64, p2: f64, u: f64) -> f64 {
    let v = 1.0 - u;
    3.0 * v * v * u * p1 + 3.0 * v * u * u * p2 + u * u * u
}

/// Cubic-bezier easing solved by bisection (x is monotone in u for x1, x2 in 0..1), as easing.py does.
fn bezier(x1: f64, y1: f64, x2: f64, y2: f64, x: f64) -> f64 {
    let (mut lo, mut hi) = (0.0, 1.0);
    for _ in 0..50 {
        let mid = (lo + hi) / 2.0;
        if bez(x1, x2, mid) < x {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    bez(y1, y2, (lo + hi) / 2.0)
}

/// A damped spring released at 0, settling on 1 (mass 1, the stretch's 0..1 read as one second).
fn spring(x: f64, stiffness: f64, damping: f64) -> f64 {
    let w0 = stiffness.sqrt();
    let zeta = damping / (2.0 * w0);
    if zeta < 1.0 {
        let wd = w0 * (1.0 - zeta * zeta).sqrt();
        return 1.0 - (-zeta * w0 * x).exp() * ((wd * x).cos() + zeta * w0 / wd * (wd * x).sin());
    }
    1.0 - (-w0 * x).exp() * (1.0 + w0 * x)
}

/// The standard four-arc bounce.
fn bounce(mut x: f64) -> f64 {
    let (n, d) = (7.5625, 2.75);
    if x < 1.0 / d {
        return n * x * x;
    }
    if x < 2.0 / d {
        x -= 1.5 / d;
        return n * x * x + 0.75;
    }
    if x < 2.5 / d {
        x -= 2.25 / d;
        return n * x * x + 0.9375;
    }
    x -= 2.625 / d;
    n * x * x + 0.984375
}
