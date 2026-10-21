//! The synthesized effect presets (a port of sfxFoley.ts): risers, sweeps, booms, whooshes, chimes,
//! pops, beds and clicks; one sample at a time (render_sfx drives it). The social-video set is kit.rs.

use std::f64::consts::PI;

use super::{js_round, TAU};

/// One stereo sample of `preset` at `t` seconds (`u`: 0 … 1 through the clip; `n`: noise, `lp`: it
/// low-passed; `ph`: the two oscillator phases, carried from sample to sample).
pub(super) fn synth(preset: &str, ph: &mut (f64, f64), t: f64, u: f64, n: f64, lp: f64, pitch: f64, dur: f64, sr: f64) -> (f64, f64) {
    let (mut ph1, mut ph2) = *ph;
    let (sig_l, sig_r);
    match preset {
        "riser" | "uplifter" => {
            let up = preset == "uplifter";
            let swell = u.powf(if up { 1.6 } else { 2.2 }) * (PI * (u * 1.04).min(1.0)).sin();
            let f = ((if up { 220.0 } else { 130.0 }) + (if up { 1650.0 } else { 980.0 }) * u.powf(if up { 1.8 } else { 2.4 })) * pitch;
            ph1 += TAU * f / sr;
            ph2 += TAU * f * (if up { 1.99 } else { 1.498 }) / sr;
            sig_l = (ph1.sin() * 0.5 + ph2.sin() * 0.25 + lp * 0.45) * swell;
            sig_r = ((ph1 + 0.5).sin() * 0.5 + ph2.sin() * 0.25 + n * 0.35 * u) * swell;
        }
        "swell" => {
            let env = (PI * u).sin() * u.powf(0.7);
            let f = 220.0 * pitch;
            sig_l = ((TAU * f * t).sin() * 0.45 + (TAU * f * 1.5 * t).sin() * 0.3 + (TAU * f * 1.25 * t).sin() * 0.25) * env;
            sig_r = ((TAU * f * 1.003 * t).sin() * 0.45 + (TAU * f * 1.497 * t).sin() * 0.3 + (TAU * f * 2.0 * t).sin() * 0.25) * env;
        }
        "sweep" | "transition" => {
            let tr = preset == "transition";
            let bell = (PI * u).sin();
            let f = ((if tr { 180.0 } else { 120.0 }) + (if tr { 1200.0 } else { 840.0 }) * (PI * u.powf(0.85)).sin()) * pitch;
            ph1 += TAU * f / sr;
            let val = (ph1.sin() * 0.45 + lp * 0.55) * bell;
            sig_l = if tr { val * (1.0 - u * 0.6) } else { val };
            sig_r = if tr { val * (0.4 + u * 0.6) } else { val };
        }
        "reverseCymbal" => {
            let env = u.powf(3.2) * if u > 0.96 { (1.0 - u) / 0.04 } else { 1.0 };
            let metal = (TAU * 3850.0 * t).sin() * 0.25 + (TAU * 6120.0 * t).sin() * 0.25 + (TAU * 8430.0 * t).sin() * 0.2 + n * 0.55;
            sig_l = metal * env * 0.85;
            sig_r = (metal * 0.85 - n * 0.2) * env * 0.85;
        }
        "subDrop" | "drop" | "downlifter" => {
            let down = preset == "downlifter";
            let start_f = if down { 420.0 } else if preset == "drop" { 180.0 } else { 115.0 };
            let rate = if down { 2.4 } else { 4.8 };
            ph1 += TAU * (32.0 + start_f * (-t * rate).exp()) * pitch / sr;
            let sub = (ph1.sin() * 1.6).tanh() * (-t * if down { 1.8 } else { 2.6 }).exp();
            let air = if down { lp * (-t * 2.2).exp() * 0.35 } else { 0.0 };
            sig_l = sub * 0.85 + air;
            sig_r = sub * 0.85 + air;
        }
        "boom" | "impact" | "hit" | "hitHard" | "thud" => {
            let (thud, hard, hit) = (preset == "thud", preset == "hitHard", preset == "hit");
            let base = if thud { 48.0 } else if hit { 65.0 } else { 36.0 };
            let drop = if thud { 70.0 } else if hard { 160.0 } else { 95.0 };
            let decay = if thud { 9.5 } else if hit { 6.5 } else if hard { 4.2 } else { 2.8 };
            ph1 += TAU * (base + drop * (-t * 14.0).exp()) * pitch / sr;
            let sub = (ph1.sin() * if hard { 2.2 } else { 1.6 }).tanh() * (-t * decay).exp();
            let punch = (TAU * (if hard { 310.0 } else { 190.0 }) * pitch * t).sin() * (-t * 32.0).exp() * if hard { 0.65 } else { 0.4 };
            let rumble = lp * (-t * (decay * 1.4)).exp() * if preset == "impact" || hard { 0.5 } else { 0.2 };
            sig_l = sub * 0.8 + punch + rumble;
            sig_r = sub * 0.8 + punch + rumble * 0.9;
        }
        "rumble" => {
            let env = (PI * u).sin();
            ph1 += TAU * 44.0 * pitch / sr;
            ph2 += TAU * 61.0 * pitch / sr;
            sig_l = (ph1.sin() * 0.55 + ph2.sin() * 0.3 + lp * 0.4) * env;
            sig_r = ((ph1 + 0.4).sin() * 0.55 + ph2.sin() * 0.3 + lp * 0.4) * env;
        }
        "braam" | "sting" => {
            let sting = preset == "sting";
            let f = (if sting { 293.66 } else { 65.41 }) * pitch;
            let env = (1.0 - (-t * if sting { 80.0 } else { 35.0 }).exp()) * (-t * if sting { 3.2 } else { 1.8 }).exp();
            let saw = (TAU * f * t).sin() + (TAU * f * (if sting { 1.189 } else { 2.0 }) * t).sin() * 0.65 + (TAU * f * 3.0 * t).sin() * 0.45 + (TAU * f * 4.0 * t).sin() * 0.25;
            sig_l = (saw * 1.5).tanh() * env * 0.7;
            sig_r = ((saw + (TAU * f * 1.005 * t).sin() * 0.5) * 1.5).tanh() * env * 0.7;
        }
        "whoosh" | "swoosh" => {
            let sw = preset == "swoosh";
            let bell = (PI * u).sin();
            let f = ((if sw { 340.0 } else { 150.0 }) + (if sw { 880.0 } else { 480.0 }) * bell) * pitch;
            ph1 += TAU * f / sr;
            let air = ((if sw { n * 0.45 + lp * 0.4 } else { lp * 0.75 }) + ph1.sin() * 0.35) * bell.powf(if sw { 1.8 } else { 1.2 });
            sig_l = air;
            sig_r = air;
        }
        "shimmer" | "portal" | "warp" => {
            let base = if preset == "shimmer" { 659.25 } else if preset == "portal" { 440.0 } else { 329.63 };
            let sweep = if preset == "portal" { 180.0 * (PI * u).sin() } else if preset == "warp" { -140.0 * u } else { 40.0 * (TAU * 3.0 * u).sin() };
            let f = (base + sweep) * pitch;
            ph1 += TAU * f / sr;
            ph2 += TAU * f * 1.5 / sr;
            let env = (PI * u).sin();
            sig_l = (ph1.sin() * 0.5 + ph2.sin() * 0.35) * env;
            sig_r = ((ph1 * 1.003 + 0.4).sin() * 0.5 + ph2.sin() * 0.35) * env;
        }
        "tapeStop" => {
            ph1 += TAU * (520.0 * (1.0 - u * 0.92).powf(2.6) + 28.0) * pitch / sr;
            let env = if u > 0.88 { (1.0 - u) / 0.12 } else { 1.0 };
            sig_l = (ph1.sin() * 1.4).tanh() * env * 0.8;
            sig_r = sig_l;
        }
        "glitch" => {
            let step = (u * 12.0).floor();
            ph1 += TAU * (240.0 + ((step as i64 * 173) % 920) as f64) * pitch / sr;
            let gate = if (u * 12.0) % 1.0 < 0.75 { 1.0 } else { 0.0 };
            sig_l = js_round(ph1.sin() * 4.0) / 4.0 * gate * 0.75;
            sig_r = if step as i64 % 2 == 0 { sig_l } else { -sig_l };
        }
        "zap" | "laser" => {
            let zap = preset == "zap";
            let f = ((if zap { 2200.0 } else { 1400.0 }) * (-u * if zap { 7.5 } else { 4.5 }).exp() + if zap { 90.0 } else { 130.0 }) * pitch;
            let fm = if zap { (TAU * 95.0 * t).sin() * 0.35 } else { 0.0 };
            ph1 += TAU * f * (1.0 + fm) / sr;
            sig_l = (ph1.sin() * 1.45).tanh() * (-u * if zap { 6.5 } else { 4.5 }).exp();
            sig_r = sig_l;
        }
        "chime" | "ding" | "success" | "notification" => {
            let base = if preset == "ding" { 1318.5 } else if preset == "notification" { 587.33 } else { 880.0 };
            let f = base * pitch;
            let env = (1.0 - (-t * 180.0).exp()) * (-t * 4.8).exp();
            let note = match preset {
                "success" => if u < 0.25 { 1.0 } else if u < 0.5 { 1.25 } else { 1.5 },
                "notification" => if u < 0.35 { 1.0 } else { 1.498 },
                _ => 1.0,
            };
            let bell = (TAU * f * note * t).sin() * 0.65 + (TAU * f * note * (if preset == "chime" { 2.756 } else { 2.0 }) * t).sin() * 0.25 * (-t * 8.0).exp();
            sig_l = bell * env;
            sig_r = bell * env;
        }
        "pop" | "bounce" => {
            let pop = preset == "pop";
            let f = if pop { (180.0 + 540.0 * u.powf(1.8)) * pitch } else { (160.0 + 380.0 * (PI * u * 2.5).cos().abs() * (-u * 2.2).exp()) * pitch };
            ph1 += TAU * f / sr;
            sig_l = ph1.sin() * (-u * if pop { 9.5 } else { 4.5 }).exp();
            sig_r = sig_l;
        }
        "rain" | "wind" | "vinyl" | "drone" => {
            let fade = (t / 0.15).min(1.0) * ((dur - t) / 0.15).min(1.0);
            match preset {
                "drone" => {
                    let f = 55.0 * pitch;
                    sig_l = ((TAU * f * t).sin() * 0.6 + (TAU * f * 1.5 * t).sin() * 0.3 + lp * 0.1) * fade * 0.65;
                    sig_r = ((TAU * f * 1.003 * t).sin() * 0.6 + (TAU * f * 1.497 * t).sin() * 0.3 + lp * 0.1) * fade * 0.65;
                }
                "vinyl" => {
                    let crackle = if n.abs() > 0.96 { n * 0.85 } else { lp * 0.12 };
                    sig_l = crackle * fade;
                    sig_r = crackle * fade;
                }
                "rain" => {
                    let drop = if n.abs() > 0.92 { (TAU * 1800.0 * t).sin() * 0.35 } else { 0.0 };
                    sig_l = (lp * 0.45 + n * 0.15 + drop) * fade * 0.65;
                    sig_r = (lp * 0.45 + n * 0.18 - drop * 0.5) * fade * 0.65;
                }
                _ => {
                    let m = 0.5 + 0.5 * (TAU * 0.65 * t).sin();
                    sig_l = lp * m * fade * 0.65;
                    sig_r = lp * (1.0 - m * 0.4) * fade * 0.65;
                }
            }
        }
        "shutter" => {
            let c1 = (-t * 110.0).exp();
            let c2 = if t > 0.045 { (-(t - 0.045) * 95.0).exp() * 0.85 } else { 0.0 };
            let val = ((TAU * 1420.0 * t).sin() * 0.5 + n * 0.5) * (c1 + c2);
            sig_l = val;
            sig_r = val;
        }
        "footstep" => {
            let heel = (TAU * 115.0 * (-t * 22.0).exp() * t).sin() * (-t * 26.0).exp() * 0.7;
            let scuff = if t > 0.03 { lp * (-(t - 0.03) * 18.0).exp() * 0.45 } else { 0.0 };
            sig_l = heel + scuff;
            sig_r = heel + scuff;
        }
        _ => {
            let f = (match preset { "tick" => 2450.0, "snap" => 1720.0, "tap" => 640.0, "key" => 820.0, _ => 1120.0 }) * pitch;
            let decay = match preset { "tick" => 85.0, "snap" => 55.0, "tap" => 36.0, _ => 48.0 };
            let body = (TAU * f * t).sin() * 0.65 + (TAU * f * 0.48 * t).sin() * 0.35;
            let val = (body * 0.7 + lp * if preset == "snap" { 0.55 } else { 0.25 }) * (-t * decay).exp();
            sig_l = val;
            sig_r = val;
        }
    }
    *ph = (ph1, ph2);
    (sig_l, sig_r)
}
