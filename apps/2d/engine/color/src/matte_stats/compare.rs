//! `compare`: the matte against a reference matte (an artist's, another tool's, an earlier version of the key).

use super::{in_region, r6, Thresholds};
use serde_json::{json, Value};

fn grad(a: &[f32], w: usize, h: usize, x: usize, y: usize) -> (f32, f32) {
    let at = |xx: usize, yy: usize| a[yy * w + xx];
    (at((x + 1).min(w - 1), y) - at(x.saturating_sub(1), y), at(x, (y + 1).min(h - 1)) - at(x, y.saturating_sub(1)))
}

/// `iou` of alpha > `inside`, `mad` (mean |a − r|), `edgeMad` (the same where either is in the band), `sad` (sum |a − r|
/// as % of the region's pixels; `sadPx` the sum), `gradientError` (mean length of the difference of the central-difference gradients).
pub fn compare(a: &[f32], r: &[f32], w: usize, h: usize, reg: Option<&[bool]>, th: &Thresholds) -> Value {
    let (mut inter, mut union, mut sad, mut band_sad, mut band_n, mut n, mut gerr) = (0usize, 0usize, 0f64, 0f64, 0usize, 0usize, 0f64);
    let (lo, hi, ins) = (th.band_lo as f32, th.band_hi as f32, th.inside as f32);
    let in_band = |v: f32| v >= lo && v <= hi;
    for y in 0..h {
        for x in 0..w {
            let i = y * w + x;
            if !in_region(reg, i) {
                continue;
            }
            n += 1;
            let (va, vr) = (a[i], r[i]);
            let d = (va - vr).abs() as f64;
            sad += d;
            let (ma, mr) = (va > ins, vr > ins);
            inter += (ma && mr) as usize;
            union += (ma || mr) as usize;
            if in_band(va) || in_band(vr) {
                band_sad += d;
                band_n += 1;
            }
            let (ga, gr) = (grad(a, w, h, x, y), grad(r, w, h, x, y));
            gerr += (((ga.0 - gr.0) as f64).powi(2) + ((ga.1 - gr.1) as f64).powi(2)).sqrt();
        }
    }
    let nf = n.max(1) as f64;
    json!({
        "iou": r6(if union == 0 { 1.0 } else { inter as f64 / union as f64 }),
        "mad": r6(sad / nf),
        "edgeMad": if band_n > 0 { json!(r6(band_sad / band_n as f64)) } else { Value::Null },
        "edgePx": band_n,
        "sad": r6(100.0 * sad / nf), "sadPx": r6(sad),
        "gradientError": r6(gerr / nf),
    })
}
