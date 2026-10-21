//! Shot match and auto balance (docs/phase1/GRADING.md §4.3, §7.3; package G7): a correction computed from measured
//! frames, returned as the fields of an ordinary grade layer (the host writes them with `grade.match` / `grade.auto`:
//! the agent reads, edits and undoes plain numbers). Plain statistics, our own maths, no library:
//!
//! 1. The shot (ACEScg, as the compositor made it, with its grade) and the reference are measured by `scope::measure`
//!    (the one definition of every number) in the picture's `domain` (the display: what `grade.compare` reads), over
//!    the whole frame or a `region`. Percentile / zone / chroma statistics are robust to the 1 % tails by
//!    construction (p5, p50, p95; zone means are means).
//! 2. A model of the layer has up to eleven numbers: `lift`, `gamma`, `gain` (master: black point, mid, white point
//!    in ACEScct), the `log` wheels' red and blue offsets in shadows, mids and highs (colour balance; green follows so
//!    each wheel leaves the luma alone, the master is the levels), `saturation`, and `hue` (degrees, for the skin line).
//! 3. Targets are the reference's numbers (`fit_match`) or fixed ones (`fit_auto`: black and white points, an
//!    even tone split, neutral casts). Residuals are scaled so 1.0 is about 0.01 of a luma / cast / saturation unit
//!    and 2 degrees of skin hue.
//! 4. The numbers are found by Levenberg–Marquardt on the residuals, **running the real CPU grade over the shot's
//!    pixels** for every trial (`Grade::apply_all`, then the view, then `measure`): the numbers land, they do not
//!    just move the right way. The fields are rounded to four places before the last measurement, so the `after`
//!    block describes exactly the numbers returned.
//!
//! `strength` (0 … 1) scales every number's distance from neutral before that last measurement.
use super::Grade;
use crate::Rgb;
use crate::scope::measure::{Options, measure};
use crate::scope::{Domain, Frame, Region, compare};
use serde_json::{Map, Value, json};

const N: usize = 11;
const NEUTRAL: [f64; N] = [0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0];
const LO: [f64; N] = [-0.8, 0.25, 0.2, -0.12, -0.12, -0.12, -0.12, -0.12, -0.12, 0.0, -60.0];
const HI: [f64; N] = [0.8, 4.0, 5.0, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 3.0, 60.0];
/// The finite-difference step of each number.
const STEP: [f64; N] = [0.01, 0.02, 0.02, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.03, 1.0];
/// A light pull toward neutral on every number in play (residual units per unit of the number): where several
/// numbers fit the targets equally (lift against gamma against gain) the smallest correction wins, and a number the
/// targets do not feel stays where it is. About 0.5 residual units (0.005 luma) at a lift of 0.1.
const PRIOR: [f64; N] = [5.0, 2.5, 2.5, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 2.5, 0.1];
/// One residual unit, in the unit of each statistic.
const UNIT_LUMA: f64 = 0.01;
const UNIT_CAST: f64 = 0.01;
const UNIT_SAT: f64 = 0.01;
const UNIT_SKIN_DEG: f64 = 2.0;
/// Pixels of the shot the trials run over (a stride of the frame; the final numbers use the same ones).
const TRIAL_PIXELS: usize = 90_000;

/// Which numbers a fit may move.
#[derive(Clone, Copy, Debug, Default)]
pub struct Active {
    pub lift: bool,
    pub gamma: bool,
    pub gain: bool,
    pub balance: bool,
    pub saturation: bool,
    pub hue: bool,
}

impl Active {
    fn flags(&self) -> [bool; N] {
        let b = self.balance;
        [self.lift, self.gamma, self.gain, b, b, b, b, b, b, self.saturation, self.hue]
    }
}

/// What a fit steers the picture's statistics to.
#[derive(Clone, Debug, Default)]
pub struct Target {
    /// Luma percentiles by key (`p5`, `p50`, `p95` …) and the value wanted.
    pub luma: Vec<(&'static str, f64)>,
    /// Per zone (shadows, mids, highs): the wanted `[castRG, castBY]`.
    pub casts: [Option<[f64; 2]>; 3],
    pub sat: Option<f64>,
    /// The wanted skin deviation from the skin line, degrees.
    pub skin_dev: Option<f64>,
}

const ZONES: [&str; 3] = ["shadows", "mids", "highs"];

fn num(v: &Value, path: &[&str]) -> Option<f64> {
    path.iter().try_fold(v, |v, k| v.get(*k))?.as_f64()
}

impl Target {
    /// The residuals of a measurement (constant length for one target; a statistic a trial lacks reads as met).
    fn residuals(&self, s: &Value) -> Vec<f64> {
        let mut r = vec![];
        for (k, want) in &self.luma {
            r.push(num(s, &["luma", k]).map_or(0.0, |v| (v - want) / UNIT_LUMA));
        }
        for (z, want) in self.casts.iter().enumerate() {
            if let Some([rg, by]) = want {
                r.push(num(s, &["balance", ZONES[z], "castRG"]).map_or(0.0, |v| (v - rg) / UNIT_CAST));
                r.push(num(s, &["balance", ZONES[z], "castBY"]).map_or(0.0, |v| (v - by) / UNIT_CAST));
            }
        }
        if let Some(want) = self.sat {
            r.push(num(s, &["vector", "satMean"]).map_or(0.0, |v| (v - want) / UNIT_SAT));
        }
        if let Some(want) = self.skin_dev {
            r.push(num(s, &["vector", "skin", "devDeg"]).map_or(0.0, |v| (v - want) / UNIT_SKIN_DEG));
        }
        r
    }
}

/// A wheel's green that keeps its luma: the wheels move red and blue to balance colour, and green follows so the
/// Rec.709 luma of the offset is zero (a colour balance should not also be an exposure change).
fn wheel_g(r: f64, b: f64) -> f64 {
    -(0.2126 * r + 0.0722 * b) / 0.7152
}

/// The grade of one set of numbers, in the order a layer runs its fields (src/engine/video/gradeProgram.ts):
/// saturation, hue, then lift / gamma / gain, then the log wheels.
/// With a hue-vs-saturation table (`HUE_NODES + 1` samples, the last the first) after the wheels, where a layer's curves run.
fn spec_with(x: &[f64; N], hue_sat: Option<&[f32]>) -> Value {
    let mut ops = vec![];
    if x[9] != 1.0 {
        ops.push(json!({ "op": "saturation", "saturation": x[9], "luma": "rec709" }));
    }
    if x[10] != 0.0 {
        ops.push(json!({ "op": "hue", "degrees": x[10] }));
    }
    if x[0] != 0.0 || x[1] != 1.0 || x[2] != 1.0 {
        ops.push(json!({ "op": "lgg", "lift": [0, 0, 0, x[0]], "gamma": [1, 1, 1, x[1]], "gain": [1, 1, 1, x[2]] }));
    }
    if x[3..9].iter().any(|v| *v != 0.0) {
        ops.push(json!({ "op": "log", "shadow": [x[3], wheel_g(x[3], x[4]), x[4], 0], "mid": [x[5], wheel_g(x[5], x[6]), x[6], 0], "high": [x[7], wheel_g(x[7], x[8]), x[8], 0] }));
    }
    if let Some(t) = hue_sat {
        ops.push(json!({ "op": "hsl_curves", "hueSat": t }));
    }
    json!({ "ops": ops })
}

/// The layer fields of a set of numbers (neutral ones left out), as `grade.set` takes them.
pub fn fields(x: &[f64; N]) -> Value {
    let mut m = Map::new();
    let wheel = |r: f64, b: f64| {
        let mut w = Map::new();
        if r != 0.0 {
            w.insert("r".into(), json!(r));
        }
        if b != 0.0 {
            w.insert("b".into(), json!(b));
        }
        if r != 0.0 || b != 0.0 {
            w.insert("g".into(), json!(round4(wheel_g(r, b))));
        }
        w
    };
    for (i, key) in [(0, "lift"), (1, "gamma"), (2, "gain")] {
        if x[i] != NEUTRAL[i] {
            m.insert(key.into(), json!({ "m": x[i] }));
        }
    }
    let log: Map<String, Value> = [("shadow", wheel(x[3], x[4])), ("mid", wheel(x[5], x[6])), ("high", wheel(x[7], x[8]))]
        .into_iter()
        .filter(|(_, w)| !w.is_empty())
        .map(|(k, w)| (k.to_string(), Value::Object(w)))
        .collect();
    if !log.is_empty() {
        m.insert("log".into(), Value::Object(log));
    }
    if x[9] != 1.0 {
        m.insert("saturation".into(), json!(x[9]));
    }
    if x[10] != 0.0 {
        m.insert("hue".into(), json!(x[10]));
    }
    Value::Object(m)
}

fn round4(v: f64) -> f64 {
    let x = (v * 1e4).round() / 1e4;
    if x == 0.0 { 0.0 } else { x }
}

/// Every `stride`-th pixel in both directions (the frame's structure, so region fractions still apply).
fn decimate(f: &Frame, max: usize) -> Frame {
    let s = ((f.width * f.height) as f64 / max as f64).sqrt().ceil().max(1.0) as usize;
    if s == 1 {
        return Frame::new(f.width, f.height, f.domain, f.px.clone());
    }
    let (w, h) = (f.width.div_ceil(s), f.height.div_ceil(s));
    let mut px = Vec::with_capacity(w * h);
    for y in (0..f.height).step_by(s) {
        for x in (0..f.width).step_by(s) {
            px.push(f.px[y * f.width + x]);
        }
    }
    Frame::new(w, h, f.domain, px)
}

/// The shot through a set of numbers, then the view, measured (`luma`, `balance`, `vector`).
struct Model<'a> {
    shot: Frame,
    view: &'a dyn Fn(Rgb) -> Rgb,
    domain: Domain,
    region: Region,
}

fn options(region: &Region) -> Options {
    Options { region: region.clone(), parts: Some(vec!["luma".into(), "balance".into(), "vector".into()]), histogram: None, zones: [0.25, 0.75] }
}

impl Model<'_> {
    fn eval(&self, x: &[f64; N]) -> Result<Value, String> {
        self.eval_with(x, None)
    }

    /// The shot's pixels through the numbers (and a hue-vs-saturation table), then the view: the picture as displayed.
    fn display(&self, x: &[f64; N], hue_sat: Option<&[f32]>) -> Result<Frame, String> {
        let g = Grade::from_spec(&spec_with(x, hue_sat))?;
        let mut px = self.shot.px.clone();
        g.apply_all(&mut px);
        for p in px.iter_mut() {
            *p = (self.view)(*p);
        }
        Ok(Frame::new(self.shot.width, self.shot.height, self.domain, px))
    }

    fn eval_with(&self, x: &[f64; N], hue_sat: Option<&[f32]>) -> Result<Value, String> {
        measure(&self.display(x, hue_sat)?, &options(&self.region))
    }
}

/// Solves `a x = b` (Gaussian elimination with partial pivoting); None when singular.
fn linsolve(mut a: Vec<Vec<f64>>, mut b: Vec<f64>) -> Option<Vec<f64>> {
    let n = b.len();
    for c in 0..n {
        let p = (c..n).max_by(|&i, &j| a[i][c].abs().total_cmp(&a[j][c].abs()))?;
        if a[p][c].abs() < 1e-14 {
            return None;
        }
        a.swap(c, p);
        b.swap(c, p);
        for r in c + 1..n {
            let f = a[r][c] / a[c][c];
            for k in c..n {
                a[r][k] -= f * a[c][k];
            }
            b[r] -= f * b[c];
        }
    }
    let mut x = vec![0.0; n];
    for r in (0..n).rev() {
        x[r] = (b[r] - (r + 1..n).map(|k| a[r][k] * x[k]).sum::<f64>()) / a[r][r];
    }
    Some(x)
}

fn cost(r: &[f64]) -> f64 {
    r.iter().map(|v| v * v).sum::<f64>() / 2.0
}

/// Levenberg–Marquardt from `start`: (the numbers, iterations, the largest residual in tolerance units).
fn solve(model: &Model, target: &Target, active: &Active, start: [f64; N], max_iterations: usize) -> Result<([f64; N], usize, f64), String> {
    let flags = active.flags();
    let idx: Vec<usize> = (0..N).filter(|&i| flags[i]).collect();
    let resid = |x: &[f64; N]| -> Result<Vec<f64>, String> {
        let mut v = target.residuals(&model.eval(x)?);
        v.extend(idx.iter().map(|&i| PRIOR[i] * (x[i] - NEUTRAL[i])));
        Ok(v)
    };
    let shown = |r: &[f64]| r[..r.len() - idx.len()].iter().fold(0.0, |m, v| f64::max(m, v.abs()));
    let mut x = start;
    let mut r = resid(&x)?;
    if idx.is_empty() || r.is_empty() {
        return Ok((x, 0, shown(&r)));
    }
    let mut c = cost(&r);
    let mut lambda = 1e-2;
    let mut iterations = 0;
    for _ in 0..max_iterations {
        if r[..r.len() - idx.len()].iter().all(|v| v.abs() < 0.1) {
            break;
        }
        iterations += 1;
        let (n, m) = (idx.len(), r.len());
        let mut jac = vec![vec![0.0; n]; m];
        for (k, &i) in idx.iter().enumerate() {
            let mut xp = x;
            let step = if x[i] + STEP[i] > HI[i] { -STEP[i] } else { STEP[i] };
            xp[i] += step;
            let rp = resid(&xp)?;
            for j in 0..m {
                jac[j][k] = (rp[j] - r[j]) / step;
            }
        }
        let a: Vec<Vec<f64>> = (0..n).map(|p| (0..n).map(|q| (0..m).map(|j| jac[j][p] * jac[j][q]).sum()).collect()).collect();
        let g: Vec<f64> = (0..n).map(|p| (0..m).map(|j| jac[j][p] * r[j]).sum()).collect();
        let mut improved = false;
        for _ in 0..8 {
            let damped: Vec<Vec<f64>> = (0..n).map(|p| (0..n).map(|q| a[p][q] + if p == q { lambda * (a[p][p] + 1e-9) } else { 0.0 }).collect()).collect();
            let Some(d) = linsolve(damped, g.iter().map(|v| -v).collect()) else {
                lambda *= 10.0;
                continue;
            };
            let mut xn = x;
            for (k, &i) in idx.iter().enumerate() {
                xn[i] = (x[i] + d[k]).clamp(LO[i], HI[i]);
            }
            let rn = resid(&xn)?;
            let cn = cost(&rn);
            if cn < c {
                let gain = c - cn;
                (x, r, c) = (xn, rn, cn);
                lambda = (lambda / 3.0).max(1e-7);
                improved = gain > 1e-9;
                break;
            }
            lambda *= 4.0;
        }
        if !improved {
            break;
        }
    }
    Ok((x, iterations, shown(&r)))
}

/// A fit: the layer's fields, the statistics before and after (`before` / `after` are `grade.compare` blocks: the
/// reference, or the target numbers of `fit_auto`, minus the shot), and how the search ended.
#[derive(Debug)]
pub struct Fit {
    pub fields: Value,
    pub before: Value,
    pub after: Value,
    pub iterations: usize,
    /// The largest remaining residual in tolerance units (1.0 ≈ 0.01 of luma / cast / saturation, 2 degrees of skin).
    pub residual: f64,
    pub notes: Vec<String>,
    /// The shot's own measurement (`luma`, `balance`, `vector`) before and after.
    pub shot_before: Value,
    pub shot_after: Value,
}

/// What `grade.match` may match.
#[derive(Clone, Copy, Debug)]
pub struct MatchParts {
    pub levels: bool,
    pub balance: bool,
    pub saturation: bool,
    pub skin: bool,
}

impl Default for MatchParts {
    fn default() -> Self {
        MatchParts { levels: true, balance: true, saturation: true, skin: true }
    }
}

impl MatchParts {
    pub fn parse(names: &[String]) -> Result<MatchParts, String> {
        let mut p = MatchParts { levels: false, balance: false, saturation: false, skin: false };
        for n in names {
            match n.as_str() {
                "levels" => p.levels = true,
                "balance" => p.balance = true,
                "saturation" => p.saturation = true,
                "skin" => p.skin = true,
                o => return Err(format!("a match part is levels, balance, saturation or skin; got `{o}`")),
            }
        }
        Ok(p)
    }
}

pub struct MatchOptions {
    pub parts: MatchParts,
    /// 0 … 1: how far from neutral the numbers go.
    pub strength: f64,
    /// Where the shot is read (and, unless `reference_region` is given, the reference).
    pub region: Region,
    pub reference_region: Option<Region>,
    /// Holds the average skin hue on the skin line (devDeg 0) instead of on the reference's.
    pub keep_skin: bool,
    /// Hue ranges in degrees `(from, to)` (clockwise; `from > to` wraps through red) the `hueSat` curve may move; empty = all hues.
    pub hue_ranges: Vec<(f64, f64)>,
}

impl Default for MatchOptions {
    fn default() -> Self {
        MatchOptions { parts: MatchParts::default(), strength: 1.0, region: Region::Full, reference_region: None, keep_skin: false, hue_ranges: vec![] }
    }
}

/// Hue sectors of the `hueSat` fit: one node every 30 degrees.
pub const HUE_NODES: usize = 12;
/// Pixels this near grey (HSV saturation) or this dark carry no hue worth steering.
const HUE_MIN_SAT: f32 = 0.06;
const HUE_MIN_MAX: f32 = 0.04;
/// A node needs this much hue weight (pixels) in both frames, and at least this share of the frame's pixels, or it stays at 1.
const HUE_MIN_WEIGHT: f64 = 40.0;
const HUE_MIN_SHARE: f64 = 0.002;
const HUE_K: (f64, f64) = (0.25, 3.5);

/// Pixels of a display frame placed on the hue nodes: per pixel the node below, the share on the node above (the table
/// is linear between nodes, so the weights are too) and its chroma (max - min); grey and dark pixels are left out.
struct HueSamples {
    below: Vec<u8>,
    frac: Vec<f32>,
    chroma: Vec<f32>,
    /// The pixel's index in the frame (the shot is read again after the curve).
    at: Vec<usize>,
    total: usize,
}

fn hue_samples(f: &Frame, region: &Region) -> HueSamples {
    let region = region.resolve(f.width, f.height);
    let (x0, y0, x1, y1) = region.bounds(f.width, f.height);
    let mut s = HueSamples { below: vec![], frac: vec![], chroma: vec![], at: vec![], total: 0 };
    for y in y0..y1 {
        for x in x0..x1 {
            if !region.contains(x, y) {
                continue;
            }
            s.total += 1;
            let c = f.px[y * f.width + x];
            let (mx, mn) = (c[0].max(c[1]).max(c[2]), c[0].min(c[1]).min(c[2]));
            if mx < HUE_MIN_MAX || (mx - mn) / mx < HUE_MIN_SAT {
                continue;
            }
            let (a, b) = (c[0] as f64 - 0.5 * (c[1] + c[2]) as f64, 0.866_025_403_784_438_6 * (c[1] - c[2]) as f64);
            let h = (b.atan2(a) / std::f64::consts::TAU).rem_euclid(1.0) * HUE_NODES as f64;
            s.below.push((h.floor() as usize % HUE_NODES) as u8);
            s.frac.push((h - h.floor()) as f32);
            s.chroma.push(mx - mn);
            s.at.push(y * f.width + x);
        }
    }
    s
}

/// Weighted mean chroma and weight per node; `chroma` is read in place of the samples' own (the shot after the curve).
fn node_means(s: &HueSamples, chroma: &[f32]) -> ([f64; HUE_NODES], [f64; HUE_NODES]) {
    let (mut sum, mut w) = ([0.0; HUE_NODES], [0.0; HUE_NODES]);
    for i in 0..s.below.len() {
        let (k, f) = (s.below[i] as usize, s.frac[i] as f64);
        let c = chroma[i] as f64;
        sum[k] += (1.0 - f) * c;
        w[k] += 1.0 - f;
        sum[(k + 1) % HUE_NODES] += f * c;
        w[(k + 1) % HUE_NODES] += f;
    }
    (std::array::from_fn(|k| if w[k] > 0.0 { sum[k] / w[k] } else { 0.0 }), w)
}

fn in_ranges(deg: f64, ranges: &[(f64, f64)]) -> bool {
    ranges.is_empty()
        || ranges.iter().any(|&(a, b)| {
            if (b - a).abs() >= 360.0 {
                return true;
            }
            let (a, b, d) = (a.rem_euclid(360.0), b.rem_euclid(360.0), deg.rem_euclid(360.0));
            if a <= b { d >= a - 1e-9 && d <= b + 1e-9 } else { d >= a - 1e-9 || d <= b + 1e-9 }
        })
}

/// The table of `HUE_NODES + 1` samples (the last repeats the first) of node multipliers.
fn hue_table(k: &[f64; HUE_NODES]) -> Vec<f32> {
    (0..=HUE_NODES).map(|i| k[i % HUE_NODES] as f32).collect()
}

/// The joint saturation fit: what the picture's chroma needs per 30 degree hue sector, split into one global
/// `saturation` and per-sector multipliers (`curves.hueSat`).
///
/// 1. The shot is read at the solved numbers with saturation 1; each live sector's total gain `G[n]` is the
///    reference's mean chroma over the shot's (a sector is live when it is inside `o.hue_ranges` and has 40 weighted
///    pixels and 0.2 % of the frame in both pictures).
/// 2. Without a `hueRange` the global saturation is the chroma-weighted geometric mean of the live `G[n]` (the common
///    factor: the sectors carry only the per-hue differences, so a reference with only its reds boosted does not push
///    the whole wheel up first and pull the others back down); the split is unique. With a `hueRange` the global stays
///    at 1: the excluded hues remain exactly where they were, and only the sectors in the range move, each by its
///    full gain.
/// 3. `k[n] = G[n] / s`, then refinements run the real grade (the curve acts in ACEScct, the chroma is read in the
///    display) with `s` fixed and re-measure each sector. Sectors that are not live stay at 1 (and feel only `s`).
///
/// Returns the sector multipliers and the global saturation to write; with no live sector the global is the
/// whole-frame fit's (`x[9]`) and the sectors are 1.
fn fit_hue_sat(model: &Model, reference: &Frame, x: &[f64; N], o: &MatchOptions, notes: &mut Vec<String>) -> Result<([f64; HUE_NODES], f64), String> {
    let mut k = [1.0; HUE_NODES];
    let mut base = *x;
    base[9] = 1.0;
    let pre = model.display(&base, None)?;
    let shot = hue_samples(&pre, &model.region);
    let refs = hue_samples(reference, o.reference_region.as_ref().unwrap_or(&model.region));
    let (ref_mean, ref_w) = node_means(&refs, &refs.chroma);
    let (mean, w) = node_means(&shot, &shot.chroma);
    let enough = |w: f64, total: usize| w >= HUE_MIN_WEIGHT && w >= HUE_MIN_SHARE * total as f64;
    let wanted: [bool; HUE_NODES] = std::array::from_fn(|n| in_ranges(n as f64 * 30.0, &o.hue_ranges));
    let live: [bool; HUE_NODES] = std::array::from_fn(|n| wanted[n] && enough(w[n], shot.total) && enough(ref_w[n], refs.total) && mean[n] > 1e-4);
    let short: Vec<String> = (0..HUE_NODES).filter(|&n| wanted[n] && !live[n]).map(|n| (n * 30).to_string()).collect();
    if !short.is_empty() {
        notes.push(format!("hueSat: the sectors at {} degrees have too few coloured pixels in the shot or the reference, so they stay at 1", short.join(", ")));
    }
    if !live.iter().any(|l| *l) {
        return Ok((k, x[9]));
    }
    let gain: [f64; HUE_NODES] = std::array::from_fn(|n| if live[n] { (ref_mean[n] / mean[n]).clamp(HUE_K.0 * HUE_K.0, HUE_K.1 * HUE_K.1) } else { 1.0 });
    let s = if o.hue_ranges.is_empty() {
        let (num, den) = (0..HUE_NODES).filter(|&n| live[n]).fold((0.0, 0.0), |(a, d), n| (a + w[n] * mean[n] * gain[n].ln(), d + w[n] * mean[n]));
        (num / den).exp().clamp(HUE_K.0, HUE_K.1)
    } else {
        1.0
    };
    let mut with_s = base;
    with_s[9] = s;
    for _ in 0..4 {
        let after = model.display(&with_s, Some(&hue_table(&k)))?;
        let chroma: Vec<f32> = shot.at.iter().map(|&i| { let c = after.px[i]; c[0].max(c[1]).max(c[2]) - c[0].min(c[1]).min(c[2]) }).collect();
        let now = node_means(&shot, &chroma).0;
        for n in 0..HUE_NODES {
            if live[n] && now[n] > 1e-6 {
                k[n] = (k[n] * ref_mean[n] / now[n]).clamp(HUE_K.0, HUE_K.1);
            }
        }
    }
    Ok((k, s))
}

/// `hue_sat`: the per-30-degree saturation multipliers to write as `curves.hueSat` (None: no curve).
fn finish(model: &Model, target_stats: &Value, x0: [f64; N], solved: [f64; N], hue_sat: Option<[f64; HUE_NODES]>, strength: f64, iterations: usize, residual: f64, mut notes: Vec<String>) -> Result<Fit, String> {
    let x: [f64; N] = std::array::from_fn(|i| round4(NEUTRAL[i] + strength * (solved[i] - NEUTRAL[i])));
    let hue_sat = hue_sat.map(|k| k.map(|v| round4(1.0 + strength * (v - 1.0)))).filter(|k| k.iter().any(|v| *v != 1.0));
    let before = model.eval(&x0)?;
    let after = model.eval_with(&x, hue_sat.map(|k| hue_table(&k)).as_deref())?;
    if strength < 1.0 {
        notes.push(format!("strength {strength}: the numbers are {}% of the way from neutral", (strength * 100.0).round()));
    }
    let mut f = fields(&x);
    if let (Some(k), Some(m)) = (hue_sat, f.as_object_mut()) {
        let pts: Vec<Value> = k.iter().enumerate().map(|(n, v)| json!([n * 30, v])).collect();
        m.insert("curves".into(), json!({ "hueSat": pts }));
    }
    if f.as_object().is_some_and(Map::is_empty) {
        notes.push("the shot already measures like the target: no correction was needed".into());
    }
    Ok(Fit { fields: f, before: compare::diff(&before, target_stats)?, after: compare::diff(&after, target_stats)?, iterations, residual, notes, shot_before: before, shot_after: after })
}

/// The correction that makes `shot` (scene-linear ACEScg, as the compositor made it) measure like `reference` (a
/// picture in `domain`, the display), as the layer fields to add on top of the shot's own grade. `view` takes the
/// shot's ACEScg light to `domain` (the project's view).
pub fn fit_match(shot: &Frame, reference: &Frame, view: &dyn Fn(Rgb) -> Rgb, domain: Domain, o: &MatchOptions) -> Result<Fit, String> {
    if shot.domain != Domain::AcesCg {
        return Err("fit_match takes the shot as scene-linear ACEScg".into());
    }
    if reference.domain != domain {
        return Err("fit_match takes the reference in the same domain the view produces".into());
    }
    if !(0.0..=1.0).contains(&o.strength) {
        return Err(format!("strength is 0 … 1; got {}", o.strength));
    }
    let model = Model { shot: decimate(shot, TRIAL_PIXELS), view, domain, region: o.region.clone() };
    let reference = decimate(reference, 400_000);
    let ref_stats = measure(&reference, &options(o.reference_region.as_ref().unwrap_or(&o.region)))?;
    let shot_stats = model.eval(&NEUTRAL)?;
    let mut notes = vec![];
    let mut t = Target::default();
    if o.parts.levels {
        for k in ["p5", "p50", "p95"] {
            if let Some(v) = num(&ref_stats, &["luma", k]) {
                t.luma.push((k, v));
            }
        }
    }
    if o.parts.balance {
        for z in 0..3 {
            let (rg, by) = (num(&ref_stats, &["balance", ZONES[z], "castRG"]), num(&ref_stats, &["balance", ZONES[z], "castBY"]));
            if let (Some(rg), Some(by)) = (rg, by) {
                t.casts[z] = Some([rg, by]);
            }
        }
    }
    if o.parts.saturation {
        t.sat = num(&ref_stats, &["vector", "satMean"]);
    }
    let (shot_skin, ref_skin) = (num(&shot_stats, &["vector", "skin", "devDeg"]), num(&ref_stats, &["vector", "skin", "devDeg"]));
    let want_skin = o.parts.skin || o.keep_skin;
    let mut hue = false;
    if want_skin {
        match (shot_skin, ref_skin, o.keep_skin) {
            (Some(_), _, true) => {
                t.skin_dev = Some(0.0);
                hue = true;
            }
            (Some(_), Some(r), false) => {
                t.skin_dev = Some(r);
                hue = true;
            }
            (None, _, _) => notes.push("skin: the shot has under 1 % skin pixels in this region, so the skin hue was not matched".into()),
            (Some(_), None, false) => notes.push("skin: the reference has under 1 % skin pixels in this region, so the skin hue was not matched (keepSkin holds the shot's on the skin line)".into()),
        }
    }
    // Three stages, because the zones move as the levels do: levels first (the percentiles), then colour balance,
    // saturation and skin on the levelled shot (zones that exist in both), then everything together for a few steps.
    let levels = Active { lift: o.parts.levels, gamma: o.parts.levels, gain: o.parts.levels, ..Default::default() };
    let colour = Active { balance: o.parts.balance, saturation: o.parts.saturation, hue, ..Default::default() };
    let all = Active { lift: levels.lift, gamma: levels.gamma, gain: levels.gain, balance: colour.balance, saturation: colour.saturation, hue };
    let levels_only = Target { luma: t.luma.clone(), ..Default::default() };
    let (x1, it1, _) = solve(&model, &levels_only, &levels, NEUTRAL, 20)?;
    let levelled = model.eval(&x1)?;
    for z in 0..3 {
        if num(&levelled, &["balance", ZONES[z], "castRG"]).is_none() {
            t.casts[z] = None;
        }
    }
    if num(&levelled, &["vector", "skin", "devDeg"]).is_none() {
        t.skin_dev = None;
        hue = false;
    }
    // With a `hueRange` the global saturation is not solved: the sectors in the range carry the whole match and the
    // excluded hues stay where they were (see `fit_hue_sat`).
    let global_sat = colour.saturation && o.hue_ranges.is_empty();
    if !o.hue_ranges.is_empty() {
        t.sat = None;
    }
    let colour = Active { hue, saturation: global_sat, ..colour };
    let all = Active { hue, saturation: global_sat, ..all };
    let (x2, it2, _) = solve(&model, &t, &colour, x1, 20)?;
    let (mut x, it3, residual) = solve(&model, &t, &all, x2, 20)?;
    let mut hue_sat = None;
    if o.parts.saturation {
        let (k, s) = fit_hue_sat(&model, &reference, &x, o, &mut notes)?;
        x[9] = s;
        // The sectors leave out grey and dark pixels, the whole-frame mean does not: trim the common factor so that
        // mean still lands (two secant steps; the sector multipliers stay, they carry the per-hue differences).
        if let (Some(want), true, true) = (t.sat, o.hue_ranges.is_empty(), k.iter().any(|v| *v != 1.0)) {
            let table = hue_table(&k);
            for _ in 0..2 {
                let Some(got) = num(&model.eval_with(&x, Some(&table))?, &["vector", "satMean"]).filter(|g| *g > 1e-6) else { break };
                x[9] = (x[9] * (1.0 + (want - got) / got)).clamp(HUE_K.0, HUE_K.1);
            }
        }
        hue_sat = Some(k);
    }
    finish(&model, &ref_stats, NEUTRAL, x, hue_sat, o.strength, it1 + it2 + it3, residual, notes)
}

/// What `grade.auto` may set.
#[derive(Clone, Copy, Debug)]
pub struct AutoParts {
    pub white: bool,
    pub black: bool,
    pub contrast: bool,
    pub balance: bool,
}

impl Default for AutoParts {
    /// Contrast (an even tone split) changes the look the most: it is on only when asked for.
    fn default() -> Self {
        AutoParts { white: true, black: true, contrast: false, balance: true }
    }
}

impl AutoParts {
    pub fn parse(names: &[String]) -> Result<AutoParts, String> {
        let mut p = AutoParts { white: false, black: false, contrast: false, balance: false };
        for n in names {
            match n.as_str() {
                "white" => p.white = true,
                "black" => p.black = true,
                "contrast" => p.contrast = true,
                "balance" => p.balance = true,
                o => return Err(format!("an auto part is white, black, contrast or balance; got `{o}`")),
            }
        }
        Ok(p)
    }
}

pub struct AutoOptions {
    pub parts: AutoParts,
    pub region: Region,
    /// The luma (in the picture's domain) the darkest 1 % of the pixels (luma p1) go to.
    pub black: f64,
    /// The luma the brightest 1 % (luma p99) go to (0.9: the view rolls highlights off toward 1, so 1.0 would blow the picture out).
    pub white: f64,
}

impl Default for AutoOptions {
    fn default() -> Self {
        AutoOptions { parts: AutoParts::default(), region: Region::Full, black: 0.02, white: 0.9 }
    }
}

/// An automatic balance of `shot`: the black point (luma p1 → `black`), white point (p99 → `white`), an even tone
/// split (contrast: the median halfway between them) and neutral casts in shadows, mids and highs. `before` / `after`
/// are `grade.compare` blocks against the picture the numbers aim at.
pub fn fit_auto(shot: &Frame, view: &dyn Fn(Rgb) -> Rgb, domain: Domain, o: &AutoOptions) -> Result<Fit, String> {
    if shot.domain != Domain::AcesCg {
        return Err("fit_auto takes the shot as scene-linear ACEScg".into());
    }
    if !(o.black < o.white) {
        return Err(format!("black ({}) is below white ({})", o.black, o.white));
    }
    let model = Model { shot: decimate(shot, TRIAL_PIXELS), view, domain, region: o.region.clone() };
    let stats = model.eval(&NEUTRAL)?;
    let mut t = Target::default();
    // The black and white points can only be hit together by lift and gain; the median by gamma.
    let levels = o.parts.black || o.parts.white;
    if o.parts.black {
        t.luma.push(("p1", o.black));
    }
    if o.parts.white {
        t.luma.push(("p99", o.white));
    }
    if o.parts.contrast {
        t.luma.push(("p50", o.black + 0.5 * (o.white - o.black)));
    }
    // Levels first, then the colour balance of the levelled picture (the zones move as the levels do).
    let lv = Active { lift: levels || o.parts.contrast, gamma: o.parts.contrast, gain: levels || o.parts.contrast, ..Default::default() };
    let levels_only = Target { luma: t.luma.clone(), ..Default::default() };
    let (x1, it1, _) = solve(&model, &levels_only, &lv, NEUTRAL, 20)?;
    let levelled = model.eval(&x1)?;
    if o.parts.balance {
        for z in 0..3 {
            if num(&levelled, &["balance", ZONES[z], "castRG"]).is_some() {
                t.casts[z] = Some([0.0, 0.0]);
            }
        }
    }
    let (x2, it2, _) = solve(&model, &t, &Active { balance: o.parts.balance, ..Default::default() }, x1, 20)?;
    // The wheels move the luma a little: levels and balance together for a few steps.
    let (x, it3, residual) = solve(&model, &t, &Active { balance: o.parts.balance, ..lv }, x2, 20)?;
    let iterations = it1 + it2 + it3;
    // The picture the numbers aim at, for the compare blocks: the shot's own statistics moved to the targets.
    let mut aim = stats.clone();
    if let Some(m) = aim.as_object_mut() {
        m.remove("meanLab");
    }
    for (k, v) in &t.luma {
        aim["luma"][*k] = json!(v);
    }
    for (z, c) in t.casts.iter().enumerate() {
        if let Some([rg, by]) = c {
            aim["balance"][ZONES[z]]["castRG"] = json!(rg);
            aim["balance"][ZONES[z]]["castBY"] = json!(by);
        }
    }
    finish(&model, &aim, NEUTRAL, x, None, 1.0, iterations, residual, vec![])
}
