//! `chatter` (frame-to-frame matte difference in static regions) and `temporal` (area and centroid over the frames).

use super::{in_region, r6, Thresholds};
use crate::Rgb;
use serde_json::{json, Value};

const BINS: usize = 1 << 16;

/// Histogram of |Δ| in [0, 1] that keeps the largest value of each bin: percentiles come back as an actual value
/// (exact when the values in a bin are equal, and off by < 1.6e-5 otherwise).
struct Hist {
    count: Vec<u32>,
    max: Vec<f32>,
    n: usize,
    sum: f64,
}

impl Hist {
    fn new() -> Hist {
        Hist { count: vec![0; BINS], max: vec![0.0; BINS], n: 0, sum: 0.0 }
    }
    fn add(&mut self, d: f32) {
        let b = ((d.clamp(0.0, 1.0) * (BINS - 1) as f32) as usize).min(BINS - 1);
        self.count[b] += 1;
        self.max[b] = self.max[b].max(d);
        self.n += 1;
        self.sum += d as f64;
    }
    fn json(&self) -> Value {
        if self.n == 0 {
            return json!({ "px": 0 });
        }
        let k = ((self.n - 1) as f64 * 0.99).round() as usize;
        let (mut seen, mut p99) = (0usize, 0f32);
        for b in 0..BINS {
            seen += self.count[b] as usize;
            if seen > k {
                p99 = self.max[b];
                break;
            }
        }
        json!({ "px": self.n, "mad": r6(self.sum / self.n as f64), "p99": r6(p99 as f64) })
    }
}

fn luma(c: Rgb) -> f32 {
    0.272_228_72 * c[0] + 0.674_081_77 * c[1] + 0.053_689_52 * c[2]
}

/// Over every consecutive pair: where the plate's luma changed by less than `static_luma` (all pixels when there is no
/// plate), `|α_t − α_{t−1}|` per zone of the pair's mean alpha: screen < `band_lo`, core > `band_hi`, edge between.
pub fn chatter(alpha: &[&[f32]], plate: &[&[Rgb]], reg: Option<&[bool]>, th: &Thresholds) -> Value {
    if alpha.len() < 2 {
        return Value::Null;
    }
    let mut zones = [Hist::new(), Hist::new(), Hist::new()];
    let (mut region_px, mut static_px) = (0usize, 0usize);
    for t in 1..alpha.len() {
        let (a, b) = (alpha[t - 1], alpha[t]);
        for i in 0..a.len() {
            if !in_region(reg, i) {
                continue;
            }
            region_px += 1;
            if !plate.is_empty() && (luma(plate[t][i]) - luma(plate[t - 1][i])).abs() >= th.static_luma as f32 {
                continue;
            }
            static_px += 1;
            let mean = (a[i] + b[i]) * 0.5;
            let z = if mean < th.band_lo as f32 { 2 } else if mean > th.band_hi as f32 { 1 } else { 0 };
            zones[z].add((b[i] - a[i]).abs());
        }
    }
    json!({
        "frames": alpha.len(), "static": if plate.is_empty() { "all pixels (no plate)" } else { "plate luma change below staticLuma" },
        "staticPct": r6(100.0 * static_px as f64 / region_px.max(1) as f64),
        "edge": zones[0].json(), "core": zones[1].json(), "screen": zones[2].json(),
    })
}

fn pick_series<T: Clone>(v: &[T], cap: usize) -> Vec<T> {
    if v.len() <= cap {
        return v.to_vec();
    }
    (0..cap).map(|k| v[k * (v.len() - 1) / (cap - 1)].clone()).collect()
}

/// Area of alpha > `inside` per frame (px), its change frame to frame (down-sampled to `series` entries), and the
/// distance the centroid of that area moves between frames (px).
pub fn temporal(alpha: &[&[f32]], w: usize, reg: Option<&[bool]>, th: &Thresholds) -> Value {
    let mut area = vec![];
    let mut cen = vec![];
    for a in alpha {
        let (mut n, mut sx, mut sy) = (0usize, 0f64, 0f64);
        for (i, v) in a.iter().enumerate() {
            if *v > th.inside as f32 && in_region(reg, i) {
                n += 1;
                sx += (i % w) as f64;
                sy += (i / w) as f64;
            }
        }
        area.push(n);
        cen.push(if n > 0 { Some((sx / n as f64, sy / n as f64)) } else { None });
    }
    let delta: Vec<i64> = area.windows(2).map(|p| p[1] as i64 - p[0] as i64).collect();
    let jumps: Vec<f64> = cen.windows(2).filter_map(|p| Some(((p[1]?.0 - p[0]?.0).powi(2) + (p[1]?.1 - p[0]?.1).powi(2)).sqrt())).collect();
    let mut out = json!({ "frames": alpha.len(), "areaPx": pick_series(&area, th.series), "areaDelta": pick_series(&delta, th.series) });
    if !jumps.is_empty() {
        out["centroidJump"] = json!({ "mean": r6(jumps.iter().sum::<f64>() / jumps.len() as f64), "max": r6(jumps.iter().cloned().fold(0.0, f64::max)) });
    }
    out
}
