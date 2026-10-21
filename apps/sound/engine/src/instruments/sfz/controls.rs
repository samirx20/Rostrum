//! SFZ controllers and the region opcodes built on them (sfz.rs reads regions through this).
//! A score has no live controllers, so every MIDI CC sits at its instrument's default (`set_ccN` /
//! `set_hdccN` in `<control>`, else the MIDI reset values: CC 7 = 100, CC 10 = 64, CC 11 = 127, the
//! rest 0); the instrument plays as it sounds when loaded. From those values, once per file:
//! regions gated by `loccN` / `hiccN` (and the `hdcc` forms) play or not; a modulation
//! `<target>_onccN` (or the v1 `<target>ccN`), shaped by `<target>_curveccN` (the built-in curves 0–6
//! and `<curve>` headers), moves its target; `xfin_*cc` / `xfout_*cc` crossfades scale the region.
//! Per note: the extended controllers 131 (velocity) and 133 (key) as modulation sources, velocity
//! and key crossfades (`xfin_lovel` … `xfout_hikey`, power curve), a velocity curve (`amp_velcurve_N`),
//! `amp_random` (dB, seeded by the note), `width` (stereo width, %), `note_polyphony` (a later note
//! on the same key stops it, fading over `off_time`). A modulation of a target the engine does not
//! play (a filter, an LFO) is accepted only while its controller leaves it at zero; anything else is
//! an error naming it.

use std::collections::HashMap;

/// Additive targets a controller can move (amplitude multiplies; it is handled apart).
const TARGETS: &[&str] = &["volume", "pan", "tune", "offset", "amp_veltrack", "ampeg_delay", "ampeg_attack", "ampeg_hold", "ampeg_decay", "ampeg_sustain", "ampeg_release", "width"];

/// The default controller values (0 … 1) and the file's `<curve>`s.
pub struct Controls { cc: HashMap<u32, f64>, curves: HashMap<u32, Vec<(f64, f64)>> }

impl Controls {
    pub fn new(control: &HashMap<String, String>, curves: &[HashMap<String, String>]) -> Result<Controls, String> {
        let mut cc: HashMap<u32, f64> = [(7, 100.0 / 127.0), (10, 0.5), (11, 1.0)].into();
        for (k, v) in control {
            let (n, scale) = match (k.strip_prefix("set_hdcc"), k.strip_prefix("set_cc")) { (Some(n), _) => (n, 1.0), (_, Some(n)) => (n, 127.0), _ => continue };
            let x: f64 = v.parse().map_err(|_| format!("SFZ {k}={v} is not a number"))?;
            cc.insert(n.parse().map_err(|_| format!("SFZ {k} is not a controller"))?, x / scale);
        }
        let mut out = HashMap::new();
        for c in curves {
            let idx: u32 = c.get("curve_index").and_then(|v| v.parse().ok()).ok_or("SFZ <curve> without a curve_index")?;
            let mut pts: Vec<(f64, f64)> = c.iter().filter_map(|(k, v)| Some((k.strip_prefix('v')?.parse::<f64>().ok()? / 127.0, v.parse().ok()?))).collect();
            pts.sort_by(|a, b| a.0.total_cmp(&b.0));
            out.insert(idx, pts);
        }
        Ok(Controls { cc, curves: out })
    }

    /// A controller's value (0 … 1); `None` for the per-note ones (131 velocity, 133 key).
    fn value(&self, n: u32) -> Option<f64> { if n == 131 || n == 133 { None } else { Some(*self.cc.get(&n).unwrap_or(&0.0)) } }

    /// A curve applied to x (0 … 1): sfizz's built-ins 0–6 or the file's own.
    fn curve(&self, idx: u32, x: f64) -> Result<f64, String> {
        builtin(idx, x).map_or_else(|| self.curves.get(&idx).map(|p| interp(p, x)).ok_or(format!("SFZ curve {idx} is not defined")), Ok)
    }
}

/// sfizz's built-in curves 0–6 at x (0 … 1).
fn builtin(idx: u32, x: f64) -> Option<f64> {
    Some(match idx { 0 => x, 1 => 2.0 * x - 1.0, 2 => 1.0 - x, 3 => 1.0 - 2.0 * x, 4 => x * x, 5 => x.sqrt(), 6 => (1.0 - x).sqrt(), _ => return None })
}

/// Linear interpolation through points (x ascending), held flat past the ends.
fn interp(p: &[(f64, f64)], x: f64) -> f64 {
    let Some(first) = p.first() else { return x };
    if x <= first.0 { return first.1; }
    for w in p.windows(2) { if x <= w[1].0 { return w[0].1 + (w[1].1 - w[0].1) * (x - w[0].0) / (w[1].0 - w[0].0).max(1e-9); } }
    p.last().unwrap().1
}

/// A crossfade range: gain rises over [lo, hi] (fade in) or falls over it (fade out), power curve.
#[derive(Clone, Debug, PartialEq, Default)]
pub struct Fade { pub fade_in: Option<(f64, f64)>, pub fade_out: Option<(f64, f64)> }

impl Fade {
    fn gain(&self, x: f64) -> f64 {
        let i = self.fade_in.map_or(1.0, |(lo, hi)| if x >= hi { 1.0 } else if x <= lo { 0.0 } else { ((x - lo) / (hi - lo)).sqrt() });
        let o = self.fade_out.map_or(1.0, |(lo, hi)| if x <= lo { 1.0 } else if x >= hi { 0.0 } else { ((hi - x) / (hi - lo)).sqrt() });
        i * o
    }
}

/// What a region adds beyond the plain opcodes.
#[derive(Clone, Debug, PartialEq, Default)]
pub struct Ext {
    /// Linear gain from `amplitude` and the controller crossfades.
    pub gain: f64,
    pub vel_fade: Fade, pub key_fade: Fade,
    /// `amp_velcurve_N` points (velocity 0 … 1 → gain), empty: the default curve.
    pub velcurve: Vec<(f64, f64)>,
    pub amp_random: f64, pub width: f64,
    pub note_polyphony: Option<u32>, pub off_time: Option<f64>,
    /// Per-note modulations: (target, amount, source 131 velocity | 133 key, curve).
    pub per_note: Vec<(String, f64, u32, u32)>,
}

/// Reads the controller opcodes of a merged region: the additive deltas for the plain targets, its `Ext`,
/// or `None` when its controller gates keep it silent. Every opcode it reads is reported in `used`.
pub fn region(o: &HashMap<&str, &str>, c: &Controls, used: &mut Vec<String>) -> Result<Option<(HashMap<&'static str, f64>, Ext)>, String> {
    let num = |k: &str| -> Result<f64, String> { o.get(k).unwrap().parse().map_err(|_| format!("SFZ {k}={} is not a number", o[k])) };
    let mut add: HashMap<&'static str, f64> = HashMap::new();
    let mut e = Ext { gain: o.get("amplitude").map_or(Ok(100.0), |_| num("amplitude"))? / 100.0, width: 1.0, ..Default::default() };
    let (mut cc_fade_in, mut cc_fade_out): (HashMap<u32, (f64, f64)>, HashMap<u32, (f64, f64)>) = Default::default();
    for (&k, _) in o.iter() {
        let digits = k.len() - k.bytes().rev().take_while(|b| b.is_ascii_digit()).count();
        let (stem, n) = (&k[..digits], k[digits..].parse::<u32>().ok());
        let mut take = || used.push(k.to_string());
        match (stem, n) {
            ("locc" | "hicc" | "lohdcc" | "hihdcc", Some(n)) => {
                take();
                let v = c.value(n).ok_or(format!("SFZ {k}: a gate on controller {n} is not supported"))?;
                let x = if stem.contains("hd") { num(k)? } else { num(k)? / 127.0 };
                if (stem.starts_with("lo") && v < x - 1e-9) || (stem.starts_with("hi") && v > x + 1e-9) { return Ok(None); }
            }
            ("xfin_locc" | "xfin_hicc" | "xfout_locc" | "xfout_hicc", Some(n)) => {
                take();
                let m = if stem.starts_with("xfin") { &mut cc_fade_in } else { &mut cc_fade_out };
                let r = m.entry(n).or_insert((0.0, 0.0));
                if stem.ends_with("locc") { r.0 = num(k)? / 127.0 } else { r.1 = num(k)? / 127.0 }
            }
            ("amp_velcurve_", Some(n)) => { take(); e.velcurve.push((n as f64 / 127.0, num(k)?)); }
            _ => {}
        }
        if let Some(n) = n {
            // A modulation: <target>_onccN or <target>ccN (the curve is read with it).
            let target = stem.strip_suffix("_oncc").or_else(|| stem.strip_suffix("cc").filter(|t| !t.ends_with("_curve") && !t.is_empty() && *t != "lo" && *t != "hi" && !t.starts_with("xf") && !t.starts_with("on_") && !t.ends_with("hd")));
            if let Some(t) = target {
                used.push(k.to_string());
                let curve_key = format!("{t}_curvecc{n}");
                let curve = o.get(curve_key.as_str()).map_or(Ok(0.0), |v| v.parse::<f64>().map_err(|_| format!("SFZ {curve_key}={v}")))? as u32;
                if o.contains_key(curve_key.as_str()) { used.push(curve_key); }
                let amount = num(k)?;
                match c.value(n) {
                    None => { if t == "amplitude" || !TARGETS.contains(&t) { return Err(format!("SFZ {k}: velocity/key modulation of {t} is not supported")); }
                        if builtin(curve, 0.5).is_none() { return Err(format!("SFZ {k}: a velocity/key modulation takes a built-in curve (0–6)")); } e.per_note.push((t.to_string(), amount, n, curve)); }
                    Some(v) => {
                        let x = c.curve(curve, v)?;
                        if t == "amplitude" { e.gain *= amount / 100.0 * x; }
                        else if let Some(&t) = TARGETS.iter().find(|&&x| x == t) { *add.entry(t).or_insert(0.0) += amount * x; }
                        else if (amount * x).abs() > 1e-9 { return Err(format!("SFZ {k}: the engine does not play {t} (its controller {n} is not at zero)")); }
                    }
                }
            }
        }
    }
    for (n, (lo, hi)) in cc_fade_in { e.gain *= Fade { fade_in: Some((lo, hi)), fade_out: None }.gain(c.value(n).unwrap_or(0.0)); }
    for (n, (lo, hi)) in cc_fade_out { e.gain *= Fade { fade_in: None, fade_out: Some((lo, hi)) }.gain(c.value(n).unwrap_or(0.0)); }
    let pair = |a: &str, b: &str, da: f64, db: f64| -> Result<Option<(f64, f64)>, String> {
        if !o.contains_key(a) && !o.contains_key(b) { return Ok(None); }
        Ok(Some((o.get(a).map_or(Ok(da), |_| num(a))?, o.get(b).map_or(Ok(db), |_| num(b))?)))
    };
    e.vel_fade = Fade { fade_in: pair("xfin_lovel", "xfin_hivel", 0.0, 0.0)?, fade_out: pair("xfout_lovel", "xfout_hivel", 127.0, 127.0)? };
    e.key_fade = Fade { fade_in: pair("xfin_lokey", "xfin_hikey", 0.0, 0.0)?, fade_out: pair("xfout_lokey", "xfout_hikey", 127.0, 127.0)? };
    for k in ["amplitude", "xfin_lovel", "xfin_hivel", "xfout_lovel", "xfout_hivel", "xfin_lokey", "xfin_hikey", "xfout_lokey", "xfout_hikey", "amp_random", "width", "note_polyphony", "off_time", "off_mode", "xf_velcurve", "xf_keycurve", "xf_cccurve"] {
        if o.contains_key(k) { used.push(k.into()); }
    }
    if o.get("off_mode").is_some_and(|m| *m != "fast" && *m != "time" && *m != "normal") { return Err(format!("SFZ off_mode={} is not supported", o["off_mode"])); }
    if o.get("xf_velcurve").or(o.get("xf_keycurve")).or(o.get("xf_cccurve")).is_some_and(|m| *m != "power") { return Err("SFZ crossfade curves other than power are not supported".into()); }
    if o.contains_key("amp_random") { e.amp_random = num("amp_random")?; }
    if o.contains_key("width") { e.width = num("width")? / 100.0; }
    e.width += add.remove("width").unwrap_or(0.0) / 100.0;
    if o.contains_key("note_polyphony") { e.note_polyphony = Some(num("note_polyphony")? as u32); }
    if o.contains_key("off_time") { e.off_time = Some(num("off_time")?); }
    e.velcurve.sort_by(|a, b| a.0.total_cmp(&b.0));
    Ok(Some((add, e)))
}

impl Ext {
    /// The per-note modulations at this key (0 … 127) and velocity (0 … 1): (target, amount to add).
    pub fn per_note_deltas(&self, key: f64, velocity: f64) -> Vec<(&str, f64)> {
        self.per_note.iter().map(|(t, amount, src, curve)| (t.as_str(), amount * builtin(*curve, if *src == 131 { velocity } else { key / 127.0 }).unwrap_or(0.0))).collect()
    }

    /// The note's gain from this region's own shaping: velocity curve (else v²) under `veltrack`, the crossfades, amp_random.
    pub fn note_gain(&self, veltrack: f64, key: f64, velocity: f64, seed: f64) -> f64 {
        let v = velocity.clamp(0.0, 1.0);
        let curve = if self.velcurve.is_empty() { v * v } else { interp(&[[(0.0, 0.0)].as_slice(), &self.velcurve].concat(), v) };
        let vel127 = v * 127.0;
        self.gain * ((1.0 - veltrack) + veltrack * curve) * self.vel_fade.gain(vel127) * self.key_fade.gain(key) * 10f64.powf(self.amp_random * seed / 20.0)
    }
}

#[cfg(test)]
#[path = "controls_tests.rs"]
mod tests;
