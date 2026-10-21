//! Microphone takes over the transport (play.rs): each packet placed at the mix time heard with it
//! (the transport's clock), kept inside the punch, a jump (the loop came round, a seek) starting a take
//! of its own; each take written as a mono float WAV and reported. Calibrating: the take is the
//! metronome recorded back, measured and stored as the microphone's delay (calib.rs).

use crate::live::record::Packet;
use crate::live::transport::Clock;

struct Take {
    start: f64,
    last: f64,
    samples: Vec<f32>,
}

/// What a calibration measures against: the beat (s), the output and the microphone.
pub struct Calibrating {
    pub beat: f64,
    pub device: String,
    pub mic_device: String,
}

pub struct Takes {
    /// The folder takes are written to.
    pub dir: String,
    pub rate: f64,
    /// The microphone's own delay, as calibrated: a take moves to where it was played.
    pub input_offset: Option<f64>,
    pub calibrating: Option<Calibrating>,
    take: Option<Take>,
    /// Takes written.
    pub taken: usize,
}

impl Takes {
    pub fn new(dir: String, rate: f64, input_offset: Option<f64>, calibrating: Option<Calibrating>) -> Takes {
        Takes { dir, rate, input_offset, calibrating, take: None, taken: 0 }
    }

    /// A packet from the microphone, while recording is `armed` (with its punch).
    pub fn packet(&mut self, p: &Packet, armed: Option<Option<(f64, f64)>>, clock: &Clock) {
        let (Some(punch), Some(t0)) = (armed, clock.mix_at(p.at)) else { return };
        let (from, to) = punch.unwrap_or((f64::MIN, f64::MAX));
        for (i, x) in p.samples.iter().enumerate() {
            let t = t0 + i as f64 / self.rate;
            if t < from || t >= to {
                if t >= to {
                    self.finish();
                }
                continue;
            }
            // A jump (the loop came round, a seek): the pass so far is a take of its own.
            if self.take.as_ref().is_some_and(|k| t < k.last - 0.05 || t > k.last + 0.25) {
                self.finish();
            }
            let k = self.take.get_or_insert(Take { start: t, last: t, samples: vec![] });
            k.samples.push(*x);
            k.last = t;
        }
    }

    /// The take so far, written and reported (nothing when there is none).
    pub fn finish(&mut self) {
        let Some(mut t) = self.take.take().filter(|t| !t.samples.is_empty()) else { return };
        if let Some(c) = &self.calibrating {
            match crate::live::calib::measure(&t.samples, self.rate, t.start, c.beat) {
                Some((_, spread, _)) if spread > 10.0 => println!("{}", serde_json::json!({ "error": format!("the clicks came back {spread:.0} ms apart from each other (noise, or the device fell behind): not stored; calibrate again in a quiet room") })),
                Some((ms, spread, clicks)) => match crate::live::calib::store(&c.device, &c.mic_device, ms, spread) {
                    Ok(f) => println!("{}", serde_json::json!({ "calibration": { "offsetMs": (ms * 100.0).round() / 100.0, "spreadMs": (spread * 100.0).round() / 100.0, "clicks": clicks, "file": f } })),
                    Err(e) => println!("{}", serde_json::json!({ "error": e })),
                },
                None => println!("{}", serde_json::json!({ "error": "the microphone did not hear the metronome (fewer than 4 clicks): turn the speakers up, or hold the microphone near them" })),
            }
        }
        t.start -= self.input_offset.unwrap_or(0.0);
        let file = std::path::Path::new(&self.dir).join(format!("take-{}-{}.wav", std::process::id(), self.taken));
        self.taken += 1;
        let peak = t.samples.iter().fold(0f32, |m, v| m.max(v.abs()));
        match std::fs::write(&file, crate::mix::wavio::write_mono(&t.samples, self.rate as u32)) {
            Ok(()) => println!("{}", serde_json::json!({ "take": { "file": file.to_string_lossy(), "start": t.start, "seconds": t.samples.len() as f64 / self.rate, "rate": self.rate, "peakDb": (20.0 * (peak.max(1e-6) as f64).log10() * 10.0).round() / 10.0 } })),
            Err(e) => println!("{}", serde_json::json!({ "error": format!("{}: {e}", file.display()) })),
        }
    }
}
