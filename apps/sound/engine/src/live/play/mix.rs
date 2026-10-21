//! What `rostrum-sound play` plays (play.rs): the mix read from its render (a WAV the engine wrote, or a
//! schedule rendered here), and, for a surround bed, played the way the monitor chose for the device
//! (monitor.rs) — the same way again for every reload, so the stream's channels never change under it.

use std::sync::{Arc, Mutex};

use crate::bed::Layout;
use crate::live::frames::{self, Frames};
use crate::fx::master::MasterSpec;
use crate::live::monitor::{self, Device, Monitor};

/// A mix as read: stereo, ready to play; or a surround bed for the monitor to place.
pub enum Mix {
    Stereo(Frames),
    Bed(Vec<Vec<f32>>, Layout),
}

/// The mix in a file (and its rate). A stereo WAV is read as it always was (sfz.rs), so what plays is
/// sample for sample what played before surround monitoring.
pub fn read(path: &str) -> Result<(Mix, f64), String> {
    if path.ends_with(".json") {
        let s = crate::mix::schedule::Schedule::parse(&std::fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?)?;
        let m = crate::mix::render::render(&s)?;
        let mix = if m.layout == Layout::Stereo { Mix::Stereo(Frames::from_channels(&m.channels, 0x3)) } else { Mix::Bed(m.channels, m.layout) };
        return Ok((mix, s.sample_rate as f64));
    }
    if let Ok((chs, sr)) = crate::mix::wavio::read(path) {
        if chs.len() > 2 {
            let layout = Layout::of_channels(chs.len()).map_err(|e| format!("{path}: {e}"))?;
            return Ok((Mix::Bed(chs, layout), sr));
        }
    }
    let s = crate::instruments::sfz::read_wav(std::path::Path::new(path))?;
    Ok((Mix::Stereo(Frames::stereo(&s.frames)), s.rate))
}

/// How a session monitors: asked (`--monitor`), the mastering spec its folds are held to (`--master`),
/// and, once the device is open, the mode chosen and the channels the stream plays.
pub struct Monitoring {
    pub asked: Option<Monitor>,
    pub master: Option<MasterSpec>,
    pub chosen: Mutex<Option<(Monitor, String, usize)>>,
}

impl Monitoring {
    pub fn from_args(args: &[String]) -> Result<Arc<Monitoring>, String> {
        let value = |name: &str| args.iter().position(|a| a == name).map(|i| args.get(i + 1).cloned().ok_or(format!("{name} takes a value"))).transpose();
        let asked = match value("--monitor")? {
            Some(m) => Monitor::parse(&m)?,
            None => None,
        };
        let master = value("--master")?.map(|j| serde_json::from_str(&j).map_err(|e| format!("--master: {e}"))).transpose()?;
        Ok(Arc::new(Monitoring { asked, master, chosen: Mutex::new(None) }))
    }

    /// The mix for this device, at the device's rate; remembers the choice.
    pub fn first(&self, mix: &Mix, from: f64, dev: &Device) -> Result<Frames, String> {
        let layout = match mix {
            Mix::Stereo(_) => Layout::Stereo,
            Mix::Bed(_, l) => *l,
        };
        let (mode, why) = monitor::choose(self.asked, layout, dev)?;
        let f = self.played(mix, mode, from, dev.rate)?;
        *self.chosen.lock().unwrap() = Some((mode, why, f.channels));
        Ok(f)
    }

    /// A new render of the mix (a reload), monitored as the first was.
    pub fn again(&self, mix: &Mix, from: f64, rate: u32) -> Result<Frames, String> {
        let (mode, _, channels) = self.chosen.lock().unwrap().clone().ok_or("the stream is not open yet")?;
        let f = self.played(mix, mode, from, rate)?;
        if f.channels != channels {
            return Err(format!("the new mix plays on {} channels and the stream on {channels} (its layout changed): stop and play again", f.channels));
        }
        Ok(f)
    }

    fn played(&self, mix: &Mix, mode: Monitor, from: f64, rate: u32) -> Result<Frames, String> {
        let f = match mix {
            Mix::Stereo(f) => f.clone(),
            Mix::Bed(chs, layout) => monitor::prepare(chs, *layout, mode, self.master.clone(), from)?,
        };
        Ok(frames::resample(&f, from, rate as f64))
    }

    /// The `ready` line's account of it.
    pub fn report(&self, dev_channels: Option<usize>) -> serde_json::Value {
        match &*self.chosen.lock().unwrap() {
            Some((m, why, ch)) => serde_json::json!({ "mode": m.name(), "why": why, "channels": ch, "deviceChannels": dev_channels }),
            None => serde_json::Value::Null,
        }
    }
}

impl Mix {
    /// Seconds of it at `rate`.
    pub fn seconds(&self, rate: f64) -> f64 {
        match self {
            Mix::Stereo(f) => f.len() as f64 / rate,
            Mix::Bed(chs, _) => chs.first().map_or(0, Vec::len) as f64 / rate,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_stereo_mix_plays_sample_for_sample_as_before_whatever_the_device() {
        let n = 4410;
        let chs: Vec<Vec<f32>> = (0..2).map(|c| (0..n).map(|i| ((i * (c + 3)) as f32 * 0.01).sin() * 0.5).collect()).collect();
        let file = std::env::temp_dir().join(format!("rostrum-playmix-{}.wav", std::process::id()));
        std::fs::write(&file, crate::mix::wavio::write(&chs, Layout::Stereo, 44100)).unwrap();
        let path = file.to_string_lossy().to_string();
        // Before surround monitoring: sfz::read_wav, then the transport's stereo resample.
        let old = crate::instruments::sfz::read_wav(&file).unwrap();
        let before = Frames::stereo(&crate::live::transport::resample(&old.frames, old.rate, 48000.0));
        let (mix, from) = read(&path).unwrap();
        let m = Monitoring { asked: None, master: None, chosen: Mutex::new(None) };
        for dev in [Device { rate: 48000, channels: 2, mask: 0x3, form_factor: 3, name: "headphones".into() }, Device { rate: 48000, channels: 6, mask: 0x3F, form_factor: 1, name: "5.1".into() }] {
            assert_eq!(m.first(&mix, from, &dev).unwrap(), before, "{}", dev.name);
            assert_eq!(m.chosen.lock().unwrap().as_ref().unwrap().0, Monitor::Stereo);
        }
        let _ = std::fs::remove_file(file);
    }

    #[test]
    fn a_bed_is_monitored_by_the_device_and_a_reload_keeps_the_mode() {
        let chs: Vec<Vec<f32>> = (0..6).map(|c| vec![0.05 * c as f32; 2000]).collect();
        let mix = Mix::Bed(chs.clone(), Layout::Surround51);
        let m = Monitoring { asked: None, master: None, chosen: Mutex::new(None) };
        let speakers = Device { rate: 48000, channels: 2, mask: 0x3, form_factor: 1, name: "Speakers".into() };
        assert_eq!(m.first(&mix, 48000.0, &speakers).unwrap().channels, 2);
        assert_eq!(m.report(Some(2))["mode"], "stereo");
        let wide = Device { rate: 48000, channels: 6, mask: 0x60F, form_factor: 1, name: "AVR".into() };
        assert_eq!(m.first(&mix, 48000.0, &wide).unwrap().channels, 6);
        assert_eq!(m.again(&mix, 48000.0, 48000).unwrap().channels, 6);
        // The layout changed under a running 6-channel stream: said, not folded silently.
        assert!(m.again(&Mix::Stereo(Frames::from_channels(&chs[..2], 0x3)), 48000.0, 48000).unwrap_err().contains("stop and play again"));
    }
}
