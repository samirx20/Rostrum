//! Matte statistics (docs/phase2/KEYING_ROTO.md §6.2, COMP_CORE.md §5): what a matte measures as, as numbers an agent
//! reads (`matte.read`). Never a score, never advice. Pure CPU: the host (or the keyer's CPU reference) hands over the
//! alpha frames and, when it has them, the plate, the despilled foreground and the local screen colour.
//!
//!   coverage  pure 0 / pure 1 / partial share, 16-bin histogram, area and bbox of alpha > 0.5
//!   edge      band width along the normal at ≤ 64 contour samples, contour length, soft share        (edge.rs)
//!   holes     holes inside the filled subject outline, loose specks outside it                        (edge.rs)
//!   chatter   frame-to-frame |Δα| in static regions per zone (needs ≥ 2 frames)                      (temporal.rs)
//!   spill     screen excess in the edge band and the foreground, before and after despill, edge hue (spill.rs)
//!   screen    residual alpha where it should be 0, uniformity of the local screen colour             (spill.rs)
//!   temporal  area per frame, area delta, centroid jump                                              (temporal.rs)
//!   compare   against a reference matte                                                              (compare.rs)
//!   notes     the numbers as plain statements
//!
//! Blocks that describe one frame (coverage, edge, holes, spill, screen, compare) measure frame `focus`; chatter and
//! temporal use all of them. `edge` and `holes` run on a half-size copy when the frame is wider than `half_above`
//! (areas and lengths are still px of the frame). `outlineJitter` (contour against its smoothed self) is not measured.

mod compare;
mod edge;
mod spill;
mod temporal;
#[cfg(test)]
mod tests;

use crate::Rgb;
use serde_json::{json, Value};

/// The fields of KEYING_ROTO §6.2, all overridable.
#[derive(Clone, Debug)]
pub struct Thresholds {
    /// Alpha ≤ this is pure 0 (0.005).
    pub pure0: f64,
    /// Alpha ≥ this is pure 1 (0.995).
    pub pure1: f64,
    /// The partial-alpha band (0.05 to 0.95): edge width, edge zone, spill's edge band.
    pub band_lo: f64,
    pub band_hi: f64,
    /// The subject is alpha > this (0.5).
    pub inside: f64,
    /// The screen is alpha < this (0.01).
    pub screen_below: f64,
    /// A plate pixel is static when its luma (ACEScg, linear) moved by less than this between frames (0.01).
    pub static_luma: f64,
    /// Contour samples for the band width (64).
    pub edge_points: usize,
    /// `edge` and `holes` work on half size when the frame is wider than this (1000 px).
    pub half_above: usize,
    /// Entries kept of the `areaDelta` series (32).
    pub series: usize,
}

impl Default for Thresholds {
    fn default() -> Self {
        Thresholds { pure0: 0.005, pure1: 0.995, band_lo: 0.05, band_hi: 0.95, inside: 0.5, screen_below: 0.01, static_luma: 0.01, edge_points: 64, half_above: 1000, series: 32 }
    }
}

/// What to measure. Every image is `width × height`, row by row.
pub struct StatsInput<'a> {
    pub width: usize,
    pub height: usize,
    /// Alpha frames, f32, 0 … 1 (at least one).
    pub alpha: Vec<&'a [f32]>,
    /// The plate per frame, straight ACEScg (empty, or one per alpha frame).
    pub plate: Vec<&'a [Rgb]>,
    /// The despilled foreground per frame, premultiplied ACEScg (empty, or one per alpha frame).
    pub fg: Vec<&'a [Rgb]>,
    /// The local screen colour per frame, ACEScg (empty, or one per alpha frame).
    pub local: Vec<&'a [Rgb]>,
    /// Only pixels with value > 0.5 are measured.
    pub region: Option<&'a [f32]>,
    /// A reference alpha for frame `focus`.
    pub reference: Option<&'a [f32]>,
    /// The screen colour, ACEScg; else the plate's mean where alpha < `screen_below`.
    pub screen: Option<Rgb>,
    /// The frame the single-frame blocks measure (0).
    pub focus: usize,
    pub thresholds: Thresholds,
}

impl<'a> StatsInput<'a> {
    pub fn new(width: usize, height: usize, alpha: Vec<&'a [f32]>) -> StatsInput<'a> {
        StatsInput { width, height, alpha, plate: vec![], fg: vec![], local: vec![], region: None, reference: None, screen: None, focus: 0, thresholds: Thresholds::default() }
    }
}

pub(crate) fn r6(v: f64) -> f64 {
    (v * 1e6).round() / 1e6
}

pub(crate) fn in_region(reg: Option<&[bool]>, i: usize) -> bool {
    reg.is_none_or(|r| r[i])
}

fn coverage(a: &[f32], w: usize, reg: Option<&[bool]>, th: &Thresholds) -> (Value, usize, usize) {
    let (mut n, mut p0, mut p1, mut area) = (0usize, 0usize, 0usize, 0usize);
    let mut hist = [0usize; 16];
    let (mut x0, mut y0, mut x1, mut y1) = (usize::MAX, usize::MAX, 0usize, 0usize);
    for (i, &v) in a.iter().enumerate() {
        if !in_region(reg, i) {
            continue;
        }
        n += 1;
        if v as f64 <= th.pure0 {
            p0 += 1;
        } else if v as f64 >= th.pure1 {
            p1 += 1;
        }
        hist[((v.clamp(0.0, 1.0) * 16.0) as usize).min(15)] += 1;
        if v as f64 > th.inside {
            area += 1;
            let (x, y) = (i % w, i / w);
            (x0, y0, x1, y1) = (x0.min(x), y0.min(y), x1.max(x + 1), y1.max(y + 1));
        }
    }
    let pct = |c: usize| r6(100.0 * c as f64 / n.max(1) as f64);
    let bbox = if area > 0 { json!([x0, y0, x1, y1]) } else { Value::Null };
    let v = json!({ "px": n, "pure0": pct(p0), "pure1": pct(p1), "partial": pct(n - p0 - p1), "hist": hist, "areaPx": area, "bbox": bbox });
    (v, n, area)
}

fn f(v: &Value, path: &[&str]) -> Option<f64> {
    path.iter().try_fold(v, |v, k| v.get(*k)).and_then(Value::as_f64)
}

fn notes(out: &Value, th: &Thresholds) -> Vec<String> {
    let mut n = vec![];
    let c = &out["coverage"];
    n.push(format!(
        "alpha > {} covers {} px of {} measured; {}% of them are ≤ {}, {}% ≥ {}, {}% between",
        th.inside, c["areaPx"], c["px"], c["pure0"], th.pure0, c["pure1"], th.pure1, c["partial"]
    ));
    if let (Some(p50), Some(p90), Some(mx)) = (f(out, &["edge", "bandWidthPx", "p50"]), f(out, &["edge", "bandWidthPx", "p90"]), f(out, &["edge", "bandWidthPx", "max"])) {
        n.push(format!("edge band ({} to {}) is {p50} px at p50, {p90} px at p90, {mx} px at max over {} contour samples", th.band_lo, th.band_hi, out["edge"]["samples"]));
    }
    let h = &out["holes"];
    n.push(format!(
        "{} holes, {} px (largest {}) inside the filled outline of {} px; {} loose specks, {} px outside it",
        h["count"], h["areaPx"], h["largest"], h["subjectAreaPx"], h["looseSpecks"]["count"], h["looseSpecks"]["areaPx"]
    ));
    if out["chatter"].is_object() {
        for z in ["edge", "core", "screen"] {
            if let (Some(m), Some(p)) = (f(out, &["chatter", z, "mad"]), f(out, &["chatter", z, "p99"])) {
                n.push(format!("chatter in the {z} zone: mad {m}, p99 {p} over {} static px, {} frames", out["chatter"][z]["px"], out["chatter"]["frames"]));
            }
        }
    }
    if out["spill"].is_object() {
        for z in ["edgeBand", "foreground"] {
            let s = &out["spill"][z];
            for (k, label) in [("before", "before despill"), ("after", "after despill")] {
                if let Some(p) = f(s, &[k, "p95"]) {
                    n.push(format!("spill excess in the {} {label}: mean {}, p95 {p}", if z == "edgeBand" { "edge band" } else { "foreground" }, s[k]["mean"]));
                }
            }
        }
        if let Some(d) = f(out, &["spill", "edgeHue", "meanDeg"]) {
            n.push(format!("edge band hue {d}°{}", f(out, &["spill", "edgeHue", "screenDeg"]).map(|s| format!(", screen hue {s}°")).unwrap_or_default()));
        }
    }
    if let (Some(m), Some(x)) = (f(out, &["screen", "residual", "mean"]), f(out, &["screen", "residual", "max"])) {
        n.push(format!("alpha below {} over {} px: mean {m}, max {x}", th.screen_below, out["screen"]["px"]));
    }
    if let Some(a) = out["temporal"]["centroidJump"].as_object() {
        n.push(format!("centroid moves {} px on average, {} px at most, over {} frames", a["mean"], a["max"], out["temporal"]["frames"]));
    }
    if out["compare"].is_object() {
        let c = &out["compare"];
        n.push(format!("against the reference: iou {}, mad {}, edge mad {}, sad {}%, gradient error {}", c["iou"], c["mad"], c["edgeMad"], c["sad"], c["gradientError"]));
    }
    n
}

/// Measure the matte. `Err` names an input that does not fit (wrong size, wrong frame count).
pub fn measure(input: &StatsInput) -> Result<Value, String> {
    let (w, h) = (input.width, input.height);
    let th = &input.thresholds;
    if w == 0 || h == 0 || input.alpha.is_empty() {
        return Err("matte_stats: needs a non-empty picture and at least one alpha frame".into());
    }
    let nf = input.alpha.len();
    let size = |what: &str, len: usize| if len == w * h { Ok(()) } else { Err(format!("matte_stats: {what} has {len} pixels; {w} × {h} is {}", w * h)) };
    for a in &input.alpha {
        size("an alpha frame", a.len())?;
    }
    for (what, n) in [("plate", input.plate.len()), ("fg", input.fg.len()), ("local", input.local.len())] {
        if n != 0 && n != nf {
            return Err(format!("matte_stats: {what} has {n} frames; alpha has {nf}"));
        }
    }
    for p in &input.plate {
        size("a plate frame", p.len())?;
    }
    for p in &input.fg {
        size("a fg frame", p.len())?;
    }
    for p in &input.local {
        size("a local frame", p.len())?;
    }
    for (what, img) in [("region", input.region), ("reference", input.reference)] {
        if let Some(i) = img {
            size(what, i.len())?;
        }
    }
    if input.focus >= nf {
        return Err(format!("matte_stats: focus {} is outside the {nf} frames", input.focus));
    }
    let reg: Option<Vec<bool>> = input.region.map(|r| r.iter().map(|v| *v > 0.5).collect());
    let reg = reg.as_deref();
    let k = input.focus;
    let a = input.alpha[k];
    let (cov, _n, _area) = coverage(a, w, reg, th);
    let work = edge::Work::new(a, reg, w, h, th);
    let screen = spill::screen_colour(a, input.plate.get(k).copied(), input.screen, reg, th);
    let mut out = json!({
        "width": w, "height": h, "frames": nf, "focus": k, "regionGiven": reg.is_some(),
        "coverage": cov,
        "edge": edge::edge(&work, th),
        "holes": edge::holes(&work, th),
        "chatter": temporal::chatter(&input.alpha, &input.plate, reg, th),
        "spill": spill::spill(a, input.plate.get(k).copied(), input.fg.get(k).copied(), reg, screen, th),
        "screen": spill::screen(a, input.local.get(k).copied(), input.plate.get(k).copied(), reg, th),
        "temporal": temporal::temporal(&input.alpha, w, reg, th),
    });
    if let Some((c, of)) = screen {
        out["screenColour"] = json!({ "rgb": c.map(|v| r6(v as f64)), "of": of });
    }
    if let Some(r) = input.reference {
        out["compare"] = compare::compare(a, r, w, h, reg, th);
    }
    let n = notes(&out, th);
    out["notes"] = json!(n);
    Ok(out)
}
