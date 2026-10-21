//! White balance: the light's white from a colour temperature and tint, and the CAT02 adaptation of ACEScg
//! from that white to the neutral one (6500 K Planckian, tint 0).
//! Planckian locus: Krystek, "An algorithm to calculate correlated colour temperature", Color Research &
//! Application 10 (1985): CIE 1960 (u, v) as rational functions of T, valid 1000 … 15000 K (kelvin is
//! clamped there). Tint moves the white along the locus normal by `tint / TINT_SCALE` in uv (Adobe's scale);
//! + points to the green side (higher v).
use crate::matrix::{self, Cat, Mat3};
use crate::spaces::Gamut;

pub const NEUTRAL_KELVIN: f64 = 6500.0;
pub const TINT_SCALE: f64 = 3000.0;
pub(crate) const KELVIN_RANGE: (f64, f64) = (1000.0, 15000.0);
/// u(T) = (U0 + U1·T + U2·T²) / (1 + U3·T + U4·T²); v(T) likewise.
pub(crate) const KU: [f64; 5] = [0.860117757, 1.54118254e-4, 1.28641212e-7, 8.42420235e-4, 7.08145163e-7];
pub(crate) const KV: [f64; 5] = [0.317398726, 4.22806245e-5, 4.20481691e-8, -2.89741816e-5, 1.61456053e-7];

/// A Krystek rational and its derivative at T.
fn rational(k: &[f64; 5], t: f64) -> (f64, f64) {
    let (p, q) = (k[0] + k[1] * t + k[2] * t * t, 1.0 + k[3] * t + k[4] * t * t);
    let (dp, dq) = (k[1] + 2.0 * k[2] * t, k[3] + 2.0 * k[4] * t);
    (p / q, (dp * q - p * dq) / (q * q))
}

/// The light's white (CIE xy) at `kelvin` (clamped to 1000 … 15000) and `tint`.
pub fn white_xy(kelvin: f64, tint: f64) -> [f64; 2] {
    let t = kelvin.clamp(KELVIN_RANGE.0, KELVIN_RANGE.1);
    let ((u, du), (v, dv)) = (rational(&KU, t), rational(&KV, t));
    let (n, duv) = ((du * du + dv * dv).sqrt(), tint / TINT_SCALE);
    let (u, v) = (u + duv * dv / n, v - duv * du / n);
    let d = 2.0 * u - 8.0 * v + 4.0;
    [3.0 * u / d, 2.0 * v / d]
}

/// ACEScg → ACEScg: CAT02 from the light's white to the neutral white.
pub fn wb_matrix(kelvin: f64, tint: f64) -> Mat3 {
    let to_xyz = Gamut::get("acescg").expect("acescg").to_xyz();
    let cat = Cat::Cat02.adapt(white_xy(kelvin, tint), white_xy(NEUTRAL_KELVIN, 0.0));
    matrix::mul(&matrix::inverse(&to_xyz), &matrix::mul(&cat, &to_xyz))
}

/// The same adaptation factored for the GPU: `A⁻¹ · diag(REF / cone(white)) · A`, with `A` = CAT02 · ACEScg → XYZ
/// and REF the neutral white's cone response. Returns (A, A⁻¹, REF).
pub(crate) fn basis() -> (Mat3, Mat3, [f64; 3]) {
    let a = matrix::mul(&Cat::Cat02.cone(), &Gamut::get("acescg").expect("acescg").to_xyz());
    let reference = matrix::apply(&Cat::Cat02.cone(), matrix::xy_to_xyz(white_xy(NEUTRAL_KELVIN, 0.0)));
    (a, matrix::inverse(&a), reference)
}
