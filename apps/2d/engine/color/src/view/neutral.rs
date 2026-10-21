//! Khronos PBR Neutral (https://modelviewer.dev/examples/tone-mapping, Apache-2.0), on linear Rec.709:
//! bit-identical to `rostrum-3d/src/post/mod.rs`'s `neutral` for SDR, plus its exact inverse.
//!
//! HDR (`hdr1000`), BT.2408 style: graphics white is 203 nits (display 2.03), and the curve is Khronos'
//! scaled to a display whose asymptote is P = 1000 / 203 graphics whites: `y = P · K(x / P)` for the
//! compression (knee at 0.76 P, so the curve is the identity up to 0.76 P = 761 nits), the toe untouched.
//! So mid grey and everything below the knee land at exactly 2.03 × their SDR-identity value, and only
//! highlights above ~761 nits are compressed towards 1000 nits. P = 1 gives Khronos' curve exactly.
//! Scene 1.0 lands at 0.96 × 203 = 195 nits (Khronos' 0.04 toe offset, as in SDR).
use super::Target;
use crate::Rgb;

pub(crate) const START: f32 = 0.8 - 0.04;
pub(crate) const DESAT: f32 = 0.15;
const HDR_WHITE: f32 = 2.03;

/// (asymptote P in graphics-white units, graphics white in display units).
pub(crate) fn shape(t: Target) -> (f32, f32) {
    match t {
        Target::Sdr => (1.0, 1.0),
        Target::Hdr1000 => (10.0 / HDR_WHITE, HDR_WHITE),
    }
}

fn max3(c: Rgb) -> f32 {
    c[0].max(c[1]).max(c[2])
}
fn min3(c: Rgb) -> f32 {
    c[0].min(c[1]).min(c[2])
}

/// The Khronos curve with asymptote `p` (p = 1: the published one, operation for operation).
pub(crate) fn curve(mut c: Rgb, p: f32) -> Rgb {
    let x = min3(c);
    let offset = if x < 0.08 { x - 6.25 * x * x } else { 0.04 };
    c = c.map(|v| v - offset);
    let peak = max3(c);
    let start = START * p;
    if peak < start {
        return c;
    }
    let d = p - start;
    let new_peak = p - d * d / (peak + d - start);
    c = c.map(|v| v * new_peak / peak);
    let g = 1.0 - 1.0 / (DESAT / p * (peak - new_peak) + 1.0);
    c.map(|v| v + (new_peak - v) * g)
}

/// Gamut map onto what the curve reaches from non-negative sources (the inverse never returns negative
/// light). Above the knee the curve mixes every channel towards the peak n by g(n), so a reachable colour's
/// relative spread (max − min) / max is at most 1 − g(n), which falls from 1 at the knee to 0 at p: a
/// bright, saturated display colour (a clipped, coloured highlight, a pure graphics primary) has no
/// non-negative preimage. Such a colour is darkened at constant chromaticity (every channel by one factor,
/// hue and saturation kept) to the brightest peak whose 1 − g(n) holds its spread; with u = p − n and
/// q = 1 / r − 1 over DESAT / p (r the relative spread), that peak solves u² − (q + 2d) u + d² = 0. A
/// clipped highlight moves by a fraction of a code; pure #ff0000 lands at the knee (0.76). Colours outside
/// the display gamut (a negative channel) first go towards grey at their own peak until the smallest
/// channel is 0. Reachable colours are returned unchanged, bit for bit.
pub(crate) fn reach(y: Rgb, p: f32) -> Rgb {
    let np = max3(y);
    if np <= 0.0 {
        return [0.0; 3];
    }
    let lo = min3(y);
    let y = if lo < 0.0 { y.map(|v| np - (np - v) * np / (np - lo)) } else { y };
    let r = (np - min3(y)) / np;
    let (start, d) = (START * p, p - START * p);
    if np < start || r <= 1.0 / (DESAT / p * (d * d / (p - np) - d + start - np) + 1.0) {
        return y;
    }
    let q = (1.0 / r - 1.0) / (DESAT / p) + 2.0 * d;
    let u = (q - (q * q - 4.0 * d * d).max(0.0).sqrt()) / 2.0;
    y.map(|v| v * (p - u) / np)
}

/// The inverse of `curve` for outputs below `cap` (< p; channels above it are taken as `cap`), never
/// negative light: outputs no non-negative source reaches go through `reach` first. Exact (unchanged)
/// for every output of a scene whose smallest channel is ≥ 0 (the toe folds negatives onto positives).
pub(crate) fn curve_inv(y: Rgb, p: f32, cap: f32) -> Rgb {
    let y = reach(y.map(|v| v.min(cap)), p);
    let np = max3(y); // the desaturation mixes towards new_peak, so the largest channel is new_peak itself
    let start = START * p;
    let c = if np < start {
        y
    } else {
        let d = p - start;
        let peak = d * d / (p - np) - d + start;
        let g = 1.0 - 1.0 / (DESAT / p * (peak - np) + 1.0);
        y.map(|v| (v - np * g) / (1.0 - g) * peak / np)
    };
    // Toe: min(out) = 6.25 x² below x = 0.08 (min 0.04), else x − 0.04. `reach` puts the smallest channel
    // on the boundary (0 up to rounding): rounding never makes light negative.
    let c = c.map(|v| v.max(0.0));
    let m = min3(c);
    let offset = if m >= 0.04 {
        0.04
    } else if m > 0.0 {
        0.4 * m.sqrt() - m
    } else {
        0.0
    };
    c.map(|v| v + offset)
}

/// Linear Rec.709 scene → display linear in the target's primaries.
pub(crate) fn forward(c: Rgb, t: Target) -> Rgb {
    let (p, white) = shape(t);
    let y = curve(c, p);
    match t {
        Target::Sdr => y,
        Target::Hdr1000 => super::mul(&super::mats().r709_2020, y.map(|v| v * white)),
    }
}

/// Display linear in the target's primaries → linear Rec.709 scene. Display values at or above half a
/// 10-bit code below the peak (the forward only approaches the peak) invert to the scene value of that
/// cap: SDR white → scene ≈ 49.8, which re-renders within half a code of white.
pub(crate) fn inverse(d: Rgb, t: Target) -> Rgb {
    let (p, white) = shape(t);
    let y = match t {
        Target::Sdr => d,
        Target::Hdr1000 => super::mul(&super::mats().r2020_709, d).map(|v| v / white),
    };
    curve_inv(y, p, t.cap() / white)
}
