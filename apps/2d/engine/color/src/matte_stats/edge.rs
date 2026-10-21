//! The matte's outline: `edge` (band width along the normal at contour samples) and `holes` (connected regions inside the
//! filled subject outline, specks outside it). Both run on a half-size copy of the matte when the frame is large
//! (`Thresholds::half_above`); areas and lengths are reported in px of the full frame.

use super::{r6, Thresholds};
use serde_json::{json, Value};

/// The matte (and region) at working size: the frame itself, or its 2 × 2 box average.
pub struct Work {
    pub a: Vec<f32>,
    pub w: usize,
    pub h: usize,
    pub scale: usize,
    pub region: Option<Vec<bool>>,
}

impl Work {
    pub fn new(a: &[f32], region: Option<&[bool]>, w: usize, h: usize, th: &Thresholds) -> Work {
        if w <= th.half_above || w < 2 || h < 2 {
            return Work { a: a.to_vec(), w, h, scale: 1, region: region.map(|r| r.to_vec()) };
        }
        let (ww, wh) = (w.div_ceil(2), h.div_ceil(2));
        let mut out = vec![0f32; ww * wh];
        let mut reg = region.map(|_| vec![false; ww * wh]);
        for y in 0..wh {
            for x in 0..ww {
                let (mut s, mut n, mut r) = (0f32, 0u32, 0u32);
                for yy in 2 * y..(2 * y + 2).min(h) {
                    for xx in 2 * x..(2 * x + 2).min(w) {
                        s += a[yy * w + xx];
                        n += 1;
                        if region.is_some_and(|g| g[yy * w + xx]) {
                            r += 1;
                        }
                    }
                }
                out[y * ww + x] = s / n as f32;
                if let Some(g) = reg.as_mut() {
                    g[y * ww + x] = r * 2 > n;
                }
            }
        }
        Work { a: out, w: ww, h: wh, scale: 2, region: reg }
    }
    fn inside(&self, i: usize) -> bool {
        self.region.as_ref().is_none_or(|r| r[i])
    }
}

fn bilinear(a: &[f32], w: usize, h: usize, x: f32, y: f32) -> f32 {
    let x = x.clamp(0.0, (w - 1) as f32);
    let y = y.clamp(0.0, (h - 1) as f32);
    let (x0, y0) = (x.floor() as usize, y.floor() as usize);
    let (x1, y1) = ((x0 + 1).min(w - 1), (y0 + 1).min(h - 1));
    let (fx, fy) = (x - x0 as f32, y - y0 as f32);
    let top = a[y0 * w + x0] * (1.0 - fx) + a[y0 * w + x1] * fx;
    let bot = a[y1 * w + x0] * (1.0 - fx) + a[y1 * w + x1] * fx;
    top * (1.0 - fy) + bot * fy
}

/// Distance from (x, y) along (dx, dy) to where the matte first reaches `threshold` (≥ for `up`, ≤ otherwise); `None`
/// when it does not within `cap` px. Piecewise-linear refinement between 0.25 px steps.
fn walk(wk: &Work, p: (f32, f32), dir: (f32, f32), threshold: f32, up: bool, cap: f32) -> Option<f32> {
    let hit = |v: f32| if up { v >= threshold } else { v <= threshold };
    let step = 0.25f32;
    let mut prev = bilinear(&wk.a, wk.w, wk.h, p.0, p.1);
    if hit(prev) {
        return Some(0.0);
    }
    let mut d = 0.0f32;
    while d < cap {
        d += step;
        let v = bilinear(&wk.a, wk.w, wk.h, p.0 + dir.0 * d, p.1 + dir.1 * d);
        if hit(v) {
            let t = (prev - threshold) / (prev - v);
            return Some(d - step + t * step);
        }
        prev = v;
    }
    None
}

fn percentile_sorted(v: &[f64], p: f64) -> f64 {
    v[((v.len() - 1) as f64 * p).round() as usize]
}

/// `edge`: band width (alpha from `band_lo` to `band_hi`) along the gradient at ≤ `edge_points` contour pixels
/// (boundary pixels of alpha > `inside`, evenly spaced in raster order), contour length in pixel edges, soft share.
pub fn edge(wk: &Work, th: &Thresholds) -> Value {
    let (w, h) = (wk.w, wk.h);
    let m = |i: usize| wk.a[i] > th.inside as f32;
    let mut contour_edges = 0usize;
    let mut boundary = vec![];
    let (mut partial, mut nonzero) = (0usize, 0usize);
    for y in 0..h {
        for x in 0..w {
            let i = y * w + x;
            if !wk.inside(i) {
                continue;
            }
            let v = wk.a[i];
            if v > th.band_lo as f32 {
                nonzero += 1;
                if v <= th.band_hi as f32 {
                    partial += 1;
                }
            }
            if !m(i) {
                continue;
            }
            let mut n = 0;
            if x > 0 && !m(i - 1) {
                n += 1;
            }
            if x + 1 < w && !m(i + 1) {
                n += 1;
            }
            if y > 0 && !m(i - w) {
                n += 1;
            }
            if y + 1 < h && !m(i + w) {
                n += 1;
            }
            if n > 0 {
                contour_edges += n;
                boundary.push((x, y));
            }
        }
    }
    let s = wk.scale as f64;
    let soft = if nonzero > 0 { partial as f64 / nonzero as f64 } else { 0.0 };
    if boundary.is_empty() {
        return json!({ "contourPx": 0, "softFraction": r6(soft), "samples": 0 });
    }
    let n = th.edge_points.min(boundary.len()).max(1);
    let mut widths = vec![];
    for k in 0..n {
        let (x, y) = boundary[k * boundary.len() / n];
        let at = |xx: isize, yy: isize| wk.a[yy.clamp(0, h as isize - 1) as usize * w + xx.clamp(0, w as isize - 1) as usize];
        let (xi, yi) = (x as isize, y as isize);
        let (gx, gy) = (at(xi + 1, yi) - at(xi - 1, yi), at(xi, yi + 1) - at(xi, yi - 1));
        let mag = (gx * gx + gy * gy).sqrt();
        if mag < 1e-6 {
            continue;
        }
        let (dx, dy) = (gx / mag, gy / mag);
        let cap = 64.0;
        let p = (x as f32, y as f32);
        let hi = walk(wk, p, (dx, dy), th.band_hi as f32, true, cap).unwrap_or(cap);
        let lo = walk(wk, p, (-dx, -dy), th.band_lo as f32, false, cap).unwrap_or(cap);
        widths.push((hi + lo) as f64 * s);
    }
    widths.sort_by(|a, b| a.total_cmp(b));
    if widths.is_empty() {
        return json!({ "contourPx": r6(contour_edges as f64 * s), "softFraction": r6(soft), "samples": 0 });
    }
    json!({
        "bandWidthPx": { "p50": r6(percentile_sorted(&widths, 0.5)), "p90": r6(percentile_sorted(&widths, 0.9)), "max": r6(*widths.last().unwrap()) },
        "contourPx": r6(contour_edges as f64 * s), "softFraction": r6(soft), "samples": widths.len(),
    })
}

/// 4-connected components of `mask == target`: labels (0 = other, ids from 1) and the first pixel of each.
fn label(mask: &[bool], target: bool, w: usize, h: usize) -> (Vec<u32>, Vec<usize>) {
    let mut lab = vec![0u32; w * h];
    let mut firsts = vec![];
    let mut stack = vec![];
    for s in 0..w * h {
        if mask[s] != target || lab[s] != 0 {
            continue;
        }
        firsts.push(s);
        let id = firsts.len() as u32;
        lab[s] = id;
        stack.push(s);
        while let Some(i) = stack.pop() {
            let (x, y) = (i % w, i / w);
            let mut push = |j: usize| {
                if mask[j] == target && lab[j] == 0 {
                    lab[j] = id;
                    stack.push(j);
                }
            };
            if x > 0 {
                push(i - 1);
            }
            if x + 1 < w {
                push(i + 1);
            }
            if y > 0 {
                push(i - w);
            }
            if y + 1 < h {
                push(i + w);
            }
        }
    }
    (lab, firsts)
}

/// `holes`: the subject is the largest connected region of alpha > `inside`; its filled outline is everything the
/// frame border cannot reach without crossing it. Holes: connected regions of alpha ≤ `inside` inside that outline.
/// `looseSpecks`: the other alpha > `inside` regions outside it (an island inside a hole is neither).
/// A region counts when a pixel of it is in the region mask; its area is the pixels in the mask.
pub fn holes(wk: &Work, th: &Thresholds) -> Value {
    let (w, h) = (wk.w, wk.h);
    let m: Vec<bool> = wk.a.iter().map(|v| *v > th.inside as f32).collect();
    let (lm, fm) = label(&m, true, w, h);
    let s2 = (wk.scale * wk.scale) as f64;
    let zero = json!({ "count": 0, "areaPx": 0, "largest": 0 });
    if fm.is_empty() {
        return json!({ "count": 0, "areaPx": 0, "largest": 0, "looseSpecks": zero, "subjectAreaPx": 0 });
    }
    let (mut tot_m, mut reg_m) = (vec![0usize; fm.len()], vec![0usize; fm.len()]);
    for i in 0..w * h {
        if lm[i] != 0 {
            tot_m[lm[i] as usize - 1] += 1;
            if wk.inside(i) {
                reg_m[lm[i] as usize - 1] += 1;
            }
        }
    }
    let main = (0..fm.len()).max_by_key(|k| tot_m[*k]).unwrap() as u32 + 1;
    // What the border reaches without crossing the subject.
    let mut outside = vec![false; w * h];
    let mut stack = vec![];
    for i in (0..w).chain((1..h).map(|y| y * w)).chain((1..h).map(|y| y * w + w - 1)).chain((0..w).map(|x| (h - 1) * w + x)) {
        if lm[i] != main && !outside[i] {
            outside[i] = true;
            stack.push(i);
        }
    }
    while let Some(i) = stack.pop() {
        let (x, y) = (i % w, i / w);
        let mut push = |j: usize| {
            if lm[j] != main && !outside[j] {
                outside[j] = true;
                stack.push(j);
            }
        };
        if x > 0 {
            push(i - 1);
        }
        if x + 1 < w {
            push(i + 1);
        }
        if y > 0 {
            push(i - w);
        }
        if y + 1 < h {
            push(i + w);
        }
    }
    let (ln, fnn) = label(&m, false, w, h);
    let mut reg_n = vec![0usize; fnn.len()];
    for i in 0..w * h {
        if ln[i] != 0 && wk.inside(i) {
            reg_n[ln[i] as usize - 1] += 1;
        }
    }
    let stat = |items: Vec<usize>| {
        let items: Vec<usize> = items.into_iter().filter(|a| *a > 0).collect();
        json!({ "count": items.len(), "areaPx": r6(items.iter().sum::<usize>() as f64 * s2), "largest": r6(items.iter().copied().max().unwrap_or(0) as f64 * s2) })
    };
    let holes: Vec<usize> = (0..fnn.len()).filter(|j| !outside[fnn[*j]]).map(|j| reg_n[j]).collect();
    let specks: Vec<usize> = (0..fm.len()).filter(|k| *k as u32 + 1 != main && outside[fm[*k]]).map(|k| reg_m[k]).collect();
    let outline = (0..w * h).filter(|i| !outside[*i] && wk.inside(*i)).count();
    let mut v = stat(holes);
    v["looseSpecks"] = stat(specks);
    v["subjectAreaPx"] = json!(r6(outline as f64 * s2));
    v
}
