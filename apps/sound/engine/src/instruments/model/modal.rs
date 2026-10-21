//! Modal synthesis: a struck object as a bank of decaying resonances (frequency, decay, level), each a
//! two-pole resonator driven by the strike's force. The strike is a half-sine force pulse whose length
//! is the contact time — a soft mallet or a felt beater stays on longer, so it excites only the low
//! modes; a hard one is short and brings out the high ones. Damping can change mid-note (a damper, a
//! hand on a cymbal) and the pitch can bend (a drum head's tension falling after the hit).

use std::f64::consts::PI;

/// One resonance: Hz, seconds to fall 60 dB, level.
#[derive(Clone, Copy, Debug)]
pub struct Mode {
    pub freq: f64,
    pub t60: f64,
    pub amp: f64,
}

/// A two-pole resonator; its impulse response is `amp · r^n · sin(θ(n+1))`.
#[derive(Clone, Copy, Default)]
pub struct Resonator {
    a1: f64,
    a2: f64,
    g: f64,
    y1: f64,
    y2: f64,
}

impl Resonator {
    pub fn new(m: &Mode, sr: f64) -> Resonator {
        let mut r = Resonator::default();
        r.set(m.freq, m.t60, m.amp, sr);
        r
    }
    /// Retunes in place (the state is kept, so a bend or a damper is click-free).
    pub fn set(&mut self, freq: f64, t60: f64, amp: f64, sr: f64) {
        let th = 2.0 * PI * freq.min(sr * 0.49) / sr;
        let r = (-6.907_755 / (t60.max(1e-4) * sr)).exp();
        self.a1 = 2.0 * r * th.cos();
        self.a2 = -r * r;
        self.g = amp * th.sin();
    }
    #[inline]
    pub fn tick(&mut self, x: f64) -> f64 {
        let y = self.a1 * self.y1 + self.a2 * self.y2 + self.g * x;
        self.y2 = self.y1;
        self.y1 = super::flush(y);
        y
    }
}

/// A strike's force: a half-sine `contact` seconds long with unit area (the low modes' level does not
/// depend on the hardness, only how far up the strike reaches).
pub fn pulse(contact: f64, sr: f64) -> Vec<f64> {
    let n = ((contact * sr).round() as usize).max(1);
    let raw: Vec<f64> = (0..n).map(|i| (PI * (i as f64 + 0.5) / n as f64).sin()).collect();
    let sum: f64 = raw.iter().sum();
    raw.into_iter().map(|v| v / sum).collect()
}

/// Rings `modes` from the force `exc`, `len` samples; from `damp_at` on every mode falls in at most
/// `damp_t60` seconds (a damper). Modes above the Nyquist limit are left out.
pub fn ring(modes: &[Mode], exc: &[f64], len: usize, damp_at: Option<usize>, damp_t60: f64, sr: f64) -> Vec<f64> {
    let mut out = vec![0.0; len];
    for m in modes.iter().filter(|m| m.freq < sr * 0.45 && m.amp != 0.0) {
        let mut r = Resonator::new(m, sr);
        // Where it is too quiet to matter, it stops (a −100 dB floor).
        let audible = ((m.t60 * 100.0 / 60.0) * sr) as usize + exc.len();
        let end = len.min(match damp_at {
            Some(d) => audible.min(d + (damp_t60 * 100.0 / 60.0 * sr) as usize),
            None => audible,
        });
        for (i, o) in out.iter_mut().enumerate().take(end) {
            if Some(i) == damp_at && damp_t60 < m.t60 {
                r.set(m.freq, damp_t60, m.amp, sr);
            }
            *o += r.tick(exc.get(i).copied().unwrap_or(0.0));
        }
    }
    out
}

/// A one-pole high-pass and low-pass, for shaping noise (cutoff in Hz).
pub fn one_pole(x: &mut [f64], cutoff: f64, high: bool, sr: f64) {
    let a = (-2.0 * PI * cutoff / sr).exp();
    let mut s = 0.0;
    for v in x.iter_mut() {
        s = (1.0 - a) * *v + a * s;
        *v = if high { *v - s } else { s };
    }
}

/// The level a free-free bar's mode `k` (0-based) is struck with at `pos` (0: the end, 0.5: the middle):
/// its mode shape there (symmetric modes are cosines about the centre, antisymmetric sines).
pub fn bar_shape(k: usize, pos: f64) -> f64 {
    let beta = (2 * k + 3) as f64 * PI / 2.0;
    let x = pos - 0.5;
    if k % 2 == 0 { (beta * x).cos() } else { (beta * x).sin() * 1.4 }
}
