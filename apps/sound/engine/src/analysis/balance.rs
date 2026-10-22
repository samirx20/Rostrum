//! A mix's balance, measured for the readout (agents cannot hear): energy per band — the same bands
//! as `analyze` (sub, bass, lowMid, mid, high) — over where a track sounds, and its level in the
//! speech band (300 Hz – 3.4 kHz) every 100 ms, so TypeScript can tell when a voice is masked by the
//! bed, a lead is buried, or a mix is heavy in the lows or dull on top (src/engine/sound/checks/balance.ts).

use crate::fx::eq::{biquad, Coeffs};

pub const BANDS: [(&str, f64, f64); 5] = [("sub", 20.0, 60.0), ("bass", 60.0, 250.0), ("lowMid", 250.0, 1000.0), ("mid", 1000.0, 4000.0), ("high", 4000.0, 16000.0)];
/// The speech band's step (seconds).
pub const SPEECH_STEP: f64 = 0.1;

/// A band-pass (two high-passes at `lo`, two low-passes at `hi`: 24 dB / octave each side) with its state.
struct Band {
    stages: [Coeffs; 4],
    z: [[f64; 2]; 4],
}

impl Band {
    fn new(lo: f64, hi: f64, sr: f64) -> Band {
        Band { stages: [biquad("highpass", lo, 0.0, 0.707, sr), biquad("highpass", lo, 0.0, 0.707, sr), biquad("lowpass", hi, 0.0, 0.707, sr), biquad("lowpass", hi, 0.0, 0.707, sr)], z: [[0.0; 2]; 4] }
    }

    fn run(&mut self, x: f64) -> f64 {
        let mut y = x;
        for (s, zz) in self.stages.iter().zip(self.z.iter_mut()) {
            y = s.tick(zz, y);
        }
        y
    }
}

/// One band's level over the sounding frames: its filter, and the energy and frames summed so far.
struct Level {
    band: Band,
    sum: f64,
    n: usize,
}

/// A mean power in dB, to a tenth (−140 for silence): what every readout reports.
pub fn db(power: f64) -> f64 {
    if power > 1e-14 { ((10.0 * power.log10()) * 10.0).round() / 10.0 } else { -140.0 }
}

/// A signal's balance measured as it comes, block by block (a track or the mix read from disk): the mono sum,
/// energy per band over the 10 ms frames where it sounds (above −50 dBFS) and, when asked, the speech band's level
/// every 100 ms. The same figures, bit for bit, however the signal is cut into blocks.
pub struct Balance {
    frame: usize,
    floor: f64,
    /// Mono samples not yet in a whole frame.
    pending: Vec<f64>,
    levels: Vec<Level>,
    speech: Option<Speech>,
}

struct Speech {
    band: Band,
    step: usize,
    /// The filtered samples of the current step.
    part: Vec<f64>,
    out: Vec<f64>,
}

impl Balance {
    pub fn new(sr: f64, speech: bool) -> Balance {
        let levels = BANDS.iter().map(|&(_, lo, hi)| Level { band: Band::new(lo, hi.min(sr * 0.45), sr), sum: 0.0, n: 0 }).collect();
        let speech = speech.then(|| Speech { band: Band::new(300.0, 3400.0, sr), step: (sr * SPEECH_STEP).round().max(1.0) as usize, part: vec![], out: vec![] });
        Balance { frame: (sr * 0.01).round().max(1.0) as usize, floor: 10f64.powf(-50.0 / 10.0), pending: vec![], levels, speech }
    }

    /// The next frames of a stereo signal (left, right).
    pub fn push(&mut self, l: &[f32], r: &[f32]) {
        self.pending.extend(l.iter().zip(r).map(|(a, b)| (*a as f64 + *b as f64) * 0.5));
        let whole = self.pending.len() / self.frame * self.frame;
        if whole > 0 {
            let rest = self.pending.split_off(whole);
            let done = std::mem::replace(&mut self.pending, rest);
            self.frames(&done);
        }
    }

    /// Whole frames (and a last short one), each band on its own core.
    fn frames(&mut self, m: &[f64]) {
        let (frame, floor) = (self.frame, self.floor);
        let sounding: Vec<bool> = m.chunks(frame).map(|c| c.iter().map(|x| x * x).sum::<f64>() / c.len() as f64 > floor).collect();
        let sounding = &sounding;
        std::thread::scope(|s| {
            for lv in self.levels.iter_mut() {
                s.spawn(move || {
                    for (f, c) in m.chunks(frame).enumerate() {
                        let y: Vec<f64> = c.iter().map(|&x| lv.band.run(x)).collect();
                        if sounding[f] {
                            lv.sum += y.iter().map(|x| x * x).sum::<f64>();
                            lv.n += y.len();
                        }
                    }
                });
            }
            if let Some(sp) = &mut self.speech {
                s.spawn(move || {
                    for &x in m {
                        let y = sp.band.run(x);
                        sp.part.push(y);
                        if sp.part.len() == sp.step {
                            sp.out.push(db(sp.part.iter().map(|x| x * x).sum::<f64>() / sp.part.len() as f64));
                            sp.part.clear();
                        }
                    }
                });
            }
        });
    }

    /// The bands (dB) and the speech band's levels (empty when not asked).
    pub fn finish(mut self) -> ([f64; 5], Vec<f64>) {
        let rest = std::mem::take(&mut self.pending);
        if !rest.is_empty() {
            self.frames(&rest);
        }
        let mut bands = [-140.0; 5];
        for (k, lv) in self.levels.iter().enumerate() {
            bands[k] = if lv.n > 0 { db(lv.sum / lv.n as f64) } else { -140.0 };
        }
        let speech = self.speech.map_or(vec![], |mut sp| {
            if !sp.part.is_empty() {
                sp.out.push(db(sp.part.iter().map(|x| x * x).sum::<f64>() / sp.part.len() as f64));
            }
            sp.out
        });
        (bands, speech)
    }
}

fn measure(l: &[f32], r: &[f32], total: usize, sr: f64, speech: bool) -> ([f64; 5], Vec<f64>) {
    let n = total.min(l.len()).min(r.len());
    let mut b = Balance::new(sr, speech);
    b.push(&l[..n], &r[..n]);
    b.finish()
}

/// Energy per band (dB, mean power) over the 10 ms frames where the signal sounds (above −50 dBFS).
pub fn bands(l: &[f32], r: &[f32], total: usize, sr: f64) -> [f64; 5] {
    measure(l, r, total, sr, false).0
}

/// The speech band's level (dB) every 100 ms.
#[cfg(test)]
pub fn speech(l: &[f32], r: &[f32], total: usize, sr: f64) -> Vec<f64> {
    measure(l, r, total, sr, true).1
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_low_tone_lands_in_the_bass_band_and_a_high_one_up_top() {
        let sr = 44100.0;
        let tone = |hz: f64| -> Vec<f32> { (0..44100).map(|i| (0.5 * (2.0 * std::f64::consts::PI * hz * i as f64 / sr).sin()) as f32).collect() };
        let low = tone(110.0);
        let b = bands(&low, &low, low.len(), sr);
        assert!(b[1] > b[3] + 30.0, "{b:?}");
        let high = tone(6000.0);
        let b = bands(&high, &high, high.len(), sr);
        assert!(b[4] > b[1] + 30.0, "{b:?}");
        let s = speech(&high, &high, high.len(), sr);
        assert_eq!(s.len(), 10);
    }
}
