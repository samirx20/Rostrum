//! CIE Lab (D65) of a mean colour, ΔE2000 (Sharma, Wu, Dalal 2005), and the difference of two `measure` results
//! (`grade.compare`).
use crate::matrix::{apply, xy_to_xyz};
use crate::spaces::{Gamut, D65};
use serde_json::{json, Map, Value};

/// Lab (D65) of a linear Rec.709 colour.
pub fn lab_of(lin709: [f64; 3]) -> [f64; 3] {
    let xyz = apply(&Gamut::get("lin_rec709").expect("registered").to_xyz(), lin709);
    let white = xy_to_xyz(D65);
    let f = |t: f64| if t > 216.0 / 24389.0 { t.cbrt() } else { (24389.0 / 27.0 * t + 16.0) / 116.0 };
    let (fx, fy, fz) = (f(xyz[0] / white[0]), f(xyz[1] / white[1]), f(xyz[2] / white[2]));
    [116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)]
}

/// ΔE2000 between two Lab colours.
pub fn delta_e2000(a: [f64; 3], b: [f64; 3]) -> f64 {
    let (l1, a1, b1, l2, a2, b2) = (a[0], a[1], a[2], b[0], b[1], b[2]);
    let (c1, c2) = (a1.hypot(b1), a2.hypot(b2));
    let cm = (c1 + c2) / 2.0;
    let g = 0.5 * (1.0 - (cm.powi(7) / (cm.powi(7) + 25f64.powi(7))).sqrt());
    let (ap1, ap2) = ((1.0 + g) * a1, (1.0 + g) * a2);
    let (cp1, cp2) = (ap1.hypot(b1), ap2.hypot(b2));
    let hp = |b: f64, ap: f64| if b == 0.0 && ap == 0.0 { 0.0 } else { b.atan2(ap).to_degrees().rem_euclid(360.0) };
    let (h1, h2) = (hp(b1, ap1), hp(b2, ap2));
    let dl = l2 - l1;
    let dc = cp2 - cp1;
    let dh = if cp1 * cp2 == 0.0 { 0.0 } else if (h2 - h1).abs() <= 180.0 { h2 - h1 } else if h2 - h1 > 180.0 { h2 - h1 - 360.0 } else { h2 - h1 + 360.0 };
    let dhh = 2.0 * (cp1 * cp2).sqrt() * (dh.to_radians() / 2.0).sin();
    let lbar = (l1 + l2) / 2.0;
    let cbar = (cp1 + cp2) / 2.0;
    let hbar = if cp1 * cp2 == 0.0 { h1 + h2 } else if (h1 - h2).abs() <= 180.0 { (h1 + h2) / 2.0 } else if h1 + h2 < 360.0 { (h1 + h2 + 360.0) / 2.0 } else { (h1 + h2 - 360.0) / 2.0 };
    let t = 1.0 - 0.17 * (hbar - 30.0).to_radians().cos() + 0.24 * (2.0 * hbar).to_radians().cos() + 0.32 * (3.0 * hbar + 6.0).to_radians().cos() - 0.20 * (4.0 * hbar - 63.0).to_radians().cos();
    let dtheta = 30.0 * (-((hbar - 275.0) / 25.0).powi(2)).exp();
    let rc = 2.0 * (cbar.powi(7) / (cbar.powi(7) + 25f64.powi(7))).sqrt();
    let sl = 1.0 + 0.015 * (lbar - 50.0).powi(2) / (20.0 + (lbar - 50.0).powi(2)).sqrt();
    let (sc, sh) = (1.0 + 0.045 * cbar, 1.0 + 0.015 * cbar * t);
    let rt = -(2.0 * dtheta).to_radians().sin() * rc;
    ((dl / sl).powi(2) + (dc / sc).powi(2) + (dhh / sh).powi(2) + rt * (dc / sc) * (dhh / sh)).sqrt()
}

fn num(v: &Value, path: &[&str]) -> Option<f64> {
    path.iter().try_fold(v, |v, k| v.get(*k))?.as_f64()
}
fn rd(v: f64, places: i32) -> f64 {
    let k = 10f64.powi(places);
    let x = (v * k).round() / k;
    if x == 0.0 { 0.0 } else { x }
}

/// `b - a` for the numbers an agent steers by: the same blocks as `measure` gives, as differences (`a` is the shot,
/// `b` the reference: a positive `dLumaP50` means the reference is brighter), and ΔE2000 of the mean colours.
pub fn diff(a: &Value, b: &Value) -> Result<Value, String> {
    if a["space"] != b["space"] {
        return Err(format!("the two scope reads are in different spaces ({} and {}); read both in the same `space`", a["space"], b["space"]));
    }
    let mut out = Map::new();
    out.insert("space".into(), a["space"].clone());
    let d = |path: &[&str], places| num(a, path).zip(num(b, path)).map(|(x, y)| rd(y - x, places));
    for (key, path) in [("dLumaP50", ["luma", "p50"]), ("dLumaP95", ["luma", "p95"]), ("dLumaP5", ["luma", "p5"]), ("dLumaMean", ["luma", "mean"])] {
        if let Some(v) = d(&path, 4) {
            out.insert(key.into(), json!(v));
        }
    }
    let mut bal = Map::new();
    for zone in ["shadows", "mids", "highs"] {
        let (rg, by) = (d(&["balance", zone, "castRG"], 4), d(&["balance", zone, "castBY"], 4));
        if let (Some(rg), Some(by)) = (rg, by) {
            bal.insert(zone.into(), json!({ "castRG": rg, "castBY": by }));
        }
    }
    if !bal.is_empty() {
        out.insert("dBalance".into(), Value::Object(bal));
    }
    if let Some(v) = d(&["vector", "satMean"], 4) {
        out.insert("dSat".into(), json!(v));
    }
    if let Some(v) = num(a, &["vector", "hueMean"]).zip(num(b, &["vector", "hueMean"])).map(|(x, y)| rd((y - x + 180.0).rem_euclid(360.0) - 180.0, 1)) {
        out.insert("dHue".into(), json!(v));
    }
    for (key, path) in [("dClippedWhite", ["clipped", "white"]), ("dClippedBlack", ["clipped", "black"])] {
        if let Some(v) = d(&path, 2) {
            out.insert(key.into(), json!(v));
        }
    }
    let skin = |v: &Value| num(v, &["vector", "skin", "devDeg"]);
    if skin(a).is_some() || skin(b).is_some() {
        out.insert("skinDevDeg".into(), json!({ "shot": skin(a), "reference": skin(b) }));
    }
    let lab = |v: &Value| -> Option<[f64; 3]> {
        let l = v.get("meanLab")?.as_array()?;
        Some([l.first()?.as_f64()?, l.get(1)?.as_f64()?, l.get(2)?.as_f64()?])
    };
    if let Some((la, lb)) = lab(a).zip(lab(b)) {
        out.insert("deltaE".into(), json!(rd(delta_e2000(la, lb), 2)));
    }
    Ok(Value::Object(out))
}
