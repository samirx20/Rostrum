//! Click, tick, tap, pop: a layered small sound. A transient (the first millisecond's snap, high-passed
//! noise), a tuned body (a few decaying partials whose spacing and ring come from the material: soft
//! plastic's close, damped ones, glass's wide clear ones, metal's long beating ones), a knock (low noise,
//! for soft materials) and a tick of air. `bend` sweeps the body's pitch into the note (a knock) or up
//! into it (a pop).

use super::P;
use crate::sfx::{Rng, Svf};
use std::f64::consts::TAU;

/// Partial ratios and ring time (s) for soft plastic, glass, metal.
const PLASTIC: ([f64; 5], f64, f64) = ([1.0, 1.58, 2.21, 2.93, 3.6], 0.018, 1.6);
const GLASS: ([f64; 5], f64, f64) = ([1.0, 2.32, 4.25, 6.63, 9.38], 0.12, 1.2);
const METAL: ([f64; 5], f64, f64) = ([1.0, 2.76, 5.40, 8.93, 13.34], 0.35, 0.9);

fn lerp(a: f64, b: f64, x: f64) -> f64 {
    a + (b - a) * x
}

/// (ratios, ring time, partial fall-off) for a material 0 … 1.
fn material(x: f64) -> ([f64; 5], f64, f64) {
    let (a, b, k) = if x < 0.5 { (PLASTIC, GLASS, x * 2.0) } else { (GLASS, METAL, x * 2.0 - 1.0) };
    let mut ratios = [0.0; 5];
    for (i, r) in ratios.iter_mut().enumerate() {
        *r = lerp(a.0[i], b.0[i], k);
    }
    (ratios, lerp(a.1, b.1, k), lerp(a.2, b.2, k))
}

pub fn render(p: &P, m: &mut [f64], s: &mut [f64], rng: &mut Rng, sr: f64) {
    let (pitch, mat, tight) = (p.f("pitch"), p.f("material"), p.f("tight"));
    let (body, transient, air, bend) = (p.f("body"), p.f("transient"), p.f("air"), p.f("bend"));
    let (ratios, ring, falloff) = material(mat);
    let ring = ring * (1.0 - 0.85 * tight);
    let detune = 0.0015 * mat;
    let t_tau = 0.0006 * (1.6 - tight);
    let mut phase = [[0.0f64; 5]; 2];
    let (mut hp, mut knock, mut airf) = ([Svf::default(); 2], [Svf::default(); 2], [Svf::default(); 2]);
    let start_phase: Vec<f64> = (0..5).map(|_| rng.u()).collect();
    for i in 0..m.len() {
        let t = i as f64 / sr;
        let glide = 2f64.powf(bend * (-t / 0.012).exp());
        let mut out = [0.0f64; 2];
        for (ch, o) in out.iter_mut().enumerate() {
            let side = if ch == 0 { 1.0 - detune } else { 1.0 + detune };
            let mut b = 0.0;
            for (k, ratio) in ratios.iter().enumerate() {
                let f = pitch * ratio * glide * side;
                if f > 18000.0 {
                    continue;
                }
                phase[ch][k] += f / sr;
                let tau = ring / (1.0 + 0.4 * k as f64);
                b += (TAU * (phase[ch][k] + start_phase[k])).sin() * (-t / tau).exp() / ((k + 1) as f64).powf(falloff);
            }
            let n = rng.n();
            let (_, _, h) = hp[ch].run(n, 2000.0 + 4000.0 * mat, 0.8, sr);
            let (lo, _, _) = knock[ch].run(n, pitch * 0.5, 1.0, sr);
            let (_, a, _) = airf[ch].run(n, 8000.0, 0.7, sr);
            // The body swells in over 0.3 ms so its first cycle doesn't click on its own.
            let onset = (t / 0.0003).min(1.0);
            *o = b * body * onset + h * transient * 1.5 * (-t / t_tau).exp() + lo * (1.0 - mat) * body * 0.8 * (-t / 0.008).exp()
                + a * air * 0.8 * (-t / 0.01).exp();
        }
        m[i] = 0.5 * (out[0] + out[1]);
        s[i] = 0.5 * (out[0] - out[1]);
    }
}
