//! A record's surface, for the tape effect (tapefx.rs): `hiss`, a soft noise bed, and `crackle`, the ticks
//! and the odd pop of a played record. Both are absolute levels, not following the music: at 1 the hiss sits
//! near -34 dBFS RMS and the loudest pops near -12 dBFS. Every random draw is keyed by the frame and the
//! channel, so a block-by-block render, a whole one and a re-render are the same sound (preview = export).
//! Ticks land on each channel apart (the image stays wide); pops land on both, a little louder on one side.

use std::f64::consts::PI;

/// Ticks per second per channel at `crackle` 1, and pops per second.
const TICKS: f64 = 34.0;
const POPS: f64 = 0.9;

pub(crate) struct Surface {
    sr: f64,
    tick_decay: f64,
    pop_decay: f64,
    hiss_lp_a: f64,
    hp_a: f64,
    ch: Vec<Chan>,
}

#[derive(Clone, Default)]
struct Chan {
    tick: f64,
    pop: f64,
    hiss_lp: f64,
    hp_in: f64,
    hp_out: f64,
}

impl Surface {
    pub fn new(channels: usize, sr: f64) -> Self {
        let decay = |seconds: f64| (-1.0 / (seconds * sr)).exp();
        let lp = |hz: f64| 1.0 - (-2.0 * PI * hz / sr).exp();
        Surface { sr, tick_decay: decay(0.00025), pop_decay: decay(0.0014), hiss_lp_a: lp(7000.0), hp_a: (-2.0 * PI * 180.0 / sr).exp(), ch: vec![Chan::default(); channels] }
    }

    /// The surface's sample at frame `g` on channel `c` (0 when both amounts are 0).
    pub fn at(&mut self, g: usize, c: usize, hiss: f64, crackle: f64) -> f64 {
        if hiss <= 0.0 && crackle <= 0.0 && self.ch[c].tick.abs() + self.ch[c].pop.abs() < 1e-9 {
            return 0.0;
        }
        let (sr, s) = (self.sr, &mut self.ch[c]);
        let noise = 2.0 * rand(g, c as u64, 1) - 1.0;
        if crackle > 0.0 {
            if rand(g, c as u64, 2) < crackle * TICKS / sr {
                // A heavy tail: most ticks are faint, a few are sharp.
                s.tick += 0.22 * crackle.sqrt() * rand(g, c as u64, 3).powi(4) * sign(g, c as u64);
            }
            if rand(g, 99, 4) < crackle * POPS / sr {
                let side = 0.75 + 0.25 * rand(g, c as u64, 5);
                s.pop += 0.25 * crackle.sqrt() * (0.4 + 0.6 * rand(g, 99, 6)) * side * sign(g, 99);
            }
        }
        let burst = s.tick * noise.abs() + s.pop * (0.6 + 0.4 * noise);
        s.tick *= self.tick_decay;
        s.pop *= self.pop_decay;
        s.hiss_lp += self.hiss_lp_a * (noise - s.hiss_lp);
        let x = burst + 0.05 * hiss * s.hiss_lp;
        // Above the lows: the surface is no rumble, and no step is left behind.
        s.hp_out = self.hp_a * (s.hp_out + x - s.hp_in);
        s.hp_in = x;
        s.hp_out
    }
}

fn sign(g: usize, c: u64) -> f64 {
    if rand(g, c, 7) < 0.5 { -1.0 } else { 1.0 }
}

/// A uniform number in [0, 1) from the frame, the channel and what it is for (splitmix64).
fn rand(g: usize, c: u64, salt: u64) -> f64 {
    let mut z = (g as u64).wrapping_mul(0x9E37_79B9_7F4A_7C15) ^ c.wrapping_mul(0xD1B5_4A32_D192_ED03) ^ salt.wrapping_mul(0x94D0_49BB_1331_11EB);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^= z >> 31;
    (z >> 11) as f64 / (1u64 << 53) as f64
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_sound_in_any_blocks_and_silent_at_zero() {
        let sr = 48000.0;
        let run = |split: usize| {
            let mut s = Surface::new(2, sr);
            let mut out = vec![];
            for start in (0..24000).step_by(split) {
                for g in start..(start + split).min(24000) {
                    out.push((s.at(g, 0, 0.5, 0.6), s.at(g, 1, 0.5, 0.6)));
                }
            }
            out
        };
        assert_eq!(run(512), run(24000));
        let out = run(24000);
        let rms = (out.iter().map(|(l, _)| l * l).sum::<f64>() / out.len() as f64).sqrt();
        assert!(rms > 1e-4 && rms < 0.05, "{rms}");
        let same = out.iter().filter(|(l, r)| (l - r).abs() < 1e-12).count();
        assert!(same < out.len() / 10, "left and right are independent");
        let mut quiet = Surface::new(1, sr);
        assert!((0..4800).all(|g| quiet.at(g, 0, 0.0, 0.0) == 0.0));
    }
}
