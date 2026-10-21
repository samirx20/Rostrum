//! The `compress` program (docs/phase2/COMPOSITING.md, V5): a layer given a codec's look. A coordinate shader (`half4 main(float2 p)`
//! reading `src`) that runs JPEG's own transform on the picture's display colour: RGB → YCbCr, the pixel's 8 × 8 block (luma; chroma
//! blocks cover 16 × 16 px when `chroma` > 0.5, each chroma sample the mean of a 2 × 2 cell: 4:2:0) through the orthonormal DCT, every
//! coefficient quantised by a step that grows with frequency (`strength` × a JPEG-like table: 16 + 5.93 (u + v) for luma, capped at 121;
//! 17 + 5.93 (u + v) for chroma, capped at 99; in 0 … 255 units, so `strength` 1 is about JPEG quality 50, 0.5 quality 75, 2 quality 25),
//! then the inverse for the pixel itself. Detail loss (high frequencies gone), block edges and ringing next to edges all come from that
//! one rounding. `ringing` 1 rounds like a codec; 0 shrinks each coefficient toward 0 by half its step instead (the detail goes, the
//! rounding noise does not). The block grid is the box's own pixel grid (a plate's blocks start at its picture's corner); colour of
//! transparent neighbours is taken from the pixel itself, alpha is kept. The picture is processed at the render's pixel size.
//! Display values past 1 (a plate brought in through a view's inverse, e.g. AgX, holds whites and bright greens at 10 … 1000×)
//! go through a log shoulder first (|x| > 1 → ±(1 + ln |x|), undone after): on the encoded value itself the rounding error grew
//! with the value and, raised to 2.4 back to linear, overflowed the half-float picture into black and coloured specks. 0 … 1 is untouched.
//!
//! The CPU twin ([`compress_rgb`]) runs the same maths on a straight display-encoded opaque RGB image.

use super::{Program, prelude};

/// Luma quantisation step at frequency (u, v), 0 … 255 units, at `strength` 1.
pub fn q_luma(u: usize, v: usize) -> f32 {
    (16.0 + 5.93 * (u + v) as f32).min(121.0)
}

/// Chroma quantisation step at frequency (u, v), at `strength` 1.
pub fn q_chroma(u: usize, v: usize) -> f32 {
    (17.0 + 5.93 * (u + v) as f32).min(99.0)
}

/// The orthonormal 8-point DCT basis: `c[u][x]`.
fn basis() -> [[f32; 8]; 8] {
    std::array::from_fn(|u| {
        let a = if u == 0 { 0.353_553_4 } else { 0.5 };
        std::array::from_fn(|x| a * ((2 * x + 1) as f32 * u as f32 * std::f32::consts::PI / 16.0).cos())
    })
}

fn quantise(f: f32, q: f32, ringing: f32) -> f32 {
    let hard = (f / q + 0.5).floor() * q;
    let soft = f.signum() * (f.abs() - 0.5 * q).max(0.0);
    soft + (hard - soft) * ringing
}

/// One block's channel through the transform and quantisation; returns the reconstructed value at (ox, oy).
fn block(d: &[f32; 64], q: &dyn Fn(usize, usize) -> f32, strength: f32, ringing: f32, ox: usize, oy: usize) -> f32 {
    let c = basis();
    let mut t = [0f32; 64];
    for y in 0..8 {
        for u in 0..8 {
            t[y * 8 + u] = (0..8).map(|x| d[y * 8 + x] * c[u][x]).sum();
        }
    }
    let mut out = 0.0;
    for v in 0..8 {
        for u in 0..8 {
            let f: f32 = (0..8).map(|y| t[y * 8 + u] * c[v][y]).sum();
            out += quantise(f, strength * q(u, v), ringing) * c[u][ox] * c[v][oy];
        }
    }
    out
}

/// The log shoulder past 1 (identity on -1 … 1, C¹ at ±1) and its inverse, capped where the inverse reaches the half-float range.
pub fn shoulder(x: f32) -> f32 {
    if x.abs() <= 1.0 { x } else { x.signum() * (1.0 + x.abs().ln()) }
}

pub fn unshoulder(x: f32) -> f32 {
    if x.abs() <= 1.0 { x } else { x.signum() * (x.abs().min(SHOULDER_CAP) - 1.0).exp() }
}

/// Shouldered value whose inverse, decoded to linear, stays inside half floats (e^(10.5 − 1) ≈ 13 360 encoded … well past any view's white).
const SHOULDER_CAP: f32 = 10.5;

fn to_ycc(c: [f32; 3]) -> [f32; 3] {
    let (r, g, b) = (shoulder(c[0]), shoulder(c[1]), shoulder(c[2]));
    [(0.299 * r + 0.587 * g + 0.114 * b - 0.5) * 255.0, (-0.168_736 * r - 0.331_264 * g + 0.5 * b) * 255.0, (0.5 * r - 0.418_688 * g - 0.081_312 * b) * 255.0]
}

fn from_ycc(y: f32, cb: f32, cr: f32) -> [f32; 3] {
    let (y, cb, cr) = (y / 255.0 + 0.5, cb / 255.0, cr / 255.0);
    [unshoulder(y + 1.402 * cr).max(0.0), unshoulder(y - 0.344_136 * cb - 0.714_136 * cr).max(0.0), unshoulder(y + 1.772 * cb).max(0.0)]
}

/// The CPU twin on a straight, display-encoded, opaque RGB image (`w` × `h`, row-major); outside the picture reads as the pixel's own colour.
pub fn compress_rgb(px: &[[f32; 3]], w: usize, h: usize, strength: f32, chroma: bool, ringing: f32) -> Vec<[f32; 3]> {
    let at = |x: i64, y: i64, own: [f32; 3]| if x < 0 || y < 0 || x >= w as i64 || y >= h as i64 { own } else { px[y as usize * w + x as usize] };
    let s = if chroma { 2i64 } else { 1 };
    let mut out = vec![[0f32; 3]; w * h];
    for py in 0..h as i64 {
        for pxx in 0..w as i64 {
            let own = px[py as usize * w + pxx as usize];
            if strength <= 0.0 {
                out[py as usize * w + pxx as usize] = own;
                continue;
            }
            let (ox, oy) = ((pxx / 8) * 8, (py / 8) * 8);
            let mut ly = [0f32; 64];
            for j in 0..8 {
                for i in 0..8 {
                    ly[(j * 8 + i) as usize] = to_ycc(at(ox + i, oy + j, own))[0];
                }
            }
            let (cx, cy) = ((pxx / (8 * s)) * 8 * s, (py / (8 * s)) * 8 * s);
            let (mut cb, mut cr) = ([0f32; 64], [0f32; 64]);
            for j in 0..8 {
                for i in 0..8 {
                    let (mut a, mut b) = (0.0, 0.0);
                    for dj in 0..s {
                        for di in 0..s {
                            let t = to_ycc(at(cx + s * i + di, cy + s * j + dj, own));
                            a += t[1];
                            b += t[2];
                        }
                    }
                    let n = (s * s) as f32;
                    cb[(j * 8 + i) as usize] = a / n;
                    cr[(j * 8 + i) as usize] = b / n;
                }
            }
            let y = block(&ly, &q_luma, strength, ringing, (pxx - ox) as usize, (py - oy) as usize);
            let (qx, qy) = (((pxx - cx) / s) as usize, ((py - cy) / s) as usize);
            let u = block(&cb, &q_chroma, strength, ringing, qx, qy);
            let v = block(&cr, &q_chroma, strength, ringing, qx, qy);
            out[py as usize * w + pxx as usize] = from_ycc(y, u, v);
        }
    }
    out
}

pub(crate) fn program() -> Program {
    let p = prelude();
    Program {
        name: "compress",
        blender: false,
        code: format!(
            "{p}uniform shader src;
uniform float4 box;
uniform float strength;
uniform float chroma;
uniform float ringing;
float sh(float x) {{ return abs(x) <= 1.0 ? x : sign(x) * (1.0 + log(abs(x))); }}
float unsh(float x) {{ return abs(x) <= 1.0 ? x : sign(x) * exp(min(abs(x), {cap}) - 1.0); }}
float3 ycc(float2 q, float3 own) {{
    half4 t = src.eval(q);
    float3 c = t.a > 0.0 ? toDisp(float3(t.rgb) / float(t.a)) : own;
    c = float3(sh(c.r), sh(c.g), sh(c.b));
    return float3((0.299 * c.r + 0.587 * c.g + 0.114 * c.b - 0.5) * 255.0,
                  (-0.168736 * c.r - 0.331264 * c.g + 0.5 * c.b) * 255.0,
                  (0.5 * c.r - 0.418688 * c.g - 0.081312 * c.b) * 255.0);
}}
half4 main(float2 p) {{
    half4 c0 = src.eval(p);
    if (c0.a <= 0.0 || strength <= 0.0) {{ return c0; }}
    float3 own = toDisp(float3(c0.rgb) / float(c0.a));
    float2 pix = floor(p - box.xy);
    float s = chroma > 0.5 ? 2.0 : 1.0;
    float2 o8 = floor(pix / 8.0) * 8.0;
    float2 oc = floor(pix / (8.0 * s)) * 8.0 * s;
    float2 g = box.xy + 0.5;
    float C[64];
    for (int u = 0; u < 8; u++) {{
        float a = u == 0 ? 0.35355339 : 0.5;
        for (int x = 0; x < 8; x++) {{ C[u * 8 + x] = a * cos((2.0 * float(x) + 1.0) * float(u) * 0.19634954); }}
    }}
    float dy[64];
    float dcb[64];
    float dcr[64];
    for (int j = 0; j < 8; j++) {{
        for (int i = 0; i < 8; i++) {{
            float3 t = ycc(g + o8 + float2(float(i), float(j)), own);
            float3 k = t;
            if (s > 1.5) {{
                k = float3(0.0);
                for (int dj = 0; dj < 2; dj++) {{
                    for (int di = 0; di < 2; di++) {{ k += ycc(g + oc + s * float2(float(i), float(j)) + float2(float(di), float(dj)), own); }}
                }}
                k *= 0.25;
            }}
            dy[j * 8 + i] = t.x;
            dcb[j * 8 + i] = k.y;
            dcr[j * 8 + i] = k.z;
        }}
    }}
    float2 l = pix - o8;
    float2 lc = floor((pix - oc) / s);
    float3 res = float3(0.0);
    for (int ch = 0; ch < 3; ch++) {{
        float t[64];
        for (int y = 0; y < 8; y++) {{
            for (int u = 0; u < 8; u++) {{
                float a = 0.0;
                for (int x = 0; x < 8; x++) {{ float dv = ch == 0 ? dy[y * 8 + x] : (ch == 1 ? dcb[y * 8 + x] : dcr[y * 8 + x]); a += dv * C[u * 8 + x]; }}
                t[y * 8 + u] = a;
            }}
        }}
        float2 at = ch == 0 ? l : lc;
        float acc = 0.0;
        for (int v = 0; v < 8; v++) {{
            for (int u = 0; u < 8; u++) {{
                float f = 0.0;
                for (int y = 0; y < 8; y++) {{ f += t[y * 8 + u] * C[v * 8 + y]; }}
                float q = strength * (ch == 0 ? min(16.0 + 5.93 * float(u + v), 121.0) : min(17.0 + 5.93 * float(u + v), 99.0));
                float hard = floor(f / q + 0.5) * q;
                float soft = sign(f) * max(abs(f) - 0.5 * q, 0.0);
                float qv = mix(soft, hard, ringing);
                float bx = 0.0; float by = 0.0;
                for (int k = 0; k < 8; k++) {{
                    if (float(k) == at.x) {{ bx = C[u * 8 + k]; }}
                    if (float(k) == at.y) {{ by = C[v * 8 + k]; }}
                }}
                acc += qv * bx * by;
            }}
        }}
        if (ch == 0) {{ res.x = acc; }} else if (ch == 1) {{ res.y = acc; }} else {{ res.z = acc; }}
    }}
    float y = res.x / 255.0 + 0.5;
    float cb = res.y / 255.0;
    float cr = res.z / 255.0;
    float3 rgb = max(float3(unsh(y + 1.402 * cr), unsh(y - 0.344136 * cb - 0.714136 * cr), unsh(y + 1.772 * cb)), float3(0.0));
    return half4(half3(fromDisp(rgb) * c0.a), c0.a);
}}
",
            cap = super::lit(SHOULDER_CAP)
        ),
        uniforms: &["strength", "chroma", "ringing"],
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn grey(w: usize, h: usize, f: impl Fn(usize, usize) -> f32) -> Vec<[f32; 3]> {
        (0..w * h).map(|k| { let v = f(k % w, k / w); [v, v, v] }).collect()
    }

    /// The biggest luma step across an 8-px grid line, in a smooth ramp, against the step inside blocks.
    fn grid_step(img: &[[f32; 3]], w: usize, h: usize) -> (f32, f32) {
        let (mut on, mut inside, mut a, mut b) = (0.0, 0.0, 0.0, 0.0);
        for y in 0..h {
            for x in 1..w {
                let d = (img[y * w + x][0] - img[y * w + x - 1][0]).abs();
                if x % 8 == 0 { on += d; a += 1.0 } else { inside += d; b += 1.0 }
            }
        }
        (on / a, inside / b)
    }

    #[test]
    fn strength_zero_and_flat_pictures_are_unchanged() {
        let flat = grey(16, 16, |_, _| 0.4);
        let out = compress_rgb(&flat, 16, 16, 1.0, false, 1.0);
        assert!(out.iter().all(|p| (p[0] - 0.4).abs() < 0.004), "a flat patch survives the rounding: {:?}", out[5]);
        let ramp = grey(16, 16, |x, y| (x + y) as f32 / 40.0);
        assert_eq!(compress_rgb(&ramp, 16, 16, 0.0, true, 1.0), ramp);
    }

    #[test]
    fn values_past_white_keep_their_size_and_stay_finite() {
        // A bright patch (display 20 … 40): never inf, never black, within 2× (the codec's rounding is on a 0 … 255 scale; on the
        // shoulder's log scale it costs a lot past white, so the comp runs `compress` on the view's display picture in a linear edit).
        let hot = grey(16, 16, |x, y| 20.0 + ((x * 7 + y * 3) % 11) as f32 * 2.0);
        let out = compress_rgb(&hot, 16, 16, 2.5, true, 1.0);
        for (o, i) in out.iter().zip(&hot) {
            assert!(o.iter().all(|v| v.is_finite() && *v > 0.0), "{o:?}");
            assert!(o[0] / i[0] > 0.5 && o[0] / i[0] < 2.0, "{} → {}", i[0], o[0]);
        }
        for x in [-30.0f32, -1.0, -0.4, 0.0, 0.7, 1.0, 3.0, 500.0] {
            assert!((unshoulder(shoulder(x)) - x).abs() <= 1e-4 * x.abs().max(1.0), "{x}");
        }
    }

    #[test]
    fn a_smooth_ramp_turns_into_flat_blocks_with_steps_between_them() {
        let ramp = grey(64, 16, |x, y| 0.2 + 0.0035 * x as f32 + 0.002 * y as f32);
        let (on0, in0) = grid_step(&ramp, 64, 16);
        assert!((on0 / in0 - 1.0).abs() < 0.01);
        for s in [2.0, 4.0] {
            let (on, inside) = grid_step(&compress_rgb(&ramp, 64, 16, s, false, 1.0), 64, 16);
            assert!(on > 3.0 * inside, "strength {s}: steps on the grid {on}, inside the blocks {inside}");
        }
    }

    #[test]
    fn fine_detail_goes_and_an_edge_rings() {
        // Alternating columns: the highest frequency, gone at strength 1.
        let stripes = grey(16, 16, |x, _| if x % 2 == 0 { 0.51 } else { 0.49 });
        let out = compress_rgb(&stripes, 16, 16, 1.0, false, 1.0);
        let amp = (out[4][0] - out[5][0]).abs();
        assert!(amp < 0.005, "the stripes' 0.02 swing is quantised away: {amp}");
        // A step inside a block: the flat sides overshoot or wobble after rounding (ringing), more than a 0.5 % step.
        let step = grey(16, 8, |x, _| if x < 4 { 0.2 } else { 0.8 });
        let out = compress_rgb(&step, 16, 8, 1.0, false, 1.0);
        let wob = (0..4).map(|x| (out[x][0] - 0.2).abs()).fold(0.0f32, f32::max);
        assert!(wob > 0.004, "the dark side is not flat any more: {wob}");
        let soft = compress_rgb(&step, 16, 8, 1.0, false, 0.0);
        assert!(soft.iter().all(|p| p[0].is_finite()));
    }

    #[test]
    fn chroma_subsampling_smears_a_colour_edge_but_keeps_luma() {
        // Red / green halves with equal luma, edge at x = 5 (odd): luma stays, chroma loses its edge.
        let (r, g) = ([0.8, 0.2, 0.2], [0.0, 0.5, 0.0]);
        let ly = |c: [f32; 3]| 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2];
        let scale = ly(r) / ly(g);
        let g = [g[0] * scale, g[1] * scale, g[2] * scale];
        let img: Vec<[f32; 3]> = (0..16 * 16).map(|k| if (k % 16) < 5 { r } else { g }).collect();
        let full = compress_rgb(&img, 16, 16, 0.2, false, 1.0);
        let sub = compress_rgb(&img, 16, 16, 0.2, true, 1.0);
        let err = |o: &[[f32; 3]]| (0..16).map(|x| (o[x][0] - img[x][0]).abs()).sum::<f32>();
        assert!(err(&sub) > err(&full) * 1.5, "4:2:0 costs the colour edge more: {} vs {}", err(&sub), err(&full));
    }

    /// Calibration run (not a check): `COMPRESS_CAL=<854x480 rgb24 file> cargo test --profile agent -p rostrum-color calibrate -- --ignored --nocapture`
    /// prints matchStats' blockiness (engine/video/matchStats.ts, same steps) of the twin's output by strength.
    #[test]
    #[ignore]
    fn calibrate_blockiness() {
        let Ok(path) = std::env::var("COMPRESS_CAL") else { return };
        let raw = std::fs::read(path).unwrap();
        let (w, h) = (854usize, 480usize);
        let img: Vec<[f32; 3]> = (0..w * h).map(|k| [raw[k * 3] as f32 / 255.0, raw[k * 3 + 1] as f32 / 255.0, raw[k * 3 + 2] as f32 / 255.0]).collect();
        let ratio = |im: &[[f32; 3]]| {
            let l: Vec<f32> = im.iter().map(|p| (0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2])).collect();
            let (mut col, mut row) = ([[0f64; 2]; 8], [[0f64; 2]; 8]);
            for y in 1..h {
                for x in 1..w {
                    let v = l[y * w + x];
                    let (dx, dy) = ((v - l[y * w + x - 1]).abs(), (v - l[(y - 1) * w + x]).abs());
                    if dx < 0.06 { col[x & 7][0] += dx as f64; col[x & 7][1] += 1.0; }
                    if dy < 0.06 { row[y & 7][0] += dy as f64; row[y & 7][1] += 1.0; }
                }
            }
            let best = |b: &[[f64; 2]; 8]| {
                let m: Vec<f64> = b.iter().map(|c| c[0] / c[1]).collect();
                let ph = (0..8).max_by(|&a, &c| m[a].partial_cmp(&m[c]).unwrap()).unwrap();
                m[ph] / ((m.iter().sum::<f64>() - m[ph]) / 7.0)
            };
            (best(&col) + best(&row)) / 2.0
        };
        if let Ok(out) = std::env::var("COMPRESS_OUT") {
            let o = compress_rgb(&img, w, h, 2.5, true, 1.0);
            std::fs::write(out, o.iter().flat_map(|p| p.map(|v| (v * 255.0).round() as u8)).collect::<Vec<u8>>()).unwrap();
        }
        println!("strength 0: {:.3}", ratio(&img));
        for s in [0.15f32, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0] {
            println!("strength {s}: {:.3}", ratio(&compress_rgb(&img, w, h, s, true, 1.0)));
        }
    }
}
