//! The AOV tools' programs (docs/phase2/PASSES_OFX.md §2, X4b–d): `fog`, `position` (world P from depth + camera),
//! `defocus` (defocus.rs) and `vectorBlur` (vblur.rs). Coordinate shaders (`half4 main(float2 p)`, `uniform shader src;
//! uniform float4 box;`) whose auxiliary passes (depth, velocity) ride beside the picture: the renderer draws the k-th image
//! (`images="name href;…"`, in the order the program lists) into the box moved k box-widths right (anyrender_skia
//! `runtime_shader_filter`, Rostrum patch X4: the Skia bindings give one child only), so image k is read at `p + (k·box.w, 0)`.
//! Every read snaps to a pixel centre (nearest) and clamps into the box, so the CPU twin (integer texels) is exact.
//!
//! Camera space: x right, y up, z forward (view depth `Z`); screen y down. `fog`: linear premultiplied light. `position`: data,
//! RGB = world P, A = 1 where depth is finite, else transparent black. Depth reaches the shader as half floats (anyrender_skia draws
//! the aux image into an F16 layer, which saturates infinity at 65504): a depth of 6·10⁴ m or more reads as infinite, in the twins too.

/// Depth at or beyond this reads as infinite.
pub const FAR: f32 = 6.0e4;

use super::Program;

/// The SkSL every AOV program starts with: pixel-snapped reads of the picture (`S`) and of aux image `k` (`A`), in box px.
pub(crate) const PRELUDE: &str = "uniform shader src;
uniform float4 box;
float2 cl(float2 q) { return clamp(floor(q) + 0.5, float2(0.5), box.zw - 0.5); }
float4 S(float2 q) { return float4(src.eval(box.xy + cl(q))); }
float4 A(int k, float2 q) { return float4(src.eval(box.xy + cl(q) + float2(float(k) * box.z, 0.0))); }
float far(float z, float maxZ) { return (z >= 6.0e4 || z != z) ? maxZ : min(z, maxZ); }
";

/// Fog from depth: `c·T + fogColor·a·(1 − T)`, T = exp(−density·z^falloff) (infinite depth: T = 0), alpha unchanged.
pub fn fog(c: [f32; 4], z: f32, density: f32, falloff: f32, color: [f32; 3]) -> [f32; 4] {
    let t = if z < FAR { (-density * z.max(0.0).powf(falloff)).exp() } else { 0.0 };
    [c[0] * t + color[0] * c[3] * (1.0 - t), c[1] * t + color[1] * c[3] * (1.0 - t), c[2] * t + color[2] * c[3] * (1.0 - t), c[3]]
}

/// World position of the pixel at `q` (box px, pixel centre) with view depth `z`: pinhole of `focal_mm` on a `film_mm` wide sensor
/// across `size[0]` px; `c2w` the camera-to-world rows. Infinite depth: transparent black.
pub fn position(q: [f32; 2], z: f32, size: [f32; 2], focal_mm: f32, film_mm: f32, c2w: [[f32; 4]; 3]) -> [f32; 4] {
    if !(z < FAR) {
        return [0.0; 4];
    }
    let fpx = focal_mm / film_mm * size[0];
    let x = [(q[0] - size[0] * 0.5) / fpx * z, -(q[1] - size[1] * 0.5) / fpx * z, z, 1.0];
    let d = |r: [f32; 4]| r[0] * x[0] + r[1] * x[1] + r[2] * x[2] + r[3] * x[3];
    [d(c2w[0]), d(c2w[1]), d(c2w[2]), 1.0]
}

pub(crate) fn fog_program() -> Program {
    Program {
        name: "fog",
        blender: false,
        code: format!(
            "{PRELUDE}uniform float density; uniform float falloff; uniform float3 fogColor;
half4 main(float2 p) {{
    float2 q = p - box.xy;
    float4 c = S(q);
    float z = A(1, q).r;
    float t = (z >= 6.0e4 || z != z) ? 0.0 : exp(-density * pow(max(z, 0.0), falloff));
    return half4(float4(c.rgb * t + fogColor * c.a * (1.0 - t), c.a));
}}
"
        ),
        uniforms: &["density", "falloff", "fogColor"],
    }
}

pub(crate) fn position_program() -> Program {
    Program {
        name: "position",
        blender: false,
        code: format!(
            "{PRELUDE}uniform float4 lens; uniform float4 r0; uniform float4 r1; uniform float4 r2;
half4 main(float2 p) {{
    float2 q = floor(p - box.xy) + 0.5;
    float z = A(1, q).r;
    if (z >= 6.0e4 || z != z) {{ return half4(0.0); }}
    float fpx = lens.x / lens.y * box.z;
    float4 x = float4((q.x - box.z * 0.5) / fpx * z, -(q.y - box.w * 0.5) / fpx * z, z, 1.0);
    return half4(float4(dot(r0, x), dot(r1, x), dot(r2, x), 1.0));
}}
"
        ),
        uniforms: &["lens", "r0", "r1", "r2"],
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fog_is_the_analytic_blend_and_infinite_depth_is_full_fog() {
        let c = [0.2, 0.4, 0.6, 0.8];
        let f = fog(c, 3.0, 0.25, 1.0, [0.5, 0.5, 0.5]);
        let t = (-0.75f32).exp();
        assert!((f[0] - (0.2 * t + 0.5 * 0.8 * (1.0 - t))).abs() < 1e-6 && f[3] == 0.8, "{f:?}");
        let f = fog(c, f32::INFINITY, 0.25, 1.0, [0.5, 0.5, 0.5]);
        assert!((f[1] - 0.4).abs() < 1e-6 && f[3] == 0.8, "{f:?}");
        assert_eq!(fog([0.0; 4], 2.0, 1.0, 1.0, [1.0; 3]), [0.0; 4], "fog never fills empty pixels");
    }

    #[test]
    fn position_inverts_the_pinhole() {
        let c2w = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]];
        let p = position([32.0, 24.0], 5.0, [64.0, 48.0], 50.0, 36.0, c2w);
        assert!(p[0].abs() < 1e-6 && p[1].abs() < 1e-6 && p[2] == 5.0 && p[3] == 1.0, "{p:?}");
        let p = position([64.0, 24.0], 5.0, [64.0, 48.0], 50.0, 36.0, c2w);
        assert!((p[0] - 0.5 * 36.0 / 50.0 * 5.0).abs() < 1e-5, "{p:?}");
        assert_eq!(position([1.0, 1.0], f32::INFINITY, [64.0, 48.0], 50.0, 36.0, c2w), [0.0; 4]);
    }
}
