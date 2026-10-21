//! `vectorBlur` (X4d): motion blur from the velocity pass, a depth-aware gather along the motion. Aux images: 1 velocity (px per frame,
//! now → next), 2 velocityPrev (previous → now; absent = `velocity`), 3 depth (absent = no depth test); `vScale` takes file px to box px.
//!
//! The exposure covers ±shutter/2 frames around the frame. Pixel `s` therefore leaves the trail A→B, A = s − velocityPrev·shutter/2,
//! B = s + velocity·shutter/2, and it contributes to the centre `c` when `c` lies within ¾ px of that segment (½ px past its ends),
//! with weight Δ/max(len, 1) (Δ = the tap spacing): scatter-as-gather, so a static pixel beside a moving object receives its trail.
//! Where to look: the 24 probe taps over `maxRadius` find the fastest pixel; `samples` taps run along its direction over ± its
//! half trail. What the trails do not cover is the pixel's own colour when it is static, else the mean of the uncovered taps (the
//! background the moving pixel uncovers). With depth, a tap behind the centre never contributes. The limit: the fastest pixel
//! must lie within `maxRadius` of the centre, and a pixel moving against several directions blurs along the fastest one's.

use super::aov::PRELUDE;
use super::Program;

pub struct VBlur {
    /// Fraction of a frame the shutter is open (0 … 1).
    pub shutter: f32,
    /// Taps along the motion (1 … 64).
    pub samples: f32,
    /// Probe radius in px.
    pub max_radius: f32,
}

type V2 = [f32; 2];

fn len(v: V2) -> f32 {
    (v[0] * v[0] + v[1] * v[1]).sqrt()
}

/// The CPU twin at pixel centre `q` (box px). `vel`, `velp` in box px per frame (`velp` = `vel` without a previous pass); `depth`
/// `None` skips the depth test. Texels clamp into `size`.
pub fn vector_blur_pixel(src: &impl Fn(i32, i32) -> [f32; 4], vel: &impl Fn(i32, i32) -> V2, velp: &impl Fn(i32, i32) -> V2, depth: Option<&dyn Fn(i32, i32) -> f32>, q: V2, size: V2, b: &VBlur) -> [f32; 4] {
    let snap = |p: V2| [p[0].floor().clamp(0.0, size[0] - 1.0) as i32, p[1].floor().clamp(0.0, size[1] - 1.0) as i32];
    let centre = |p: [i32; 2]| [p[0] as f32 + 0.5, p[1] as f32 + 0.5];
    let c = snap(q);
    let qc = centre(c);
    let colour = |p: [i32; 2]| src(p[0], p[1]);
    let h = b.shutter * 0.5;
    let (mut best, mut dir, mut reach) = (-1.0f32, [0.0f32; 2], 0.0f32);
    for i in -1..24 {
        let p = if i < 0 { c } else { snap([q[0] + b.max_radius * ((i as f32 + 0.5) / 24.0).sqrt() * (i as f32 * 2.399_963).cos(), q[1] + b.max_radius * ((i as f32 + 0.5) / 24.0).sqrt() * (i as f32 * 2.399_963).sin()]) };
        let (v, vp) = (vel(p[0], p[1]), velp(p[0], p[1]));
        let m = len(v).max(len(vp));
        if m > best {
            best = m;
            let d = if len(v) > 1e-3 { v } else { vp };
            dir = d.map(|x| x / len(d).max(1e-6));
            reach = m * h;
        }
    }
    if reach < 0.25 {
        return colour(c);
    }
    let n = b.samples.clamp(1.0, 64.0).floor();
    let delta = 2.0 * reach / n;
    let zc = depth.map(|z| z(c[0], c[1]));
    let (mut acc, mut w_sum, mut rem, mut rem_n) = ([0.0f32; 4], 0.0f32, [0.0f32; 4], 0.0f32);
    for k in 0..n as i32 {
        let t = (k as f32 + 0.5) / n * 2.0 - 1.0;
        let s = snap([qc[0] + dir[0] * reach * t, qc[1] + dir[1] * reach * t]);
        let sp = centre(s);
        let (v, vp) = (vel(s[0], s[1]), velp(s[0], s[1]));
        let (a, bb) = ([sp[0] - vp[0] * h, sp[1] - vp[1] * h], [sp[0] + v[0] * h, sp[1] + v[1] * h]);
        let seg = [bb[0] - a[0], bb[1] - a[1]];
        let l = len(seg);
        let w = [qc[0] - a[0], qc[1] - a[1]];
        let covers = l >= 0.5 && (w[0] * seg[1] - w[1] * seg[0]).abs() / l <= 0.75 && (w[0] * seg[0] + w[1] * seg[1]) / l >= -0.5 && (w[0] * seg[0] + w[1] * seg[1]) / l <= l + 0.5;
        if let (Some(zc), Some(z)) = (zc, depth) {
            if z(s[0], s[1]) > zc * 1.05 + 0.01 {
                continue;
            }
        }
        let col = colour(s);
        if covers {
            let wt = delta / l.max(1.0);
            for i in 0..4 {
                acc[i] += col[i] * wt;
            }
            w_sum += wt;
        } else {
            for i in 0..4 {
                rem[i] += col[i];
            }
            rem_n += 1.0;
        }
    }
    let (vc, vcp) = (vel(c[0], c[1]), velp(c[0], c[1]));
    let own = colour(c);
    let rest = if len([vc[0] * h + vcp[0] * h, vc[1] * h + vcp[1] * h]) < 0.5 || rem_n == 0.0 { own } else { rem.map(|x| x / rem_n) };
    let left = 1.0 - w_sum.min(1.0);
    let norm = w_sum.max(1.0);
    std::array::from_fn(|i| (acc[i] + rest[i] * left) / norm)
}

pub(crate) fn program() -> Program {
    Program {
        name: "vectorBlur",
        blender: false,
        code: format!(
            "{PRELUDE}uniform float shutter; uniform float samples; uniform float maxRadius; uniform float2 flags; uniform float vScale;
float2 V(int k, float2 q) {{ return A(k, q).rg * vScale; }}
float2 VP(float2 q) {{ return flags.x > 0.5 ? V(2, q) : V(1, q); }}
half4 main(float2 p) {{
    float2 q = floor(p - box.xy) + 0.5;
    float h = shutter * 0.5;
    float best = -1.0; float2 dir = float2(0.0); float reach = 0.0;
    for (int i = -1; i < 24; i++) {{
        float rr = maxRadius * sqrt((float(i) + 0.5) / 24.0);
        float ang = float(i) * 2.399963;
        float2 pq = i < 0 ? q : q + rr * float2(cos(ang), sin(ang));
        float2 v = V(1, pq); float2 vp = VP(pq);
        float m = max(length(v), length(vp));
        if (m > best) {{
            best = m;
            float2 d = length(v) > 1e-3 ? v : vp;
            dir = d / max(length(d), 1e-6);
            reach = m * h;
        }}
    }}
    if (reach < 0.25) {{ return half4(S(q)); }}
    float n = clamp(floor(samples), 1.0, 64.0);
    float delta = 2.0 * reach / n;
    float zc = flags.y > 0.5 ? A(3, q).r : 0.0;
    float4 acc = float4(0.0); float wsum = 0.0; float4 rem = float4(0.0); float remn = 0.0;
    for (int k = 0; k < 64; k++) {{
        if (float(k) >= n) {{ break; }}
        float t = (float(k) + 0.5) / n * 2.0 - 1.0;
        float2 sp = floor(q + dir * reach * t) + 0.5;
        sp = clamp(sp, float2(0.5), box.zw - 0.5);
        float2 v = V(1, sp); float2 vp = VP(sp);
        float2 a = sp - vp * h; float2 b = sp + v * h;
        float2 seg = b - a; float l = length(seg);
        float2 w = q - a;
        float al = l > 0.0 ? dot(w, seg) / l : 0.0;
        bool covers = l >= 0.5 && abs(w.x * seg.y - w.y * seg.x) / max(l, 1e-6) <= 0.75 && al >= -0.5 && al <= l + 0.5;
        if (flags.y > 0.5 && A(3, sp).r > zc * 1.05 + 0.01) {{ continue; }}
        float4 col = S(sp);
        if (covers) {{ float wt = delta / max(l, 1.0); acc += col * wt; wsum += wt; }}
        else {{ rem += col; remn += 1.0; }}
    }}
    float2 vc = V(1, q); float2 vcp = VP(q);
    float4 own = S(q);
    float4 rest = (length((vc + vcp) * h) < 0.5 || remn == 0.0) ? own : rem / remn;
    return half4((acc + rest * (1.0 - min(wsum, 1.0))) / max(wsum, 1.0));
}}
"
        ),
        uniforms: &["shutter", "samples", "maxRadius", "flags", "vScale"],
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn run(shutter: f32, x: i32) -> f32 {
        // A 20 px wide rectangle of value 1 on 0, moving 8 px/frame to the right; rectangle at columns 20..40, static elsewhere.
        let src = |i: i32, _: i32| if (20..40).contains(&i) { [1.0, 1.0, 1.0, 1.0] } else { [0.0, 0.0, 0.0, 1.0] };
        let vel = |i: i32, _: i32| if (20..40).contains(&i) { [8.0, 0.0] } else { [0.0, 0.0] };
        let b = VBlur { shutter, samples: 32.0, max_radius: 24.0 };
        vector_blur_pixel(&src, &vel, &vel, None, [x as f32 + 0.5, 10.5], [64.0, 20.0], &b)[0]
    }

    #[test]
    fn a_moving_rectangle_blurs_to_the_analytic_trail() {
        // Shutter 1: the edge is smeared over |v|·shutter = 8 px, centred on the edge: columns 16..24 at the leading edge x = 40 → 36..44.
        let (outside, inside) = (run(1.0, 44), run(1.0, 35));
        assert!(outside < 0.05 && inside > 0.95, "{outside} {inside}");
        let mid = run(1.0, 40);
        assert!((mid - 0.5).abs() < 0.2, "{mid}");
        // Shutter ½: the trail is 4 px: 38..42.
        assert!(run(0.5, 43) < 0.05 && run(0.5, 37) > 0.95, "{} {}", run(0.5, 43), run(0.5, 37));
        // Far static background stays black.
        assert_eq!(run(1.0, 55), 0.0);
    }
}
