//! The matte programs (COMP_CORE §3, §6): a matte is an opaque grey picture `(v, v, v, 1)`.
//!
//! | program | kind | maths |
//! |---|---|---|
//! | `matteFrom` | colour | `channel` 0 r, 1 g, 2 b, 3 a, 4 luma; r / g / b / luma read the premultiplied colour in linear ACEScg (luma: AP1 Y), a the alpha |
//! | `matteCombine` | blender | m = part, c = accumulated: `mode` 0 add `max(c, m)`, 1 subtract `c(1 − m)`, 2 intersect `c·m`, 3 min |
//! | `matteLevels` | colour | `t = clamp((v − black) / (white − black), 0, 1) ^ gamma` (white − black floored at 1e-6); `invert` > 0.5: `1 − t` |
//! | `norm` | colour | `rgb / a`, alpha 1 (a ≤ 1e-4: opaque black): undoes the fade a blur gives at the frame's border |
//! | `matteApply` | blender | m = grey matte, c = picture: `c · m.r` |
//! | `threshold` | colour | `step(threshold, v)`: 1 where v ≥ threshold |

use super::{Program, Uniforms, ap1_y, grey, prelude, to_cg, uf, unpre};
use crate::pipeline::Working;

pub fn matte_from(channel: usize, w: Working, c: [f32; 4]) -> [f32; 4] {
    if channel == 3 {
        return grey(c[3]);
    }
    let u = unpre(c);
    let g = to_cg(w, [u[0], u[1], u[2]]).map(|v| v * u[3]);
    let y = ap1_y();
    grey(match channel {
        0..=2 => g[channel],
        _ => g[0] * y[0] + g[1] * y[1] + g[2] * y[2],
    })
}

pub fn matte_combine(mode: usize, m: f32, c: f32) -> [f32; 4] {
    grey(match mode {
        0 => c.max(m),
        1 => c * (1.0 - m),
        2 => c * m,
        _ => c.min(m),
    })
}

pub fn levels(v: f32, black: f32, white: f32, gamma: f32, invert: bool) -> f32 {
    let t = ((v - black) / (white - black).max(1e-6)).clamp(0.0, 1.0);
    let t = if t <= 0.0 { 0.0 } else { t.powf(gamma) };
    if invert { 1.0 - t } else { t }
}

pub fn norm(c: [f32; 4]) -> [f32; 4] {
    if c[3] <= 1e-4 { [0.0, 0.0, 0.0, 1.0] } else { [c[0] / c[3], c[1] / c[3], c[2] / c[3], 1.0] }
}

pub fn apply(m: [f32; 4], c: [f32; 4]) -> [f32; 4] {
    c.map(|v| v * m[0])
}

pub fn threshold(v: f32, t: f32) -> f32 {
    if v >= t { 1.0 } else { 0.0 }
}

pub(crate) fn eval(name: &str, u: Uniforms, w: Working, m: [f32; 4], c: [f32; 4]) -> Option<[f32; 4]> {
    Some(match name {
        "matteFrom" => matte_from(uf(u, "channel").round() as usize, w, c),
        "matteCombine" => matte_combine(uf(u, "mode").round() as usize, m[0], c[0]),
        "matteLevels" => grey(levels(c[0], uf(u, "black"), uf(u, "white"), uf(u, "gamma"), uf(u, "invert") > 0.5)),
        "norm" => norm(c),
        "matteApply" => apply(m, c),
        "threshold" => grey(threshold(c[0], uf(u, "threshold"))),
        "solid" => {
            let a = uf(u, "alpha");
            let x = super::from_cg(w, super::u3(u, "color"));
            [x[0] * a, x[1] * a, x[2] * a, a]
        }
        _ => return None,
    })
}

pub(crate) fn programs() -> Vec<Program> {
    let p = prelude();
    let y = ap1_y().map(super::lit);
    let colour = |name, uniforms, body: &str| Program { name, blender: false, code: format!("{p}{body}"), uniforms };
    let blender = |name, uniforms, body: &str| Program { name, blender: true, code: format!("{p}{body}"), uniforms };
    vec![
        // A `{ solid }` source: a linear ACEScg colour in the working space, premultiplied by `alpha` (it reads no picture).
        colour(
            "solid",
            &["color", "alpha"],
            "uniform float3 color;
uniform float alpha;
half4 main(half4 c) {
    return half4(half3(fromCg(color) * alpha), alpha);
}
",
        ),
        colour(
            "matteFrom",
            &["channel"],
            &format!(
                "uniform float channel;
half4 main(half4 c) {{
    int k = int(channel + 0.5);
    if (k == 3) {{ return half4(grey(float(c.a))); }}
    float4 u = unpre(float4(c));
    float3 g = toCg(u.rgb) * u.a;
    float v = k == 0 ? g.r : k == 1 ? g.g : k == 2 ? g.b : g.r * {} + g.g * {} + g.b * {};
    return half4(grey(v));
}}
",
                y[0], y[1], y[2]
            ),
        ),
        blender(
            "matteCombine",
            &["mode"],
            "uniform float mode;
half4 main(half4 m, half4 c) {
    int k = int(mode + 0.5);
    float a = float(c.r);
    float b = float(m.r);
    return half4(grey(k == 0 ? max(a, b) : k == 1 ? a * (1.0 - b) : k == 2 ? a * b : min(a, b)));
}
",
        ),
        colour(
            "matteLevels",
            &["black", "white", "gamma", "invert"],
            "uniform float black;
uniform float white;
uniform float gamma;
uniform float invert;
half4 main(half4 c) {
    float t = clamp((float(c.r) - black) / max(white - black, 1e-6), 0.0, 1.0);
    t = t <= 0.0 ? 0.0 : pow(t, gamma);
    return half4(grey(invert > 0.5 ? 1.0 - t : t));
}
",
        ),
        colour(
            "norm",
            &[],
            "half4 main(half4 c) {
    float4 p = float4(c);
    return p.a <= 1e-4 ? half4(0.0, 0.0, 0.0, 1.0) : half4(float4(p.rgb / p.a, 1.0));
}
",
        ),
        blender("matteApply", &[], "half4 main(half4 m, half4 c) {\n    return half4(float4(c) * float(m.r));\n}\n"),
        colour(
            "threshold",
            &["threshold"],
            "uniform float threshold;
half4 main(half4 c) {
    return half4(grey(float(c.r) >= threshold ? 1.0 : 0.0));
}
",
        ),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mattes() {
        assert_eq!(matte_from(3, Working::AcesCg, [0.1, 0.2, 0.3, 0.4]), grey(0.4));
        // White in any working space is ACEScg white: luma 1.
        assert!((matte_from(4, Working::Display, [1.0; 4])[0] - 1.0).abs() < 1e-4);
        assert_eq!(matte_combine(1, 0.25, 0.8)[0], 0.8 * 0.75);
        assert_eq!(levels(0.5, 0.25, 0.75, 1.0, false), 0.5);
        assert_eq!(levels(0.5, 0.25, 0.75, 1.0, true), 0.5);
        assert_eq!(norm([0.2, 0.2, 0.2, 0.5]), [0.4, 0.4, 0.4, 1.0]);
        assert_eq!(norm([0.0; 4]), [0.0, 0.0, 0.0, 1.0]);
    }
}
