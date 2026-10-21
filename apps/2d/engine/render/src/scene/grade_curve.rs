//! A layer's levels and curves (grade_fields.py) as the one grade's `curves` operation: rostrum-color `Curves`
//! tables, sampled evenly over ACEScct code 0 … 1. The fields speak screen brightness (sRGB-encoded 0 … 1, as a
//! photo editor's levels and curves do), so each sample is decoded to light, taken to screen brightness, reshaped,
//! and encoded back; beyond black and white the shift at the end carries on (the grade keeps over-bright light).

use rostrum_color::Curve;
use serde_json::{json, Map, Value};

/// Samples per table: the GPU form reads every sample per pixel, and 64 puts about 30 across the screen range.
const SAMPLES: usize = 64;

fn num(p: &Map<String, Value>, f: &str) -> f64 {
    p.get(f).and_then(Value::as_f64).unwrap_or(0.0)
}

/// A curve's points "x,y x,y …": each 0 … 1, at least two, x rising. Empty = the straight line.
pub fn points(text: &str) -> Result<Vec<(f64, f64)>, String> {
    if text.trim().is_empty() {
        return Ok(vec![(0.0, 0.0), (1.0, 1.0)]);
    }
    let mut out: Vec<(f64, f64)> = vec![];
    for (i, p) in text.split_whitespace().enumerate() {
        let xy = p.split_once(',').and_then(|(x, y)| Some((x.parse::<f64>().ok()?, y.parse::<f64>().ok()?)));
        let (x, y) = xy.ok_or_else(|| format!("point {} \"{p}\" is not x,y (two numbers and a comma, no space)", i + 1))?;
        if !(0.0..=1.0).contains(&x) || !(0.0..=1.0).contains(&y) {
            return Err(format!("point {} \"{p}\" is outside 0 … 1", i + 1));
        }
        if out.last().is_some_and(|l| x <= l.0) {
            return Err(format!("point {} \"{p}\": x must rise from one point to the next", i + 1));
        }
        out.push((x, y));
    }
    if out.len() < 2 {
        return Err("a curve needs at least two points".into());
    }
    Ok(out)
}

/// The smooth curve through the points that never overshoots them (monotone cubic, PCHIP tangents), flat beyond the ends.
fn through(p: &[(f64, f64)], x: f64) -> f64 {
    let n = p.len();
    if x <= p[0].0 {
        return p[0].1;
    }
    if x >= p[n - 1].0 {
        return p[n - 1].1;
    }
    let slope = |i: usize| (p[i + 1].1 - p[i].1) / (p[i + 1].0 - p[i].0);
    let tangent = |i: usize| -> f64 {
        if i == 0 || i == n - 1 {
            return slope(i.min(n - 2));
        }
        let (d0, d1) = (slope(i - 1), slope(i));
        if d0 * d1 <= 0.0 {
            return 0.0;
        }
        let (h0, h1) = (p[i].0 - p[i - 1].0, p[i + 1].0 - p[i].0);
        let (w0, w1) = (2.0 * h1 + h0, h1 + 2.0 * h0);
        (w0 + w1) / (w0 / d0 + w1 / d1)
    };
    let k = p.windows(2).position(|w| x <= w[1].0).unwrap_or(n - 2);
    let h = p[k + 1].0 - p[k].0;
    let t = (x - p[k].0) / h;
    let (t2, t3) = (t * t, t * t * t);
    let y = (2.0 * t3 - 3.0 * t2 + 1.0) * p[k].1 + (t3 - 2.0 * t2 + t) * h * tangent(k) + (-2.0 * t3 + 3.0 * t2) * p[k + 1].1 + (t3 - t2) * h * tangent(k + 1);
    y.clamp(0.0, 1.0)
}

/// Levels on one screen brightness: in black / white stretch, the middle's gamma, out black / white.
fn levels(p: &Map<String, Value>, d: f64) -> f64 {
    let t = ((d - num(p, "inBlack")) / (num(p, "inWhite") - num(p, "inBlack")).max(1e-6)).clamp(0.0, 1.0);
    num(p, "outBlack") + (num(p, "outWhite") - num(p, "outBlack")) * t.powf(1.0 / num(p, "gamma").max(1e-3))
}

/// The ACEScct table of a reshaping of screen brightness (module doc).
fn table(f: impl Fn(f64) -> f64) -> Vec<f32> {
    let code = |lin: f64| Curve::AcesCct.encode(lin as f32) as f64;
    let screen_code = |d: f64| code(Curve::Srgb.decode(d.clamp(0.0, 1.0) as f32) as f64);
    let (c0, c1) = (code(0.0), code(1.0));
    (0..SAMPLES)
        .map(|i| {
            let c = i as f64 / (SAMPLES - 1) as f64;
            let lin = Curve::AcesCct.decode(c as f32) as f64;
            let out = if lin <= 0.0 {
                c - c0 + screen_code(f(0.0))
            } else if lin >= 1.0 {
                c - c1 + screen_code(f(1.0))
            } else {
                screen_code(f(Curve::Srgb.encode(lin as f32) as f64))
            };
            out as f32
        })
        .collect()
}

/// The `curves` grade op (spec form) of a layer's levels and curves; None when both are off. Levels and the
/// "all channels" curve make the master table, each channel's curve its own (applied after the master).
pub fn op(p: &Map<String, Value>) -> Result<Option<Value>, String> {
    let on = |f: &str| p.get(f).and_then(Value::as_bool).unwrap_or(false);
    let (lv, cv) = (on("levels"), on("curves"));
    if !lv && !cv {
        return Ok(None);
    }
    let curve = |f: &str| -> Result<Option<Vec<(f64, f64)>>, String> {
        if !cv {
            return Ok(None);
        }
        let pts = points(p.get(f).and_then(Value::as_str).unwrap_or("")).map_err(|e| format!("{f}: {e}"))?;
        Ok((pts != [(0.0, 0.0), (1.0, 1.0)]).then_some(pts))
    };
    let master = curve("curve")?;
    let mut op = json!({ "op": "curves" });
    if lv || master.is_some() {
        op["master"] = json!(table(|d| {
            let d = if lv { levels(p, d) } else { d };
            master.as_ref().map_or(d, |m| through(m, d))
        }));
    }
    for (f, ch) in [("curveR", "r"), ("curveG", "g"), ("curveB", "b")] {
        if let Some(c) = curve(f)? {
            op[ch] = json!(table(|d| through(&c, d)));
        }
    }
    Ok(Some(op))
}

