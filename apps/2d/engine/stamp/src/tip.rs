//! One pixel of one dab: the tip's coverage there (`brush.py` `dabs`, the part before the coverage is kept). Every
//! step is the numpy expression's own, in its own precision: numpy works in f32 where the arrays are f32 and a Python
//! number joins them (NEP 50), in f64 where an f64 array or a NumPy scalar does. No step is fused or reordered.

use crate::{Dab, Stroke};

#[derive(Clone, Copy, PartialEq)]
pub enum Tip {
    Round,
    Bristle,
    Chalk,
    Flat,
    Block,
    Line,
}

impl Tip {
    /// The kit's `TIPS` order.
    pub fn from_id(id: f64) -> Option<Tip> {
        [Tip::Round, Tip::Bristle, Tip::Chalk, Tip::Flat, Tip::Block, Tip::Line].get(id as usize).copied()
    }
}

/// marks.py `_ss`: clip to 0..1, then x·x·(3 − 2x).
pub fn ss(x: f64) -> f64 {
    let x = x.max(0.0).min(1.0);
    x * x * (3.0 - 2.0 * x)
}

/// A bristle or flat dab's profile across the tip, ragged at the stroke's ends (numpy makes it per dab, then picks
/// from it per pixel); empty for the other tips.
pub fn across(st: &Stroke, d: &Dab, out: &mut Vec<f64>) {
    out.clear();
    if matches!(st.tip, Tip::Bristle | Tip::Flat) {
        out.extend((0..st.kr).map(|k| st.prof[k] * ss((d.s - st.start[k]) / 0.06) * ss((1.0 - st.end[k] - d.s) / 0.06)));
    }
}

/// The dab's coverage at (x, y), with its strength, grain and mask; `idx` its place across the tip profile; `across`
/// the dab's profile (`across`).
pub fn coverage(st: &Stroke, d: &Dab, across: &[f64], x: usize, y: usize) -> (f64, usize) {
    let dx = x as f32 - d.x as f32;
    let dy = y as f32 - d.y as f32;
    let (c, s) = (d.cos as f32, d.sin as f32);
    let r = d.r;
    let u = (dx * c + dy * s) as f64 / r;
    let vv = (dy * c - dx * s) as f64 / r;
    let idx = ((vv.max(-1.0).min(1.0) + 1.0) * (st.kr - 1) as f64 / 2.0) as i32 as usize;
    let (soft, along) = (st.soft, st.along);
    let dist = || (dx * dx + dy * dy).sqrt() as f64;
    let mut a = match st.tip {
        Tip::Round | Tip::Chalk => {
            let a = ss((r - dist()) / f64::max(1.0, soft * r));
            if st.tip == Tip::Chalk {
                let f = st.paper_f.expect("chalk has its paper")[y * st.w + x];
                ss((a - (0.85f32 * (1.0f32 - f)) as f64) / 0.3)
            } else {
                a
            }
        }
        Tip::Line => ((r + 0.5) - dist()).max(0.0).min(1.0),
        Tip::Bristle => {
            let q = u / along;
            ss((1.0 - q * q - vv * vv) / soft)
        }
        Tip::Flat => ss((1.0 - u.abs() / along) / soft) * ss((1.0 - vv.abs()) / (soft * 0.3)),
        Tip::Block => {
            let ew = f64::max(1.0, soft * r * 0.15);
            let al = d.t + u * r;
            let (r0, rl) = (st.r0, st.rl);
            ss((d.wv - vv.abs()) * r / ew)
                * ss((along - u.abs()) * r / ew)
                * ss((al + along * r0 - st.start[idx] * r0) / ew)
                * ss((st.length + along * rl - st.end[idx] * rl - al) / ew)
                * st.prof[idx]
        }
    };
    if matches!(st.tip, Tip::Bristle | Tip::Flat) {
        a *= across[idx];
    }
    a *= d.a;
    if let Some(g) = st.grain {
        let tg = g as f32 * (1.0f32 - st.paper_g.expect("grain has its paper")[y * st.w + x]);
        a = ((a - tg as f64) / (1.001f32 - tg) as f64).max(0.0).min(1.0);
    }
    if let Some(m) = st.mask {
        a *= m[y * st.w + x] as f64;
    }
    (a, idx)
}
