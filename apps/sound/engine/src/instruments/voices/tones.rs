//! The named instruments' and the classic kit's sound, one sample at a time (Voice::next calls these).

use std::f64::consts::PI;

use super::{fast_noise, Voice};

fn warm_saw(p: f64) -> f64 {
    p.sin() * 0.62 + (p * 2.0 + 0.3).sin() * 0.24 + (p * 3.0 + 0.7).sin() * 0.1 + (p * 4.0 + 1.1).sin() * 0.04
}

#[derive(Clone, Copy, PartialEq)]
pub(super) enum Inst { FeltPiano, GrandPiano, WarmPad, AnalogStrings, Spiccato, Choir, Brass, SubBass, Shepard, Marimba, Pluck }

impl Inst {
    pub(super) fn parse(name: &str) -> Inst {
        match name {
            "feltPiano" => Inst::FeltPiano,
            "grandPiano" => Inst::GrandPiano,
            "warmPad" => Inst::WarmPad,
            "analogStrings" => Inst::AnalogStrings,
            "spiccatoStrings" => Inst::Spiccato,
            "choirPad" => Inst::Choir,
            "cinematicBrass" => Inst::Brass,
            "subBass" => Inst::SubBass,
            "shepardRiser" => Inst::Shepard,
            "glassMarimba" => Inst::Marimba,
            _ => Inst::Pluck,
        }
    }
    pub(super) fn release_tail(self) -> f64 {
        match self {
            Inst::WarmPad | Inst::AnalogStrings | Inst::Choir => 0.65,
            Inst::FeltPiano | Inst::GrandPiano => 0.55,
            Inst::Spiccato => 0.18,
            _ => 0.25,
        }
    }
}

impl Voice {
    fn advance(&mut self, sr: f64, ratios: [f64; 3], f: f64) {
        for k in 0..3 {
            self.p[k] += 2.0 * PI * f * ratios[k] / sr;
        }
    }

    /// (left, right, cutoff Hz, filter damping) before the voice's low-pass.
    pub(super) fn note(&mut self, inst: Inst, f: f64, v: f64, dur: f64, i: usize, t: f64) -> (f64, f64, f64, f64) {
        let sr = self.sr;
        match inst {
            Inst::FeltPiano | Inst::GrandPiano => {
                let felt = inst == Inst::FeltPiano;
                let attack = 1.0 - (-t * if felt { 95.0 } else { 180.0 }).exp();
                let decay = (f / 180.0).max(1.2);
                let sustain = if t <= dur {
                    0.75 * (-t * 1.4 * decay).exp() + 0.25 * (-t * 0.45).exp()
                } else {
                    (0.75 * (-dur * 1.4 * decay).exp() + 0.25 * (-dur * 0.45).exp()) * (-(t - dur) * 9.5).exp()
                };
                let env = attack * sustain;
                self.advance(sr, [1.0, 2.0007, 3.0022], f);
                let thump = fast_noise(i as f64 + v * 97.0) * (-t * 160.0).exp() * if felt { 0.06 } else { 0.1 };
                let s = self.p[0].sin() * 0.68
                    + self.p[1].sin() * (if felt { 0.22 } else { 0.3 }) * (-t * 2.8).exp()
                    + self.p[2].sin() * (if felt { 0.05 } else { 0.12 }) * (-t * 5.5).exp()
                    + thump;
                let cutoff = if felt { (1200.0 * (-t * 1.8).exp() + 320.0).max(380.0) } else { (3200.0 * (-t * 1.5).exp() + 600.0).max(700.0) };
                (s * env, s * env, cutoff, 0.85)
            }
            Inst::WarmPad | Inst::AnalogStrings => {
                let pad = inst == Inst::WarmPad;
                let att_dur = (dur * if pad { 0.3 } else { 0.28 }).min(0.45).max(if pad { 0.18 } else { 0.15 });
                let att = if t < att_dur { (PI * 0.5 * t / att_dur).sin() } else { 1.0 };
                let rel = if t <= dur { 1.0 } else if t < dur + att_dur { (PI * 0.5 * (t - dur) / att_dur).cos() } else { 0.0 };
                let env = att * rel;
                if pad {
                    self.advance(sr, [0.9948, 1.0, 1.0052], f);
                    let l = (warm_saw(self.p[0]) * 0.45 + warm_saw(self.p[1]) * 0.35 + (self.p[1] * 0.5).sin() * 0.25) * env;
                    let r = (warm_saw(self.p[2]) * 0.45 + warm_saw(self.p[1]) * 0.35 + (self.p[1] * 0.5).sin() * 0.25) * env;
                    (l, r, 420.0 + 520.0 * (PI * (t / dur.max(0.5)).min(1.0)).sin(), 0.7)
                } else {
                    let vib = 1.0 + (2.0 * PI * 5.1 * t + v * 1.1).sin() * 0.0032;
                    self.advance(sr, [0.996 * vib, vib, 1.004 * vib], f);
                    let l = (warm_saw(self.p[0]) * 0.55 + warm_saw(self.p[1]) * 0.45) * env;
                    let r = (warm_saw(self.p[2]) * 0.55 + warm_saw(self.p[1]) * 0.45) * env;
                    (l, r, 1150.0 + 450.0 * att, 0.78)
                }
            }
            Inst::Spiccato => {
                let env = (1.0 - (-t * 140.0).exp()) * (-t * 6.8).exp();
                self.advance(sr, [0.9965, 1.0, 1.0035], f);
                let rosin = fast_noise((i + self.start) as f64) * (-t * 65.0).exp() * 0.14;
                let l = (warm_saw(self.p[0]) * 0.5 + warm_saw(self.p[1]) * 0.5 + rosin) * env;
                let r = (warm_saw(self.p[2]) * 0.5 + warm_saw(self.p[1]) * 0.5 + rosin) * env;
                (l, r, 480.0 + 1350.0 * (-t * 11.0).exp(), 0.75)
            }
            Inst::Choir => {
                let att = (t / (dur * 0.35).min(0.65).max(0.22)).min(1.0);
                let rel = if t <= dur { 1.0 } else { (-(t - dur) * 3.5).exp() };
                let env = att * rel;
                let vib = 1.0 + (2.0 * PI * 4.6 * t + v * 1.4).sin() * 0.0035;
                self.advance(sr, [0.9955 * vib, vib, 1.0045 * vib], f);
                let glottal = warm_saw(self.p[0]) * 0.38 + warm_saw(self.p[1]) * 0.38 + warm_saw(self.p[2]) * 0.38;
                let fc1 = 2.0 * (PI * 660.0 / sr).sin();
                let fc2 = 2.0 * (PI * 1120.0 / sr).sin();
                let [f1_lp, f1_bp, f2_lp, f2_bp] = &mut self.formant;
                *f1_bp += fc1 * (glottal - *f1_lp - 0.28 * *f1_bp);
                *f1_lp += fc1 * *f1_bp;
                *f2_bp += fc2 * (glottal - *f2_lp - 0.32 * *f2_bp);
                *f2_lp += fc2 * *f2_bp;
                let s = (*f1_bp * 0.65 + *f2_bp * 0.35 + self.p[1].sin() * 0.35) * env;
                (s, s * 0.92 + warm_saw(self.p[2]) * 0.12 * env, 1800.0, 0.85)
            }
            Inst::Brass => {
                let swell = (t / (dur * 0.3).min(0.35).max(0.08)).powf(0.85).min(1.0);
                let rel = if t <= dur { 1.0 } else { (-(t - dur) * 6.5).exp() };
                let env = swell * rel;
                self.advance(sr, [0.996, 1.0, 1.004], f);
                let drive = 0.9 + swell * 0.7;
                let l = ((warm_saw(self.p[0]) * 0.55 + warm_saw(self.p[1]) * 0.55) * drive).tanh() * env;
                let r = ((warm_saw(self.p[2]) * 0.55 + warm_saw(self.p[1]) * 0.55) * drive).tanh() * env;
                (l, r, 340.0 + 1950.0 * swell, 0.65)
            }
            Inst::SubBass => {
                let att = 1.0 - (-t * 65.0).exp();
                let rel = if t <= dur { (-t * 0.85).exp() } else { (-(t - dur) * 12.0).exp() };
                self.advance(sr, [1.0, 2.0, 0.0], f);
                let s = ((self.p[0].sin() * 0.88 + self.p[1].sin() * 0.22 * (-t * 3.5).exp()) * 1.35).tanh() * att * rel;
                (s, s, 190.0, 0.9)
            }
            Inst::Shepard => {
                let u = (t / dur.max(0.25)).min(1.0);
                let sweep = 2f64.powf(u);
                self.advance(sr, [0.5 * sweep, sweep, 2.0 * sweep], f);
                let env = (PI * (u * 0.98).min(1.0)).sin() * u.powf(0.4);
                let s = (warm_saw(self.p[0]) * 0.45 + warm_saw(self.p[1]) * 0.4 + self.p[2].sin() * (1.0 - u) * 0.2) * env;
                (s, s, 280.0 + 1900.0 * u.powf(1.4), 0.68)
            }
            Inst::Marimba => {
                let env = (1.0 - (-t * 240.0).exp()) * (-t * 6.0).exp();
                self.advance(sr, [1.0, 3.99, 0.0], f);
                let s = (self.p[0].sin() * 0.82 + self.p[1].sin() * 0.18 * (-t * 18.0).exp()) * env;
                (s, s, 2200.0, 0.85)
            }
            Inst::Pluck => {
                let env = (1.0 - (-t * 190.0).exp()) * (-t * 7.2).exp();
                self.advance(sr, [0.998, 1.002, 0.0], f);
                (warm_saw(self.p[0]) * env, warm_saw(self.p[1]) * env, 420.0 + 1800.0 * (-t * 9.5).exp(), 0.72)
            }
        }
    }

    /// A synthesized hit at `t`: `tune` scales its pitches and filters, `decay` stretches its envelopes.
    pub(super) fn drum(&mut self, voice: &str, i: usize, t: f64, tune: f64, decay: f64) -> f64 {
        let sr = self.sr;
        let te = t / decay.max(0.01);
        let dt = 1.0 / sr;
        let n = fast_noise((i + self.start) as f64);
        let one_pole = |lp: &mut f64, hz: f64| *lp += (dt / (1.0 / (2.0 * PI * hz) + dt)) * (n - *lp);
        let svf = |lp: &mut f64, bp: &mut f64, hz: f64, q: f64| {
            let f = 2.0 * (PI * hz / sr).sin();
            let hp = n - *lp - q * *bp;
            *bp += f * hp;
            *lp += f * *bp;
        };
        let [lp, _] = &mut self.lp;
        let [bp, _] = &mut self.bp;
        match voice {
            "kick" => {
                self.p[0] += 2.0 * PI * tune * (42.0 + 95.0 * (-t * 42.0).exp()) / sr;
                let body = (self.p[0].sin() * 1.35).tanh() * (-te * 7.8).exp();
                one_pole(lp, 280.0 * tune);
                body * 0.92 + *lp * (-t * 95.0).exp() * 0.45
            }
            "snare" => {
                self.p[0] += 2.0 * PI * tune * (175.0 + 65.0 * (-t * 38.0).exp()) / sr;
                let shell = self.p[0].sin() * (-te * 20.0).exp();
                svf(lp, bp, 2200.0 * tune, 0.7);
                shell * 0.52 + *bp * (-te * 14.0).exp() * 0.75
            }
            "clap" => {
                let burst = if t < 0.009 { 1.0 } else if t < 0.018 { (-(t - 0.009) * 160.0).exp() } else if t < 0.027 { (-(t - 0.018) * 160.0).exp() } else { (-(te - 0.027) * 15.0).exp() };
                svf(lp, bp, 1450.0 * tune, 0.55);
                *bp * burst * 1.1
            }
            "hat" => {
                one_pole(lp, (6500.0 * tune).min(sr * 0.45));
                (n - *lp) * (-te * 58.0).exp() * 0.48
            }
            "openHat" | "cymbal" => {
                one_pole(lp, (5200.0 * tune).min(sr * 0.45));
                (n - *lp) * (-te * if voice == "cymbal" { 4.5 } else { 8.5 }).exp() * 0.45
            }
            "tom" => {
                self.p[0] += 2.0 * PI * tune * (86.0 + 54.0 * (-t * 18.0).exp()) / sr;
                (self.p[0].sin() * 1.2).tanh() * (-te * 9.5).exp()
            }
            _ => {
                svf(lp, bp, 1550.0 * tune, 0.25);
                *bp * (-te * 85.0).exp() * 1.2
            }
        }
    }
}
