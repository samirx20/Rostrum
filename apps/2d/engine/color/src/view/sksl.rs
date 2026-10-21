//! The views as SkSL colour filters for the compositor (C5). UNTESTED in this crate (no Skia here): a
//! faithful transliteration of the CPU code, generated from the same constants and matrices (no second copy
//! of any number). `half4 main(half4 c)`, premultiplied in and out. The inverse filter takes display linear
//! in the target's primaries (1.0 = 100 nits) and returns ACEScg; the forward filter the reverse.
use super::{Kind, M3, M3c, Target, View, agx, legacy, mats, neutral};

/// SkSL source plus the uniform float arrays it declares (name, values), in declaration order.
pub struct Sksl {
    pub code: String,
    pub uniforms: Vec<(&'static str, Vec<f32>)>,
}

/// An f32 as an SkSL literal (shortest round-trip form, always with a `.` or an exponent).
pub(crate) fn f(x: f32) -> String {
    format!("{x:?}")
}
fn mul_m(a: &M3, b: &M3) -> M3 {
    std::array::from_fn(|r| std::array::from_fn(|c| (0..3).map(|k| a[r][k] * b[k][c]).sum()))
}
/// A row-major `M3` as SkSL's column-major `float3x3(...)`.
pub fn mat(m: &M3) -> String {
    let v: Vec<String> = (0..3).flat_map(|c| (0..3).map(move |r| f(m[r][c]))).collect();
    format!("float3x3({})", v.join(", "))
}
fn matc(c: &M3c) -> String {
    mat(&std::array::from_fn(|r| std::array::from_fn(|k| c[k][r])))
}

fn wrap(body: String, call: &str) -> String {
    format!(
        "{body}\nhalf4 main(half4 c) {{\n    float a = float(c.a);\n    float3 x = a > 0.0 ? float3(c.rgb) / a : float3(0.0);\n    \
         return half4(half3({call}(x) * a), c.a);\n}}\n"
    )
}

fn neutral_code(t: Target) -> String {
    let (p, white) = neutral::shape(t);
    let m = mats();
    let (to_disp, from_disp) = match t {
        Target::Sdr => (super::IDENTITY, super::IDENTITY),
        Target::Hdr1000 => (m.r709_2020, m.r2020_709),
    };
    format!(
        "const float START = {}; const float DESAT = {}; const float P = {}; const float WHITE = {}; const float CAP = {};\n\
         const float3x3 CG_709 = {}; const float3x3 R709_CG = {}; const float3x3 TO_DISP = {}; const float3x3 FROM_DISP = {};\n{}",
        f(neutral::START), f(neutral::DESAT), f(p), f(white), f(t.cap() / white),
        mat(&m.cg_709), mat(&m.r709_cg), mat(&to_disp), mat(&from_disp), NEUTRAL
    )
}

const NEUTRAL: &str = r#"
float3 viewFwd(float3 cg) {
    float3 c = CG_709 * cg;
    float x = min(c.r, min(c.g, c.b));
    c -= x < 0.08 ? x - 6.25 * x * x : 0.04;
    float pk = max(c.r, max(c.g, c.b)); float st = START * P;
    if (pk >= st) {
        float d = P - st; float np = P - d * d / (pk + d - st);
        c *= np / pk;
        c = mix(c, float3(np), 1.0 - 1.0 / (DESAT / P * (pk - np) + 1.0));
    }
    return TO_DISP * (c * WHITE);
}
float3 reach(float3 y) {
    float np = max(y.r, max(y.g, y.b));
    if (np <= 0.0) { return float3(0.0); }
    float lo = min(y.r, min(y.g, y.b));
    if (lo < 0.0) { y = np - (np - y) * np / (np - lo); }
    float r = (np - min(y.r, min(y.g, y.b))) / np;
    float st = START * P; float dd = P - st;
    if (np < st || r <= 1.0 / (DESAT / P * (dd * dd / (P - np) - dd + st - np) + 1.0)) { return y; }
    float q = (1.0 / r - 1.0) / (DESAT / P) + 2.0 * dd;
    float u = (q - sqrt(max(q * q - 4.0 * dd * dd, 0.0))) / 2.0;
    return y * ((P - u) / np);
}
float3 viewInv(float3 d) {
    float3 y = reach(min(FROM_DISP * d / WHITE, float3(CAP)));
    float np = max(y.r, max(y.g, y.b)); float st = START * P; float3 c = y;
    if (np >= st) {
        float dd = P - st; float pk = dd * dd / (P - np) - dd + st;
        float g = 1.0 - 1.0 / (DESAT / P * (pk - np) + 1.0);
        c = (y - np * g) / (1.0 - g) * pk / np;
    }
    c = max(c, float3(0.0));
    float m = min(c.r, min(c.g, c.b));
    return R709_CG * (c + (m >= 0.04 ? 0.04 : (m > 0.0 ? 0.4 * sqrt(m) - m : 0.0)));
}
"#;

fn agx_code() -> String {
    let (m, i) = (mats(), agx::inv());
    let p = agx::POLY.map(f);
    format!(
        "const float MIN_EV = {}; const float MAX_EV = {};\n\
         float poly(float x) {{ return (((((({} * x + {}) * x + {}) * x + {}) * x + {}) * x + {}) * x + {}); }}\n\
         float dpoly(float x) {{ return ((((6.0 * {} * x + 5.0 * {}) * x + 4.0 * {}) * x + 3.0 * {}) * x + 2.0 * {}) * x + {}; }}\n\
         const float3x3 CG_709 = {}; const float3x3 R709_CG = {}; const float3x3 TO_2020 = {}; const float3x3 FROM_2020 = {};\n\
         const float3x3 INSET = {}; const float3x3 OUTSET = {}; const float3x3 FROM_2020_INV = {}; const float3x3 OUTSET_INV = {};\n\
         const float3x3 INSET_INV = {}; const float3x3 TO_2020_INV = {};\n{}",
        f(agx::MIN_EV), f(agx::MAX_EV), p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[0], p[1], p[2], p[3], p[4], p[5],
        mat(&m.cg_709), mat(&m.r709_cg), matc(&agx::TO_2020), matc(&agx::FROM_2020), matc(&agx::INSET), matc(&agx::OUTSET),
        matc(&i.from_2020), matc(&i.outset), matc(&i.inset), matc(&i.to_2020), AGX
    )
}

const AGX: &str = r#"
float3 viewFwd(float3 cg) {
    float3 v = INSET * (TO_2020 * (CG_709 * cg));
    v = clamp((log2(max(v, float3(1e-10))) - MIN_EV) / (MAX_EV - MIN_EV), 0.0, 1.0);
    v = pow(max(OUTSET * float3(poly(v.r), poly(v.g), poly(v.b)), float3(0.0)), float3(2.2));
    return clamp(FROM_2020 * v, 0.0, 1.0);
}
float polyInv(float y) {
    y = clamp(y, poly(0.0), poly(1.0));
    float lo = 0.0; float hi = 1.0; float x = clamp(y, 0.0, 1.0);
    for (int i = 0; i < 24; i++) {
        float e = poly(x) - y;
        if (e > 0.0) { hi = x; } else { lo = x; }
        float n = x - e / dpoly(x);
        x = (n > lo && n < hi) ? n : 0.5 * (lo + hi);
    }
    return x;
}
float3 viewInv(float3 d) {
    float3 v = pow(max(FROM_2020_INV * clamp(d, 0.0, 1.0), float3(0.0)), float3(1.0 / 2.2));
    v = OUTSET_INV * v;
    v = exp2(float3(polyInv(v.r), polyInv(v.g), polyInv(v.b)) * (MAX_EV - MIN_EV) + MIN_EV);
    return R709_CG * (TO_2020_INV * (INSET_INV * v));
}
"#;

fn legacy_code() -> String {
    let (m, (oi, ii)) = (mats(), legacy::inv());
    let k = [legacy::A, legacy::B, legacy::C, legacy::D, legacy::E].map(f);
    format!(
        "const float A = {}; const float B = {}; const float C = {}; const float D = {}; const float E = {};\n\
         const float3x3 CG_709 = {}; const float3x3 R709_CG = {}; const float3x3 IN = {}; const float3x3 OUT = {};\n\
         const float3x3 OUT_INV = {}; const float3x3 IN_INV = {};\n{}",
        k[0], k[1], k[2], k[3], k[4], mat(&m.cg_709), mat(&m.r709_cg), matc(&legacy::IN), matc(&legacy::OUT),
        matc(oi), matc(ii), LEGACY
    )
}

const LEGACY: &str = r#"
float3 viewFwd(float3 cg) {
    float3 v = IN * (CG_709 * cg / 0.6);
    return clamp(OUT * ((v * (v + A) - B) / (v * (C * v + D) + E)), 0.0, 1.0);
}
float fitInv(float y) {
    float qa = y * C - 1.0; float qb = y * D - A; float qc = y * E + B;
    if (abs(qa) < 1e-7) { return -qc / qb; }
    return (-qb - sqrt(max(qb * qb - 4.0 * qa * qc, 0.0))) / (2.0 * qa);
}
float3 viewInv(float3 d) {
    float3 f = OUT_INV * clamp(d, 0.0, 1.0);
    return R709_CG * (IN_INV * float3(fitInv(f.r), fitInv(f.g), fitInv(f.b)) * 0.6);
}
"#;

fn standard_code() -> String {
    let m = mats();
    format!(
        "const float3x3 CG_709 = {}; const float3x3 R709_CG = {};\n\
         float3 viewFwd(float3 cg) {{ return clamp(CG_709 * cg, 0.0, 1.0); }}\nfloat3 viewInv(float3 d) {{ return R709_CG * d; }}\n",
        mat(&m.cg_709), mat(&m.r709_cg)
    )
}

impl View {
    fn sksl(&self, t: Target, call_fwd: bool) -> Result<Sksl, String> {
        self.check(t)?;
        let (body, uniforms, f, i) = match self.kind {
            Kind::Neutral => (neutral_code(t), vec![], "viewFwd", "viewInv"),
            Kind::Agx => (agx_code(), vec![], "viewFwd", "viewInv"),
            Kind::AcesLegacy => (legacy_code(), vec![], "viewFwd", "viewInv"),
            Kind::Standard => (standard_code(), vec![], "viewFwd", "viewInv"),
            Kind::Aces2 => {
                let a = super::aces2::Aces2::get(t);
                (super::aces2::sksl::code(a), super::aces2::sksl::uniforms(a), "acesFwd", "acesInv")
            }
        };
        Ok(Sksl { code: wrap(body, if call_fwd { f } else { i }), uniforms })
    }
    /// SkSL colour filter: display linear (target primaries) → ACEScg, premultiplied. Untested here.
    pub fn sksl_inverse(&self, t: Target) -> Result<Sksl, String> {
        self.sksl(t, false)
    }
    /// SkSL colour filter: ACEScg → display linear (target primaries), premultiplied. Untested here.
    pub fn sksl_forward(&self, t: Target) -> Result<Sksl, String> {
        self.sksl(t, true)
    }
    /// SkSL colour filter for a display-referred layer drawn into an ACEScg surface (the compositor's linear
    /// blend): Skia drew its sRGB colours as ACEScg light (decode + matrix), so this turns that light back into
    /// display light in the target (Rec.709 → target primaries, graphics white at `HDR_GRAPHICS_WHITE` in HDR)
    /// and through the inverse view: the layer leaves the forward view as it was authored.
    pub fn sksl_display_in(&self, t: Target) -> Result<Sksl, String> {
        let s = self.sksl(t, false)?;
        let m = mats();
        let to_target: M3 = match t {
            Target::Sdr => m.cg_709,
            Target::Hdr1000 => mul_m(&m.r709_2020, &m.cg_709).map(|r| r.map(|v| v * crate::pipeline::HDR_GRAPHICS_WHITE)),
        };
        let code = s.code.replacen("half4 main(half4 c)", "half4 viewInvMain(half4 c)", 1);
        let code = format!(
            "{code}
const float3x3 DISPLAY_IN = {};
half4 main(half4 c) {{
    float a = float(c.a);
    float3 x = a > 0.0 ? float3(c.rgb) / a : float3(0.0);
    return viewInvMain(half4(half3(DISPLAY_IN * x * a), c.a));
}}
",
            mat(&to_target)
        );
        Ok(Sksl { code, uniforms: s.uniforms })
    }
    /// The inverse of [`View::sksl_display_in`]: ACEScg light → the forward view → back to the light Skia drew a display-referred
    /// picture as (target → Rec.709 display light → ACEScg). A program that must see the picture as shown (the comp's `compress`:
    /// a codec saw display code values, not the inverse view's light, which runs to 10 … 1000× under AgX) runs between this and display-in.
    pub fn sksl_display_out(&self, t: Target) -> Result<Sksl, String> {
        let s = self.sksl(t, true)?;
        let m = mats();
        let to_target: M3 = match t {
            Target::Sdr => m.cg_709,
            Target::Hdr1000 => mul_m(&m.r709_2020, &m.cg_709).map(|r| r.map(|v| v * crate::pipeline::HDR_GRAPHICS_WHITE)),
        };
        let inv = crate::matrix::inverse(&to_target.map(|r| r.map(|v| v as f64))).map(|r| r.map(|v| v as f32));
        let code = s.code.replacen("half4 main(half4 c)", "half4 viewFwdMain(half4 c)", 1);
        let code = format!(
            "{code}
const float3x3 DISPLAY_OUT = {};
half4 main(half4 c) {{
    half4 d = viewFwdMain(c);
    float a = float(d.a);
    float3 x = a > 0.0 ? float3(d.rgb) / a : float3(0.0);
    return half4(half3(DISPLAY_OUT * x * a), d.a);
}}
",
            mat(&inv)
        );
        Ok(Sksl { code, uniforms: s.uniforms })
    }
}
