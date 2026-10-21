//! `relight` (docs/phase2/PASSES_OFX.md §2, X4e): Lambert light from the normal pass, added to the picture or replacing it. Not a diffuse /
//! specular split: an additive correction; light groups are the physical relight. A coordinate shader on the AOV prelude (aov.rs); aux images
//! in the program's order: 1 normal (world, unit), 2 position (world P), 3 albedo. `flags` = (has position, has albedo, replace, light count).
//!
//! Per light `i` two float4s: `lNa` = (L toward the light | kind 0 directional, 1 point) — for a point light the position —, and `lNb` =
//! (colour·intensity | radius). Result `albedo · Σ max(N·L, 0) · colour · atten`, `atten` = 1 (directional) or inverse-square with an
//! optional smooth falloff window `(1 − (d/r)⁴)²` (radius 0: none). Albedo is the albedo pass times the coverage, else the picture's own
//! (premultiplied) colour. Alpha is unchanged.

use super::aov::PRELUDE;
use super::Program;

/// Most lights one relight takes.
pub const MAX_LIGHTS: usize = 8;

/// One light as the program takes it. Directional: `v` = unit vector toward the light; point: `v` = world position. `color` already holds the intensity.
#[derive(Clone, Copy, Debug)]
pub struct Light {
    pub point: bool,
    pub v: [f32; 3],
    pub color: [f32; 3],
    pub radius: f32,
}

fn irradiance(l: &Light, n: [f32; 3], p: [f32; 3]) -> [f32; 3] {
    let (dir, atten) = if l.point {
        let d = [l.v[0] - p[0], l.v[1] - p[1], l.v[2] - p[2]];
        let d2 = (d[0] * d[0] + d[1] * d[1] + d[2] * d[2]).max(1e-6);
        let r = d2.sqrt();
        let win = if l.radius > 0.0 { let t = (r / l.radius).powi(4); (1.0 - t).clamp(0.0, 1.0).powi(2) } else { 1.0 };
        ([d[0] / r, d[1] / r, d[2] / r], win / d2)
    } else {
        (l.v, 1.0)
    };
    let nl = (n[0] * dir[0] + n[1] * dir[1] + n[2] * dir[2]).max(0.0) * atten;
    [l.color[0] * nl, l.color[1] * nl, l.color[2] * nl]
}

/// The CPU twin: picture `c` (premultiplied), world normal `n`, world position `p`, optional albedo pass colour.
pub fn relight_pixel(c: [f32; 4], n: [f32; 3], p: [f32; 3], albedo: Option<[f32; 3]>, lights: &[Light], replace: bool) -> [f32; 4] {
    let len = (n[0] * n[0] + n[1] * n[1] + n[2] * n[2]).sqrt();
    if !(len > 1e-6) || !len.is_finite() {
        return if replace { [0.0, 0.0, 0.0, c[3]] } else { c };
    }
    let n = [n[0] / len, n[1] / len, n[2] / len];
    let mut e = [0.0f32; 3];
    for l in lights.iter().take(MAX_LIGHTS) {
        let i = irradiance(l, n, p);
        for k in 0..3 { e[k] += i[k]; }
    }
    let alb = albedo.map_or([c[0], c[1], c[2]], |a| [a[0] * c[3], a[1] * c[3], a[2] * c[3]]);
    let base = if replace { [0.0; 3] } else { [c[0], c[1], c[2]] };
    [base[0] + alb[0] * e[0], base[1] + alb[1] * e[1], base[2] + alb[2] * e[2], c[3]]
}

pub(crate) fn program() -> Program {
    let decl: String = (0..MAX_LIGHTS).map(|i| format!("uniform float4 l{i}a; uniform float4 l{i}b; ")).collect();
    let calls: String = (0..MAX_LIGHTS).map(|i| format!("    if (flags.w > {i}.5) {{ e += lit(l{i}a, l{i}b, n, P); }}\n")).collect();
    Program {
        name: "relight",
        blender: false,
        code: format!(
            "{PRELUDE}uniform float4 flags; {decl}
float3 lit(float4 a, float4 b, float3 n, float3 P) {{
    float3 dir = a.xyz; float att = 1.0;
    if (a.w > 0.5) {{
        float3 d = a.xyz - P;
        float d2 = max(dot(d, d), 1e-6);
        float r = sqrt(d2);
        float win = 1.0;
        if (b.w > 0.0) {{ float t = r / b.w; t = t * t; t = t * t; win = clamp(1.0 - t, 0.0, 1.0); win = win * win; }}
        dir = d / r; att = win / d2;
    }}
    return b.rgb * (max(dot(n, dir), 0.0) * att);
}}
half4 main(float2 p) {{
    float2 q = p - box.xy;
    float4 c = S(q);
    float3 n = A(1, q).rgb;
    float len = length(n);
    if (!(len > 1e-6) || len > 1.0e6) {{ return half4(flags.z > 0.5 ? float4(0.0, 0.0, 0.0, c.a) : c); }}
    n = n / len;
    float3 P = flags.x > 0.5 ? A(2, q).rgb : float3(0.0);
    float3 e = float3(0.0);
{calls}    float3 alb = flags.y > 0.5 ? A(3, q).rgb * c.a : c.rgb;
    float3 base = flags.z > 0.5 ? float3(0.0) : c.rgb;
    return half4(float4(base + alb * e, c.a));
}}
"
        ),
        uniforms: Box::leak(
            ["flags"].into_iter().map(String::from).chain((0..MAX_LIGHTS).flat_map(|i| [format!("l{i}a"), format!("l{i}b")])).map(|s| &*Box::leak(s.into_boxed_str())).collect::<Vec<&'static str>>().into_boxed_slice(),
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_flat_albedo_under_one_directional_light_is_n_dot_l() {
        let l = Light { point: false, v: [0.0, 0.6, 0.8], color: [2.0, 2.0, 2.0], radius: 0.0 };
        let c = [0.5, 0.5, 0.5, 1.0];
        let r = relight_pixel(c, [0.0, 1.0, 0.0], [0.0; 3], Some([0.5; 3]), &[l], true);
        assert!((r[0] - 0.5 * 0.6 * 2.0).abs() < 1e-6, "{r:?}");
        let r = relight_pixel(c, [0.0, -1.0, 0.0], [0.0; 3], None, &[l], false);
        assert_eq!(r, c, "a back-facing surface gets nothing added");
    }

    #[test]
    fn a_point_light_falls_off_with_the_square_of_the_distance_and_the_window() {
        let l = |radius| Light { point: true, v: [0.0, 4.0, 0.0], color: [1.0; 3], radius };
        let a = relight_pixel([1.0, 1.0, 1.0, 1.0], [0.0, 1.0, 0.0], [0.0; 3], None, &[l(0.0)], true);
        assert!((a[0] - 1.0 / 16.0).abs() < 1e-6, "{a:?}");
        let b = relight_pixel([1.0, 1.0, 1.0, 1.0], [0.0, 1.0, 0.0], [0.0; 3], None, &[l(4.0)], true);
        assert_eq!(b[0], 0.0, "no light at the falloff radius");
    }
}
