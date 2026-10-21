//! ACES log encodings of AP1 linear.

const LOG_MAX: f64 = 65504.0;

/// ACEScc, Academy S-2014-003 §4.
pub fn acescc_enc(x: f64) -> f64 {
    if x <= 0.0 {
        (-16.0 + 9.72) / 17.52
    } else if x < 2f64.powi(-15) {
        ((2f64.powi(-16) + x * 0.5).log2() + 9.72) / 17.52
    } else {
        (x.log2() + 9.72) / 17.52
    }
}
pub fn acescc_dec(y: f64) -> f64 {
    if y < (9.72 - 15.0) / 17.52 {
        (2f64.powf(y * 17.52 - 9.72) - 2f64.powi(-16)) * 2.0
    } else if y < (LOG_MAX.log2() + 9.72) / 17.52 {
        2f64.powf(y * 17.52 - 9.72)
    } else if y.is_nan() {
        y
    } else {
        LOG_MAX
    }
}

/// ACEScct, Academy S-2016-001 §4.4: ACEScc with a linear toe below 0.0078125.
pub(super) const CCT_A: f64 = 10.540_237_741_654_5;
pub(super) const CCT_B: f64 = 0.072_905_534_195_835_5;
/// The code where the toe meets the log (linear 0.0078125).
pub(super) const CCT_Y_BRK: f64 = 0.155_251_141_552_511;
pub fn acescct_enc(x: f64) -> f64 {
    if x <= 0.0078125 { CCT_A * x + CCT_B } else { (x.log2() + 9.72) / 17.52 }
}
pub fn acescct_dec(y: f64) -> f64 {
    if y <= CCT_Y_BRK { (y - CCT_B) / CCT_A } else { 2f64.powf(y * 17.52 - 9.72) }
}
