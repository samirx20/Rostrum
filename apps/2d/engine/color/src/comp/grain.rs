//! The `grain` program (docs/phase2/TRACKING_CLEANUP.md §2.1): grain that matches a plate, added to a comp layer or a clip's picture.
//! A coordinate shader (`half4 main(float2 p)` reading `src`): per pixel and channel, Gaussian-ish noise (the sum of three hashed
//! uniforms) from a 3 × 3 Gaussian kernel of hashes (`sk` px: the correlation, so the noise has the plate's grain size), fresh each
//! frame (`seed` moves the hash), scaled per channel by `std` (display-referred standard deviation of the raw noise), by an amplitude
//! that follows the pixel's display luma (`curve`: four values at luma 1/8, 3/8, 5/8, 7/8, linearly between) and by `amount`.
//! The noise is added to the display-encoded colour and the result converted back, which is the same as adding it in linear light
//! scaled by the encoding's slope at the pixel: the display-referred std is the plate's, in every working space.

use super::{Program, prelude};

/// The tap offsets of the correlation kernel.
const TAPS: [i32; 3] = [-1, 0, 1];

/// Dave Hoskins' hash33 (float-only, no bit ops): three uniforms in 0 … 1 for the cell `p`.
pub fn hash3(p: [f32; 2]) -> [f32; 3] {
    let fract = |v: f32| v - v.floor();
    let mut q = [fract(p[0] * 0.1031), fract(p[1] * 0.1030), fract(p[0] * 0.0973)];
    let d = q[0] * (q[1] + 33.33) + q[1] * (q[0] + 33.33) + q[2] * (q[2] + 33.33);
    q = [q[0] + d, q[1] + d, q[2] + d];
    [fract((q[0] + q[1]) * q[2]), fract((q[0] + q[2]) * q[1]), fract((q[1] + q[2]) * q[0])]
}

/// One cell's noise per channel, unit std: Irwin–Hall of three uniforms.
fn cell(q: [f32; 2]) -> [f32; 3] {
    let a = hash3(q);
    let b = hash3([q[0] + 41.7, q[1] + 13.3]);
    let c = hash3([q[0] + 7.1, q[1] + 59.9]);
    std::array::from_fn(|k| (a[k] + b[k] + c[k] - 1.5) * 2.0)
}

/// The correlated unit-std noise of pixel `(x, y)` (frame-local integer coordinates), `sk` the kernel's σ in px, `seed` the frame's.
pub fn noise(x: f32, y: f32, sk: f32, seed: f32) -> [f32; 3] {
    let sk = sk.max(0.05);
    let (mut acc, mut w2) = ([0f32; 3], 0f32);
    for dy in TAPS {
        for dx in TAPS {
            let w = (-((dx * dx + dy * dy) as f32) / (2.0 * sk * sk)).exp();
            let n = cell([x + dx as f32 + seed * 17.0, y + dy as f32 + seed * 31.0]);
            for k in 0..3 {
                acc[k] += w * n[k];
            }
            w2 += w * w;
        }
    }
    acc.map(|v| v / w2.sqrt())
}

/// The amplitude multiplier at display luma `l` (the four `curve` values, interpolated between their centres).
pub fn amplitude(curve: [f32; 4], l: f32) -> f32 {
    let t = l.clamp(0.0, 1.0) * 4.0 - 0.5;
    let w: [f32; 4] = std::array::from_fn(|k| (1.0 - (t - k as f32).abs()).max(0.0));
    let s: f32 = w.iter().sum();
    (0..4).map(|k| curve[k] * w[k]).sum::<f32>() / s.max(1e-6)
}

pub(crate) fn program() -> Program {
    let p = prelude();
    Program {
        name: "grain",
        blender: false,
        code: format!(
            "{p}uniform shader src;
uniform float4 box;
uniform float3 std;
uniform float4 curve;
uniform float sk;
uniform float seed;
uniform float amount;
float3 h3(float2 p) {{
    float3 q = fract(float3(p.xyx) * float3(0.1031, 0.1030, 0.0973));
    q += dot(q, q.yxz + 33.33);
    return fract((q.xxy + q.yzz) * q.zyx);
}}
float3 cell(float2 q) {{
    float3 a = h3(q); float3 b = h3(q + float2(41.7, 13.3)); float3 c = h3(q + float2(7.1, 59.9));
    return (a + b + c - 1.5) * 2.0;
}}
half4 main(float2 p) {{
    half4 c = src.eval(p);
    if (c.a <= 0.0) {{ return c; }}
    float4 u = unpre(float4(c));
    float3 d = toDisp(u.rgb);
    float l = clamp(dot(d, float3(0.2126, 0.7152, 0.0722)), 0.0, 1.0);
    float t = l * 4.0 - 0.5;
    float4 w = max(float4(1.0) - abs(float4(t) - float4(0.0, 1.0, 2.0, 3.0)), float4(0.0));
    float m = dot(curve, w) / max(w.x + w.y + w.z + w.w, 0.000001);
    float s2 = max(sk, 0.05);
    float2 q0 = floor(p - box.xy) + float2(seed * 17.0, seed * 31.0);
    float3 acc = float3(0.0); float w2 = 0.0;
    for (int j = -1; j <= 1; j++) {{
        for (int i = -1; i <= 1; i++) {{
            float k = exp(-float(i * i + j * j) / (2.0 * s2 * s2));
            acc += k * cell(q0 + float2(float(i), float(j)));
            w2 += k * k;
        }}
    }}
    d = max(d + acc / sqrt(w2) * std * (m * amount), float3(0.0));
    return half4(half3(fromDisp(d) * u.a), c.a);
}}
"
        ),
        uniforms: &["std", "curve", "sk", "seed", "amount"],
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn noise_has_unit_std_and_more_correlation_with_a_wider_kernel() {
        let stats = |sk: f32| {
            let (mut s, mut s2, mut c, mut n) = (0f64, 0f64, 0f64, 0f64);
            for y in 0..64 {
                for x in 0..64 {
                    let a = noise(x as f32, y as f32, sk, 3.0)[1] as f64;
                    let b = noise(x as f32 + 1.0, y as f32, sk, 3.0)[1] as f64;
                    s += a;
                    s2 += a * a;
                    c += a * b;
                    n += 1.0;
                }
            }
            let m = s / n;
            let var = s2 / n - m * m;
            (var.sqrt(), (c / n - m * m) / var)
        };
        let (std0, rho0) = stats(0.05);
        let (std1, rho1) = stats(1.0);
        assert!((std0 - 1.0).abs() < 0.08 && (std1 - 1.0).abs() < 0.08, "std {std0} {std1}");
        assert!(rho0.abs() < 0.1 && rho1 > 0.3, "rho {rho0} {rho1}");
    }

    #[test]
    fn frames_differ_and_the_curve_interpolates() {
        assert_ne!(noise(5.0, 5.0, 0.5, 1.0), noise(5.0, 5.0, 0.5, 2.0));
        assert!((amplitude([1.0, 2.0, 3.0, 4.0], 0.0) - 1.0).abs() < 1e-6);
        assert!((amplitude([1.0, 2.0, 3.0, 4.0], 0.5) - 2.5).abs() < 1e-6);
    }
}
