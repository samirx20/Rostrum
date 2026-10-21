//! The transport's clock (mix time by speaker time) and the resampler a mix plays through when the
//! device will not run at its rate.

/// Mix times by speaker time: the clock entries of recent blocks, read by the play-head readout
/// and by microphone packets.
#[derive(Default)]
pub struct Clock(std::collections::VecDeque<(f64, Option<f64>)>);

impl Clock {
    pub fn push(&mut self, at: f64, t: Option<f64>) {
        self.0.push_back((at, t));
        while self.0.len() > 2000 {
            self.0.pop_front();
        }
    }

    /// The mix time heard at `q` (QPC seconds): the last block heard by then, plus the time since; None when not rolling.
    pub fn mix_at(&self, q: f64) -> Option<f64> {
        let &(at, t) = self.0.iter().rev().find(|(at, _)| *at <= q)?;
        t.map(|t| t + (q - at))
    }
}

/// A stereo mix decoded at `from` Hz, played at `to` Hz, when the device will not run at the mix's rate:
/// the one resampler (frames.rs `resample`, cubic), on stereo frames.
pub fn resample(mix: &[[f32; 2]], from: f64, to: f64) -> Vec<[f32; 2]> {
    let f = crate::live::frames::resample(&crate::live::frames::Frames::stereo(mix), from, to);
    f.data.chunks_exact(2).map(|c| [c[0], c[1]]).collect()
}
