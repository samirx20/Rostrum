//! `aces-legacy`: three.js's `ACESFilmicToneMapping` (MIT; Stephen Hill's fit of the ACES 1.x RRT + ODT), on
//! linear Rec.709, SDR only. Only for `.trd`s that said `toneMapping: "aces"`. The forward is
//! `rostrum-3d/src/post/mod.rs`'s `aces`, operation for operation.
//!
//! Inverse: analytic. The per-channel rational fit `y = (v² + a v − b) / (c v² + d v + e)` is solved as a
//! quadratic (its positive root); exact for display within [0, 1] whose fit-space values lie in the fit's
//! range for v ≥ 0, which covers display white (white inverts to a finite scene ≈ 15).
use super::{M3c, inv_cols, mulc};
use crate::Rgb;
use std::sync::OnceLock;

pub(crate) const IN: M3c = [[0.59719, 0.07600, 0.02840], [0.35458, 0.90834, 0.13383], [0.04823, 0.01566, 0.83777]];
pub(crate) const OUT: M3c = [[1.60475, -0.10208, -0.00327], [-0.53108, 1.10813, -0.07276], [-0.07367, -0.00605, 1.07602]];
pub(crate) const A: f32 = 0.0245786;
pub(crate) const B: f32 = 0.000090537;
pub(crate) const C: f32 = 0.983729;
pub(crate) const D: f32 = 0.4329510;
pub(crate) const E: f32 = 0.238081;

/// Linear Rec.709 scene → linear Rec.709 display, [0, 1].
pub(crate) fn forward(c: Rgb) -> Rgb {
    let v = mulc(&IN, c.map(|v| v / 0.6));
    let fit = v.map(|v| (v * (v + A) - B) / (v * (C * v + D) + E));
    mulc(&OUT, fit).map(|v| v.clamp(0.0, 1.0))
}

fn fit_inv(y: f32) -> f32 {
    let (y, (a, b, c, d, e)) = (y as f64, (A as f64, B as f64, C as f64, D as f64, E as f64));
    let (qa, qb, qc) = (y * c - 1.0, y * d - a, y * e + b);
    if qa.abs() < 1e-12 {
        return (-qc / qb) as f32;
    }
    ((-qb - (qb * qb - 4.0 * qa * qc).max(0.0).sqrt()) / (2.0 * qa)) as f32
}

/// (OUT⁻¹, IN⁻¹), column-major.
pub(crate) fn inv() -> &'static (M3c, M3c) {
    static M: OnceLock<(M3c, M3c)> = OnceLock::new();
    M.get_or_init(|| (inv_cols(&OUT), inv_cols(&IN)))
}

/// Linear Rec.709 display → linear Rec.709 scene.
pub(crate) fn inverse(d: Rgb) -> Rgb {
    let (out_inv, in_inv) = inv();
    let fit = mulc(out_inv, d.map(|v| v.clamp(0.0, 1.0)));
    mulc(in_inv, fit.map(fit_inv)).map(|v| v * 0.6)
}
