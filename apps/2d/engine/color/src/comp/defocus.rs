//! `defocus` (X4c): a depth-aware disc gather, a thin-lens circle of confusion from the depth pass. Aux image 1 = depth.
//!
//! CoC diameter on the sensor c = A·f·|z − s| / (z·(s − f)), A = f/N; the disc radius in px is c/2 · (box.w / film width). Per
//! pixel: the pixels within `INNER` px exactly (20 neighbours and itself, one px² each: a disc of a pixel or two is never left to
//! a tap or two), then `n` taps on a Vogel ring from `INNER` out to `maxRadius` (px; the cap): r² = INNER² + (R² − INNER²)(i + ½)/n,
//! each tap turned by the golden angle from the last, so every tap stands for the same area π(R² − INNER²)/n. `n` follows the area (one tap per `AREA_PER_TAP` px², at most
//! `MAX_TAPS`) unless `taps` sets it: taps far apart draw each a shifted copy of an edge (2026-10-18: 64 taps on r = R·u² put the
//! outer ones ~10 px apart at R = 24, and the halos of far boxes over the sky came out as stair-stepped ghost copies). The whole
//! pattern turns per pixel by interleaved gradient noise, so what spacing remains reads as fine grain, not as copies. A tap
//! contributes as scatter-as-gather: its own CoC radius if it is in front of the centre (soft over 2 % of the centre's depth),
//! else the centre's; weight = area · coverage of the tap's distance by that radius / (π max(r, ½)²). Infinite depth (≥ 6e4: a half float's +inf) reads as `maxDepth`; never NaN. The limit: radius ≤ maxRadius.

use super::aov::PRELUDE;
use super::Program;

/// cos and sin of the golden angle (2.3999632 rad).
const GC: f32 = -0.737_368_9;
const GS: f32 = 0.675_490_3;
/// px² of the disc per tap when `taps` is automatic (0), and the most taps a pixel takes.
pub const AREA_PER_TAP: f32 = 3.0;
pub const MAX_TAPS: f32 = 1024.0;
/// The radius (px) read pixel by pixel.
pub const INNER: f32 = 2.5;

pub struct Defocus {
    /// Focal length (m), f-stop, focus distance (m), film width (m).
    pub lens: [f32; 4],
    pub max_radius: f32,
    pub max_depth: f32,
    /// Taps per pixel; 0 = from the disc's area.
    pub taps: f32,
}

fn depth_of(d: &Defocus, z: f32) -> f32 {
    if z < super::aov::FAR { z.min(d.max_depth) } else { d.max_depth }
}

/// The disc radius in px for view depth `z` (`size_w`: the box width in px).
pub fn coc_radius(d: &Defocus, z: f32, size_w: f32) -> f32 {
    let [f, n, s, film] = d.lens;
    let z = depth_of(d, z).max(1e-3);
    (0.5 * (f / n) * f * (z - s).abs() / (z * (s - f).max(1e-6)) * size_w / film).min(d.max_radius)
}

/// The taps a pixel takes: `taps`, else one per `AREA_PER_TAP` px² of the disc; 1 … `MAX_TAPS`.
pub fn tap_count(d: &Defocus) -> f32 {
    let n = if d.taps > 0.0 { d.taps } else { (std::f32::consts::PI * d.max_radius * d.max_radius / AREA_PER_TAP).ceil() };
    n.clamp(1.0, MAX_TAPS).floor()
}

fn fract(x: f32) -> f32 {
    x - x.floor()
}

/// Interleaved gradient noise (Jimenez 2014) at pixel centre `q`: the pattern's turn, in turns.
fn ign(q: [f32; 2]) -> f32 {
    fract(52.982_918 * fract(0.067_110_56 * q[0] + 0.005_837_15 * q[1]))
}

fn weight(re: f32, dist: f32, geo: f32) -> f32 {
    geo * (re - dist + 0.5).clamp(0.0, 1.0) / (std::f32::consts::PI * re.max(0.5).powi(2))
}

/// A pixel's depth for the gather: the nearest depth in its 3×3 (reads outside the frame clamp to the edge pixel). An antialiased edge
/// pixel of a bright emitter carries the emitter's light but the far sky's depth; this gives it the emitter's, so it spreads with the emitter's circle.
fn nearest_depth(depth: &impl Fn(i32, i32) -> f32, p: [i32; 2], size: [f32; 2], d: &Defocus) -> f32 {
    let mut z = f32::INFINITY;
    for j in -1..=1 {
        for i in -1..=1 {
            let (x, y) = ((p[0] + i).clamp(0, size[0] as i32 - 1), (p[1] + j).clamp(0, size[1] as i32 - 1));
            z = z.min(depth_of(d, depth(x, y)));
        }
    }
    z
}

/// The CPU twin at pixel centre `q`; `src(i, j)` premultiplied, `depth(i, j)` view depth, texels clamped into `size`.
pub fn defocus_pixel(src: &impl Fn(i32, i32) -> [f32; 4], depth: &impl Fn(i32, i32) -> f32, q: [f32; 2], size: [f32; 2], d: &Defocus) -> [f32; 4] {
    let snap = |p: [f32; 2]| [p[0].floor().clamp(0.0, size[0] - 1.0) as i32, p[1].floor().clamp(0.0, size[1] - 1.0) as i32];
    let z_at = |p: [i32; 2]| nearest_depth(depth, p, size, d);
    let c = snap(q);
    let (zc, c0) = (depth_of(d, z_at(c)), coc_radius(d, z_at(c), size[0]));
    let n = tap_count(d);
    let r0 = INNER.min(d.max_radius);
    let ring = d.max_radius * d.max_radius - r0 * r0;
    let area = std::f32::consts::PI * ring / n;
    let mut acc = [0.0f32; 4];
    let mut w_sum = 0.0;
    let mut add = |p: [i32; 2], r: f32, geo: f32| {
        let zs = z_at(p);
        let fr = ((zc - depth_of(d, zs)) / (0.02 * zc + 1e-4)).clamp(0.0, 1.0);
        let re = c0 + (coc_radius(d, zs, size[0]) - c0) * fr;
        let w = weight(re, r, geo);
        let t = src(p[0], p[1]);
        for k in 0..4 {
            acc[k] += t[k] * w;
        }
        w_sum += w;
    };
    for j in -2..=2 {
        for i in -2..=2 {
            let r2 = (i * i + j * j) as f32;
            if r2 <= r0 * r0 {
                add(snap([q[0] + i as f32, q[1] + j as f32]), r2.sqrt(), 1.0);
            }
        }
    }
    // The tap direction turns by the golden angle each tap (a recurrence, not cos / sin of i·2.4: the twin and the shader then agree to the pixel).
    let a0 = std::f32::consts::TAU * ign(q);
    let mut dir = [a0.cos(), a0.sin()];
    for i in 0..n as i32 {
        let t = dir;
        dir = [t[0] * GC - t[1] * GS, t[1] * GC + t[0] * GS];
        if ring <= 0.0 {
            break;
        }
        let r = (r0 * r0 + ring * (i as f32 + 0.5) / n).sqrt();
        add(snap([q[0] + r * t[0], q[1] + r * t[1]]), r, area);
    }
    if w_sum <= 1e-12 { src(c[0], c[1]) } else { acc.map(|v| v / w_sum) }
}

pub(crate) fn program() -> Program {
    Program {
        name: "defocus",
        blender: false,
        code: format!(
            "{PRELUDE}uniform float4 lens; uniform float maxRadius; uniform float maxDepth; uniform float taps;
float rad(float z) {{
    z = max(far(z, maxDepth), 0.001);
    return min(0.5 * (lens.x / lens.y) * lens.x * abs(z - lens.z) / (z * max(lens.z - lens.x, 1e-6)) * box.z / lens.w, maxRadius);
}}
float wgt(float re, float dist, float geo) {{ return geo * clamp(re - dist + 0.5, 0.0, 1.0) / (3.14159265 * pow(max(re, 0.5), 2.0)); }}
float zn(float2 q) {{
    float z = 1e30;
    for (int j = -1; j <= 1; j++) {{
        for (int i = 0; i <= 2; i++) {{ z = min(z, far(A(1, q + float2(float(i - 1), float(j))).r, maxDepth)); }}
    }}
    return z;
}}
half4 main(float2 p) {{
    float2 q = floor(p - box.xy) + 0.5;
    float zc = zn(q);
    float c0 = rad(zc);
    float n = floor(clamp(taps > 0.0 ? taps : ceil(3.14159265 * maxRadius * maxRadius / {AREA_PER_TAP:.1}), 1.0, {MAX_TAPS:.1}));
    float r0 = min({INNER:.1}, maxRadius);
    float ring = maxRadius * maxRadius - r0 * r0;
    float area = 3.14159265 * ring / n;
    float4 acc = float4(0.0);
    float wsum = 0.0;
    for (int j = -2; j <= 2; j++) {{
        for (int i = -2; i <= 2; i++) {{
            float r2 = float(i * i + j * j);
            if (r2 <= r0 * r0) {{
                float2 pq = q + float2(float(i), float(j));
                float zs = zn(pq);
                float fr = clamp((zc - far(zs, maxDepth)) / (0.02 * zc + 1e-4), 0.0, 1.0);
                float w = wgt(c0 + (rad(zs) - c0) * fr, sqrt(r2), 1.0);
                acc += S(pq) * w;
                wsum += w;
            }}
        }}
    }}
    float a0 = 6.28318531 * fract(52.982918 * fract(0.06711056 * q.x + 0.00583715 * q.y));
    float2 dir = float2(cos(a0), sin(a0));
    for (int i = 0; i < {MAX_TAPS:.0}; i++) {{
        if (float(i) >= n || ring <= 0.0) {{ break; }}
        float2 t = dir;
        dir = float2(t.x * {GC} - t.y * {GS}, t.y * {GC} + t.x * {GS});
        float r = sqrt(r0 * r0 + ring * (float(i) + 0.5) / n);
        float2 pq = q + r * t;
        float zs = zn(pq);
        float fr = clamp((zc - far(zs, maxDepth)) / (0.02 * zc + 1e-4), 0.0, 1.0);
        float re = c0 + (rad(zs) - c0) * fr;
        float w = wgt(re, r, area);
        acc += S(pq) * w;
        wsum += w;
    }}
    return half4(wsum <= 1e-12 ? S(q) : acc / wsum);
}}
"
        ),
        uniforms: &["lens", "maxRadius", "maxDepth", "taps"],
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_circle_of_confusion_is_zero_at_focus_and_follows_the_formula() {
        let d = Defocus { lens: [0.05, 2.0, 4.0, 0.036], max_radius: 1e9, max_depth: 1e4, taps: 64.0 };
        assert_eq!(coc_radius(&d, 4.0, 1920.0), 0.0);
        // f = 50 mm, N = 2, s = 4 m, z = 8 m: c = (0.025·0.05·4) / (8·3.95) m on the sensor → px by 1920 / 0.036.
        let want = 0.5 * 0.025 * 0.05 * 4.0 / (8.0 * 3.95) * 1920.0 / 0.036;
        assert!((coc_radius(&d, 8.0, 1920.0) - want).abs() / want < 1e-5);
        assert!(coc_radius(&d, f32::INFINITY, 1920.0).is_finite());
    }

    #[test]
    fn in_focus_is_unchanged_and_a_sharp_front_edge_holds() {
        let d = Defocus { lens: [0.05, 2.0, 4.0, 0.036], max_radius: 16.0, max_depth: 1e4, taps: 64.0 };
        let src = |i: i32, _j: i32| if i < 32 { [1.0, 0.0, 0.0, 1.0] } else { [0.0, 0.0, 1.0, 1.0] };
        let flat = |_: i32, _: i32| 4.0;
        for i in [10, 31, 32, 50] {
            let c = defocus_pixel(&src, &flat, [i as f32 + 0.5, 20.5], [64.0, 48.0], &d);
            assert!((c[0] - src(i, 0)[0]).abs() < 1e-5 && (c[2] - src(i, 0)[2]).abs() < 1e-5, "{i}: {c:?}");
        }
        // Sharp (in focus) left half in front of a far, blurred right half: the left keeps its edge, the right never bleeds over it.
        let z = |i: i32, _: i32| if i < 32 { 4.0 } else { 60.0 };
        let c = defocus_pixel(&src, &z, [31.5, 20.5], [64.0, 48.0], &d);
        assert!(c[0] > 0.999, "foreground edge pixel: {c:?}");
    }

    /// A bright emitter's antialiased edge pixel carries its light but the far sky's depth: the 3×3 nearest-depth pass gives it the near depth.
    #[test]
    fn an_emitter_edge_pixel_takes_the_near_depth() {
        let d = Defocus { lens: [0.05, 2.0, 4.0, 0.036], max_radius: 16.0, max_depth: 1e4, taps: 64.0 };
        let size = [32.0, 32.0];
        // A disc of radius 6 at (16,16), 17 m away, over infinite sky; depth is the disc's where coverage > 0.5, so the 1-px rim keeps sky depth.
        let cov = |i: i32, j: i32| ((6.5 - (((i - 16) * (i - 16) + (j - 16) * (j - 16)) as f32).sqrt()).clamp(0.0, 1.0));
        let depth = |i: i32, j: i32| if cov(i, j) > 0.5 { 17.0 } else { f32::INFINITY };
        let rim = (22, 16); // coverage 0.5: lamp light, sky depth
        assert!(cov(rim.0, rim.1) > 0.0 && depth(rim.0, rim.1).is_infinite());
        assert_eq!(nearest_depth(&depth, [rim.0, rim.1], size, &d), 17.0);
        // Far from the disc: still the sky (max depth); at the frame's corner: clamped reads, never 0.
        assert_eq!(nearest_depth(&depth, [0, 0], size, &d), 1e4);
        let flat = |_: i32, _: i32| 9.0;
        assert_eq!(nearest_depth(&flat, [0, 31], size, &d), 9.0);
    }

    /// A far box over infinite sky (the 2026-10-18 stair-step halos): the twin vs a dense disc average of the same radius.
    #[test]
    fn a_box_corner_blurs_like_a_dense_disc_not_like_shifted_copies() {
        let (w, h) = (96usize, 96usize);
        let d = Defocus { lens: [0.2, 1.4, 3.0, 0.012], max_radius: 24.0, max_depth: 1000.0, taps: 0.0 };
        let inside = |i: i32, j: i32| (24..72).contains(&i) && (40..96).contains(&j);
        let src = |i: i32, j: i32| if inside(i, j) { [0.1, 0.4, 1.0, 1.0] } else { [0.0, 0.0, 0.02, 1.0] };
        // Box and sky both far behind the focus: one radius (the cap) everywhere, so the right answer is a plain disc average.
        let z = |i: i32, _j: i32| if (24..72).contains(&i) { 20.0 } else { f32::INFINITY };
        let r = coc_radius(&d, 20.0, w as f32).min(coc_radius(&d, f32::INFINITY, w as f32));
        assert!(r > 20.0, "{r}");
        let dense = |x: f32, y: f32| {
            let (mut acc, mut n) = (0.0, 0.0);
            for a in -96..=96 {
                for b in -96..=96 {
                    let (dx, dy) = (a as f32 * 0.25, b as f32 * 0.25);
                    if dx * dx + dy * dy <= r * r {
                        let (i, j) = (((x + dx).floor() as i32).clamp(0, w as i32 - 1), ((y + dy).floor() as i32).clamp(0, h as i32 - 1));
                        acc += src(i, j)[2];
                        n += 1.0;
                    }
                }
            }
            acc / n
        };
        let (mut worst, mut sum, mut count) = (0.0f32, 0.0f32, 0.0f32);
        // Around the box's top-left corner, where the halo stepped.
        for j in 24..56 {
            for i in 8..40 {
                let q = [i as f32 + 0.5, j as f32 + 0.5];
                let e = (defocus_pixel(&src, &z, q, [w as f32, h as f32], &d)[2] - dense(q[0], q[1])).abs();
                worst = worst.max(e);
                sum += e;
                count += 1.0;
            }
        }
        eprintln!("corner vs dense disc: mean {} worst {}", sum / count, worst);
        assert!(sum / count < 0.01 && worst < 0.06, "mean {} worst {worst}", sum / count);
    }
}
