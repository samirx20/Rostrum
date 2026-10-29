//! Tremolo: the level of each side of a pair rises and falls with a sine at `rate` Hz, down by `depth` (0 … 1) at
//! its lowest. `stereo` sets how far the right side's cycle runs behind the left's: 0 both together (an amplitude
//! tremolo, the image stays put), 1 half a turn (one side loud while the other is soft: an auto-pan, the stereo
//! vibrato of a Rhodes Suitcase). At `stereo` 1 and `depth` 1 the two gains always sum to one, so the sound moves
//! across without its level pumping. On a mono source (L = R) any `stereo` above 0 makes the sides differ.

use std::f64::consts::PI;

use super::BLOCK;
use crate::mix::schedule::Param;

pub struct Tremolo {
    rate: f64,
    stereo: f64,
    depth: Param,
    sr: f64,
    phase: f64,
    started: bool,
    d: f64,
}

impl Tremolo {
    pub fn new(rate: f64, depth: &Param, stereo: f64, sr: f64) -> Self {
        Tremolo { rate, stereo, depth: depth.clone(), sr, phase: 0.0, started: false, d: depth.at(0.0) }
    }

    pub fn pair(&mut self, l: &mut [f32], r: &mut [f32], t0: usize) {
        let step = 2.0 * PI * self.rate / self.sr;
        if !self.started && t0 > 0 {
            // A render that starts later in the song (a heard stretch): the sweep where it is at that frame.
            self.phase = (step * t0 as f64) % (2.0 * PI);
        }
        self.started = true;
        for i in 0..l.len().min(r.len()) {
            if (t0 + i) % BLOCK == 0 {
                self.d = self.depth.at((t0 + i) as f64 / self.sr).clamp(0.0, 1.0);
            }
            let d = self.d;
            // Each gain runs 1 (top) … 1 − depth (bottom); the cycle starts at the top.
            let gain = |ph: f64| 1.0 - d * (0.5 - 0.5 * ph.cos());
            l[i] = (l[i] as f64 * gain(self.phase)) as f32;
            r[i] = (r[i] as f64 * gain(self.phase - PI * self.stereo)) as f32;
            self.phase = (self.phase + step) % (2.0 * PI);
        }
    }
}

/// The stereo correlation of a pair: 1 the same on both sides (mono), 0 unrelated, −1 opposite.
#[cfg(test)]
pub fn correlation(l: &[f32], r: &[f32]) -> f64 {
    let (mut lr, mut ll, mut rr) = (0.0, 0.0, 0.0);
    for (a, b) in l.iter().zip(r) {
        let (a, b) = (*a as f64, *b as f64);
        lr += a * b;
        ll += a * a;
        rr += b * b;
    }
    lr / (ll * rr).sqrt().max(1e-12)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stereo_one_pans_without_pumping_and_stereo_zero_stays_mono() {
        let sr = 48000.0;
        let x: Vec<f32> = (0..48000).map(|i| (0.5 * (2.0 * PI * 440.0 * i as f64 / sr).sin()) as f32).collect();
        let (mut l, mut r) = (x.clone(), x.clone());
        let mut t = Tremolo::new(4.0, &Param::Value(1.0), 1.0, sr);
        for (k, (a, b)) in l.chunks_mut(500).zip(r.chunks_mut(500)).enumerate() {
            t.pair(a, b, k * 500);
        }
        // The two gains sum to one: L + R is the source, the level does not pump.
        assert!(l.iter().zip(&r).zip(&x).all(|((a, b), s)| (a + b - s).abs() < 1e-5));
        // Half a cycle on (125 ms at 4 Hz), the sound has crossed from one side to the other.
        let peak = |c: &[f32], a: usize| c[a..a + 600].iter().fold(0f32, |m, v| m.max(v.abs()));
        assert!(peak(&l, 0) > 0.45 && peak(&r, 0) < 0.05);
        assert!(peak(&l, 6000) < 0.05 && peak(&r, 6000) > 0.45);
        assert!(correlation(&l, &r) < 0.5);
        // Stereo 0: both sides move together, a mono source stays mono, at its lowest down by `depth`.
        let (mut l, mut r) = (x.clone(), x.clone());
        Tremolo::new(4.0, &Param::Value(0.6), 0.0, sr).pair(&mut l, &mut r, 0);
        assert!(correlation(&l, &r) > 0.9999);
        assert!((peak(&l, 5700) - 0.2).abs() < 0.01, "{}", peak(&l, 5700));
    }
}
