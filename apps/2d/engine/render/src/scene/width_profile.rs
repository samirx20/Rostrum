//! A path's varied stroke width (ENGINE_CONTRACT.md § 4 path): `widthProfile` read and evaluated, and the tapers.
//! The width at u (0..1 along the line) is strokeWidth × profile(u) × taper(u); super::stroke_width draws it.

use std::f64::consts::FRAC_PI_2;

/// `widthProfile` "pos,mult pos,mult …" read: positions 0..1, each after the one before, multipliers 0 or more;
/// "" = no profile (an even width). Errors name `id.widthProfile`.
pub fn read(id: &str, text: &str) -> Result<Vec<(f64, f64)>, String> {
    let bad = |why: String| {
        format!("{id}.widthProfile: {why} (it takes \"position,multiplier\" pairs such as \"0,0.5 0.5,1.5 1,0.5\": positions 0..1, each after the one before, multipliers 0 or more)")
    };
    let mut out: Vec<(f64, f64)> = vec![];
    for pair in text.split_whitespace() {
        let (p, m) = pair.split_once(',').ok_or_else(|| bad(format!("\"{pair}\" is not a pair")))?;
        let num = |s: &str| s.parse::<f64>().ok().filter(|x| x.is_finite()).ok_or_else(|| bad(format!("\"{s}\" in \"{pair}\" is not a number")));
        let (p, m) = (num(p)?, num(m)?);
        if !(0.0..=1.0).contains(&p) {
            return Err(bad(format!("position {p} is outside 0..1")));
        }
        if m < 0.0 {
            return Err(bad(format!("multiplier {m} is below 0")));
        }
        if let Some(last) = out.last().filter(|l| p <= l.0) {
            return Err(bad(format!("position {p} does not come after {}", last.0)));
        }
        out.push((p, m));
    }
    Ok(out)
}

/// The profile's multiplier at u: 1 with no points; held before the first and after the last; between them a
/// monotone cubic (Fritsch–Butland tangents), so it never overshoots a point and never dips below 0.
pub fn at(pts: &[(f64, f64)], u: f64) -> f64 {
    let n = pts.len();
    match pts {
        [] => return 1.0,
        [p] => return p.1,
        _ if u <= pts[0].0 => return pts[0].1,
        _ if u >= pts[n - 1].0 => return pts[n - 1].1,
        _ => {}
    }
    let slope = |k: usize| (pts[k + 1].1 - pts[k].1) / (pts[k + 1].0 - pts[k].0);
    let tangent = |k: usize| match k {
        0 => slope(0),
        k if k == n - 1 => slope(n - 2),
        k => {
            let (a, b) = (slope(k - 1), slope(k));
            if a * b <= 0.0 { 0.0 } else { 2.0 * a * b / (a + b) }
        }
    };
    let i = pts.windows(2).position(|w| u < w[1].0).unwrap_or(n - 2);
    let ((x0, y0), (x1, y1)) = (pts[i], pts[i + 1]);
    let h = x1 - x0;
    let t = (u - x0) / h;
    let (t2, t3) = (t * t, t * t * t);
    let y = (2.0 * t3 - 3.0 * t2 + 1.0) * y0 + (t3 - 2.0 * t2 + t) * h * tangent(i) + (3.0 * t2 - 2.0 * t3) * y1 + (t3 - t2) * h * tangent(i + 1);
    y.max(0.0)
}

/// The tapers at u: over the first `start` and the last `end` of the line the width eases from 0 as sin(π/2 · x),
/// x = how far into the taper u is. A sine rises at once (a pointed tip, not a needle) and meets the full width
/// with no kink, like a brush pressed down and lifted. Both apply (multiplied) where they overlap.
pub fn taper(u: f64, start: f64, end: f64) -> f64 {
    let ramp = |x: f64| (x.clamp(0.0, 1.0) * FRAC_PI_2).sin();
    let a = if start > 0.0 { ramp(u / start) } else { 1.0 };
    let b = if end > 0.0 { ramp((1.0 - u) / end) } else { 1.0 };
    a * b
}

/// Two profiles blended at eased progress p (a widthProfile key to the next, eval.rs): at every position of either,
/// both profiles' multipliers (by `at`, so an empty one is 1) mixed by p, never below 0. Same positions mix pair by pair.
pub fn blend(a: &[(f64, f64)], b: &[(f64, f64)], p: f64) -> Vec<(f64, f64)> {
    let mut at_pos: Vec<f64> = a.iter().chain(b).map(|q| q.0).collect();
    at_pos.sort_by(f64::total_cmp);
    at_pos.dedup();
    at_pos.into_iter().map(|u| (u, (at(a, u) + (at(b, u) - at(a, u)) * p).max(0.0))).collect()
}

/// A profile written back as "pos,mult pos,mult …" (what `read` takes).
pub fn write(pts: &[(f64, f64)]) -> String {
    pts.iter().map(|(p, m)| format!("{p},{m}")).collect::<Vec<_>>().join(" ")
}

#[cfg(test)]
mod tests {
    #[test]
    fn halfway_blend_mixes_at_every_position_of_either() {
        let (a, b) = (super::read("p", "0,1 1,1").unwrap(), super::read("p", "0,0 0.5,2 1,0").unwrap());
        assert_eq!(super::write(&super::blend(&a, &b, 0.5)), "0,0.5 0.5,1.5 1,0.5");
        assert_eq!(super::blend(&[], &[], 0.5), vec![]);
    }
}
