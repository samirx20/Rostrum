//! Material foley (a port of sfxFoley.ts): a material's modes struck, scraped, slid, shattered, rolled,
//! tapped or bounced, with its noise texture; one sample at a time (render_sfx drives it).

use std::f64::consts::PI;

use super::TAU;
use crate::mix::schedule::Material;

/// One stereo sample of `preset` on material `m` at `t` seconds (`u`: 0 … 1 through the clip; `n`: noise, `lp`: it low-passed).
pub(super) fn material(m: &Material, preset: &str, t: f64, u: f64, n: f64, lp: f64, pitch: f64, dur: f64) -> (f64, f64) {
    let (sig_l, sig_r);
    let act = if preset.is_empty() { "impact" } else { preset };
    let mut env = (-t * m.decay).exp();
    let mut fmod = 1.0;
    let mut sub = 0.0;
    match act {
        "scrape" | "slide" => {
            let rub = if act == "scrape" { 0.6 + 0.4 * (TAU * 28.0 * t).sin() } else { 1.0 };
            env = (PI * u).sin() * rub;
            fmod = if act == "scrape" { 0.9 + 0.25 * u } else { 1.15 - 0.2 * u };
        }
        "shatter" => {
            let shard = (u * 9.0).floor();
            let local = (t - shard / 9.0 * dur).max(0.0);
            env = (-local * (m.decay * 1.8)).exp() * (1.0 - u * 0.4);
            fmod = 1.0 + ((shard as i64 * 7) % 5) as f64 * 0.22;
        }
        "roll" => {
            let rate = 8.0 + 14.0 * u;
            env = (TAU * rate * t).cos().abs() * (-t * (m.decay * 0.35)).exp();
            fmod = 0.85 + 0.3 * u;
        }
        "tap" | "click" | "snap" => {
            env = (-t * (m.decay * 2.2)).exp();
            fmod = if act == "snap" { 1.25 } else { 1.1 };
        }
        "bounce" => {
            fmod = 0.65 + 0.45 * (1.0 - (2.0 * u - 1.0).abs());
            env = (-t * (m.decay * 0.8)).exp();
        }
        _ => {
            let wf = if m.base_freq < 500.0 { 75.0 } else { 130.0 };
            sub = (TAU * wf * (-t * 18.0).exp() * t).sin() * (-t * 16.0).exp() * 0.42;
        }
    }
    let f0 = m.base_freq * pitch * fmod;
    let mut modal = 0.0;
    for (r, ratio) in m.ratios.iter().enumerate() {
        let decay = if act == "scrape" || act == "slide" { 1.0 } else { (-t * m.decay * r as f64 * 0.35).exp() };
        modal += (TAU * f0 * ratio * t).sin() * decay / m.ratios.len() as f64;
    }
    let tex = if act == "scrape" { n } else { lp } * env;
    let val = modal * env * (1.0 - m.noise_mix * 0.45) + tex * m.noise_mix + sub;
    sig_l = val;
    sig_r = val * 0.96 + modal * env * 0.08;
    (sig_l, sig_r)
}
