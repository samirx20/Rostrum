//! A stroke's dabs laid in order (`brush.py` `dabs`): each pixel of a dab gets its coverage (tip.rs), the stroke's
//! coverage there grows to it, wet paint first takes up the brush's reservoir, then the paint is laid (paint.rs).
//! The reservoir (D×D RGBA, the paint the brush passed over) follows numpy's arrays: picked up before the dab
//! changes the layer, laid with the reservoir as it was, then taken up into it.

use crate::{paint, tip, Dab, Stroke};

/// Lays `dabs` into `layer` (H×W×4) and fills `cov` (the stroke's bbox [x0, y0, x1, y1]).
#[allow(clippy::too_many_arguments)]
pub fn lay(st: &Stroke, dabs: &[Dab], (h, w): (usize, usize), bbox: [usize; 4], d: usize, layer: &mut [f32], cov: &mut [f32], under: Option<(&[f32], usize)>) -> Result<(), String> {
    let [bx0, by0, bx1, _] = bbox;
    let cw = bx1 - bx0;
    let k = 1.0 - st.wet;
    let mut res: Option<Vec<f32>> = None;
    let mut pick = vec![0f32; d * d * 4];
    let mut across = Vec::with_capacity(st.kr);
    // What was under the stroke, for the modes that blend with it (its bbox, RGBA).
    let under0: Vec<f32> = if st.mode.reads_under() {
        (bbox[1]..bbox[3]).flat_map(|y| layer[(y * w + bx0) * 4..(y * w + bx1) * 4].iter().copied()).collect()
    } else {
        Vec::new()
    };
    for dab in dabs {
        let [x0, x1, y0, y1] = dab.bx;
        if x1 <= x0 || y1 <= y0 {
            continue;
        }
        let [oy, ox] = dab.at;
        if st.wet > 0.0 {
            if y0 < oy || y1 > oy + d as i64 || x0 < ox || x1 > ox + d as i64 {
                return Err(format!("a dab ({x0}..{x1}, {y0}..{y1}) outside its reservoir ({ox}, {oy}, {d})"));
            }
            // The canvas edge repeats (numpy's clamped indices; inside, the same pixels, a row at a time).
            let inside = ox >= 0 && ox + d as i64 <= w as i64;
            for j in 0..d {
                let sy = (oy + j as i64).clamp(0, h as i64 - 1) as usize;
                if inside {
                    let at = (sy * w + ox as usize) * 4;
                    pick[j * d * 4..(j + 1) * d * 4].copy_from_slice(&layer[at..at + d * 4]);
                }
                for i in 0..d {
                    let sx = (ox + i as i64).clamp(0, w as i64 - 1) as usize;
                    let p = &mut pick[(j * d + i) * 4..][..4];
                    if !inside {
                        p.copy_from_slice(&layer[(sy * w + sx) * 4..][..4]);
                    }
                    if st.sample_all {
                        let (u, row) = under.ok_or("sample_all needs the composite below")?;
                        let under = &u[sy * row + sx * 4..][..3];
                        for ch in 0..3 {
                            p[ch] += (1.0f32 - p[3]) * under[ch];
                        }
                        p[3] = 1.0;
                    }
                }
            }
            if res.is_none() {
                res = Some(pick.clone());
            }
        }
        tip::across(st, dab, &mut across);
        for y in y0 as usize..y1 as usize {
            for x in x0 as usize..x1 as usize {
                let (a, idx) = tip::coverage(st, dab, &across, x, y);
                let cv = &mut cov[(y - by0) * cw + (x - bx0)];
                let c0 = *cv;
                let c1 = f64::max(c0 as f64, a);
                *cv = c1 as f32;
                let tint = 1.0 + st.cj * 0.6 * st.streak[idx];
                let col = dab.col.map(|c| c as f64 * tint);
                let px = &mut layer[(y * w + x) * 4..][..4];
                if let Some(res) = &res {
                    let r = &res[(((y as i64 - oy) as usize) * d + (x as i64 - ox) as usize) * 4..][..4];
                    let la = a * dab.lay;
                    for ch in 0..4 {
                        px[ch] = (px[ch] as f64 + la * (r[ch] - px[ch]) as f64) as f32;
                    }
                }
                let base = if under0.is_empty() { &[][..] } else { &under0[((y - by0) * cw + (x - bx0)) * 4..][..4] };
                paint::apply(px, c0, c1, col, st.mode, k, base);
            }
        }
        if let Some(res) = res.as_mut() {
            let (take, take32) = (dab.take, dab.take as f32);
            if dab.take_weak {
                res.iter_mut().zip(&pick).for_each(|(r, p)| *r += take32 * (*p - *r));
            } else {
                res.iter_mut().zip(&pick).for_each(|(r, p)| *r = (*r as f64 + take * (*p - *r) as f64) as f32);
            }
        }
    }
    Ok(())
}
