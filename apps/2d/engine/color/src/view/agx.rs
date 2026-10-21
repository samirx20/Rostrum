//! AgX on linear Rec.709, SDR only. Structure, inset / outset matrices and the log2 range are Filament's
//! (`filament/src/ToneMapper.cpp`, Apache-2.0; its outset is `inverse(AgXOutsetMatrixInv)`, which three.js
//! spells out); the sigmoid is three.js's 6th-degree polynomial (`tonemapping_pars_fragment.glsl.js`, MIT),
//! not Filament's 7th-degree one: Filament's is not monotonic on [0, 1] (so has no inverse) and differs from
//! three.js's by up to 17 sRGB codes, and three.js's is what both of Rostrum's 3D renderers show today. The
//! forward is `rostrum-3d/src/post/mod.rs`'s `agx`, operation for operation. Never from Blender (GPL).
//!
//! Inverse: analytic except the polynomial (safeguarded Newton, f64). Exact where no forward clamp acts:
//! inset-space channels within [2^-12.47, 2^4.03] (scene ≈ 1.75e-4 … 16.3 per channel), outset output ≥ 0
//! and display within [0, 1]. Display greys above ≈ 0.9969 (the curve's top) are unreachable; they invert
//! to the top of the log range.
use super::{M3c, inv_cols, mulc};
use crate::Rgb;
use std::sync::OnceLock;

pub(crate) const TO_2020: M3c = [[0.6274, 0.0691, 0.0164], [0.3293, 0.9195, 0.0880], [0.0433, 0.0113, 0.8956]];
pub(crate) const FROM_2020: M3c = [[1.6605, -0.1246, -0.0182], [-0.5876, 1.1329, -0.1006], [-0.0728, -0.0083, 1.1187]];
pub(crate) const INSET: M3c = [
    [0.856627153315983, 0.137318972929847, 0.11189821299995],
    [0.0951212405381588, 0.761241990602591, 0.0767994186031903],
    [0.0482516061458583, 0.101439036467562, 0.811302368396859],
];
pub(crate) const OUTSET: M3c = [
    [1.1271005818144368, -0.1413297634984383, -0.14132976349843826],
    [-0.11060664309660323, 1.157823702216272, -0.11060664309660294],
    [-0.016493938717834573, -0.016493938717834257, 1.2519364065950405],
];
pub(crate) const MIN_EV: f32 = -12.47393;
pub(crate) const MAX_EV: f32 = 4.026069;
/// three.js `agxDefaultContrastApprox`, highest power first (x⁶ … x⁰).
pub(crate) const POLY: [f32; 7] = [15.5, -40.14, 31.96, -6.868, 0.4298, 0.1191, -0.00232];

fn poly(x: f32) -> f32 {
    let (x2, x4) = (x * x, x * x * x * x);
    POLY[0] * x4 * x2 + POLY[1] * x4 * x + POLY[2] * x4 + POLY[3] * x2 * x + POLY[4] * x2 + POLY[5] * x + POLY[6]
}

/// Linear Rec.709 scene → linear Rec.709 display, [0, 1].
pub(crate) fn forward(c: Rgb) -> Rgb {
    let v = mulc(&INSET, mulc(&TO_2020, c)).map(|v| ((v.max(1e-10).log2() - MIN_EV) / (MAX_EV - MIN_EV)).clamp(0.0, 1.0));
    let v = mulc(&OUTSET, v.map(poly)).map(|v| v.max(0.0).powf(2.2));
    mulc(&FROM_2020, v).map(|v| v.clamp(0.0, 1.0))
}

/// The polynomial's inverse on [0, 1], in f64: Newton kept inside a bisection bracket.
pub(crate) fn poly_inv(y: f32) -> f32 {
    let p = |x: f64| POLY.iter().fold(0.0, |a, &k| a * x + k as f64);
    let dp = |x: f64| POLY[..6].iter().enumerate().fold(0.0, |a, (i, &k)| a * x + (6 - i) as f64 * k as f64);
    let y = (y as f64).clamp(p(0.0), p(1.0));
    let (mut lo, mut hi, mut x) = (0.0f64, 1.0f64, y.clamp(0.0, 1.0));
    for _ in 0..60 {
        let f = p(x) - y;
        if f.abs() < 1e-12 {
            break;
        }
        if f > 0.0 { hi = x } else { lo = x }
        let n = x - f / dp(x);
        x = if n > lo && n < hi { n } else { 0.5 * (lo + hi) };
    }
    x as f32
}

pub(crate) struct Inv {
    pub from_2020: M3c,
    pub outset: M3c,
    pub inset: M3c,
    pub to_2020: M3c,
}

pub(crate) fn inv() -> &'static Inv {
    static I: OnceLock<Inv> = OnceLock::new();
    I.get_or_init(|| Inv {
        from_2020: inv_cols(&FROM_2020),
        outset: inv_cols(&OUTSET),
        inset: inv_cols(&INSET),
        to_2020: inv_cols(&TO_2020),
    })
}

/// Linear Rec.709 display → linear Rec.709 scene.
pub(crate) fn inverse(d: Rgb) -> Rgb {
    let m = inv();
    let v = mulc(&m.from_2020, d.map(|v| v.clamp(0.0, 1.0))).map(|v| v.max(0.0).powf(1.0 / 2.2));
    let v = mulc(&m.outset, v).map(|y| (poly_inv(y) * (MAX_EV - MIN_EV) + MIN_EV).exp2());
    mulc(&m.to_2020, mulc(&m.inset, v))
}
