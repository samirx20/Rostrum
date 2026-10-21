//! The one hue / saturation / luma measurement on ACEScct values (GRADING.md §2): the hue / lum / sat curves, colour
//! boost, the hue rotation and (G3) the qualifier all read it here. Definitions in mod.rs's doc; the SkSL twin
//! (`SKSL`) is the same maths, written once beside it.

type V = [f64; 3];

/// Rec.709 luma weights (on any space's values, as Resolve and OCIO's GradingPrimary use them).
pub const LUMA_709: [f64; 3] = [0.2126, 0.7152, 0.0722];
const SQRT3_2: f64 = 0.866_025_403_784_438_6;
const INV_SQRT3: f64 = 0.577_350_269_189_625_8;
/// Below this squared hue-plane chroma a colour is a grey (hue 0).
const GREY: f64 = 1e-16;

/// A colour's hue (0 … 1, 0 = red), saturation (0 … 1) and Rec.709 luma (in its own units).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Hsl {
    pub hue: f64,
    pub sat: f64,
    pub luma: f64,
}

pub fn luma(v: V) -> f64 {
    LUMA_709[0] * v[0] + LUMA_709[1] * v[1] + LUMA_709[2] * v[2]
}

/// The measurement (mod.rs doc): hue about the grey axis, HSV saturation, Rec.709 luma.
pub fn hsl(v: V) -> Hsl {
    let (a, b) = (v[0] - 0.5 * (v[1] + v[2]), SQRT3_2 * (v[1] - v[2]));
    let mut hue = if a * a + b * b > GREY { b.atan2(a) / std::f64::consts::TAU } else { 0.0 };
    if hue < 0.0 {
        hue += 1.0;
    }
    if hue >= 1.0 {
        hue = 0.0;
    }
    let (mx, mn) = (v[0].max(v[1]).max(v[2]), v[0].min(v[1]).min(v[2]));
    let sat = if mx > 0.0 { ((mx - mn) / mx).clamp(0.0, 1.0) } else { 0.0 };
    Hsl { hue, sat, luma: luma(v) }
}

/// `v` rotated by `degrees` about the grey axis, luma kept (mod.rs `Hue`).
pub fn hue_rotate(v: V, degrees: f64) -> V {
    let (s, c) = degrees.to_radians().sin_cos();
    let m = (v[0] + v[1] + v[2]) / 3.0;
    let p = v.map(|x| x - m);
    let cross = [p[2] - p[1], p[0] - p[2], p[1] - p[0]];
    let r: V = std::array::from_fn(|k| m + c * p[k] + s * INV_SQRT3 * cross[k]);
    let d = luma(v) - luma(r);
    r.map(|x| x + d)
}

/// A table of N samples evenly over x = 0 … 1 inclusive, linear between, held at the ends.
pub fn table(t: &[f32], x: f64) -> f64 {
    let p = x.clamp(0.0, 1.0) * (t.len() - 1) as f64;
    let k = (p.floor() as usize).min(t.len() - 2);
    let (a, b) = (t[k] as f64, t[k + 1] as f64);
    a + (b - a) * (p - k as f64)
}

/// The same in SkSL: `luma709(v)`, `hslOf(v)` → (hue, sat, luma), `hueRotate(v, degrees)`.
pub(super) fn sksl() -> String {
    let f = |x: f64| crate::view::sksl::f(x as f32);
    let [r, g, b] = LUMA_709.map(f);
    format!(
        "float luma709(float3 v) {{ return dot(v, float3({r}, {g}, {b})); }}\n\
         float3 hslOf(float3 v) {{\n    float a = v.r - 0.5 * (v.g + v.b); float b = {s3} * (v.g - v.b);\n    \
         float hue = a * a + b * b > {grey} ? atan(b, a) / {tau} : 0.0;\n    hue = hue < 0.0 ? hue + 1.0 : hue;\n    \
         float mx = max(v.r, max(v.g, v.b)); float mn = min(v.r, min(v.g, v.b));\n    \
         float sat = mx > 0.0 ? clamp((mx - mn) / mx, 0.0, 1.0) : 0.0;\n    return float3(hue, sat, luma709(v));\n}}\n\
         float3 hueRotate(float3 v, float deg) {{\n    float t = radians(deg); float c = cos(t); float s = sin(t);\n    \
         float m = (v.r + v.g + v.b) / 3.0; float3 p = v - m;\n    \
         float3 r = m + c * p + s * {i3} * float3(p.b - p.g, p.r - p.b, p.g - p.r);\n    return r + (luma709(v) - luma709(r));\n}}\n",
        s3 = f(SQRT3_2),
        grey = "1e-16",
        tau = f(std::f64::consts::TAU),
        i3 = f(INV_SQRT3),
    )
}
