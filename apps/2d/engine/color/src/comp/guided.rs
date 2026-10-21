//! `matteGuide*`: a matte's edge guided by another picture (He, Sun, Tang's guided filter, written here; Gaussian windows
//! instead of box windows so the blur is the compositor's own `feGaussianBlur`). A holdout cut from a soft depth has a
//! ramp a few px wide that ignores the plate's real edge; filtered with the plate's luma as the guide, the matte's edge
//! lands on the guide's edge: q = ā·I + b̄ with a = cov(I, p) / (var(I) + ε), b = mean(p) − a·mean(I), means over a
//! Gaussian of σ px. Pointwise programs around blurs (the compiler wires them, compileMatte.ts `refine`):
//!
//! | program | shape | |
//! |---|---|---|
//! | `guideMoments` | blender | m = matte p, c = guide I (grey): rgb = (I, p, I·p) |
//! | `guideSquare` | colour | c = guide I (grey): grey(I²) |
//! | `guideCoef` | blender | m = blurred moments, c = blurred I²: rgb = (a, b) coded as v / [`SPAN`] + ½, clamped to ±[`LIM`] |
//! | `guideApply` | blender | m = blurred coefficients, c = guide I: grey(clamp(ā·I + b̄, 0, 1)) |
//!
//! The coefficients cross the half-float buffers as `v / SPAN + 0.5` so a negative one is not clipped.

use super::{Program, grey, prelude};

/// Coefficient coding: a value v in ±LIM travels as `v / SPAN + 0.5` (so ±4 → 0 … 1).
pub const SPAN: f32 = 8.0;
pub const LIM: f32 = 4.0;

pub fn moments(p: f32, i: f32) -> [f32; 4] {
    [i, p, i * p, 1.0]
}

/// a and b from the blurred moments (mean I, mean p, mean Ip) and the blurred I².
pub fn coef(m: [f32; 4], ii: f32, eps: f32) -> [f32; 4] {
    let (mi, mp, mip) = (m[0], m[1], m[2]);
    let var = (ii - mi * mi).max(0.0);
    let a = ((mip - mi * mp) / (var + eps)).clamp(-LIM, LIM);
    let b = (mp - a * mi).clamp(-LIM, LIM);
    [a / SPAN + 0.5, b / SPAN + 0.5, 0.0, 1.0]
}

pub fn apply(ab: [f32; 4], i: f32) -> [f32; 4] {
    let (a, b) = ((ab[0] - 0.5) * SPAN, (ab[1] - 0.5) * SPAN);
    grey((a * i + b).clamp(0.0, 1.0))
}

/// The CPU twin of the whole refine on one-channel images: `p` the matte, `guide` the guide's luma, σ px windows.
pub fn refine(p: &[f32], guide: &[f32], w: usize, h: usize, sigma: f32, eps: f32) -> Vec<f32> {
    use super::spatial::blur;
    let pic = |f: &dyn Fn(usize) -> [f32; 4]| -> Vec<[f32; 4]> { (0..w * h).map(f).collect() };
    let norm = |v: Vec<[f32; 4]>| -> Vec<[f32; 4]> { v.into_iter().map(|c| if c[3] <= 1e-4 { [0.0, 0.0, 0.0, 1.0] } else { [c[0] / c[3], c[1] / c[3], c[2] / c[3], 1.0] }).collect() };
    let m1 = norm(blur(&pic(&|k| moments(p[k], guide[k])), w, h, sigma));
    let m2 = norm(blur(&pic(&|k| grey(guide[k] * guide[k])), w, h, sigma));
    let ab = norm(blur(&pic(&|k| coef(m1[k], m2[k][0], eps)), w, h, sigma));
    (0..w * h).map(|k| apply(ab[k], guide[k])[0]).collect()
}

pub(crate) fn programs() -> Vec<Program> {
    let p = prelude();
    let (span, lim) = (super::lit(SPAN), super::lit(LIM));
    vec![
        Program {
            name: "guideMoments",
            blender: true,
            code: format!("{p}half4 main(half4 m, half4 c) {{\n    float i = float(c.r);\n    float v = float(m.r);\n    return half4(half3(i, v, i * v), 1.0);\n}}\n"),
            uniforms: &[],
        },
        Program {
            name: "guideSquare",
            blender: false,
            code: format!("{p}half4 main(half4 c) {{\n    float i = float(c.r);\n    return half4(grey(i * i));\n}}\n"),
            uniforms: &[],
        },
        Program {
            name: "guideCoef",
            blender: true,
            code: format!(
                "{p}uniform float eps;
half4 main(half4 m, half4 c) {{
    float mi = float(m.r);
    float mp = float(m.g);
    float mip = float(m.b);
    float v = max(float(c.r) - mi * mi, 0.0);
    float a = clamp((mip - mi * mp) / (v + eps), -{lim}, {lim});
    float b = clamp(mp - a * mi, -{lim}, {lim});
    return half4(half3(a / {span} + 0.5, b / {span} + 0.5, 0.0), 1.0);
}}
"
            ),
            uniforms: &["eps"],
        },
        Program {
            name: "guideApply",
            blender: true,
            code: format!(
                "{p}half4 main(half4 m, half4 c) {{
    float a = (float(m.r) - 0.5) * {span};
    float b = (float(m.g) - 0.5) * {span};
    return half4(grey(clamp(a * float(c.r) + b, 0.0, 1.0)));
}}
"
            ),
            uniforms: &[],
        },
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A matte that is a 6 px ramp across a step the guide has sharp: refined, the biggest jump between neighbours (the ramp's is 1/6) sits at the guide's step.
    #[test]
    fn a_soft_matte_takes_the_guides_sharp_edge() {
        let (w, h) = (64, 8);
        let step = 32usize;
        let guide: Vec<f32> = (0..w * h).map(|k| if (k % w) < step { 0.1 } else { 0.8 }).collect();
        let soft: Vec<f32> = (0..w * h).map(|k| (((k % w) as f32 - step as f32 + 3.0) / 6.0).clamp(0.0, 1.0)).collect();
        let biggest = |v: &[f32]| (1..w).map(|x| ((v[x] - v[x - 1]).abs(), x)).fold((0.0f32, 0usize), |m, d| if d.0 > m.0 { d } else { m });
        let (j0, _) = biggest(&soft);
        let q = refine(&soft, &guide, w, h, 3.0, 0.002);
        let (j1, at) = biggest(&q);
        assert!((j0 - 1.0 / 6.0).abs() < 1e-4, "the input ramp is soft: {j0}");
        assert!(j1 > 0.35, "refined: biggest step {j1}");
        assert_eq!(at, step, "the step sits at the guide's edge");
        assert!(q[5] < 0.05 && q[60] > 0.95, "the flat sides stay: {} {}", q[5], q[60]);
    }

    #[test]
    fn a_flat_guide_only_smooths_the_matte() {
        let (w, h) = (32, 8);
        let guide = vec![0.4f32; w * h];
        let p: Vec<f32> = (0..w * h).map(|k| if (k % w) < 16 { 0.0 } else { 1.0 }).collect();
        let q = refine(&p, &guide, w, h, 2.0, 0.01);
        // a = 0, b = mean p: a blurred matte, not a sharper one.
        assert!(q[15] > 0.2 && q[15] < 0.8, "{}", q[15]);
    }

    #[test]
    fn the_coefficient_code_survives_a_negative_a() {
        let c = coef([0.5, 0.2, 0.5 * 0.2 - 0.04, 1.0], 0.25 + 0.04, 1e-6); // cov −0.04, var 0.04 → a = −1
        assert!(c[0] < 0.5 && c[0] > 0.0);
        // a = −1, b = 0.7: at I = 0.5 the output is the matte's own mean, 0.2.
        assert!((apply(c, 0.5)[0] - 0.2).abs() < 2e-3, "{}", apply(c, 0.5)[0]);
    }
}
