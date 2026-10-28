//! Effects: the insert chain over any bed (chain.rs) and its inserts — EQ (eq.rs), compressor, delay,
//! reverb, saturation, tape (tapefx.rs, with a record's surface: vinyl.rs) and limiter (inserts.rs), stereo width (stereo.rs), convolution (convolve.rs),
//! the dialogue repairs (dialogue/) and plugins — the track and clip processing ported from the TS
//! mixdown (dsp.rs: tone, fades, the reverb), the mastering stage (master.rs), the tone match
//! (matcheq.rs) and a live layer's inserts (livefx.rs). Parameters may be envelopes over time;
//! automated parameters are re-evaluated every 32 samples (coefficients included), constants once.

pub mod chain;
pub mod convolve;
pub mod dsp;
pub mod eq;
pub mod inserts;
pub mod livefx;
pub mod master;
pub mod matcheq;
pub mod reverb;
pub mod state;
pub mod stereo;
pub mod tapefx;
pub mod vinyl;
#[cfg(test)]
mod tests;

use crate::mix::schedule::Param;

const BLOCK: usize = 32;

impl Param {
    /// The value at time `t` (seconds): constant, or straight lines between points, held at the ends.
    pub fn at(&self, t: f64) -> f64 {
        match self {
            Param::Value(v) => *v,
            Param::Envelope(pts) => {
                if pts.is_empty() {
                    return 0.0;
                }
                if t <= pts[0][0] {
                    return pts[0][1];
                }
                for w in pts.windows(2) {
                    let ([t0, v0], [t1, v1]) = (w[0], w[1]);
                    if t <= t1 {
                        return if t1 > t0 { v0 + (v1 - v0) * (t - t0) / (t1 - t0) } else { v1 };
                    }
                }
                pts[pts.len() - 1][1]
            }
        }
    }
    fn automated(&self) -> bool {
        matches!(self, Param::Envelope(_))
    }
}

/// The length every channel shares.
fn frames(chs: &[&mut [f32]]) -> usize {
    chs.iter().map(|c| c.len()).min().unwrap_or(0)
}
