//! Stereo width (src/core/soundDsl/soundtrack/effects.ts `{ type: "width" }`): the mid / side balance of a
//! pair — 0 folds it to mono, 1 leaves it, up to 2 widens — with the side signal high-passed at
//! `monoBelow` Hz so the low end stays centred (a mix's bass and kick).

use crate::mix::schedule::Param;

/// One pair's width, its side low-pass kept between blocks (fx/state.rs).
pub struct Width {
    amount: Param,
    mono_below: f64,
    a: f64,
    sr: f64,
    lp: f64,
    w: f64,
}

impl Width {
    pub fn new(amount: &Param, mono_below: f64, sr: f64) -> Self {
        let a = if mono_below > 0.0 { (-2.0 * std::f64::consts::PI * mono_below / sr).exp() } else { 0.0 };
        Width { amount: amount.clone(), mono_below, a, sr, lp: 0.0, w: amount.at(0.0) }
    }

    pub fn pair(&mut self, l: &mut [f32], r: &mut [f32], t0: usize) {
        let a = self.a;
        for i in 0..l.len().min(r.len()) {
            if (t0 + i) % 32 == 0 {
                self.w = self.amount.at((t0 + i) as f64 / self.sr);
            }
            let w = self.w;
            let (m, s) = ((l[i] as f64 + r[i] as f64) * 0.5, (l[i] as f64 - r[i] as f64) * 0.5);
            // The side's lows (one-pole low-pass) stay as they are when widening and fold away when narrowing.
            self.lp = (1.0 - a) * s + a * self.lp;
            let lp = self.lp;
            let side = if self.mono_below > 0.0 { (s - lp) * w + lp * w.min(1.0) } else { s * w };
            l[i] = (m + side) as f32;
            r[i] = (m - side) as f32;
        }
    }
}

#[cfg(test)]
pub fn width(amount: &Param, mono_below: f64, l: &mut [f32], r: &mut [f32], sr: f64) {
    Width::new(amount, mono_below, sr).pair(l, r, 0);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_is_mono_one_is_unchanged_and_two_widens() {
        let sr = 44100.0;
        let tone = |f: f64, p: f64| (0..4410).map(|i| (2.0 * std::f64::consts::PI * f * i as f64 / sr + p).sin() as f32).collect::<Vec<f32>>();
        let (l0, r0) = (tone(2000.0, 0.0), tone(2000.0, 1.0));
        let side = |l: &[f32], r: &[f32]| l.iter().zip(r).map(|(a, b)| ((a - b) as f64).powi(2)).sum::<f64>();
        let run = |w: f64| { let (mut l, mut r) = (l0.clone(), r0.clone()); width(&Param::Value(w), 0.0, &mut l, &mut r, sr); (l, r) };
        let (l, r) = run(0.0);
        assert!(side(&l, &r) < 1e-9);
        let (l, r) = run(1.0);
        assert!((side(&l, &r) - side(&l0, &r0)).abs() < 1e-6);
        let (l, r) = run(2.0);
        assert!(side(&l, &r) > 3.5 * side(&l0, &r0));
        // Lows stay centred when widening with monoBelow.
        let (mut l, mut r) = (tone(50.0, 0.0), tone(50.0, 0.5));
        let before = side(&l, &r);
        width(&Param::Value(2.0), 200.0, &mut l, &mut r, sr);
        assert!(side(&l, &r) < 1.3 * before, "a 50 Hz side is not widened under monoBelow 200");
    }
}
