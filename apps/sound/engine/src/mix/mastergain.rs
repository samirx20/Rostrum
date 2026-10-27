//! The master's gain at any frame: its fader (or lane) times its fades, then the mastering stage's gain as it
//! was applied to the mix (glue, the gain to the loudness target, the limiter: fx/master.rs Dynamics). One
//! source for the mix (bus.rs) and the stems (render/stems.rs): every stem takes the very gain the mix took, so
//! the stems add up to the mix wherever only these stages acted.

use std::sync::Arc;

use crate::fx::master::Dynamics;
use crate::mix::schedule::Param;
use crate::mix::schedule::Schedule;

/// How long the end of a ring-out fades (seconds): only what still rings RING_MAX s past the end hears it.
const TAIL_FADE_S: f64 = 1.5;

#[derive(Clone)]
pub struct MasterGain {
    fader: Param,
    sr: f64,
    fade_in: usize,
    fade_out: usize,
    /// Frames in the song (where its fade-out ends).
    song: usize,
    /// A ring-out's last frame (song + RING_MAX): what still rings there fades out over TAIL_FADE_S, never a cut.
    ring_end: Option<usize>,
    /// The song frame the file starts at (a range), and the frames in the file.
    pub offset: usize,
    pub total: usize,
    /// The mastering stage's gain to its loudness target (linear; 1 without one).
    pub norm: f64,
    /// The mastering stage's gain at every frame of the file (it includes `norm`); None without a mastering stage.
    pub dynamics: Option<Arc<Dynamics>>,
}

impl MasterGain {
    pub fn new(s: &Schedule) -> MasterGain {
        let (offset, end) = s.range.unwrap_or((0, s.total_samples));
        MasterGain { fader: crate::mix::buses::master_fader(s), sr: s.sample_rate as f64, fade_in: s.fade_in_samples, fade_out: s.fade_out_samples, song: s.song_samples.unwrap_or(s.total_samples), ring_end: s.song_samples.map(|_| s.total_samples), offset, total: end - offset, norm: 1.0, dynamics: None }
    }

    /// The fades' envelope at song frame `i`.
    fn env(&self, i: usize) -> f64 {
        let (fi, fo, total) = (self.fade_in, self.fade_out, self.song);
        let mut env = 1.0;
        if fi > 0 && i < fi {
            env = 0.5 * (1.0 - (std::f64::consts::PI * (i as f64 / fi.max(1) as f64)).cos());
        }
        if fo > 0 && i >= total {
            env = 0.0; // past a song's faded end: its ring-out was faded with it
        } else if fo > 0 && i + fo >= total {
            let rem = (total as f64 - 1.0 - i as f64) / (fo.max(2) - 1) as f64;
            env = f64::min(env, (0.5 * (1.0 - (std::f64::consts::PI * rem).cos())).powf(2.2));
        }
        if let Some(last) = self.ring_end {       // a cymbal still ringing when the ring-out runs out fades, not cut
            let tf = (TAIL_FADE_S * self.sr) as usize;
            if i + tf >= last {
                let rem = (last as f64 - 1.0 - i as f64).max(0.0) / tf.max(2) as f64;
                env = f64::min(env, 0.5 * (1.0 - (std::f64::consts::PI * rem).cos()));
            }
        }
        env
    }

    /// Fader times fades at frame `i` of the file (what the mix takes before its mastering stage).
    pub fn lin(&self, i: usize) -> f64 {
        let i = i + self.offset;
        self.fader.at(i as f64 / self.sr) * self.env(i)
    }

    /// The mastering stage's gain at frames `at .. at + n` of the file (glue × target gain × limiter; `norm` alone
    /// without a mastering stage).
    pub fn mastering(&self, at: usize, n: usize) -> Result<Vec<f64>, String> {
        match &self.dynamics {
            Some(d) => d.read(at, n),
            None => Ok(vec![self.norm; n]),
        }
    }

    /// The whole gain at frames `at .. at + n` of the file, as the mix took it and the stems carry it.
    pub fn stem_block(&self, at: usize, n: usize) -> Result<Vec<f32>, String> {
        Ok(self.mastering(at, n)?.into_iter().enumerate().map(|(k, m)| (self.lin(at + k) * m) as f32).collect())
    }
}
