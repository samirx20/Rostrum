//! The master's linear gain at any frame: its fader (or lane) times its fades, and the gain to the loudness
//! target. One source for the mix (bus.rs) and the stems (render/stems.rs), computed per frame as it is
//! needed rather than kept as a song-long curve.

use crate::mix::schedule::Param;
use crate::mix::schedule::Schedule;

#[derive(Clone)]
pub struct MasterGain {
    fader: Param,
    sr: f64,
    fade_in: usize,
    fade_out: usize,
    /// Frames in the file.
    pub total: usize,
    /// The mastering stage's gain to its loudness target (linear; 1 without one).
    pub norm: f64,
}

impl MasterGain {
    pub fn new(s: &Schedule) -> MasterGain {
        MasterGain { fader: crate::mix::buses::master_fader(s), sr: s.sample_rate as f64, fade_in: s.fade_in_samples, fade_out: s.fade_out_samples, total: s.total_samples, norm: 1.0 }
    }

    /// The fades' envelope at frame `i`.
    fn env(&self, i: usize) -> f64 {
        let (fi, fo, total) = (self.fade_in, self.fade_out, self.total);
        let mut env = 1.0;
        if fi > 0 && i < fi {
            env = 0.5 * (1.0 - (std::f64::consts::PI * (i as f64 / fi.max(1) as f64)).cos());
        }
        if fo > 0 && i + fo >= total {
            let rem = (total as f64 - 1.0 - i as f64) / (fo.max(2) - 1) as f64;
            env = f64::min(env, (0.5 * (1.0 - (std::f64::consts::PI * rem).cos())).powf(2.2));
        }
        env
    }

    /// Fader times fades at frame `i` (what the mix takes before its mastering stage).
    pub fn lin(&self, i: usize) -> f64 {
        self.fader.at(i as f64 / self.sr) * self.env(i)
    }

    /// The whole linear gain at frame `i`, as the stems carry it.
    pub fn stem(&self, i: usize) -> f32 {
        (self.lin(i) * self.norm) as f32
    }
}
