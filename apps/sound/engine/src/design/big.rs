//! Sounds for big moments. Riser: a noise sweep and a detuned tonal stack climbing to its end, with an
//! accelerating flutter and hiss near the peak. Hit: a sub thump falling into its pitch, a mid body, a
//! crack and a tail, saturated together. Sub drop: a sine falling into its pitch.

use super::{end_fade, P};
use crate::sfx::{Rng, Svf};
use std::f64::consts::TAU;

pub fn riser(p: &P, m: &mut [f64], s: &mut [f64], rng: &mut Rng, sr: f64) {
    let dur = p.f("dur");
    let (bright, curve, tone, air, texture) = (p.f("brightness"), p.f("curve"), p.f("tone"), p.f("air"), p.f("texture"));
    let pitch = p.f("pitch");
    let mut f = [[Svf::default(); 3]; 2];
    let mut ph = [[0.0f64; 3]; 2];
    let mut trem = 0.0f64;
    for i in 0..m.len() {
        let t = i as f64 / sr;
        let u = (t / dur).min(1.0);
        let c = u.powf(1.0 + 3.0 * curve);
        let gate = if t <= dur { 1.0 } else { (-(t - dur) / 0.01).exp() };
        trem += (4.0 + 28.0 * c) / sr;
        let am = 1.0 - texture * 0.5 * (0.5 + 0.5 * (TAU * trem).sin()) * c;
        let centre = 300.0 * 2f64.powf((3.0 + 2.5 * bright) * c);
        let mut out = [0.0f64; 2];
        for (ch, o) in out.iter_mut().enumerate() {
            let n = rng.n();
            let (_, band, _) = f[ch][0].run(n, centre, 0.8, sr);
            let (_, _, hiss) = f[ch][1].run(n, 6000.0, 0.9, sr);
            let mut stack = 0.0;
            for (k, d) in [-0.07, 0.0, 0.07].iter().enumerate() {
                ph[ch][k] += pitch * 2f64.powf(2.0 * c + d / 12.0 + ch as f64 * 0.004) / sr;
                stack += 2.0 * (ph[ch][k] - ph[ch][k].floor()) - 1.0;
            }
            let (lp, _, _) = f[ch][2].run(stack / 3.0, 600.0 + 6000.0 * c * bright.max(0.2), 1.0, sr);
            *o = (band * c + lp * tone * 0.6 * c + hiss * air * c.powi(3)) * am * gate;
        }
        m[i] = 0.5 * (out[0] + out[1]);
        s[i] = 0.5 * (out[0] - out[1]);
    }
    end_fade(m, sr);
    end_fade(s, sr);
}

pub fn hit(p: &P, m: &mut [f64], s: &mut [f64], rng: &mut Rng, sr: f64) {
    let (pitch, size, bright, tail, drive) = (p.f("pitch"), p.f("size"), p.f("brightness"), p.f("tail"), p.f("drive"));
    let thump = 0.03 + 0.4 * size;
    let mut ph = 0.0f64;
    let mut f = [[Svf::default(); 3]; 2];
    for i in 0..m.len() {
        let t = i as f64 / sr;
        ph += pitch * (1.0 + 2.5 * (-t / 0.03).exp()) / sr;
        let sub = (TAU * ph).sin() * (-t / thump).exp() * (0.6 + 0.6 * size);
        let mut out = [0.0f64; 2];
        for (ch, o) in out.iter_mut().enumerate() {
            let n = rng.n();
            let (_, body, _) = f[ch][0].run(n, 180.0 + 120.0 * (1.0 - size), 0.9, sr);
            let (_, _, crack) = f[ch][1].run(n, 2500.0, 0.8, sr);
            let (lo, _, _) = f[ch][2].run(n, 400.0 + 3000.0 * bright * (-t / tail).exp(), 1.0, sr);
            let x = sub + body * 1.2 * (-t / 0.07).exp() + crack * bright * 1.4 * (-t / 0.004).exp() + lo * 0.35 * (-t / (0.3 * tail)).exp();
            *o = if drive > 0.0 { (x * (1.0 + 4.0 * drive)).tanh() / (1.0 + 4.0 * drive).tanh() } else { x };
        }
        m[i] = 0.5 * (out[0] + out[1]);
        s[i] = 0.5 * (out[0] - out[1]);
    }
    end_fade(m, sr);
    end_fade(s, sr);
}

pub fn sub_drop(p: &P, m: &mut [f64], s: &mut [f64], sr: f64) {
    let (dur, pitch, drop, drive) = (p.f("dur"), p.f("pitch"), p.f("drop"), p.f("drive"));
    let mut ph = 0.0f64;
    for i in 0..m.len() {
        let t = i as f64 / sr;
        let u = (t / dur).min(1.0);
        ph += pitch * 2f64.powf(drop * (1.0 - u).powi(2)) / sr;
        let env = (t / 0.005).min(1.0) * (1.0 - u).powf(0.7);
        let x = ((TAU * ph).sin() + 0.15 * (2.0 * TAU * ph).sin()) * env;
        m[i] = if drive > 0.0 { (x * (1.0 + 4.0 * drive)).tanh() } else { x };
        s[i] = 0.0;
    }
    end_fade(m, sr);
}
