//! Track and clip processing, sample by sample: a port of src/engine/sound/masteringDsp.ts (tone
//! filter, fades / gain / pan; the stereo reverb is reverb.rs), sample by sample with whole-buffer helpers.

use std::f64::consts::{PI, SQRT_2};

#[derive(Clone, Copy, PartialEq)]
enum Tone { Neutral, Muffled, Warm, SubBoost, Bright, VoiceClarity, Radio }

pub struct ToneFilter {
    tone: Tone,
    alpha: f64,
    lp: [f64; 2],
    hp_prev: [f64; 2],
}

impl ToneFilter {
    pub fn new(name: &str, sr: f64) -> Self {
        let tone = match name {
            "muffled" => Tone::Muffled,
            "warm" => Tone::Warm,
            "sub-boost" => Tone::SubBoost,
            "bright" => Tone::Bright,
            "voice-clarity" => Tone::VoiceClarity,
            "radio" => Tone::Radio,
            _ => Tone::Neutral,
        };
        let cut = match tone { Tone::Muffled => 650.0, Tone::Warm => 2400.0, Tone::SubBoost => 320.0, Tone::Radio => 1800.0, _ => 3200.0 };
        let (rc, dt) = (1.0 / (2.0 * PI * cut), 1.0 / sr);
        ToneFilter { tone, alpha: dt / (rc + dt), lp: [0.0; 2], hp_prev: [0.0; 2] }
    }

    pub fn process(&mut self, x: [f64; 2]) -> [f64; 2] {
        if self.tone == Tone::Neutral {
            return x;
        }
        let mut out = [0.0; 2];
        for c in 0..2 {
            self.lp[c] += self.alpha * (x[c] - self.lp[c]);
            let (lp, hp) = (self.lp[c], x[c] - self.lp[c]);
            out[c] = match self.tone {
                Tone::Muffled => lp * 1.1,
                Tone::Warm => lp * 0.8 + x[c] * 0.3,
                Tone::SubBoost => x[c] * 0.85 + lp * 0.65,
                Tone::Bright => x[c] * 0.75 + hp * 0.65,
                Tone::VoiceClarity => {
                    let dc = x[c] - self.hp_prev[c] + 0.985 * lp;
                    self.hp_prev[c] = x[c];
                    ((dc * 0.4 + hp * 0.85) * 1.25).tanh()
                }
                Tone::Radio => (hp * 2.2).tanh() * 0.7,
                Tone::Neutral => x[c],
            };
        }
        out
    }
}

/// Fade in / out over a span of known length, then volume and equal-power pan (×√2 at centre).
pub struct FadeGain {
    len: usize,
    fade_in: usize,
    fade_out: usize,
    gain: [f64; 2],
}

impl FadeGain {
    pub fn new(len: usize, sr: f64, fade_in: f64, fade_out: f64, volume: f64, pan: f64) -> Self {
        let a = (pan.clamp(-1.0, 1.0) + 1.0) * PI / 4.0;
        FadeGain {
            len,
            fade_in: (fade_in * sr).floor().max(0.0) as usize,
            fade_out: (fade_out * sr).floor().max(0.0) as usize,
            gain: [volume * a.cos() * SQRT_2, volume * a.sin() * SQRT_2],
        }
    }

    /// The fade envelope at sample `i` (1 between the fades).
    pub fn env(&self, i: usize) -> f64 {
        let mut env = 1.0;
        if self.fade_in > 0 && i < self.fade_in {
            env *= (i as f64 / self.fade_in as f64 * PI / 2.0).sin();
        }
        if self.fade_out > 0 && i + self.fade_out >= self.len {
            let rem = (self.len as f64 - 1.0 - i as f64) / self.fade_out as f64;
            env *= (rem.max(0.0) * PI / 2.0).sin();
        }
        env
    }

    pub fn process(&self, i: usize, x: [f64; 2]) -> [f64; 2] {
        let env = self.env(i);
        [x[0] * env * self.gain[0], x[1] * env * self.gain[1]]
    }
}

/// Runs a per-sample stage over a stereo buffer in place.
pub fn each(left: &mut [f32], right: &mut [f32], mut f: impl FnMut(usize, [f64; 2]) -> [f64; 2]) {
    for i in 0..left.len().min(right.len()) {
        let y = f(i, [left[i] as f64, right[i] as f64]);
        left[i] = y[0] as f32;
        right[i] = y[1] as f32;
    }
}

pub fn tone(left: &mut [f32], right: &mut [f32], name: &str, sr: f64) {
    if name == "neutral" || name.is_empty() || left.is_empty() {
        return;
    }
    let mut t = ToneFilter::new(name, sr);
    each(left, right, |_, x| t.process(x));
}

pub fn fade_gain(left: &mut [f32], right: &mut [f32], sr: f64, fade_in: f64, fade_out: f64, volume: f64, pan: f64) {
    let g = FadeGain::new(left.len(), sr, fade_in, fade_out, volume, pan);
    each(left, right, |i, x| g.process(i, x));
}
