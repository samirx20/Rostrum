//! Tape (the lo-fi sound): wow (a slow pitch drift, up to about ±15 cents) and flutter (a fast waver) from a
//! modulated delay, then saturation and a darker, thinner tone as `age` rises. Between blocks it keeps the last
//! block's input, which the delay reads back into (a delay of up to a block: wow far past any musical setting).

use std::f64::consts::PI;

use super::frames;
use super::state::Insert;
use crate::mix::schedule::Param;

pub(crate) struct TapeFx {
    wow: Param,
    flutter: Param,
    age: Param,
    sr: f64,
    lp: Vec<f64>,
    hp_in: Vec<f64>,
    hp_out: Vec<f64>,
    /// The previous block's input, per channel (it ends at this block's `t0`).
    hist: Vec<Vec<f32>>,
}

impl TapeFx {
    pub fn new(wow: &Param, flutter: &Param, age: &Param, channels: usize, sr: f64) -> Self {
        let z = vec![0.0f64; channels];
        TapeFx { wow: wow.clone(), flutter: flutter.clone(), age: age.clone(), sr, lp: z.clone(), hp_in: z.clone(), hp_out: z, hist: vec![vec![]; channels] }
    }
}

impl Insert for TapeFx {
    fn block(&mut self, chs: &mut [&mut [f32]], t0: usize) -> Result<(), String> {
        let (n, sr) = (frames(chs), self.sr);
        let src: Vec<Vec<f32>> = chs.iter().map(|c| c.to_vec()).collect();
        let base = 0.008 * sr;
        for i in 0..n {
            let g = t0 + i;
            let t = g as f64 / sr;
            let (w, f, a) = (self.wow.at(t), self.flutter.at(t), self.age.at(t));
            let d = base + sr * (w * 0.0025 * (2.0 * PI * 0.55 * t).sin() + w * 0.0012 * (2.0 * PI * 0.23 * t + 1.3).sin() + f * 0.00022 * (2.0 * PI * 6.3 * t).sin());
            let pos = g as f64 - d;
            let hist = &self.hist;
            // Frame `k` of the track: this block, else the last one, else silence.
            let at = |ch: usize, k: usize| -> f64 {
                if k >= t0 {
                    src[ch].get(k - t0).copied().unwrap_or(0.0) as f64
                } else {
                    let h = &hist[ch];
                    (t0 - k).checked_sub(1).and_then(|back| h.len().checked_sub(1 + back)).map_or(0.0, |j| h[j] as f64)
                }
            };
            let read = |ch: usize| {
                if pos < 0.0 {
                    return 0.0;
                }
                let k = pos.floor() as usize;
                let fr = pos - k as f64;
                at(ch, k) * (1.0 - fr) + at(ch, k + 1) * fr
            };
            let drive = 1.0 + 2.0 * a;
            let cut = 16000.0 * (1.0 - 0.75 * a);
            let alpha = 1.0 - (-2.0 * PI * cut / sr).exp();
            let hp_a = (-2.0 * PI * (25.0 + 70.0 * a) / sr).exp();
            for (ch, out) in chs.iter_mut().enumerate() {
                // Unity gain for quiet signals; loud ones round off.
                let x = (drive * read(ch)).tanh() / drive;
                self.lp[ch] += alpha * (x - self.lp[ch]);
                // A one-pole high-pass: tape loses the deepest lows.
                self.hp_out[ch] = hp_a * (self.hp_out[ch] + self.lp[ch] - self.hp_in[ch]);
                self.hp_in[ch] = self.lp[ch];
                out[i] = self.hp_out[ch] as f32;
            }
        }
        self.hist = src;
        Ok(())
    }
}
