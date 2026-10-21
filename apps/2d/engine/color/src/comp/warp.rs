//! The `warp` and `quadMatte` programs (docs/phase2/COMP_CORE.md §6, the corner-pin / screen-insert seam): coordinate shaders
//! (`half4 main(float2 p)`, `uniform shader src; uniform float4 box;`). All quad corners are px relative to the box origin, in
//! the order top-left, top-right, bottom-right, bottom-left, packed as two float4 (x0,y0,x1,y1 / x2,y2,x3,y3).
//!
//! `warp` pins the source quad `f` of `src` onto a destination quad that moves through the shutter (`o` open, `m` mid, `c`
//! close, quadratic Lagrange in s ∈ 0…1; `samples` shutter positions at s = (k + 0.5)/n, 1 = no blur). Per output pixel and
//! sample: uv = H⁻¹(p) with H = unit square → destination quad (Heckbert), coverage = antialiased inside-test of uv in [0,1]²
//! (a 1 screen-px ramp through the local Jacobian), position = Hf(uv) with Hf = unit square → source quad, then 4 bilinear or
//! 16 Catmull-Rom taps at texel centres (texel i is centred at i + 0.5 in box px), clamped (alpha 0…1, rgb 0…alpha). The output
//! is the mean of sample × coverage. `quadMatte` is an opaque grey `(v,v,v,1)`: 1 inside the rounded rectangle
//! [inset, 1−inset]² (corner `radius`, both fractions in uv), 0 outside, a `feather` px ramp on screen.

use super::{Program, grey};

type V2 = [f32; 2];
type Quad = [V2; 4];
/// Columns of the 3 × 3 homography acting on (x, y, 1).
type H = [[f32; 3]; 3];

/// Everything `warp` reads: quads in box px, `samples` 1 … 32, `cubic` Catmull-Rom (else bilinear).
pub struct Warp {
    pub from: Quad,
    pub open: Quad,
    pub mid: Quad,
    pub close: Quad,
    pub samples: f32,
    pub cubic: bool,
}

/// Unit square → quad (Heckbert's closed form).
fn square_to(q: &Quad) -> H {
    let (d1, d2) = ([q[1][0] - q[2][0], q[1][1] - q[2][1]], [q[3][0] - q[2][0], q[3][1] - q[2][1]]);
    let s = [q[0][0] - q[1][0] + q[2][0] - q[3][0], q[0][1] - q[1][1] + q[2][1] - q[3][1]];
    let det = d1[0] * d2[1] - d2[0] * d1[1];
    let (mut g, mut h) = (0.0, 0.0);
    if det.abs() > 1e-9 {
        g = (s[0] * d2[1] - d2[0] * s[1]) / det;
        h = (d1[0] * s[1] - s[0] * d1[1]) / det;
    }
    [[q[1][0] - q[0][0] + g * q[1][0], q[1][1] - q[0][1] + g * q[1][1], g], [q[3][0] - q[0][0] + h * q[3][0], q[3][1] - q[0][1] + h * q[3][1], h], [q[0][0], q[0][1], 1.0]]
}

fn cross(a: [f32; 3], b: [f32; 3]) -> [f32; 3] {
    [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
}

fn dot(a: [f32; 3], b: [f32; 3]) -> f32 {
    a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}

/// The point of the unit square that `h` sends to `p`; `None` when `p` is behind the quad's horizon.
fn unproject(h: &H, p: V2) -> Option<V2> {
    let (x, r2) = ([p[0], p[1], 1.0], cross(h[0], h[1]));
    let w = dot(r2, x);
    if w / dot(h[2], r2) < 1e-6 {
        return None;
    }
    Some([dot(cross(h[1], h[2]), x) / w, dot(cross(h[2], h[0]), x) / w])
}

fn project(h: &H, uv: V2) -> V2 {
    let w = h[0][2] * uv[0] + h[1][2] * uv[1] + 1.0;
    [(h[0][0] * uv[0] + h[1][0] * uv[1] + h[2][0]) / w, (h[0][1] * uv[0] + h[1][1] * uv[1] + h[2][1]) / w]
}

/// Quadratic Lagrange through `o` (s = 0), `m` (0.5), `c` (1).
fn lagrange(o: &Quad, m: &Quad, c: &Quad, s: f32) -> Quad {
    let (a, b, d) = (2.0 * (s - 0.5) * (s - 1.0), -4.0 * s * (s - 1.0), 2.0 * s * (s - 0.5));
    std::array::from_fn(|k| [0, 1].map(|i| o[k][i] * a + m[k][i] * b + c[k][i] * d))
}

/// Bilinear (0, 1−t, t, 0) or Catmull-Rom weights of the four texels around `t` ∈ [0, 1).
fn weights(t: f32, cubic: bool) -> [f32; 4] {
    if !cubic {
        return [0.0, 1.0 - t, t, 0.0];
    }
    let (t2, t3) = (t * t, t * t * t);
    [(-t3 + 2.0 * t2 - t) * 0.5, (3.0 * t3 - 5.0 * t2 + 2.0) * 0.5, (-3.0 * t3 + 4.0 * t2 + t) * 0.5, (t3 - t2) * 0.5]
}

/// The picture at `pos` (box px): the weighted texels, premultiplied, clamped so ringing never makes negative light nor colour past
/// alpha × the brightest tap's own colour ÷ alpha (`peak`, at least 1), so scene-linear light above 1 survives a pin.
fn fetch(src: &impl Fn(i32, i32) -> [f32; 4], pos: V2, cubic: bool) -> [f32; 4] {
    let (tx, ty) = (pos[0] - 0.5, pos[1] - 0.5);
    let (ix, iy) = (tx.floor(), ty.floor());
    let (wx, wy) = (weights(tx - ix, cubic), weights(ty - iy, cubic));
    let mut acc = [0f32; 4];
    let mut peak = 1f32;
    for j in 0..4 {
        for i in 0..4 {
            let w = wx[i] * wy[j];
            if w != 0.0 {
                let t = src(ix as i32 + i as i32 - 1, iy as i32 + j as i32 - 1);
                if t[3] > 1e-3 {
                    peak = peak.max(t[0].max(t[1]).max(t[2]) / t[3]);
                }
                for k in 0..4 {
                    acc[k] += w * t[k];
                }
            }
        }
    }
    let a = acc[3].clamp(0.0, 1.0);
    let top = a * peak;
    [acc[0].clamp(0.0, top), acc[1].clamp(0.0, top), acc[2].clamp(0.0, top), a]
}

/// uv of `p` in a destination quad's homography and its local screen-px scale: the uv of `p` and of `p + (1,0)`, `p + (0,1)`.
fn uv3(h: &H, p: V2) -> Option<[V2; 3]> {
    Some([unproject(h, p)?, unproject(h, [p[0] + 1.0, p[1]])?, unproject(h, [p[0], p[1] + 1.0])?])
}

/// Distance in screen px from the unit square's edge `e` (> 0 inside) along uv axis `axis`.
fn edge_px(uv: &[V2; 3], axis: usize) -> f32 {
    let g = ((uv[1][axis] - uv[0][axis]).powi(2) + (uv[2][axis] - uv[0][axis]).powi(2)).sqrt();
    uv[0][axis].min(1.0 - uv[0][axis]) / g.max(1e-6)
}

/// The CPU twin of `warp` at output pixel `p` (box px; pixel (i, j) has its centre at (i + 0.5, j + 0.5)); `src(i, j)` is
/// the premultiplied input texel, transparent outside the picture.
pub fn warp_pixel(src: &impl Fn(i32, i32) -> [f32; 4], p: V2, w: &Warp) -> [f32; 4] {
    let n = (w.samples + 0.5).floor().clamp(1.0, 32.0);
    let hf = square_to(&w.from);
    let mut sum = [0f32; 4];
    for k in 0..n as i32 {
        let q = lagrange(&w.open, &w.mid, &w.close, (k as f32 + 0.5) / n);
        let Some(uv) = uv3(&square_to(&q), p) else { continue };
        let cov = (0.5 + edge_px(&uv, 0)).clamp(0.0, 1.0) * (0.5 + edge_px(&uv, 1)).clamp(0.0, 1.0);
        if cov > 0.0 {
            let c = fetch(src, project(&hf, uv[0]), w.cubic);
            for i in 0..4 {
                sum[i] += c[i] * cov;
            }
        }
    }
    sum.map(|v| v / n)
}

/// Signed distance (uv units, < 0 inside) to the rounded rectangle [inset, 1−inset]² with corner `radius`.
fn rounded(uv: V2, inset: f32, radius: f32) -> f32 {
    let r = radius.min(0.5 - inset).max(0.0);
    let half = 0.5 - inset - r;
    let q = [(uv[0] - 0.5).abs() - half, (uv[1] - 0.5).abs() - half];
    (q[0].max(0.0).powi(2) + q[1].max(0.0).powi(2)).sqrt() + q[0].max(q[1]).min(0.0) - r
}

/// The CPU twin of `quadMatte` at `p` (box px): 1 inside the rounded rectangle of the quad's plane, 0 outside.
pub fn quad_matte(p: V2, quad: &Quad, inset: f32, radius: f32, feather: f32) -> [f32; 4] {
    let Some(uv) = uv3(&square_to(quad), p) else { return grey(0.0) };
    let d = uv.map(|u| rounded(u, inset, radius));
    let g = ((d[1] - d[0]).powi(2) + (d[2] - d[0]).powi(2)).sqrt();
    grey((0.5 - d[0] / g.max(1e-9) / feather.max(1e-3)).clamp(0.0, 1.0))
}

/// The homography helpers, shared by both programs (the same formulas as above).
const HELPERS: &str = "float3x3 sqTo(float4 a, float4 b) {
    float2 p0 = a.xy; float2 p1 = a.zw; float2 p2 = b.xy; float2 p3 = b.zw;
    float2 d1 = p1 - p2; float2 d2 = p3 - p2; float2 s = p0 - p1 + p2 - p3;
    float det = d1.x * d2.y - d2.x * d1.y;
    float g = 0.0; float h = 0.0;
    if (abs(det) > 1e-9) { g = (s.x * d2.y - d2.x * s.y) / det; h = (d1.x * s.y - s.x * d1.y) / det; }
    return float3x3(p1.x - p0.x + g * p1.x, p1.y - p0.y + g * p1.y, g, p3.x - p0.x + h * p3.x, p3.y - p0.y + h * p3.y, h, p0.x, p0.y, 1.0);
}
float2 unproj(float3x3 H, float2 p, out float ok) {
    float3 x = float3(p, 1.0);
    float3 r2 = cross(H[0], H[1]);
    float w = dot(r2, x);
    ok = (w / dot(H[2], r2) < 1e-6) ? 0.0 : 1.0;
    w = (ok > 0.5) ? w : 1.0;
    return float2(dot(cross(H[1], H[2]), x), dot(cross(H[2], H[0]), x)) / w;
}
float2 proj(float3x3 H, float2 uv) {
    float w = H[0].z * uv.x + H[1].z * uv.y + 1.0;
    return float2(H[0].x * uv.x + H[1].x * uv.y + H[2].x, H[0].y * uv.x + H[1].y * uv.y + H[2].y) / w;
}
// uv of p, p + (1,0), p + (0,1); `ok` is 0 behind the horizon.
void uv3(float3x3 H, float2 p, out float2 a, out float2 b, out float2 c, out float ok) {
    float o1; float o2;
    a = unproj(H, p, ok); b = unproj(H, p + float2(1.0, 0.0), o1); c = unproj(H, p + float2(0.0, 1.0), o2);
    ok = min(ok, min(o1, o2));
}
float edgePx(float2 a, float2 b, float2 c, int axis) {
    float u = axis == 0 ? a.x : a.y;
    float g = axis == 0 ? length(float2(b.x - a.x, c.x - a.x)) : length(float2(b.y - a.y, c.y - a.y));
    return min(u, 1.0 - u) / max(g, 1e-6);
}
";

pub(crate) fn warp() -> Program {
    Program {
        name: "warp",
        blender: false,
        code: format!(
            "uniform shader src;
uniform float4 box;
uniform float4 f01; uniform float4 f23;
uniform float4 o01; uniform float4 o23;
uniform float4 m01; uniform float4 m23;
uniform float4 c01; uniform float4 c23;
uniform float samples;
uniform float cubic;
{HELPERS}float4 wts(float t) {{
    if (cubic < 0.5) {{ return float4(0.0, 1.0 - t, t, 0.0); }}
    float t2 = t * t; float t3 = t2 * t;
    return float4((-t3 + 2.0 * t2 - t) * 0.5, (3.0 * t3 - 5.0 * t2 + 2.0) * 0.5, (-3.0 * t3 + 4.0 * t2 + t) * 0.5, (t3 - t2) * 0.5);
}}
float4 fetch(float2 pos) {{
    float2 t = pos - 0.5; float2 i0 = floor(t);
    float4 wx = wts(t.x - i0.x); float4 wy = wts(t.y - i0.y);
    float4 acc = float4(0.0); float peak = 1.0;
    for (int j = 0; j < 4; j++) {{
        for (int i = 0; i < 4; i++) {{
            float w = wx[i] * wy[j];
            if (w != 0.0) {{
                float4 t = float4(src.eval(box.xy + i0 + float2(float(i) - 0.5, float(j) - 0.5)));
                if (t.a > 0.001) {{ peak = max(peak, max(t.r, max(t.g, t.b)) / t.a); }}
                acc += w * t;
            }}
        }}
    }}
    float a = clamp(acc.a, 0.0, 1.0);
    return float4(clamp(acc.rgb, float3(0.0), float3(a * peak)), a);
}}
half4 main(float2 p) {{
    float n = clamp(floor(samples + 0.5), 1.0, 32.0);
    float3x3 hf = sqTo(f01, f23);
    float2 q = p - box.xy;
    float4 sum = float4(0.0);
    for (int k = 0; k < 32; k++) {{
        if (float(k) >= n) {{ break; }}
        float s = (float(k) + 0.5) / n;
        float a = 2.0 * (s - 0.5) * (s - 1.0); float b = -4.0 * s * (s - 1.0); float d = 2.0 * s * (s - 0.5);
        float3x3 H = sqTo(o01 * a + m01 * b + c01 * d, o23 * a + m23 * b + c23 * d);
        float2 u0; float2 u1; float2 u2; float ok;
        uv3(H, q, u0, u1, u2, ok);
        if (ok < 0.5) {{ continue; }}
        float cov = clamp(0.5 + edgePx(u0, u1, u2, 0), 0.0, 1.0) * clamp(0.5 + edgePx(u0, u1, u2, 1), 0.0, 1.0);
        if (cov > 0.0) {{ sum += fetch(proj(hf, u0)) * cov; }}
    }}
    return half4(sum / n);
}}
"
        ),
        uniforms: &["f01", "f23", "o01", "o23", "m01", "m23", "c01", "c23", "samples", "cubic"],
    }
}

pub(crate) fn quad_matte_program() -> Program {
    Program {
        name: "quadMatte",
        blender: false,
        code: format!(
            "uniform shader src;
uniform float4 box;
uniform float4 q01; uniform float4 q23;
uniform float inset;
uniform float radius;
uniform float feather;
{HELPERS}float rounded(float2 uv) {{
    float r = max(min(radius, 0.5 - inset), 0.0);
    float2 q = abs(uv - 0.5) - (0.5 - inset - r);
    return length(max(q, float2(0.0))) + min(max(q.x, q.y), 0.0) - r;
}}
half4 main(float2 p) {{
    float2 u0; float2 u1; float2 u2; float ok;
    uv3(sqTo(q01, q23), p - box.xy, u0, u1, u2, ok);
    if (ok < 0.5) {{ return half4(0.0, 0.0, 0.0, 1.0); }}
    float d0 = rounded(u0); float d1 = rounded(u1); float d2 = rounded(u2);
    float g = length(float2(d1 - d0, d2 - d0));
    float v = clamp(0.5 - d0 / max(g, 1e-9) / max(feather, 1e-3), 0.0, 1.0);
    return half4(v, v, v, 1.0);
}}
"
        ),
        uniforms: &["q01", "q23", "inset", "radius", "feather"],
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const SQ: Quad = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]];

    #[test]
    fn homography_maps_the_corners_and_inverts() {
        let q: Quad = [[3.0, 2.0], [40.0, 6.0], [35.0, 30.0], [1.0, 25.0]];
        let h = square_to(&q);
        for (k, uv) in [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]].iter().enumerate() {
            let p = project(&h, *uv);
            assert!((p[0] - q[k][0]).abs() < 1e-4 && (p[1] - q[k][1]).abs() < 1e-4, "{k}: {p:?}");
        }
        let back = unproject(&h, project(&h, [0.3, 0.7])).unwrap();
        assert!((back[0] - 0.3).abs() < 1e-5 && (back[1] - 0.7).abs() < 1e-5, "{back:?}");
    }

    #[test]
    fn an_identity_pin_returns_the_picture_and_blur_averages_the_shutter() {
        let src = |i: i32, j: i32| if (0..10).contains(&i) && (0..10).contains(&j) { [i as f32 / 10.0, 0.0, 0.0, 1.0] } else { [0.0; 4] };
        let w = Warp { from: SQ, open: SQ, mid: SQ, close: SQ, samples: 1.0, cubic: true };
        let c = warp_pixel(&src, [4.5, 5.5], &w);
        assert!((c[0] - 0.4).abs() < 1e-5 && c[3] == 1.0, "{c:?}");
        assert_eq!(warp_pixel(&src, [-3.0, 5.5], &w), [0.0; 4]);
        // Moving 4 px across the shutter: the pixel at x = 2.5 is covered only by the samples whose quad has passed it.
        let moved: Quad = SQ.map(|p| [p[0] + 4.0, p[1]]);
        let w = Warp { from: SQ, open: SQ, mid: SQ.map(|p| [p[0] + 2.0, p[1]]), close: moved, samples: 8.0, cubic: false };
        let a = warp_pixel(&|_, _| [1.0; 4], [2.5, 5.5], &w)[3];
        assert!(a > 0.5 && a < 1.0, "{a}");
    }

    #[test]
    fn the_matte_is_one_inside_zero_outside_and_rounds_the_corner() {
        let m = |x: f32, y: f32, inset: f32, r: f32| quad_matte([x, y], &SQ, inset, r, 1.0)[0];
        assert_eq!(m(5.0, 5.0, 0.0, 0.0), 1.0);
        assert_eq!(m(12.0, 5.0, 0.0, 0.0), 0.0);
        assert_eq!(m(0.5, 0.5, 0.0, 0.0), 1.0);
        assert_eq!(m(0.5, 0.5, 0.0, 0.4), 0.0, "a rounded corner leaves the corner pixel out");
        assert!(m(1.5, 5.0, 0.1, 0.0) > 0.99 && m(0.5, 5.0, 0.1, 0.0) < 0.01, "inset");
    }
}
