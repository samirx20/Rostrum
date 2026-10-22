//! EQ bands: RBJ cookbook biquads (transposed direct form II), their coefficients re-evaluated every
//! 32 samples when automated (balance, panner, dialogue repairs and the sampler use the same filters).

use std::f64::consts::PI;

use super::state::Insert;
use super::{frames, BLOCK};
use crate::mix::schedule::EqBand;

#[derive(Clone, Copy, Default)]
pub(crate) struct Coeffs {
    b0: f64,
    b1: f64,
    b2: f64,
    a1: f64,
    a2: f64,
}

impl Coeffs {
    /// One sample through the filter with state `z` (transposed direct form II).
    pub(crate) fn tick(&self, z: &mut [f64; 2], x: f64) -> f64 {
        let y = self.b0 * x + z[0];
        z[0] = self.b1 * x - self.a1 * y + z[1];
        z[1] = self.b2 * x - self.a2 * y;
        y
    }

    /// Filters a buffer in place (transposed direct form II, fresh state).
    pub(crate) fn run(&self, x: &mut [f32]) {
        let mut z = [0.0f64; 2];
        for v in x.iter_mut() {
            *v = self.tick(&mut z, *v as f64) as f32;
        }
    }
}

/// RBJ cookbook biquad coefficients (normalized by a0).
pub(crate) fn biquad(shape: &str, f: f64, gain_db: f64, q: f64, sr: f64) -> Coeffs {
    let w0 = 2.0 * PI * f.clamp(10.0, sr * 0.49) / sr;
    let (cs, sn) = (w0.cos(), w0.sin());
    let alpha = sn / (2.0 * q.max(0.05));
    let a = 10f64.powf(gain_db / 40.0);
    let sa = a.sqrt();
    let (b0, b1, b2, a0, a1, a2) = match shape {
        "lowpass" => ((1.0 - cs) / 2.0, 1.0 - cs, (1.0 - cs) / 2.0, 1.0 + alpha, -2.0 * cs, 1.0 - alpha),
        "highpass" => ((1.0 + cs) / 2.0, -(1.0 + cs), (1.0 + cs) / 2.0, 1.0 + alpha, -2.0 * cs, 1.0 - alpha),
        "notch" => (1.0, -2.0 * cs, 1.0, 1.0 + alpha, -2.0 * cs, 1.0 - alpha),
        "lowshelf" => (
            a * ((a + 1.0) - (a - 1.0) * cs + 2.0 * sa * alpha),
            2.0 * a * ((a - 1.0) - (a + 1.0) * cs),
            a * ((a + 1.0) - (a - 1.0) * cs - 2.0 * sa * alpha),
            (a + 1.0) + (a - 1.0) * cs + 2.0 * sa * alpha,
            -2.0 * ((a - 1.0) + (a + 1.0) * cs),
            (a + 1.0) + (a - 1.0) * cs - 2.0 * sa * alpha,
        ),
        "highshelf" => (
            a * ((a + 1.0) + (a - 1.0) * cs + 2.0 * sa * alpha),
            -2.0 * a * ((a - 1.0) + (a + 1.0) * cs),
            a * ((a + 1.0) + (a - 1.0) * cs - 2.0 * sa * alpha),
            (a + 1.0) - (a - 1.0) * cs + 2.0 * sa * alpha,
            2.0 * ((a - 1.0) - (a + 1.0) * cs),
            (a + 1.0) - (a - 1.0) * cs - 2.0 * sa * alpha,
        ),
        _ => (1.0 + alpha * a, -2.0 * cs, 1.0 - alpha * a, 1.0 + alpha / a, -2.0 * cs, 1.0 - alpha / a), // peak
    };
    Coeffs { b0: b0 / a0, b1: b1 / a0, b2: b2 / a0, a1: a1 / a0, a2: a2 / a0 }
}

/// The EQ bands with their filter memory, kept between blocks (state.rs).
pub(crate) struct Eq {
    bands: Vec<(EqBand, bool, Coeffs, Vec<[f64; 2]>)>,
    sr: f64,
}

impl Eq {
    pub fn new(bands: &[EqBand], channels: usize, sr: f64) -> Self {
        let bands = bands
            .iter()
            .map(|b| {
                let automated = b.freq.automated() || b.gain.automated() || b.q.automated();
                (b.clone(), automated, biquad(&b.shape, b.freq.at(0.0), b.gain.at(0.0), b.q.at(0.0), sr), vec![[0.0f64; 2]; channels])
            })
            .collect();
        Eq { bands, sr }
    }
}

impl Insert for Eq {
    fn block(&mut self, chs: &mut [&mut [f32]], t0: usize) -> Result<(), String> {
        let (n, sr) = (frames(chs), self.sr);
        for (band, automated, c, z) in self.bands.iter_mut() {
            // Transposed direct form II, per channel.
            for i in 0..n {
                if *automated && (t0 + i) % BLOCK == 0 {
                    let t = (t0 + i) as f64 / sr;
                    *c = biquad(&band.shape, band.freq.at(t), band.gain.at(t), band.q.at(t), sr);
                }
                for (ch, buf) in chs.iter_mut().enumerate() {
                    buf[i] = c.tick(&mut z[ch], buf[i] as f64) as f32;
                }
            }
        }
        Ok(())
    }
}

#[cfg(test)]
pub(crate) fn eq(bands: &[EqBand], chs: &mut [&mut [f32]], sr: f64) {
    let _ = Eq::new(bands, chs.len(), sr).block(chs, 0);
}
