//! Every curve as an SkSL function `float <name>(float x)`, for GPU colour filters that change space (the
//! grade's ACEScct section and LUT nodes): a transliteration of display.rs / aces.rs / camera.rs in f32, built
//! from the same constants. NaN / inf handling is not reproduced (the CPU code is the reference for those).
use super::{Curve, aces as a, camera as c, display as d};
use crate::view::sksl::f;

/// An f64 constant as an SkSL literal.
fn k(x: f64) -> String {
    f(x as f32)
}

const L10: f64 = std::f64::consts::LOG2_10; // 10^y = exp2(y · L10)
const LG2: f64 = std::f64::consts::LOG10_2; // log10(x) = log2(x) · LG2

fn mon(g: f64, o: f64, enc: bool) -> String {
    let s = d::mon_slope(g, o);
    match enc {
        true => format!("return x >= {} ? {} * pow(x, {}) - {} : x / {};", k(o / (g - 1.0) * s), k(1.0 + o), k(1.0 / g), k(o), k(s)),
        false => format!("return x >= {} ? pow((x + {}) / {}, {}) : x * {};", k(o / (g - 1.0)), k(o), k(1.0 + o), k(g), k(s)),
    }
}

/// PQ of `x · scale_in`, times `scale_out` (PQ: 1, 1; PQ for 1.0 = 100 nits: 0.01 in, 100 out).
fn pq(enc: bool, scale_in: f64, scale_out: f64) -> String {
    let (m1, m2, c1, c2, c3) = (k(d::M1), k(d::M2), k(d::C1), k(d::C2), k(d::C3));
    let (si, so) = (k(scale_in), k(scale_out));
    match enc {
        true => format!(
            "float p = pow(abs(x * {si}), {m1}); float v = pow(({c1} + {c2} * p) / (1.0 + {c3} * p), {m2}); return (x < 0.0 ? -v : v) * {so};"
        ),
        false => format!(
            "float p = pow(abs(x * {si}), {}); float den = {c2} - {c3} * p; float v = den > 0.0 ? pow(max(p - {c1}, 0.0) / den, {}) : 1e30; \
             return (x < 0.0 ? -v : v) * {so};",
            k(1.0 / d::M2), k(1.0 / d::M1)
        ),
    }
}

fn body(curve: Curve, enc: bool) -> String {
    match (curve, enc) {
        (Curve::Linear, _) => "return x;".into(),
        (Curve::Srgb, e) => mon(2.4, 0.055, e),
        (Curve::Rec709, e) => mon(1.0 / 0.45, 0.099, e),
        (Curve::Bt1886, true) => format!("return x > 0.0 ? pow(x, {}) : x;", k(1.0 / 2.4)),
        (Curve::Bt1886, false) => "return x > 0.0 ? pow(x, 2.4) : x;".into(),
        (Curve::Pq, e) => pq(e, 1.0, 1.0),
        (Curve::Pq100, e) => if e { pq(true, 0.01, 1.0) } else { pq(false, 1.0, 100.0) },
        (Curve::Hlg, true) => format!(
            "float e = abs(x); float v = e <= {} ? sqrt(3.0 * e) : {} * log(12.0 * e - {}) + {}; return x < 0.0 ? -v : v;",
            k(1.0 / 12.0), k(d::HA), k(d::HB), k(d::HC)
        ),
        (Curve::Hlg, false) => format!(
            "float v = abs(x); float e = v <= 0.5 ? v * v / 3.0 : (exp((v - {}) / {}) + {}) / 12.0; return x < 0.0 ? -e : e;",
            k(d::HC), k(d::HA), k(d::HB)
        ),
        (Curve::AcesCc, true) => format!(
            "if (x <= 0.0) {{ return {}; }} if (x < {}) {{ return (log2({} + x * 0.5) + 9.72) / 17.52; }} return (log2(x) + 9.72) / 17.52;",
            k((-16.0 + 9.72) / 17.52), k(2f64.powi(-15)), k(2f64.powi(-16))
        ),
        (Curve::AcesCc, false) => format!(
            "if (x < {}) {{ return (exp2(x * 17.52 - 9.72) - {}) * 2.0; }} if (x < {}) {{ return exp2(x * 17.52 - 9.72); }} return 65504.0;",
            k((9.72 - 15.0) / 17.52), k(2f64.powi(-16)), k((65504f64.log2() + 9.72) / 17.52)
        ),
        (Curve::AcesCct, true) => format!("return x <= 0.0078125 ? {} * x + {} : (log2(x) + 9.72) / 17.52;", k(a::CCT_A), k(a::CCT_B)),
        (Curve::AcesCct, false) => {
            format!("return x <= {} ? (x - {}) / {} : exp2(x * 17.52 - 9.72);", k(a::CCT_Y_BRK), k(a::CCT_B), k(a::CCT_A))
        }
        (Curve::SLog3, true) => format!(
            "return x >= 0.01125 ? (420.0 + log2((x + 0.01) / 0.19) * {}) / 1023.0 : (x * {} + 95.0) / 1023.0;",
            k(261.5 * LG2), k((c::SL_CUT - 95.0) / 0.01125)
        ),
        (Curve::SLog3, false) => format!(
            "return x >= {} ? exp2((x * 1023.0 - 420.0) / 261.5 * {}) * 0.19 - 0.01 : (x * 1023.0 - 95.0) * {};",
            k(c::SL_CUT / 1023.0), k(L10), k(0.01125 / (c::SL_CUT - 95.0))
        ),
        (Curve::LogC3, e) => {
            let [cut, a, b, cc, dd, ee, ff] = c::logc3_consts().map(k);
            let c10 = k(c::logc3_consts()[3] * LG2);
            match e {
                true => format!("return x > {cut} ? {c10} * log2({a} * x + {b}) + {dd} : {ee} * x + {ff};"),
                false => format!(
                    "return x > {ee} * {cut} + {ff} ? (exp2((x - {dd}) / {cc} * {}) - {b}) / {a} : (x - {ff}) / {ee};",
                    k(L10)
                ),
            }
        }
        (Curve::LogC4, e) => {
            let (a, b, cc, s, t) = c::logc4_consts();
            let (a, b, cc, s, t) = (k(a), k(b), k(cc), k(s), k(t));
            match e {
                true => format!("return x >= {t} ? (log2({a} * x + 64.0) - 6.0) / 14.0 * {b} + {cc} : (x - {t}) / {s};"),
                false => format!("return x >= 0.0 ? (exp2(14.0 * (x - {cc}) / {b} + 6.0) - 64.0) / {a} : x * {s} + {t};"),
            }
        }
        (Curve::Log3G10, true) => format!(
            "float y = x + {}; return y < 0.0 ? y * {} : {} * log2(y * {} + 1.0);",
            k(c::RC), k(c::RG), k(c::RA * LG2), k(c::RB)
        ),
        (Curve::Log3G10, false) => format!(
            "return x < 0.0 ? x / {} - {} : (exp2(x / {} * {}) - 1.0) / {} - {};",
            k(c::RG), k(c::RC), k(c::RA), k(L10), k(c::RB), k(c::RC)
        ),
        (Curve::BmdFilm5, true) => format!(
            "return x < {} ? {} * x + {} : {} * log(x + {}) + {};",
            k(c::B_LIN_CUT), k(c::BD), k(c::BE), k(c::BA), k(c::BB), k(c::BC)
        ),
        (Curve::BmdFilm5, false) => format!(
            "return x < {} ? (x - {}) / {} : exp((x - {}) / {}) - {};",
            k(c::BD * c::B_LIN_CUT + c::BE), k(c::BE), k(c::BD), k(c::BC), k(c::BA), k(c::BB)
        ),
        (Curve::CLog2, true) => format!(
            "float y = x / 0.9; float v = {} * log2(abs(y) * {} + 1.0); return y < 0.0 ? {} - v : {} + v;",
            k(c::CL2_A * LG2), k(c::CL2_B), k(c::CL2_C), k(c::CL2_C)
        ),
        (Curve::CLog2, false) => format!(
            "float v = (exp2(abs(x - {}) / {} * {}) - 1.0) / {}; return (x < {} ? -v : v) * 0.9;",
            k(c::CL2_C), k(c::CL2_A), k(L10), k(c::CL2_B), k(c::CL2_C)
        ),
        (Curve::CLog3, true) => format!(
            "float y = x / 0.9; if (y < -0.014) {{ return -{a} * log2(-y * {b} + 1.0) + {}; }} if (y <= 0.014) {{ return {} * y + {}; }} \
             return {a} * log2(y * {b} + 1.0) + {};",
            k(c::CL3_C_NEG), k(c::CL3_LIN_S), k(c::CL3_LIN_O), k(c::CL3_C_POS), a = k(c::CL3_A * LG2), b = k(c::CL3_B)
        ),
        (Curve::CLog3, false) => format!(
            "float y = (x - {lo}) / {}; if (x < {}) {{ y = -(exp2(({} - x) / {a} * {l}) - 1.0) / {b}; }} \
             else if (x > {}) {{ y = (exp2((x - {}) / {a} * {l}) - 1.0) / {b}; }} return y * 0.9;",
            k(c::CL3_LIN_S), k(c::CL3_Y_LO), k(c::CL3_C_NEG), k(c::CL3_Y_HI), k(c::CL3_C_POS),
            lo = k(c::CL3_LIN_O), a = k(c::CL3_A), b = k(c::CL3_B), l = k(L10)
        ),
        (Curve::VLog, true) => format!("return x < 0.01 ? 5.6 * x + 0.125 : {} * log2(x + {}) + {};", k(c::VC * LG2), k(c::VB), k(c::VD)),
        (Curve::VLog, false) => format!("return x < 0.181 ? (x - 0.125) / 5.6 : exp2((x - {}) / {} * {}) - {};", k(c::VD), k(c::VC), k(L10), k(c::VB)),
        (Curve::AppleLog, true) => format!(
            "if (x >= {}) {{ return {} * log2(x + {}) + {}; }} if (x >= {r0}) {{ return {} * (x - {r0}) * (x - {r0}); }} return 0.0;",
            k(c::ART), k(c::AGAMMA), k(c::ABETA), k(c::ADELTA), k(c::AC), r0 = k(c::AR0)
        ),
        (Curve::AppleLog, false) => format!(
            "if (x >= {}) {{ return exp2((x - {}) / {}) - {}; }} if (x >= 0.0) {{ return sqrt(x / {}) + {r0}; }} return {r0};",
            k(c::AC * (c::ART - c::AR0) * (c::ART - c::AR0)), k(c::ADELTA), k(c::AGAMMA), k(c::ABETA), k(c::AC), r0 = k(c::AR0)
        ),
    }
}

impl Curve {
    /// The SkSL function name for this curve's encode (linear → code) or decode: `enc_<id>` / `dec_<id>`.
    pub fn sksl_name(self, encode: bool) -> String {
        format!("{}_{}", if encode { "enc" } else { "dec" }, self.id())
    }
    /// The SkSL function `float <sksl_name>(float x)` (f32; finite inputs).
    pub fn sksl(self, encode: bool) -> String {
        format!("float {}(float x) {{ {} }}\n", self.sksl_name(encode), body(self, encode))
    }
}
