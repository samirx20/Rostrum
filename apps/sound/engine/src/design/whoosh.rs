//! The whoosh, shaped by the move's speed curve: level, the sweep's centre and the air all follow the
//! speed, so a long slow slide breathes and a flick is a short bright cut. Layers: a body (two band-passed
//! noises), weight (low noise, with size), air (high noise at the fastest moment), a tuned whistle, and a
//! flutter. The pitch falls past the fastest point (doppler). Left and right run on their own noise, so
//! `width` opens it; `panPath` moves it with the object.

use super::{at, end_fade, P};
use crate::sfx::{Rng, Svf};
use std::f64::consts::TAU;

/// The default speed curve: builds, peaks a little past half way, falls (a plain ease-in-out move).
const BELL: &[[f64; 2]] = &[[0.0, 0.0], [0.25, 0.35], [0.55, 1.0], [0.8, 0.4], [1.0, 0.0]];

#[derive(Default, Clone, Copy)]
struct Chain {
    body: Svf,
    body2: Svf,
    weight: Svf,
    air: Svf,
    whistle: Svf,
}

struct Mix {
    centre: f64,
    amp: f64,
    size: f64,
    air: f64,
    tone: f64,
    hi: f64,
}

impl Chain {
    fn run(&mut self, x: f64, m: &Mix, sr: f64) -> f64 {
        let (_, b1, _) = self.body.run(x, m.centre, 1.1, sr);
        let (_, b2, _) = self.body2.run(x, m.centre * 2.1, 1.4, sr);
        let (lo, _, _) = self.weight.run(x, m.centre * 0.45, 1.2, sr);
        let (_, _, hp) = self.air.run(x, m.hi, 0.9, sr);
        let (_, wh, _) = self.whistle.run(x, m.centre * 1.9, 0.07, sr);
        let s = m.amp;
        (b1 + 0.5 * b2) * s + lo * m.size * 1.3 * s.powf(1.1) + hp * m.air * 0.7 * s.powf(2.5) + wh * m.tone * 0.25 * s.powf(1.5)
    }
}

/// Writes mid (`m`) and side (`s`); returns the pan per sample when the sound has a `panPath`.
pub fn render(p: &P, m: &mut [f64], s: &mut [f64], rng: &mut Rng, sr: f64) -> Option<Vec<f64>> {
    let dur = p.f("dur");
    let speed = p.lane("speed").filter(|l| !l.is_empty()).unwrap_or_else(|| BELL.to_vec());
    let pan_path = p.lane("panPath").filter(|l| !l.is_empty());
    let u_peak = speed.iter().fold((0.0, -1.0), |best, q| if q[1] > best.1 { (q[0], q[1]) } else { best }).0;
    let (bright, size, doppler, texture) = (p.f("brightness"), p.f("size"), p.f("doppler"), p.f("texture"));
    let base = 160.0 * 2f64.powf(2.2 * bright) * 2f64.powf(-1.2 * size);
    let hi = 3500.0 * 2f64.powf(bright);
    let (mut cl, mut cr) = (Chain::default(), Chain::default());
    let mut sm = 0.0f64;
    let smooth = 1.0 - (-TAU * 40.0 / sr).exp();
    let (mut flutter, mut ph) = (0.0f64, 0.0f64);
    let mut pans = pan_path.as_ref().map(|_| Vec::with_capacity(m.len()));
    for i in 0..m.len() {
        let t = i as f64 / sr;
        let u = (t / dur).min(1.0);
        let raw = if t <= dur { at(&speed, u).clamp(0.0, 1.0) } else { at(&speed, 1.0) * (-(t - dur) / 0.04).exp() };
        sm += (raw - sm) * smooth;
        let dop = -((u - u_peak) / 0.07).tanh() * doppler;
        let centre = base * 2f64.powf(3.0 * sm.powf(0.8)) * 2f64.powf(0.6 * dop);
        // Flutter: faster as the object moves faster, jittered so it never reads as a tremolo.
        flutter += (rng.n() - flutter) * (1.0 - (-TAU * 6.0 / sr).exp());
        ph += (14.0 + 34.0 * sm) * (1.0 + 0.5 * flutter) / sr;
        let am = 1.0 - texture * 0.55 * (0.5 + 0.5 * (TAU * ph).sin());
        let mix = Mix { centre, amp: sm.powf(1.4) * am, size, air: p.f("air"), tone: p.f("tone"), hi };
        let (a, b) = (rng.n(), rng.n());
        let (l, r) = (cl.run(a, &mix, sr), cr.run(b, &mix, sr));
        m[i] = 0.5 * (l + r);
        s[i] = 0.5 * (l - r);
        if let (Some(v), Some(path)) = (pans.as_mut(), pan_path.as_ref()) {
            v.push(at(path, u));
        }
    }
    end_fade(m, sr);
    end_fade(s, sr);
    pans
}
