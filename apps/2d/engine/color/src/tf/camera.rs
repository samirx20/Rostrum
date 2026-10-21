//! Camera log curves, from each vendor's published formula (scene linear 0.18 = mid grey).

/// Sony, "Technical Summary for S-Gamut3.Cine/S-Log3 and S-Gamut3/S-Log3" (2015), §1.
pub(super) const SL_CUT: f64 = 171.210_294_692_9;
pub fn slog3_enc(x: f64) -> f64 {
    if x >= 0.01125 {
        (420.0 + ((x + 0.01) / 0.19).log10() * 261.5) / 1023.0
    } else {
        (x * (SL_CUT - 95.0) / 0.01125 + 95.0) / 1023.0
    }
}
pub fn slog3_dec(y: f64) -> f64 {
    if y >= SL_CUT / 1023.0 {
        10f64.powf((y * 1023.0 - 420.0) / 261.5) * 0.19 - 0.01
    } else {
        (y * 1023.0 - 95.0) * 0.01125 / (SL_CUT - 95.0)
    }
}

/// ARRI, "ALEXA Log C Curve – Usage in VFX" (2017), LogC3 at EI 800. The parameters are derived as ARRI's
/// reference code does (3 black-offset iterations); its Table 1 is these rounded to 6 digits.
pub(super) fn logc3_consts() -> [f64; 7] {
    let gain: f64 = 800.0 / 400.0;
    let c = (gain.log2() * (0.89 - 1.0) / 3.0 + 1.0) * (500.0 / 1023.0 * 0.525);
    let (cut, d0) = (1.0 / 9.0, 400.0 / 1023.0);
    let slope = 1.0 / (cut * 10f64.ln());
    let offset = cut.log10() - slope * cut;
    let (mut b, mut d) = (0.0, d0);
    for _ in 0..3 {
        b = ((95.0 / 1023.0 - d) / c - offset) / slope;
        d = d0 - (1.0 + b).log10() * c;
    }
    let a = 1.0 / 0.18;
    [(cut - b) / a, a, b, c, d, slope * a * c, c * (slope * b + offset) + d]
}
pub fn logc3_enc(x: f64) -> f64 {
    let [cut, a, b, c, d, e, f] = logc3_consts();
    if x > cut { c * (a * x + b).log10() + d } else { e * x + f }
}
pub fn logc3_dec(y: f64) -> f64 {
    let [cut, a, b, c, d, e, f] = logc3_consts();
    if y > e * cut + f { (10f64.powf((y - d) / c) - b) / a } else { (y - f) / e }
}

/// ARRI, "ARRI LogC4 Logarithmic Color Space Specification" (2022), §4.
pub(super) fn logc4_consts() -> (f64, f64, f64, f64, f64) {
    let a = (2f64.powi(18) - 16.0) / 117.45;
    let b = (1023.0 - 95.0) / 1023.0;
    let c = 95.0 / 1023.0;
    let s = (7.0 * 2f64.ln() * 2f64.powf(7.0 - 14.0 * c / b)) / (a * b);
    let t = (2f64.powf(14.0 * (-c / b) + 6.0) - 64.0) / a;
    (a, b, c, s, t)
}
pub fn logc4_enc(x: f64) -> f64 {
    let (a, b, c, s, t) = logc4_consts();
    if x >= t { ((a * x + 64.0).log2() - 6.0) / 14.0 * b + c } else { (x - t) / s }
}
pub fn logc4_dec(y: f64) -> f64 {
    let (a, b, c, s, t) = logc4_consts();
    if y >= 0.0 { (2f64.powf(14.0 * (y - c) / b + 6.0) - 64.0) / a } else { y * s + t }
}

/// RED, "White Paper on REDWideGamutRGB and Log3G10" (2017), Log3G10 v3.
pub(super) const RA: f64 = 0.224282;
pub(super) const RB: f64 = 155.975327;
pub(super) const RC: f64 = 0.01;
pub(super) const RG: f64 = 15.1927;
pub fn log3g10_enc(x: f64) -> f64 {
    let x = x + RC;
    if x < 0.0 { x * RG } else { RA * (x * RB + 1.0).log10() }
}
pub fn log3g10_dec(y: f64) -> f64 {
    if y < 0.0 { y / RG - RC } else { (10f64.powf(y / RA) - 1.0) / RB - RC }
}

/// Blackmagic Design, "Blackmagic Generation 5 Color Science" (2021), Appendix.
pub(super) const BA: f64 = 0.086_928_760_654_912_24;
pub(super) const BB: f64 = 0.005_494_072_432_257_808;
pub(super) const BC: f64 = 0.530_013_339_229_193_9;
pub(super) const BD: f64 = 8.283_605_932_402_494;
pub(super) const BE: f64 = 0.092_465_753_424_657_53;
pub(super) const B_LIN_CUT: f64 = 0.005;
pub fn bmdfilm5_enc(x: f64) -> f64 {
    if x < B_LIN_CUT { BD * x + BE } else { BA * (x + BB).ln() + BC }
}
pub fn bmdfilm5_dec(y: f64) -> f64 {
    if y < BD * B_LIN_CUT + BE { (y - BE) / BD } else { ((y - BC) / BA).exp() - BB }
}

/// Canon, "Canon Log Gamma Curves – Description of the Canon Log, Canon Log 2 and Canon Log 3"
/// (2020, v1.2); linear scaled by 0.9 as Canon's ACES IDTs (and OCIO) do.
pub(super) const CL2_A: f64 = 0.241_360_77;
pub(super) const CL2_B: f64 = 87.099_375;
pub(super) const CL2_C: f64 = 0.092_864_125;
pub fn clog2_enc(x: f64) -> f64 {
    let x = x / 0.9;
    if x < 0.0 { -CL2_A * (-x * CL2_B + 1.0).log10() + CL2_C } else { CL2_A * (x * CL2_B + 1.0).log10() + CL2_C }
}
pub fn clog2_dec(y: f64) -> f64 {
    let x = if y < CL2_C {
        -(10f64.powf((CL2_C - y) / CL2_A) - 1.0) / CL2_B
    } else {
        (10f64.powf((y - CL2_C) / CL2_A) - 1.0) / CL2_B
    };
    x * 0.9
}
/// Canon Log 3: log segments (scale A, slope B, offsets C_NEG / C_POS) around a linear toe (LIN_S, LIN_O)
/// on |x| ≤ 0.014, which spans codes Y_LO … Y_HI.
pub(super) const CL3_A: f64 = 0.367_268_45;
pub(super) const CL3_B: f64 = 14.98325;
pub(super) const CL3_C_NEG: f64 = 0.127_839_01;
pub(super) const CL3_C_POS: f64 = 0.122_405_37;
pub(super) const CL3_LIN_S: f64 = 1.975_479_8;
pub(super) const CL3_LIN_O: f64 = 0.125_122_19;
pub(super) const CL3_Y_LO: f64 = 0.097_465_473;
pub(super) const CL3_Y_HI: f64 = 0.152_778_91;
pub fn clog3_enc(x: f64) -> f64 {
    let x = x / 0.9;
    if x < -0.014 {
        -CL3_A * (-x * CL3_B + 1.0).log10() + CL3_C_NEG
    } else if x <= 0.014 {
        CL3_LIN_S * x + CL3_LIN_O
    } else {
        CL3_A * (x * CL3_B + 1.0).log10() + CL3_C_POS
    }
}
pub fn clog3_dec(y: f64) -> f64 {
    let x = if y < CL3_Y_LO {
        -(10f64.powf((CL3_C_NEG - y) / CL3_A) - 1.0) / CL3_B
    } else if y <= CL3_Y_HI {
        (y - CL3_LIN_O) / CL3_LIN_S
    } else {
        (10f64.powf((y - CL3_C_POS) / CL3_A) - 1.0) / CL3_B
    };
    x * 0.9
}

/// Panasonic, "V-Log/V-Gamut Reference Manual" (2014, rev. 1.0), §1.
pub(super) const VB: f64 = 0.00873;
pub(super) const VC: f64 = 0.241514;
pub(super) const VD: f64 = 0.598206;
pub fn vlog_enc(x: f64) -> f64 {
    if x < 0.01 { 5.6 * x + 0.125 } else { VC * (x + VB).log10() + VD }
}
pub fn vlog_dec(y: f64) -> f64 {
    if y < 0.181 { (y - 0.125) / 5.6 } else { 10f64.powf((y - VD) / VC) - VB }
}

/// Apple, "Apple Log Profile White Paper" (2023): a quadratic toe from R0 to Rt, a log above, 0 below R0.
pub(super) const AR0: f64 = -0.056_410_88;
pub(super) const ART: f64 = 0.01;
pub(super) const AC: f64 = 47.287_112_36;
pub(super) const ABETA: f64 = 0.009_640_52;
pub(super) const AGAMMA: f64 = 0.085_504_79;
pub(super) const ADELTA: f64 = 0.693_369_45;
pub fn applelog_enc(x: f64) -> f64 {
    if x >= ART {
        AGAMMA * (x + ABETA).log2() + ADELTA
    } else if x >= AR0 {
        AC * (x - AR0) * (x - AR0)
    } else if x.is_nan() {
        x
    } else {
        0.0
    }
}
pub fn applelog_dec(y: f64) -> f64 {
    let pt = AC * (ART - AR0) * (ART - AR0);
    if y >= pt {
        2f64.powf((y - ADELTA) / AGAMMA) - ABETA
    } else if y >= 0.0 {
        (y / AC).sqrt() + AR0
    } else if y.is_nan() {
        y
    } else {
        AR0
    }
}
