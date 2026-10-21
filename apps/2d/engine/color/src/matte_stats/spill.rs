//! `spill` (residual screen colour in the edge band and the foreground, before and after despill) and `screen`
//! (what the matte leaves where it should be zero, how even the local screen colour is).

use super::{in_region, r6, Thresholds};
use crate::Rgb;
use serde_json::{json, Value};

/// The screen's colour: the one given, else the plate's mean where alpha < `screen_below`.
pub fn screen_colour(alpha: &[f32], plate: Option<&[Rgb]>, screen: Option<Rgb>, reg: Option<&[bool]>, th: &Thresholds) -> Option<(Rgb, &'static str)> {
    if let Some(s) = screen {
        return Some((s, "given"));
    }
    let plate = plate?;
    let (mut sum, mut n) = ([0f64; 3], 0usize);
    for (i, a) in alpha.iter().enumerate() {
        if *a < th.screen_below as f32 && in_region(reg, i) {
            for k in 0..3 {
                sum[k] += plate[i][k] as f64;
            }
            n += 1;
        }
    }
    (n > 0).then(|| (sum.map(|v| (v / n as f64) as f32), "plate"))
}

/// The screen channel: the largest of the screen colour (green when none is known).
pub fn channel(screen: Option<Rgb>) -> usize {
    match screen {
        Some(s) if s[2] > s[1] && s[2] > s[0] => 2,
        _ => 1,
    }
}

const CH: [&str; 3] = ["r", "g", "b"];

/// Linear screen excess `max(0, g − max(r, b))` (the channel `ch`, the others in its place).
pub fn excess(c: Rgb, ch: usize) -> f32 {
    let (o1, o2) = ((ch + 1) % 3, (ch + 2) % 3);
    (c[ch] - c[o1].max(c[o2])).max(0.0)
}

/// Hue in degrees and chroma (max − min) of a linear RGB colour.
pub fn hue(c: Rgb) -> Option<(f64, f64)> {
    let (r, g, b) = (c[0] as f64, c[1] as f64, c[2] as f64);
    let (mx, mn) = (r.max(g).max(b), r.min(g).min(b));
    let d = mx - mn;
    if d <= 0.0 {
        return None;
    }
    let h = if mx == r { ((g - b) / d).rem_euclid(6.0) } else if mx == g { (b - r) / d + 2.0 } else { (r - g) / d + 4.0 };
    Some((h * 60.0, d))
}

fn mean_p95(mut v: Vec<f32>) -> Value {
    if v.is_empty() {
        return Value::Null;
    }
    let mean = v.iter().map(|x| *x as f64).sum::<f64>() / v.len() as f64;
    let k = ((v.len() - 1) as f64 * 0.95).round() as usize;
    let (_, p, _) = v.select_nth_unstable_by(k, |a, b| a.total_cmp(b));
    json!({ "mean": r6(mean), "p95": r6(*p as f64) })
}

/// Edge band: alpha in `band_lo ..= band_hi`; foreground: above. Colours straight; the despilled colour is the premultiplied
/// `fg` divided by alpha. Hue of the edge band: circular mean weighted by chroma, the despilled colour when given.
pub fn spill(alpha: &[f32], plate: Option<&[Rgb]>, fg: Option<&[Rgb]>, reg: Option<&[bool]>, screen: Option<(Rgb, &'static str)>, th: &Thresholds) -> Value {
    if plate.is_none() && fg.is_none() {
        return Value::Null;
    }
    let ch = channel(screen.map(|s| s.0));
    let (mut eb, mut ea, mut fb, mut fa) = (vec![], vec![], vec![], vec![]);
    let (mut hs, mut hc, mut hw) = (0f64, 0f64, 0f64);
    for (i, &a) in alpha.iter().enumerate() {
        if a < th.band_lo as f32 || !in_region(reg, i) {
            continue;
        }
        let band = a <= th.band_hi as f32;
        let before = plate.map(|p| excess(p[i], ch));
        let after_c = fg.map(|f| f[i].map(|v| v / a));
        let after = after_c.map(|c| excess(c, ch));
        if band {
            eb.extend(before);
            ea.extend(after);
            if let Some((hd, w)) = after_c.or(plate.map(|p| p[i])).and_then(hue) {
                hs += w * hd.to_radians().sin();
                hc += w * hd.to_radians().cos();
                hw += w;
            }
        } else {
            fb.extend(before);
            fa.extend(after);
        }
    }
    let n_band = eb.len().max(ea.len());
    let n_fg = fb.len().max(fa.len());
    let zone = |b: Vec<f32>, a: Vec<f32>, n: usize| {
        let mut o = json!({ "px": n });
        if plate.is_some() {
            o["before"] = mean_p95(b);
        }
        if fg.is_some() {
            o["after"] = mean_p95(a);
        }
        o
    };
    let mut out = json!({ "channel": CH[ch], "edgeBand": zone(eb, ea, n_band), "foreground": zone(fb, fa, n_fg) });
    if hw > 0.0 {
        let mean = hs.atan2(hc).to_degrees().rem_euclid(360.0);
        let mut eh = json!({ "meanDeg": r6(mean), "of": if fg.is_some() { "despilled" } else { "plate" } });
        if let Some(sh) = screen.and_then(|s| hue(s.0)) {
            eh["screenDeg"] = json!(r6(sh.0));
            eh["deltaDeg"] = json!(r6((mean - sh.0 + 180.0).rem_euclid(360.0) - 180.0));
        }
        out["edgeHue"] = eh;
    }
    out
}

/// `screen`: residual alpha where alpha < `screen_below`, and the std (per channel) of the local screen colour over the
/// same pixels (the plate's colour when no local image is given).
pub fn screen(alpha: &[f32], local: Option<&[Rgb]>, plate: Option<&[Rgb]>, reg: Option<&[bool]>, th: &Thresholds) -> Value {
    let (mut n, mut sum, mut mx, mut nz) = (0usize, 0f64, 0f32, 0usize);
    let (mut s1, mut s2, mut nc) = ([0f64; 3], [0f64; 3], 0usize);
    let colours = local.map(|l| (l, "local")).or(plate.map(|p| (p, "plate")));
    for (i, &a) in alpha.iter().enumerate() {
        if a >= th.screen_below as f32 || !in_region(reg, i) {
            continue;
        }
        n += 1;
        sum += a as f64;
        mx = mx.max(a);
        if a > 0.0 {
            nz += 1;
        }
        if let Some((c, _)) = colours {
            for k in 0..3 {
                let v = c[i][k] as f64;
                s1[k] += v;
                s2[k] += v * v;
            }
            nc += 1;
        }
    }
    if n == 0 {
        return json!({ "px": 0 });
    }
    let mut out = json!({ "px": n, "residual": { "mean": r6(sum / n as f64), "max": r6(mx as f64), "nonzeroPct": r6(100.0 * nz as f64 / n as f64) } });
    if let (Some((_, of)), true) = (colours, nc > 0) {
        let std = [0, 1, 2].map(|k| r6(((s2[k] / nc as f64) - (s1[k] / nc as f64).powi(2)).max(0.0).sqrt()));
        out["uniformity"] = json!({ "std": std, "of": of });
    }
    out
}
