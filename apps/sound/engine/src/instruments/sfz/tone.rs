//! Brightness with velocity for files with few recorded loudness layers. A real instrument played harder gets brighter
//! as well as louder; a file with one or two velocity layers only gets louder inside each layer (VSCO's strings are the
//! same sound from 0.5 to 1.0). Such a note gets a high shelf at 2.5 kHz of −`depth` × (1 − velocity) dB, so a swell
//! opens up as it grows. A key with three layers or more plays as recorded. `depth` 12 dB (the default, `SfzSpec`
//! `velocityTone`) was set against the Salamander grand's 16 layers, which brighten 6 to 17 dB from velocity 0.3 to 1.0
//! (2–8 kHz against 250 Hz–1 kHz); 0 turns it off (kits, organs).

use super::Region;
use crate::fx::eq::{biquad, Coeffs};

pub const DEFAULT_DEPTH: f64 = 12.0;
const FREQ: f64 = 2500.0;

/// The recorded velocity layers that play `key` (its release samples and CC-only regions aside).
pub fn layers(regions: &[Region], key: u8) -> usize {
    let mut seen: Vec<(u8, u8)> = vec![];
    for r in regions.iter().filter(|r| !r.cc_only && !r.on_release && key >= r.lokey && key <= r.hikey) {
        if !seen.contains(&(r.lovel, r.hivel)) {
            seen.push((r.lovel, r.hivel));
        }
    }
    seen.len()
}

/// The shelf a note gets (dB, ≤ 0), or None: depth 0, a key with three layers or more, or full velocity.
pub fn shelf_db(regions: &[Region], key: u8, velocity: f64, depth: f64) -> Option<f64> {
    let db = -depth * (1.0 - velocity.clamp(0.0, 1.0));
    (depth > 0.0 && db < -0.01 && layers(regions, key) < 3).then_some(db)
}

/// A note's high shelf, one state per side.
pub struct Tone {
    c: Coeffs,
    z: [[f64; 2]; 2],
}

impl Tone {
    pub fn new(db: f64, sr: f64) -> Tone {
        Tone { c: biquad("highshelf", FREQ, db, 0.707, sr), z: [[0.0; 2]; 2] }
    }

    pub fn tick(&mut self, l: f32, r: f32) -> (f32, f32) {
        (self.c.tick(&mut self.z[0], l as f64) as f32, self.c.tick(&mut self.z[1], r as f64) as f32)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn few_layers_darken_soft_notes_and_three_layers_play_as_recorded() {
        let dir = std::env::temp_dir().join(format!("rostrum-tone-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let two = super::super::parse("<region> sample=a.wav lovel=1 hivel=63\n<region> sample=b.wav lovel=64 hivel=127", &dir).unwrap();
        let three = super::super::parse("<region> sample=a.wav hivel=40\n<region> sample=b.wav lovel=41 hivel=90\n<region> sample=c.wav lovel=91", &dir).unwrap();
        assert_eq!((layers(&two, 60), layers(&three, 60)), (2, 3));
        assert_eq!(shelf_db(&two, 60, 0.5, 12.0), Some(-6.0));
        assert_eq!(shelf_db(&two, 60, 1.0, 12.0), None);
        assert_eq!(shelf_db(&two, 60, 0.3, 0.0), None);
        assert_eq!(shelf_db(&three, 60, 0.3, 12.0), None);
        // The shelf cuts the highs and leaves the lows.
        let rms = |hz: f64| {
            let mut t = Tone::new(-12.0, 48000.0);
            let y: Vec<f32> = (0..9600).map(|i| t.tick((2.0 * std::f64::consts::PI * hz * i as f64 / 48000.0).sin() as f32, 0.0).0).collect();
            (y[4800..].iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / 4800.0).sqrt()
        };
        assert!(rms(200.0) > 0.68 && rms(10000.0) < 0.2, "{} {}", rms(200.0), rms(10000.0));
        let _ = std::fs::remove_dir_all(&dir);
    }
}
