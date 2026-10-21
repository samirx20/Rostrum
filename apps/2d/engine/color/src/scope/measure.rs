//! The numbers of §7.2: one small JSON (under 3 KB) from one pass over the frame.
use super::compare::lab_of;
use super::{Domain, Frame, Region};
use crate::Rgb;
use serde_json::{json, Map, Value};

/// The skin line on a Rec.709 vectorscope (degrees from +Cb toward +Cr).
pub const SKIN_LINE_DEG: f32 = 123.0;
/// Pixels with less than this vector radius (of full scale) are grey: left out of hue statistics.
const CHROMATIC: f32 = 0.04;
/// Skin pixels: within this many degrees of the skin line, a modest radius, not black or white.
const SKIN_SPAN_DEG: f32 = 20.0;
const SKIN_SAT: (f32, f32) = (0.05, 0.6);
const SKIN_LUMA: (f32, f32) = (0.1, 0.95);
const PARTS: [&str; 8] = ["luma", "clipped", "balance", "parade", "vector", "bands", "warnings", "histogram"];

#[derive(Debug)]
pub struct Options {
    pub region: Region,
    /// Blocks to return (None: everything but the histogram).
    pub parts: Option<Vec<String>>,
    /// 16 or 64 bins per channel (adds the `histogram` block).
    pub histogram: Option<usize>,
    /// Luma limits of the shadows / mids and mids / highs zones.
    pub zones: [f32; 2],
}

impl Default for Options {
    fn default() -> Self {
        Options { region: Region::Full, parts: None, histogram: None, zones: [0.25, 0.75] }
    }
}

impl Options {
    /// From the JSON the host sends: `region`, `parts`, `histogram`, `zones` (unknown keys are errors).
    pub fn parse(v: &Value) -> Result<Options, String> {
        let mut o = Options::default();
        let Some(m) = v.as_object() else { return Ok(o) };
        for (k, x) in m {
            match k.as_str() {
                "space" | "dir" | "name" | "images" | "hdr" | "sheet" | "title" | "input" | "inputSpace" => {}
                "region" => o.region = Region::parse(x)?,
                "parts" => {
                    let list: Vec<String> = x.as_array().ok_or("parts is a list of names")?.iter().filter_map(|s| s.as_str().map(String::from)).collect();
                    if let Some(bad) = list.iter().find(|p| !PARTS.contains(&p.as_str())) {
                        return Err(format!("unknown scope part `{bad}` (one of {})", PARTS.join(", ")));
                    }
                    o.parts = Some(list);
                }
                "histogram" => match x.as_u64() {
                    Some(n @ (16 | 64)) => o.histogram = Some(n as usize),
                    None if x.is_null() => {}
                    _ => return Err("histogram is 16 or 64 (bins per channel)".into()),
                },
                "zones" => {
                    let z: Vec<f64> = x.as_array().ok_or("zones is [shadowsEnd, midsEnd]")?.iter().filter_map(Value::as_f64).collect();
                    if z.len() != 2 || !(z[0] < z[1]) {
                        return Err("zones is [shadowsEnd, midsEnd] with the first below the second (luma values, default [0.25, 0.75])".into());
                    }
                    o.zones = [z[0] as f32, z[1] as f32];
                }
                other => return Err(format!("unknown scope option `{other}` (space, region, parts, histogram, zones)")),
            }
        }
        Ok(o)
    }
    fn wants(&self, part: &str) -> bool {
        match &self.parts {
            Some(p) => p.iter().any(|x| x == part),
            None => part != "histogram" || self.histogram.is_some(),
        }
    }
}

fn r(v: f64, places: i32) -> f64 {
    let k = 10f64.powi(places);
    let x = (v * k).round() / k;
    if x == 0.0 { 0.0 } else { x }
}
fn pct(n: usize, of: usize) -> f64 {
    if of == 0 { 0.0 } else { r(100.0 * n as f64 / of as f64, 2) }
}

/// The percentile `p` (0..100) of a sorted slice, linear between ranks.
pub fn percentile(sorted: &[f32], p: f64) -> f32 {
    match sorted.len() {
        0 => 0.0,
        n => {
            let k = (p / 100.0) * (n - 1) as f64;
            let (i, f) = (k.floor() as usize, k.fract() as f32);
            if i + 1 < n { sorted[i] + (sorted[i + 1] - sorted[i]) * f } else { sorted[n - 1] }
        }
    }
}

fn sorted(mut v: Vec<f32>) -> Vec<f32> {
    v.sort_unstable_by(f32::total_cmp);
    v
}

/// A vector-scope position (u = Cb, v = Cr, each ±1 at full scale) of an sRGB-coded Rec.709 colour.
pub fn vector_of(d: Rgb) -> (f32, f32) {
    let y = 0.2126 * d[0] + 0.7152 * d[1] + 0.0722 * d[2];
    (2.0 * (d[2] - y) / 1.8556, 2.0 * (d[0] - y) / 1.5748)
}
pub fn hue_deg(u: f32, v: f32) -> f32 {
    v.atan2(u).to_degrees().rem_euclid(360.0)
}
fn wrap180(a: f32) -> f32 {
    (a + 180.0).rem_euclid(360.0) - 180.0
}

/// The cast of an average colour in words (as `frameScopes` says it): how far red and blue sit from each other, and green from magenta.
fn cast_word([r_, g, b]: Rgb) -> String {
    let (warm, green) = (r_ - b, g - (r_ + b) / 2.0);
    let parts = [
        (warm.abs() > 0.03).then(|| format!("{} {:.2}", if warm > 0.0 { "warm" } else { "cool" }, warm.abs())),
        (green.abs() > 0.03).then(|| format!("{} {:.2}", if green > 0.0 { "green" } else { "magenta" }, green.abs())),
    ];
    let parts: Vec<String> = parts.into_iter().flatten().collect();
    if parts.is_empty() { "neutral".into() } else { parts.join(", ") }
}

/// Measures `frame` over `o.region`.
pub fn measure(frame: &Frame, o: &Options) -> Result<Value, String> {
    let d = frame.domain;
    let (x0, y0, x1, y1) = o.region.bounds(frame.width, frame.height);
    let lin_fn = d.to_lin709_fn();
    let d709 = d.d709_fn();
    let white = d.white();
    let eps = 0.5 / 255.0 * white;
    // About 1 M samples of the arrays that are sorted; every pixel goes into the counts.
    let area = (x1 - x0) * (y1 - y0);
    let keep = ((1_000_000.0 / area.max(1) as f64).min(1.0) * 65536.0) as u32;
    let mut luma = vec![];
    let mut chan: [Vec<f32>; 3] = Default::default();
    let mut sat = vec![];
    let mut bands: Vec<Vec<f32>> = vec![vec![]; 8];
    let (mut n, mut luma_sum, mut luma_sq) = (0usize, 0f64, 0f64);
    let mut zone_n = [0usize; 3];
    let mut zone_sum = [[0f64; 3]; 3];
    let (mut black, mut white_n, mut over, mut out709, mut out_p3, mut out2020) = (0usize, 0usize, 0usize, 0usize, 0usize, 0usize);
    let mut lin_sum = [0f64; 3];
    let (mut u_sum, mut v_sum, mut sat_sum) = (0f64, 0f64, 0f64);
    let mut hue_bins = [0usize; 12];
    let (mut chromatic, mut hx, mut hy) = (0usize, 0f64, 0f64);
    let (mut skin_n, mut skin_sat, mut skin_hx, mut skin_hy) = (0usize, 0f64, 0f64, 0f64);
    let mut hist: Vec<[usize; 4]> = vec![[0; 4]; o.histogram.unwrap_or(0)];
    let to_p3 = super::m3("lin_rec709", "lin_p3d65");
    let to_2020 = super::m3("lin_rec709", "lin_rec2020");
    let mut seed = 0u32;
    for y in y0..y1 {
        for x in x0..x1 {
            if !o.region.contains(x, y) {
                continue;
            }
            let c = frame.px[y * frame.width + x];
            n += 1;
            let l = d.luma(c);
            luma_sum += l as f64;
            luma_sq += (l as f64) * (l as f64);
            let z = if l < o.zones[0] { 0 } else if l < o.zones[1] { 1 } else { 2 };
            zone_n[z] += 1;
            for k in 0..3 {
                zone_sum[z][k] += c[k] as f64;
            }
            let mx = c[0].max(c[1]).max(c[2]);
            if mx <= eps { black += 1 }
            if mx >= white - eps { white_n += 1 }
            if mx > white + eps { over += 1 }
            let lin = lin_fn(c);
            for k in 0..3 {
                lin_sum[k] += lin[k] as f64;
            }
            let gam = |m: &crate::matrix::Mat3| crate::matrix::apply(m, lin.map(f64::from)).iter().any(|&v| v < -0.0005);
            if lin.iter().any(|&v| v < -0.0005) { out709 += 1 }
            if gam(&to_p3) { out_p3 += 1 }
            if gam(&to_2020) { out2020 += 1 }
            let dc = d709(c);
            let (u, v) = vector_of(dc);
            let s = (u * u + v * v).sqrt();
            u_sum += u as f64;
            v_sum += v as f64;
            sat_sum += s as f64;
            let hue = hue_deg(u, v);
            if s > CHROMATIC {
                chromatic += 1;
                hue_bins[((hue / 30.0) as usize).min(11)] += 1;
                hx += (s * hue.to_radians().cos()) as f64;
                hy += (s * hue.to_radians().sin()) as f64;
                let dy = 0.2126 * dc[0] + 0.7152 * dc[1] + 0.0722 * dc[2];
                if wrap180(hue - SKIN_LINE_DEG).abs() <= SKIN_SPAN_DEG && s >= SKIN_SAT.0 && s <= SKIN_SAT.1 && dy >= SKIN_LUMA.0 && dy <= SKIN_LUMA.1 {
                    skin_n += 1;
                    skin_sat += s as f64;
                    skin_hx += hue.to_radians().cos() as f64;
                    skin_hy += hue.to_radians().sin() as f64;
                }
            }
            if !hist.is_empty() {
                let nb = hist.len();
                let bin = |v: f32| (((v / white).clamp(0.0, 0.999_999)) * nb as f32) as usize;
                for k in 0..3 {
                    hist[bin(c[k])][k] += 1;
                }
                hist[bin(l)][3] += 1;
            }
            seed = seed.wrapping_add(1);
            if (seed.wrapping_mul(2_654_435_761) >> 8) & 0xFFFF < keep {
                luma.push(l);
                for k in 0..3 {
                    chan[k].push(c[k]);
                }
                sat.push(s / 1.0);
                bands[(x * 8 / frame.width).min(7)].push(l);
            }
        }
    }
    if n == 0 {
        return Err("the region holds no pixels".into());
    }
    let nf = n as f64;
    let luma = sorted(luma);
    let mean = luma_sum / nf;
    let std = (luma_sq / nf - mean * mean).max(0.0).sqrt();
    let pc = |s: &[f32], p: f64| percentile(s, p) as f64;
    let mut out = Map::new();
    out.insert("space".into(), json!(d.id()));
    out.insert("size".into(), json!([frame.width, frame.height]));
    if let Some(rg) = o.region.as_json() {
        out.insert("region".into(), rg);
    }
    out.insert("pixels".into(), json!(n));
    let lab = lab_of([lin_sum[0] / nf, lin_sum[1] / nf, lin_sum[2] / nf]);
    out.insert("meanLab".into(), json!([r(lab[0], 2), r(lab[1], 2), r(lab[2], 2)]));
    // Brightness beside the values: IRE on SDR display, nits on HDR display.
    let beside = |v: f64| -> Option<(&'static str, f64)> {
        match d {
            Domain::Display { hdr: false } => Some(("ire", r(v * 100.0, 1))),
            Domain::Display { hdr: true } => Some(("nits", r(crate::Curve::Pq100.decode(v as f32) as f64 * 100.0, 0))),
            _ => None,
        }
    };
    let dp = if matches!(d, Domain::Display { .. }) { 4 } else { 5 };
    if o.wants("luma") {
        let mut l = Map::new();
        for (key, p) in [("p0.1", 0.1), ("p1", 1.0), ("p5", 5.0), ("p25", 25.0), ("p50", 50.0), ("p75", 75.0), ("p95", 95.0), ("p99", 99.0), ("p99.9", 99.9)] {
            l.insert(key.into(), json!(r(pc(&luma, p), dp)));
        }
        l.insert("mean".into(), json!(r(mean, dp)));
        l.insert("std".into(), json!(r(std, dp)));
        if let Some((unit, _)) = beside(0.0) {
            let b = |p: f64| beside(pc(&luma, p)).unwrap().1;
            l.insert(unit.into(), json!({ "p5": b(5.0), "p50": b(50.0), "p95": b(95.0) }));
        }
        l.insert("zones".into(), json!({ "shadows": pct(zone_n[0], n), "mids": pct(zone_n[1], n), "highs": pct(zone_n[2], n), "limits": o.zones }));
        out.insert("luma".into(), Value::Object(l));
    }
    if o.wants("clipped") {
        out.insert("clipped".into(), json!({ "black": pct(black, n), "white": pct(white_n, n), "overRange": pct(over, n), "gamutOut": pct(out709, n), "gamutOutP3": pct(out_p3, n), "gamutOut2020": pct(out2020, n) }));
    }
    let names = ["shadows", "mids", "highs"];
    let mut balance = Map::new();
    let mut warnings: Vec<String> = vec![];
    for z in 0..3 {
        if zone_n[z] == 0 {
            continue;
        }
        let m = zone_sum[z].map(|s| (s / zone_n[z] as f64) as f32);
        let (rg, by) = (m[0] - m[1], m[2] - (m[0] + m[1]) / 2.0);
        balance.insert(names[z].into(), json!({ "r": r(m[0] as f64, dp), "g": r(m[1] as f64, dp), "b": r(m[2] as f64, dp), "castRG": r(rg as f64, 4), "castBY": r(by as f64, 4), "cast": cast_word(m) }));
        let scale = white.max(1e-6);
        for (v, plus, minus) in [(rg / scale, "red", "green"), (by / scale, "blue", "yellow")] {
            if v.abs() >= 0.03 && zone_n[z] * 20 >= n {
                warnings.push(format!("{} lean {:+.2} {}", names[z], v.abs(), if v > 0.0 { plus } else { minus }));
            }
        }
    }
    if o.wants("balance") {
        out.insert("balance".into(), Value::Object(balance));
    }
    if o.wants("parade") {
        let p = ["r", "g", "b"];
        let mut m = Map::new();
        for k in 0..3 {
            let s = sorted(std::mem::take(&mut chan[k]));
            let (p1, p99) = (pc(&s, 1.0), pc(&s, 99.0));
            m.insert(p[k].into(), json!({ "p1": r(p1, dp), "p50": r(pc(&s, 50.0), dp), "p99": r(p99, dp), "spread": r(p99 - p1, dp) }));
        }
        out.insert("parade".into(), Value::Object(m));
    }
    let sat_s = sorted(sat);
    let hue_mean = if chromatic > 0 { hy.atan2(hx).to_degrees().rem_euclid(360.0) } else { 0.0 };
    let skin_pct = pct(skin_n, n);
    if o.wants("vector") {
        let mut v = Map::new();
        v.insert("hueMean".into(), json!(r(hue_mean, 1)));
        v.insert("satMean".into(), json!(r(sat_sum / nf, 4)));
        v.insert("satP95".into(), json!(r(pc(&sat_s, 95.0), 4)));
        v.insert("centroid".into(), json!([r(u_sum / nf, 4), r(v_sum / nf, 4)]));
        v.insert("hueHist".into(), json!(hue_bins.iter().map(|&b| pct(b, chromatic.max(1))).collect::<Vec<_>>()));
        if skin_pct > 1.0 {
            let mean_hue = (skin_hy.atan2(skin_hx) as f32).to_degrees().rem_euclid(360.0);
            let s = (skin_sat / skin_n as f64) as f32;
            let dev = wrap180(mean_hue - SKIN_LINE_DEG);
            v.insert("skin".into(), json!({ "pixels": skin_pct, "hue": r(mean_hue as f64, 1), "sat": r(s as f64, 4), "devDeg": r(dev as f64, 1), "devSat": r((s * dev.to_radians().sin()) as f64, 4) }));
            if dev.abs() >= 10.0 {
                warnings.push(format!("skin sits {:.0} degrees {} of the skin line", dev.abs(), if dev > 0.0 { "toward yellow-green" } else { "toward red-magenta" }));
            }
        }
        out.insert("vector".into(), Value::Object(v));
    }
    if o.wants("bands") {
        let b: Vec<Value> = bands.into_iter().map(|b| {
            let s = sorted(b);
            json!([r(pc(&s, 5.0), 3), r(pc(&s, 50.0), 3), r(pc(&s, 95.0), 3)])
        }).collect();
        out.insert("bands".into(), json!(b));
    }
    if let Some(nb) = o.histogram.filter(|_| o.wants("histogram")) {
        let per = |k: usize| hist.iter().map(|h| (1000.0 * h[k] as f64 / nf).round() as u32).collect::<Vec<_>>();
        out.insert("histogram".into(), json!({ "bins": nb, "perMille": { "luma": per(3), "r": per(0), "g": per(1), "b": per(2) } }));
    }
    if o.wants("warnings") {
        for (v, what) in [(white_n, "clipped white"), (black, "crushed to black")] {
            if pct(v, n) >= 1.0 {
                warnings.insert(0, format!("{} % of the frame is {what}", pct(v, n)));
            }
        }
        if pct(over, n) >= 0.5 {
            warnings.insert(0, format!("{} % of the frame is above range (over 1.0)", pct(over, n)));
        }
        if pct(out709, n) >= 1.0 {
            warnings.push(format!("{} % of the frame is outside Rec.709", pct(out709, n)));
        }
        out.insert("warnings".into(), json!(warnings));
    }
    Ok(Value::Object(out))
}
