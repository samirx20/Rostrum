//! Stereo chorus: each side of a pair read back through its own short delay (12 ms) that a slow sine sweeps by up
//! to ±5 ms (`depth` 1), the right side's sweep `spread` × half a turn behind the left's. With `spread` above 0 the
//! two sides differ even on a mono source (L = R), so the chorus widens what `width` cannot. `mix` blends the
//! swept copy with the dry signal (0.5 the classic chorus, 1 only the swept copy: a vibrato). The delay lines and
//! the sweep's phase are kept between blocks (fx/state.rs).

use std::f64::consts::PI;

use super::BLOCK;
use crate::mix::schedule::Param;

const BASE_S: f64 = 0.012;
const SWEEP_S: f64 = 0.005;

pub struct Chorus {
    rate: f64,
    spread: f64,
    depth: Param,
    mix: Param,
    sr: f64,
    buf: [Vec<f64>; 2],
    w: usize,
    phase: f64,
    started: bool,
    now: (f64, f64),
}

impl Chorus {
    pub fn new(rate: f64, depth: &Param, mix: &Param, spread: f64, sr: f64) -> Self {
        let n = ((BASE_S + SWEEP_S) * sr).ceil() as usize + 4;
        Chorus { rate, spread, depth: depth.clone(), mix: mix.clone(), sr, buf: [vec![0.0; n], vec![0.0; n]], w: 0, phase: 0.0, started: false, now: (depth.at(0.0), mix.at(0.0)) }
    }

    /// The line `ch` read `d` samples back (fractional: a 4-point Hermite curve between samples).
    fn read(&self, ch: usize, d: f64) -> f64 {
        let b = &self.buf[ch];
        let n = b.len();
        let k = d.floor() as usize;
        let f = d - k as f64;
        let at = |back: usize| b[(self.w + n - back) % n];
        // Going back in time: y1 is `k` samples back, y2 one further.
        let (y0, y1, y2, y3) = (at(k.saturating_sub(1)), at(k), at(k + 1), at(k + 2));
        let c1 = 0.5 * (y2 - y0);
        let c2 = y0 - 2.5 * y1 + 2.0 * y2 - 0.5 * y3;
        let c3 = 0.5 * (y3 - y0) + 1.5 * (y1 - y2);
        ((c3 * f + c2) * f + c1) * f + y1
    }

    pub fn pair(&mut self, l: &mut [f32], r: &mut [f32], t0: usize) {
        let n = self.buf[0].len();
        let (base, sweep) = (BASE_S * self.sr, SWEEP_S * self.sr);
        let step = 2.0 * PI * self.rate / self.sr;
        if !self.started && t0 > 0 {
            // A render that starts later in the song (a heard stretch): the sweep where it is at that frame.
            self.phase = (step * t0 as f64) % (2.0 * PI);
        }
        self.started = true;
        for i in 0..l.len().min(r.len()) {
            if (t0 + i) % BLOCK == 0 {
                let t = (t0 + i) as f64 / self.sr;
                self.now = (self.depth.at(t).clamp(0.0, 1.0), self.mix.at(t).clamp(0.0, 1.0));
            }
            let (depth, mix) = self.now;
            let x = [l[i] as f64, r[i] as f64];
            self.buf[0][self.w] = x[0];
            self.buf[1][self.w] = x[1];
            let lfo = [self.phase.sin(), (self.phase - PI * self.spread).sin()];
            let wet = [self.read(0, base + sweep * depth * lfo[0]), self.read(1, base + sweep * depth * lfo[1])];
            l[i] = (x[0] * (1.0 - mix) + wet[0] * mix) as f32;
            r[i] = (x[1] * (1.0 - mix) + wet[1] * mix) as f32;
            self.w = (self.w + 1) % n;
            self.phase = (self.phase + step) % (2.0 * PI);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fx::tremolo::correlation;

    fn tone(sr: f64, n: usize) -> Vec<f32> {
        (0..n).map(|i| {
            let t = i as f64 / sr;
            (0.3 * (2.0 * PI * 220.0 * t).sin() + 0.2 * (2.0 * PI * 330.0 * t).sin() + 0.1 * (2.0 * PI * 1250.0 * t).sin()) as f32
        }).collect()
    }

    #[test]
    fn widens_a_mono_source_and_runs_the_same_in_blocks() {
        let sr = 48000.0;
        let x = tone(sr, 48000);
        let run = |spread: f64, block: usize| {
            let (mut l, mut r) = (x.clone(), x.clone());
            let mut c = Chorus::new(0.8, &Param::Value(0.7), &Param::Value(0.5), spread, sr);
            for (k, (a, b)) in l.chunks_mut(block).zip(r.chunks_mut(block)).enumerate() {
                c.pair(a, b, k * block);
            }
            (l, r)
        };
        let (l, r) = run(0.0, 48000);
        assert!(correlation(&l, &r) > 0.9999, "spread 0 keeps a mono source mono");
        let (l, r) = run(1.0, 48000);
        let c = correlation(&l, &r);
        assert!(c < 0.85, "spread 1 widens a mono source: correlation {c}");
        let (lb, rb) = run(1.0, 333);
        let diff = l.iter().zip(&lb).chain(r.iter().zip(&rb)).map(|(a, b)| (a - b).abs()).fold(0f32, f32::max);
        assert!(diff < 1e-6, "block-by-block differs by {diff}");
        // Mix 0 is the dry signal.
        let (mut l, mut r) = (x.clone(), x.clone());
        Chorus::new(0.8, &Param::Value(1.0), &Param::Value(0.0), 1.0, sr).pair(&mut l, &mut r, 0);
        assert!(l.iter().zip(&x).all(|(a, b)| (a - b).abs() < 1e-7));
    }
}
