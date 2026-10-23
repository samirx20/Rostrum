//! The social-video sound effects (risers, impacts, pops, clicks, dings; no whooshes: PURPOSE.md): built the way
//! sound designers layer them — swept band-passed noise in stereo, a tonal riser with an
//! accelerating gate, an impact as sub boom + crack + body + tail, FM bells, short bright clicks.
//! Deterministic (seeded noise per channel). Other presets are presets.rs.

use std::f64::consts::PI;

use super::{Rng, Svf};

const TAU: f64 = 2.0 * PI;

pub const PRESETS: &[&str] = &["riser", "uplifter", "impact", "boom", "hit", "hitHard", "pop", "click", "tap", "tick", "key", "toggle", "ding", "chime", "notification", "success", "error"];

fn saw(p: f64) -> f64 {
    2.0 * (p - p.floor()) - 1.0
}

/// Renders `preset` (one of PRESETS) into the buffers from sample 0; returns (left, right) per sample through `out`.
pub fn render(preset: &str, dur: f64, pitch: f64, sr: f64, mut out: impl FnMut(usize, f64, f64, f64)) {
    let len = (dur * sr).floor() as usize;
    let (mut nl, mut nr) = (Rng(0x1234_5678_9abc_def1), Rng(0x0fed_cba9_8765_4321));
    let mut f = [Svf::default(); 6];
    let mut ph = [0.0f64; 4];
    for i in 0..len {
        let t = i as f64 / sr;
        let u = (t / dur).min(1.0);
        let (a, b) = (nl.n(), nr.n());
        let tail = ((dur - t) / 0.006).clamp(0.0, 1.0);
        let (l, r) = match preset {
            "riser" | "uplifter" => {
                let up = preset == "uplifter";
                let env = u.powf(1.8) * tail;
                // Noise opens upward; under it (riser) detuned saws climb two octaves through an opening low-pass.
                let hz = 300.0 * pitch * 2f64.powf(u * 4.6);
                let (_, bl, _) = f[0].run(a, hz, 0.7, sr);
                let (_, br, _) = f[1].run(b, hz * 1.04, 0.7, sr);
                let gate_rate = 4.0 + 20.0 * u * u;
                ph[3] += gate_rate / sr;
                let gate = if up { 1.0 } else { 0.75 + 0.25 * (TAU * ph[3]).cos() };
                let mut tone = (0.0, 0.0);
                if !up {
                    let fr = 110.0 * pitch * 2f64.powf(u * 2.0);
                    for (k, d) in [-0.12f64, 0.0, 0.12].iter().enumerate() {
                        ph[k] += fr * 2f64.powf(d / 12.0) / sr;
                    }
                    let mix = (saw(ph[0]) + saw(ph[1]) + saw(ph[2])) / 3.0;
                    let (lo, _, _) = f[2].run(mix, 400.0 * 2f64.powf(u * 4.5), 0.8, sr);
                    let (lo2, _, _) = f[3].run((saw(ph[1] + 0.33) + saw(ph[2] + 0.61)) / 2.0, 400.0 * 2f64.powf(u * 4.5), 0.8, sr);
                    tone = (lo * 0.5, lo2 * 0.5);
                }
                let w = 0.3 + 0.7 * u;
                ((bl * 0.9 + tone.0) * env * gate * (1.0 + w * 0.2), (br * 0.9 + tone.1) * env * gate * (1.0 + w * 0.2))
            }
            "impact" | "boom" | "hit" | "hitHard" => {
                let (boom, hard, hit) = (preset == "boom", preset == "hitHard", preset == "hit");
                let sub_decay = if boom { 0.9 } else if hit { 0.22 } else { 0.5 };
                let f0 = (if hit { 60.0 } else { 46.0 }) + (if hard { 150.0 } else { 110.0 }) * (-t / 0.035).exp();
                ph[0] += f0 * pitch / sr;
                let sub = ((TAU * ph[0]).sin() * 1.8).tanh() * (-t / sub_decay).exp() * (t / 0.001).min(1.0);
                let (_, _, cl) = f[0].run(a, 1500.0, 1.0, sr);
                let (_, _, cr) = f[1].run(b, 1500.0, 1.0, sr);
                let crack = (-t / if hard { 0.02 } else { 0.012 }).exp() * if hard { 1.1 } else { 0.7 };
                let (_, body_l, _) = f[2].run(a, 380.0 * pitch, 1.1, sr);
                let (_, body_r, _) = f[3].run(b, 420.0 * pitch, 1.1, sr);
                let body = (-t / 0.09).exp() * 0.9;
                let (tl, _, _) = f[4].run(a, 2200.0 * (-t / 0.6).exp() + 300.0, 1.2, sr);
                let (tr, _, _) = f[5].run(b, 2200.0 * (-t / 0.6).exp() + 300.0, 1.2, sr);
                let tail_lvl = if hit { 0.0 } else { (-t / if boom { 0.9 } else { 0.55 }).exp() * 0.45 * (t / 0.01).min(1.0) };
                let l = sub * 0.95 + cl * crack + body_l * body + tl * tail_lvl;
                let r = sub * 0.95 + cr * crack + body_r * body + tr * tail_lvl;
                ((l * 1.2).tanh() * tail, (r * 1.2).tanh() * tail)
            }
            "pop" => {
                // A mouth / bubble pop: a sine bending up an octave and a half in 30 ms, a tiny click.
                let fr = 320.0 * pitch * 2f64.powf(1.6 * (1.0 - (-t / 0.012).exp()));
                ph[0] += fr / sr;
                let env = (t / 0.0008).min(1.0) * (-t / 0.035).exp();
                let (_, _, h) = f[0].run(a, 3000.0, 1.0, sr);
                let s = (TAU * ph[0]).sin() * env + h * (-t / 0.0015).exp() * 0.25;
                (s * tail, s * tail)
            }
            "click" | "tap" | "tick" | "key" => {
                // A crisp UI click: a bright band of noise for a few ms and a short tick; a tap has a body.
                let (centre, dec, body) = match preset { "tick" => (5200.0, 0.0018, 0.0), "tap" => (2600.0, 0.004, 0.6), "key" => (3400.0, 0.003, 0.35), _ => (4200.0, 0.0025, 0.25) };
                let (_, bl, _) = f[0].run(a, centre * pitch, 0.6, sr);
                let (_, br, _) = f[1].run(b, centre * pitch, 0.6, sr);
                let tick = (TAU * centre * 0.6 * pitch * t).sin() * (-t / (dec * 1.2)).exp() * 0.5;
                let low = (TAU * 420.0 * pitch * t).sin() * (-t / 0.012).exp() * body;
                let e = (-t / dec).exp() * 1.4;
                ((bl * e + tick + low) * tail, (br * e + tick + low) * tail)
            }
            "toggle" => {
                // A switch: a low click, then a brighter one 45 ms later as it lands.
                let strike = |tt: f64, hz: f64, f: &mut Svf, n: f64| if tt < 0.0 { 0.0 } else { let (_, bp, _) = f.run(n, hz, 0.7, sr); bp * (-tt / 0.003).exp() * 1.3 + (TAU * hz * 0.5 * tt).sin() * (-tt / 0.008).exp() * 0.35 };
                let l = strike(t, 1700.0 * pitch, &mut f[0], a) + strike(t - 0.045, 3600.0 * pitch, &mut f[2], a);
                let r = strike(t, 1700.0 * pitch, &mut f[1], b) + strike(t - 0.045, 3600.0 * pitch, &mut f[3], b);
                (l * tail, r * tail)
            }
            "error" => {
                // "Not allowed": two short buzzy notes falling a semitone (soft square through a low-pass), the second longer.
                let notes = [(0.0, 0.11, 466.16), (0.14, 0.2, 440.0)];
                let mut s = 0.0;
                for (k, &(at, len, hz)) in notes.iter().enumerate() {
                    let tt = t - at;
                    if tt < 0.0 || tt > len + 0.05 {
                        continue;
                    }
                    ph[k] += hz * pitch / sr;
                    let sq = ((TAU * ph[k]).sin() * 3.0).tanh();
                    let env = (tt / 0.004).min(1.0) * if tt < len { 1.0 } else { (1.0 - (tt - len) / 0.05).max(0.0) };
                    s += sq * env;
                }
                let (lo, _, _) = f[4].run(s, 2400.0, 1.0, sr);
                (lo * 0.45 * tail, lo * 0.45 * tail)
            }
            _ => {
                // Bells (FM): ding one bright strike, chime an inharmonic bell, notification two notes, success a rising triad.
                let base = match preset { "ding" => 1318.5, "chime" => 880.0, "notification" => 880.0, _ => 1046.5 } * pitch;
                let notes: &[(f64, f64)] = match preset { "notification" => &[(0.0, 1.0), (0.09, 1.4983)], "success" => &[(0.0, 1.0), (0.075, 1.2599), (0.15, 1.4983)], _ => &[(0.0, 1.0)] };
                let ratio = if preset == "chime" { 2.76 } else { 3.5 };
                let (mut l, mut r) = (0.0, 0.0);
                for &(at, n) in notes {
                    if t < at {
                        continue;
                    }
                    let tt = t - at;
                    let fc = base * n;
                    let index = 1.6 * (-tt / 0.06).exp() + 0.15;
                    let env = (tt / 0.002).min(1.0) * ((-tt / 0.32).exp() * 0.8 + (-tt / 0.06).exp() * 0.2);
                    let m = (TAU * fc * ratio * tt).sin() * index;
                    l += (TAU * fc * tt + m).sin() * env;
                    r += (TAU * fc * 1.002 * tt + m).sin() * env;
                }
                let g = 0.55 / (notes.len() as f64).sqrt();
                (l * g * tail, r * g * tail)
            }
        };
        out(i, u, l, r);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn take(preset: &str, dur: f64) -> Vec<(f64, f64)> {
        let mut out = vec![(0.0, 0.0); (dur * 44100.0) as usize];
        render(preset, dur, 1.0, 44100.0, |i, _, l, r| out[i] = (l, r));
        out
    }

    fn rms(x: &[(f64, f64)], a: f64, b: f64) -> f64 {
        let s = &x[(a * 44100.0) as usize..(b * 44100.0) as usize];
        (s.iter().map(|(l, r)| l * l + r * r).sum::<f64>() / s.len() as f64 / 2.0).sqrt()
    }

    #[test]
    fn a_riser_rises() {
        let r = take("riser", 2.0);
        assert!(rms(&r, 1.6, 1.9) > 4.0 * rms(&r, 0.2, 0.5));
        // Stereo: the two channels are different noise.
        assert!(r.iter().any(|(l, r)| (l - r).abs() > 1e-3));
    }

    #[test]
    fn every_preset_is_finite_bounded_and_the_same_twice() {
        for p in PRESETS {
            let a = take(p, 1.0);
            assert!(a.iter().all(|(l, r)| l.is_finite() && r.is_finite() && l.abs() < 3.0 && r.abs() < 3.0), "{p}");
            assert!(rms(&a, 0.0, 0.3) > 1e-4, "{p} is silent");
            assert_eq!(a, take(p, 1.0), "{p}");
        }
    }
}
