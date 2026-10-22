//! The inserts besides EQ: a compressor linked across the channels with a soft knee, a delay (damped,
//! optionally ping-pong), a reverb insert, saturation and a peak limiter (tape: tapefx.rs). Each is a struct that
//! keeps its state between blocks (state.rs); the free functions (the tests') run one over a whole buffer.

use std::f64::consts::PI;

use super::frames;
use super::state::Insert;
use super::BLOCK;
use crate::bed::Layout;
use crate::fx::reverb::Reverb;
use crate::mix::schedule::Param;

/// A compressor linked across every channel (the loudest one's peak sets the gain all share).
pub(crate) struct Compressor {
    threshold: Param,
    ratio: Param,
    makeup: Param,
    knee: f64,
    att: f64,
    rel: f64,
    sr: f64,
    automated: bool,
    gr: f64, // gain reduction in dB (≥ 0)
    now: (f64, f64, f64),
}

impl Compressor {
    pub fn new(threshold: &Param, ratio: &Param, attack_ms: f64, release_ms: f64, makeup: &Param, knee: f64, sr: f64) -> Self {
        Compressor {
            att: (-1.0 / (attack_ms / 1000.0 * sr)).exp(),
            rel: (-1.0 / (release_ms / 1000.0 * sr)).exp(),
            automated: threshold.automated() || ratio.automated() || makeup.automated(),
            now: (threshold.at(0.0), ratio.at(0.0), makeup.at(0.0)),
            threshold: threshold.clone(),
            ratio: ratio.clone(),
            makeup: makeup.clone(),
            knee,
            sr,
            gr: 0.0,
        }
    }
}

impl Insert for Compressor {
    fn block(&mut self, chs: &mut [&mut [f32]], t0: usize) -> Result<(), String> {
        for i in 0..frames(chs) {
            if self.automated && (t0 + i) % BLOCK == 0 {
                let t = (t0 + i) as f64 / self.sr;
                self.now = (self.threshold.at(t), self.ratio.at(t), self.makeup.at(t));
            }
            let (th, ra, mk) = self.now;
            let peak = (chs.iter().fold(0.0f32, |m, c| m.max(c[i].abs())) as f64).max(1e-9);
            let over = 20.0 * peak.log10() - th;
            let knee = self.knee;
            // Soft knee: a quadratic blend over `knee` dB around the threshold.
            let target = if knee > 0.0 && over.abs() <= knee / 2.0 {
                (1.0 - 1.0 / ra) * (over + knee / 2.0).powi(2) / (2.0 * knee)
            } else if over > 0.0 {
                over * (1.0 - 1.0 / ra)
            } else {
                0.0
            };
            let c = if target > self.gr { self.att } else { self.rel };
            self.gr = c * self.gr + (1.0 - c) * target;
            let g = 10f64.powf((mk - self.gr) / 20.0) as f32;
            for c in chs.iter_mut() {
                c[i] *= g;
            }
        }
        Ok(())
    }
}

#[cfg(test)]
pub(crate) fn compressor(threshold: &Param, ratio: &Param, attack_ms: f64, release_ms: f64, makeup: &Param, knee: f64, chs: &mut [&mut [f32]], sr: f64) {
    let _ = Compressor::new(threshold, ratio, attack_ms, release_ms, makeup, knee, sr).block(chs, 0);
}

/// A delay on a left/right pair (ping-pong bounces inside the pair); a lone channel echoes itself.
pub(crate) struct Delay {
    feedback: Param,
    mix: Param,
    ping_pong: bool,
    alpha: f64,
    sr: f64,
    buf: [Vec<f64>; 2],
    lp: [f64; 2],
    w: usize,
}

impl Delay {
    pub fn new(time: f64, feedback: &Param, mix: &Param, ping_pong: bool, damp: f64, sr: f64) -> Self {
        let n = ((time * sr).round() as usize).max(1);
        let alpha = (1.0 / sr) / (1.0 / (2.0 * PI * damp) + 1.0 / sr);
        Delay { feedback: feedback.clone(), mix: mix.clone(), ping_pong, alpha, sr, buf: [vec![0.0; n], vec![0.0; n]], lp: [0.0; 2], w: 0 }
    }

    pub fn pair(&mut self, l: &mut [f32], r: &mut [f32], t0: usize) {
        let n = self.buf[0].len();
        for i in 0..l.len() {
            let t = (t0 + i) as f64 / self.sr;
            let (fb, m) = (self.feedback.at(t), self.mix.at(t));
            let w = self.w;
            let wet = [self.buf[0][w], self.buf[1][w]];
            for ch in 0..2 {
                self.lp[ch] += self.alpha * (wet[ch] - self.lp[ch]);
            }
            let x = [l[i] as f64, r[i] as f64];
            if self.ping_pong {
                // Left feeds the right line and right the left: echoes bounce across.
                self.buf[0][w] = x[0] + fb * self.lp[1];
                self.buf[1][w] = fb * self.lp[0];
            } else {
                self.buf[0][w] = x[0] + fb * self.lp[0];
                self.buf[1][w] = x[1] + fb * self.lp[1];
            }
            l[i] = (x[0] + wet[0] * m) as f32;
            r[i] = (x[1] + wet[1] * m) as f32;
            self.w = (w + 1) % n;
        }
    }
}

#[cfg(test)]
pub(crate) fn delay(time: f64, feedback: &Param, mix: &Param, ping_pong: bool, damp: f64, l: &mut [f32], r: &mut [f32], sr: f64) {
    Delay::new(time, feedback, mix, ping_pong, damp, sr).pair(l, r, 0);
}

/// A reverb insert over the bed's mains (reverb.rs; the LFE stays dry), blended by `mix`.
pub(crate) struct ReverbInsert {
    rv: Reverb,
    mains: Vec<usize>,
    mix: Param,
    sr: f64,
    y: Vec<f64>,
}

impl ReverbInsert {
    pub fn new(space: &str, mix: &Param, shape: crate::fx::reverb::Shape, channels: usize, layout: Layout, sr: f64) -> Self {
        let mains: Vec<usize> = (0..channels).filter(|&c| channels == 2 || Some(c) != layout.lfe()).collect();
        ReverbInsert { rv: Reverb::shaped(space, 1.0, sr, mains.len(), shape), y: vec![0.0; mains.len()], mains, mix: mix.clone(), sr }
    }
}

impl Insert for ReverbInsert {
    fn block(&mut self, chs: &mut [&mut [f32]], t0: usize) -> Result<(), String> {
        for i in 0..frames(chs) {
            let m = self.mix.at((t0 + i) as f64 / self.sr);
            for (k, &c) in self.mains.iter().enumerate() {
                self.y[k] = chs[c][i] as f64;
            }
            self.rv.process_n(&mut self.y);
            for (k, &c) in self.mains.iter().enumerate() {
                chs[c][i] = (chs[c][i] as f64 * (1.0 - m) + self.y[k] * m) as f32;
            }
        }
        Ok(())
    }
}

pub(crate) struct Saturate {
    pub drive: Param,
    pub mix: Param,
    pub sr: f64,
}

impl Insert for Saturate {
    fn block(&mut self, chs: &mut [&mut [f32]], t0: usize) -> Result<(), String> {
        for i in 0..frames(chs) {
            let t = (t0 + i) as f64 / self.sr;
            let (d, m) = (self.drive.at(t), self.mix.at(t));
            for buf in chs.iter_mut() {
                buf[i] = saturated(buf[i] as f64, d, m) as f32;
            }
        }
        Ok(())
    }
}

/// One sample through the saturator: drive `d`, wet mix `m` (the live layers use it too).
pub(crate) fn saturated(x: f64, d: f64, m: f64) -> f64 {
    x * (1.0 - m) + (d * x).tanh() / d.tanh() * m
}

/// A peak limiter linked across every channel: the gain drops at once to keep peaks under the
/// ceiling and recovers over `release`.
pub(crate) struct Limiter {
    ceiling: f64,
    rel: f64,
    g: f64,
}

impl Limiter {
    pub fn new(ceiling_db: f64, release_ms: f64, sr: f64) -> Self {
        Limiter { ceiling: 10f64.powf(ceiling_db / 20.0), rel: (-1.0 / (release_ms / 1000.0 * sr)).exp(), g: 1.0 }
    }
}

impl Insert for Limiter {
    fn block(&mut self, chs: &mut [&mut [f32]], _t0: usize) -> Result<(), String> {
        let (ceiling, rel) = (self.ceiling, self.rel);
        for i in 0..frames(chs) {
            let peak = (chs.iter().fold(0.0f32, |m, c| m.max(c[i].abs())) as f64).max(1e-9);
            let need = (ceiling / peak).min(1.0);
            self.g = if need < self.g { need } else { rel * self.g + (1.0 - rel) * need };
            for c in chs.iter_mut() {
                c[i] = ((c[i] as f64 * self.g).clamp(-ceiling, ceiling)) as f32;
            }
        }
        Ok(())
    }
}

#[cfg(test)]
pub(crate) fn limiter(ceiling_db: f64, release_ms: f64, chs: &mut [&mut [f32]], sr: f64) {
    let _ = Limiter::new(ceiling_db, release_ms, sr).block(chs, 0);
}
