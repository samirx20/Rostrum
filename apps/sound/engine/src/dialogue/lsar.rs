//! De-clip (dialogue repair; de-click detects in declick.rs and fills here): samples known to be wrong (a clipped run, a click) are
//! re-drawn by least-squares AR interpolation (Janssen, Veldhuis & Vries 1986; Godsill & Rayner):
//! an all-pole model of the sound around the gap (least squares over its good samples only, the
//! covariance method), then the missing samples that make the model's prediction error smallest. A
//! clipped sample may only grow past the clip level (its sign kept): the constrained solution.

pub(crate) const ORDER: usize = 32;
const CONTEXT: usize = 384;
/// The longest gap solved at once (samples); longer runs are left as they are.
const MAX_GAP: usize = 512;

/// The AR model of `x` (prediction-error filter a[0] = 1 … a[p]) by the covariance method: least
/// squares over every stretch of p + 1 known samples. Too few stretches (dense damage) halve the order.
pub(crate) fn model(x: &[f64], known: &[bool], order: usize) -> Vec<f64> {
    let mut run = vec![0usize; x.len()];
    for i in 0..x.len() {
        run[i] = if known[i] { if i > 0 { run[i - 1] + 1 } else { 1 } } else { 0 };
    }
    let mut p = order;
    loop {
        let ts: Vec<usize> = (p..x.len()).filter(|&t| run[t] > p).collect();
        if ts.len() >= 2 * p || p <= 2 {
            let mut phi = vec![0.0f64; p * p];
            let mut rhs = vec![0.0f64; p];
            for &t in &ts {
                for i in 1..=p {
                    rhs[i - 1] -= x[t] * x[t - i];
                    for j in 1..=p {
                        phi[(i - 1) * p + j - 1] += x[t - i] * x[t - j];
                    }
                }
            }
            let load = 1e-9 * (0..p).map(|i| phi[i * p + i]).sum::<f64>() / p as f64 + 1e-20;
            (0..p).for_each(|i| phi[i * p + i] += load);
            let a = cholesky_solve(&mut phi, &rhs, p).unwrap_or_else(|| vec![0.0; p]);
            return std::iter::once(1.0).chain(a).collect();
        }
        p /= 2;
    }
}

/// Solves the unknown samples of `x` (where !known) in place: least prediction error under `a`.
fn interpolate(x: &mut [f64], known: &[bool], a: &[f64]) {
    let p = a.len() - 1;
    let unknown: Vec<usize> = (0..x.len()).filter(|&i| !known[i]).collect();
    let m = unknown.len();
    if m == 0 {
        return;
    }
    let mut col = vec![usize::MAX; x.len()];
    for (c, &i) in unknown.iter().enumerate() {
        col[i] = c;
    }
    let mut mm = vec![0.0f64; m * m];
    let mut v = vec![0.0f64; m];
    for t in p.max(unknown[0])..x.len().min(unknown[m - 1] + p + 1) {
        let mut row: Vec<(usize, f64)> = vec![];
        let mut b = 0.0;
        for j in 0..=p {
            let i = t - j;
            if known[i] { b += a[j] * x[i] } else { row.push((col[i], a[j])) }
        }
        for &(c1, v1) in &row {
            v[c1] += v1 * b;
            for &(c2, v2) in &row {
                mm[c1 * m + c2] += v1 * v2;
            }
        }
    }
    for c in 0..m {
        mm[c * m + c] += 1e-9;
    }
    if let Some(sol) = cholesky_solve(&mut mm, &v.iter().map(|b| -b).collect::<Vec<_>>(), m) {
        for (c, &i) in unknown.iter().enumerate() {
            x[i] = sol[c];
        }
    }
}

fn cholesky_solve(a: &mut [f64], b: &[f64], m: usize) -> Option<Vec<f64>> {
    for j in 0..m {
        let d = a[j * m + j] - (0..j).map(|k| a[j * m + k] * a[j * m + k]).sum::<f64>();
        if d <= 0.0 {
            return None;
        }
        let d = d.sqrt();
        a[j * m + j] = d;
        for i in j + 1..m {
            let s = a[i * m + j] - (0..j).map(|k| a[i * m + k] * a[j * m + k]).sum::<f64>();
            a[i * m + j] = s / d;
        }
    }
    let mut y = vec![0.0; m];
    for i in 0..m {
        y[i] = (b[i] - (0..i).map(|k| a[i * m + k] * y[k]).sum::<f64>()) / a[i * m + i];
    }
    for i in (0..m).rev() {
        y[i] = (y[i] - (i + 1..m).map(|k| a[k * m + i] * y[k]).sum::<f64>()) / a[i * m + i];
    }
    Some(y)
}

/// Gaps [from, to) merged when closer than the model order, each re-drawn from its context;
/// `floor` (when given) keeps a re-drawn sample at least as far out as the clip level.
pub(crate) fn fill(x: &mut [f32], gaps: &[(usize, usize)], floor: Option<&dyn Fn(usize) -> Option<f64>>) -> usize {
    let mut merged: Vec<(usize, usize)> = vec![];
    for &(a, b) in gaps {
        match merged.last_mut() {
            Some(last) if a < last.1 + ORDER && b - last.0 <= MAX_GAP => last.1 = b,
            _ => merged.push((a, b)),
        }
    }
    let mut bad = vec![false; x.len()];
    for &(a, b) in gaps {
        bad[a..b].iter_mut().for_each(|v| *v = true);
    }
    let mut done = 0;
    for (a, b) in merged {
        if b - a > MAX_GAP {
            continue;
        }
        // The model from a wide context; the gap solved in a narrow one (its own samples and any bad ones within two orders).
        let (cs, ce) = (a.saturating_sub(CONTEXT), (b + CONTEXT).min(x.len()));
        let wide: Vec<f64> = x[cs..ce].iter().map(|v| *v as f64).collect();
        let coeffs = model(&wide, &(cs..ce).map(|i| !bad[i]).collect::<Vec<_>>(), ORDER);
        let (s, e) = (a.saturating_sub(2 * ORDER), (b + 2 * ORDER).min(x.len()));
        let mut w: Vec<f64> = x[s..e].iter().map(|v| *v as f64).collect();
        let known: Vec<bool> = (s..e).map(|i| !bad[i]).collect();
        interpolate(&mut w, &known, &coeffs);
        for i in a..b {
            if known[i - s] {
                continue;
            }
            let mut y = w[i - s];
            if let Some(level) = floor.and_then(|f| f(i)) {
                y = if y.signum() == level.signum() && y.abs() > level.abs() { y } else { level };
            }
            x[i] = y as f32;
        }
        done += 1;
    }
    done
}

/// Clipped runs (two or more samples at `threshold` × that polarity's peak or beyond) re-drawn; returns the runs repaired.
pub fn declip(x: &mut [f32], threshold: f64) -> usize {
    let hi = x.iter().fold(0.0f32, |m, v| m.max(*v)) as f64 * threshold;
    let lo = x.iter().fold(0.0f32, |m, v| m.min(*v)) as f64 * threshold;
    let clipped = |v: f32| (v as f64 >= hi && hi > 0.0) || (v as f64 <= lo && lo < 0.0);
    let mut runs = vec![];
    let mut i = 0;
    while i < x.len() {
        if clipped(x[i]) {
            let s = i;
            while i < x.len() && clipped(x[i]) && x[i].signum() == x[s].signum() {
                i += 1;
            }
            if i - s >= 2 {
                runs.push((s, i));
            }
        } else {
            i += 1;
        }
    }
    let src: Vec<f32> = x.to_vec();
    let level = |i: usize| clipped(src[i]).then_some(if src[i] > 0.0 { hi } else { lo });
    fill(x, &runs, Some(&level))
}
