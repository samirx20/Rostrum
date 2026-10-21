//! Display and broadcast curves.

/// OCIO's "moncurve" (ExponentWithLinearTransform): `((y + o) / (1 + o))^g` above a linear toe that
/// meets it in value and slope at `y = o / (g − 1)`; negatives continue the toe.
fn mon_dec(y: f64, g: f64, o: f64) -> f64 {
    let brk = o / (g - 1.0);
    if y >= brk { ((y + o) / (1.0 + o)).powf(g) } else { y * mon_slope(g, o) }
}
fn mon_enc(x: f64, g: f64, o: f64) -> f64 {
    let brk = o / (g - 1.0) * mon_slope(g, o);
    if x >= brk { (1.0 + o) * x.powf(1.0 / g) - o } else { x / mon_slope(g, o) }
}
/// linear / code on the toe.
pub(super) fn mon_slope(g: f64, o: f64) -> f64 {
    (o * g / ((g - 1.0) * (1.0 + o))).powf(g) * (g - 1.0) / o
}

/// sRGB, IEC 61966-2-1 (as OCIO evaluates it: moncurve 2.4 / 0.055).
pub fn srgb_enc(x: f64) -> f64 {
    mon_enc(x, 2.4, 0.055)
}
pub fn srgb_dec(y: f64) -> f64 {
    mon_dec(y, 2.4, 0.055)
}

/// Rec. ITU-R BT.709-6 OETF (§1.2), as OCIO's "Camera Rec.709" evaluates it: moncurve 1/0.45 / 0.099,
/// whose slope-matched toe is 4.5138 below linear 0.017945 (the spec's rounded 4.5 / 0.018: ≤ 2.5e-4 code).
pub fn rec709_enc(x: f64) -> f64 {
    mon_enc(x, 1.0 / 0.45, 0.099)
}
pub fn rec709_dec(y: f64) -> f64 {
    mon_dec(y, 1.0 / 0.45, 0.099)
}

/// Rec. ITU-R BT.1886 EOTF with Lw = 1, Lb = 0: a pure 2.4 power; negatives pass through unchanged
/// (OCIO ExponentTransform, `pass_thru`).
pub fn bt1886_enc(x: f64) -> f64 {
    if x > 0.0 { x.powf(1.0 / 2.4) } else { x }
}
pub fn bt1886_dec(y: f64) -> f64 {
    if y > 0.0 { y.powf(2.4) } else { y }
}

/// SMPTE ST 2084:2014 (PQ), linear 1.0 = 10 000 nits; negatives mirror. ±inf encodes to the curve's
/// limit; codes past the asymptote (≈ 1.98) decode to ±inf.
pub(super) const M1: f64 = 2610.0 / 16384.0;
pub(super) const M2: f64 = 2523.0 / 4096.0 * 128.0;
pub(super) const C1: f64 = 3424.0 / 4096.0;
pub(super) const C2: f64 = 2413.0 / 4096.0 * 32.0;
pub(super) const C3: f64 = 2392.0 / 4096.0 * 32.0;
pub fn pq_enc(x: f64) -> f64 {
    let p = x.abs().powf(M1);
    let v = if p.is_infinite() { C2 / C3 } else { (C1 + C2 * p) / (1.0 + C3 * p) };
    v.powf(M2).copysign(x)
}
pub fn pq_dec(y: f64) -> f64 {
    let p = y.abs().powf(1.0 / M2);
    let den = C2 - C3 * p;
    let v = if !(den <= 0.0) { ((p - C1).max(0.0) / den).powf(1.0 / M1) } else { f64::INFINITY };
    v.copysign(y)
}

/// Rec. ITU-R BT.2100-2 HLG OETF (Table 5), scene linear 0..1; negatives mirror.
pub(super) const HA: f64 = 0.17883277;
pub(super) const HB: f64 = 0.28466892; // 1 − 4a
pub(super) const HC: f64 = 0.55991073; // 0.5 − a ln(4a)
pub fn hlg_enc(x: f64) -> f64 {
    let e = x.abs();
    let v = if e <= 1.0 / 12.0 { (3.0 * e).sqrt() } else { HA * (12.0 * e - HB).ln() + HC };
    v.copysign(x)
}
pub fn hlg_dec(y: f64) -> f64 {
    let v = y.abs();
    let e = if v <= 0.5 { v * v / 3.0 } else { (((v - HC) / HA).exp() + HB) / 12.0 };
    e.copysign(y)
}
