//! The surround panner: a track's stereo signal (after its inserts) placed in the bed (bed/mod.rs). A
//! position is an object's — azimuth, elevation, distance — plus its spread, its centre share and an
//! LFE send, each a number or an envelope over song time (the effects' Param), so a sound can fly
//! around the room. TypeScript resolved every default (src/core/soundDsl/soundtrack/surround.ts).
//!
//! - Direction: VBAP over the ring's adjacent speaker pair (Pulkki 1997; tangent law, power-normalised),
//!   an equal-power sine law across a gap wider than 180° (stereo's back).
//! - Spread: the input's left channel covers the left half of an arc 360°·spread wide centred on the
//!   azimuth, the right channel the right half (MDAP: the power mean of VBAP gains every 5° of the arc).
//!   Where the two halves overlap their coherent sum is normalised (1/√(1+ρ)), so a mono source keeps
//!   its loudness at any spread and folds down to the stereo pan law's level.
//! - `centre` 0 … 1: how much of the front image the centre speaker takes (0: a phantom between L/R).
//! - A flat bed has no height: elevation widens the source (overhead is all around) and is kept for an
//!   object export later (ADM). Distance: 1 is the speaker ring; beyond, the level falls as 1/d and the
//!   air dulls the highs (a one-pole at 20 kHz/d); inside, the source widens around the listener.
//! - LFE: a send of the input's sum through a 120 Hz 4th-order low-pass, the mains untouched.

use serde::Deserialize;

use crate::bed::Layout;
use crate::fx::eq::biquad;
use crate::mix::schedule::Param;

#[derive(Deserialize, Clone, Debug)]
pub struct Surround {
    pub az: Param,
    pub el: Param,
    pub dist: Param,
    pub spread: Param,
    pub lfe: Param,
    pub centre: Param,
}

const BLOCK: usize = 32;

/// VBAP gains of one direction (degrees) over the main speakers (the centre left out when `centre` is false).
fn point(layout: Layout, az: f64, centre: bool) -> Vec<f64> {
    let sp = layout.speakers();
    let mut ring: Vec<(f64, usize)> = sp.iter().enumerate().filter_map(|(i, s)| s.az.filter(|&a| centre || a != 0.0 || layout == Layout::Stereo).map(|a| (a, i))).collect();
    ring.sort_by(|a, b| a.0.total_cmp(&b.0));
    let mut g = vec![0.0; sp.len()];
    let th = (az + 180.0).rem_euclid(360.0) - 180.0;
    let k = ring.iter().rposition(|&(a, _)| a <= th).unwrap_or(ring.len() - 1);
    let (a1, i1) = ring[k];
    let (mut a2, i2) = ring[(k + 1) % ring.len()];
    let th = if th < a1 { th + 360.0 } else { th };
    if a2 <= a1 {
        a2 += 360.0;
    }
    let span = a2 - a1;
    let (g1, g2) = if span < 180.0 {
        let r = |d: f64| d.to_radians().sin();
        (r(a2 - th) / r(span), r(th - a1) / r(span))
    } else {
        let f = (th - a1) / span * std::f64::consts::FRAC_PI_2;
        (f.cos(), f.sin())
    };
    let n = (g1 * g1 + g2 * g2).sqrt().max(1e-12);
    g[i1] += g1 / n;
    g[i2] += g2 / n;
    g
}

/// Power-mean gains over an arc [a, b] (degrees), the centre blended in by `centre`.
fn arc(layout: Layout, a: f64, b: f64, centre: f64) -> Vec<f64> {
    let k = (((b - a) / 5.0).ceil() as usize).max(0) + 1;
    let mut acc = vec![0.0; layout.channels()];
    for p in 0..k {
        let az = if k == 1 { a } else { a + (b - a) * p as f64 / (k - 1) as f64 };
        let (with, without) = (point(layout, az, true), point(layout, az, false));
        for c in 0..acc.len() {
            acc[c] += centre * with[c] * with[c] + (1.0 - centre) * without[c] * without[c];
        }
    }
    acc.iter().map(|v| (v / k as f64).sqrt()).collect()
}

/// The gain matrix (per output channel: [from left, from right]) and the air cutoff at time `t`.
fn matrix(s: &Surround, vol: f64, layout: Layout, t: f64) -> (Vec<[f64; 2]>, Option<f64>) {
    let (el, dist) = (s.el.at(t).clamp(-90.0, 90.0), s.dist.at(t).clamp(0.0, 100.0));
    let mut spread = s.spread.at(t).clamp(0.0, 1.0);
    spread += (1.0 - spread) * el.to_radians().sin().abs();
    if dist < 1.0 {
        spread += (1.0 - spread) * (1.0 - dist);
    }
    let (az, w, centre) = (s.az.at(t), 360.0 * spread, s.centre.at(t).clamp(0.0, 1.0));
    let (gl, gr) = (arc(layout, az - w / 2.0, az, centre), arc(layout, az, az + w / 2.0, centre));
    let rho: f64 = gl.iter().zip(&gr).map(|(a, b)| a * b).sum();
    let k = vol / (1.0 + rho).sqrt() / dist.max(1.0);
    (gl.iter().zip(&gr).map(|(a, b)| [a * k, b * k]).collect(), (dist > 1.0).then(|| 20000.0 / dist))
}

/// The track's stereo signal placed in a bed of `layout`: one buffer per channel (the tests' whole-track form).
#[cfg(test)]
pub fn pan(l: &[f32], r: &[f32], s: &Surround, vol: &Param, layout: Layout, sr: f64) -> Vec<Vec<f32>> {
    Panner::new(s, vol, layout, sr).block(l, r, 0)
}

/// The panner over a track, block by block: its gains, its air filter and its LFE send carried between blocks.
pub struct Panner {
    s: Surround,
    vol: Param,
    layout: Layout,
    sr: f64,
    moving: bool,
    prev: Vec<[f64; 2]>,
    cut: Option<f64>,
    air: [f64; 2],
    lfe: Option<Lfe>,
}

struct Lfe {
    lp: crate::fx::eq::Coeffs,
    z1: [f64; 2],
    z2: [f64; 2],
    g: f64,
}

impl Panner {
    pub fn new(s: &Surround, vol: &Param, layout: Layout, sr: f64) -> Self {
        let moving = [&s.az, &s.el, &s.dist, &s.spread, &s.centre, vol].iter().any(|p| matches!(p, Param::Envelope(_)));
        let (prev, cut) = matrix(s, vol.at(0.0), layout, 0.0);
        // The LFE send: none when it is a constant 0.
        let lfe = (layout.lfe().is_some() && !matches!(s.lfe, Param::Value(v) if v <= 0.0))
            .then(|| Lfe { lp: biquad("lowpass", 120.0, 0.0, std::f64::consts::FRAC_1_SQRT_2, sr), z1: [0.0; 2], z2: [0.0; 2], g: 0.0 });
        Panner { s: s.clone(), vol: vol.clone(), layout, sr, moving, prev, cut, air: [0.0; 2], lfe }
    }

    /// Frames `t0 ..` of the track placed in the bed (`t0` a multiple of 32 but for the track's last block).
    pub fn block(&mut self, l: &[f32], r: &[f32], t0: usize) -> Vec<Vec<f32>> {
        let (n, sr, layout) = (l.len().min(r.len()), self.sr, self.layout);
        let mut out = vec![vec![0.0f32; n]; layout.channels()];
        for b in (0..n).step_by(BLOCK) {
            let end = (b + BLOCK).min(n);
            let te = (t0 + end) as f64 / sr;
            let (next, c) = if self.moving { matrix(&self.s, self.vol.at(te), layout, te) } else { (self.prev.clone(), self.cut) };
            let alpha = c.map(|f| 1.0 - (-2.0 * std::f64::consts::PI * f.min(sr * 0.45) / sr).exp());
            for i in b..end {
                let f = (i - b) as f64 / BLOCK as f64;
                let mut x = [l[i] as f64, r[i] as f64];
                if let Some(a) = alpha {
                    for ch in 0..2 {
                        self.air[ch] += a * (x[ch] - self.air[ch]);
                        x[ch] = self.air[ch];
                    }
                } else {
                    self.air = x;
                }
                for (ch, buf) in out.iter_mut().enumerate() {
                    let (p, q) = (self.prev[ch], next[ch]);
                    buf[i] = ((p[0] + (q[0] - p[0]) * f) * x[0] + (p[1] + (q[1] - p[1]) * f) * x[1]) as f32;
                }
            }
            (self.prev, self.cut) = (next, c);
        }
        if let (Some(k), Some(lfe)) = (layout.lfe(), &mut self.lfe) {
            // (left + right) / 2 × the send × the fader (and distance), through a 120 Hz low-pass (two Butterworth stages).
            for i in 0..n {
                if (t0 + i) % BLOCK == 0 {
                    let t = (t0 + i) as f64 / sr;
                    lfe.g = self.s.lfe.at(t).max(0.0) * self.vol.at(t) / self.s.dist.at(t).max(1.0);
                }
                let x = (l[i] as f64 + r[i] as f64) * 0.5 * lfe.g;
                out[k][i] += lfe.lp.tick(&mut lfe.z2, lfe.lp.tick(&mut lfe.z1, x)) as f32;
            }
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn at(az: f64) -> Surround {
        Surround { az: Param::Value(az), el: Param::Value(0.0), dist: Param::Value(1.0), spread: Param::Value(0.0), lfe: Param::Value(0.0), centre: Param::Value(1.0) }
    }
    fn power(out: &[Vec<f32>], i: usize) -> Vec<f64> {
        out.iter().map(|c| (c[i] as f64).powi(2)).collect()
    }

    #[test]
    fn a_speaker_direction_lands_on_that_speaker_alone() {
        let one = vec![0.5f32; 64];
        let lay = Layout::Surround51;
        for (az, ch) in [(0.0, 2), (-30.0, 0), (30.0, 1), (-110.0, 4), (110.0, 5)] {
            let out = pan(&one, &one, &at(az), &Param::Value(1.0), lay, 48000.0);
            let p = power(&out, 10);
            let total: f64 = p.iter().sum();
            assert!(p[ch] / total > 0.999, "az {az}: {p:?}");
            // A mono source keeps the stereo pan law's power (two channels at 0.5 each: 0.5).
            assert!((total - 0.5).abs() < 1e-6, "az {az}: {total}");
        }
    }

    #[test]
    fn between_speakers_the_power_is_kept_and_shared() {
        let one = vec![0.5f32; 64];
        for az in [-170.0, -60.0, 15.0, 70.0, 180.0] {
            let out = pan(&one, &one, &at(az), &Param::Value(1.0), Layout::Surround71, 48000.0);
            let p = power(&out, 10);
            assert!((p.iter().sum::<f64>() - 0.5).abs() < 1e-6, "{az}: {p:?}");
            assert!(p.iter().filter(|v| **v > 1e-6).count() == 2, "{az}: a pair: {p:?}");
        }
        // Without the centre, the front is a phantom between L and R.
        let out = pan(&one, &one, &Surround { centre: Param::Value(0.0), ..at(0.0) }, &Param::Value(1.0), Layout::Surround51, 48000.0);
        let p = power(&out, 10);
        assert!(p[2] < 1e-9 && (p[0] - p[1]).abs() < 1e-9, "{p:?}");
    }

    #[test]
    fn full_spread_surrounds_and_a_flight_moves_round_the_room() {
        let one = vec![0.5f32; 48000];
        let out = pan(&one, &one, &Surround { spread: Param::Value(1.0), ..at(0.0) }, &Param::Value(1.0), Layout::Surround51, 48000.0);
        let p = power(&out, 100);
        assert!([0, 1, 2, 4, 5].iter().all(|&c| p[c] > 0.03), "every main speaker: {p:?}");
        let fly = Surround { az: Param::Envelope(vec![[0.0, -110.0], [1.0, 110.0]]), ..at(0.0) };
        let out = pan(&one, &one, &fly, &Param::Value(1.0), Layout::Surround51, 48000.0);
        let loudest = |i: usize| power(&out, i).iter().enumerate().max_by(|a, b| a.1.total_cmp(b.1)).unwrap().0;
        assert_eq!([loudest(100), loudest(24000), loudest(47900)], [4, 2, 5], "Ls, then C at the midpoint, then Rs");
    }

    #[test]
    fn the_lfe_send_carries_only_the_lows() {
        let sr = 48000.0;
        let tone = |hz: f64| (0..48000).map(|i| (0.5 * (2.0 * std::f64::consts::PI * hz * i as f64 / sr).sin()) as f32).collect::<Vec<f32>>();
        let rms = |x: &[f32]| (x[24000..].iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / 24000.0).sqrt();
        let s = Surround { lfe: Param::Value(1.0), ..at(0.0) };
        let (low, high) = (tone(50.0), tone(1000.0));
        let lo = pan(&low, &low, &s, &Param::Value(1.0), Layout::Surround51, sr);
        let hi = pan(&high, &high, &s, &Param::Value(1.0), Layout::Surround51, sr);
        assert!(rms(&lo[3]) > 0.3, "50 Hz reaches the LFE: {}", rms(&lo[3]));
        assert!(rms(&hi[3]) < 0.01, "1 kHz does not: {}", rms(&hi[3]));
        assert!((rms(&hi[2]) - rms(&lo[2])).abs() < 0.01, "the mains are untouched");
    }
}
