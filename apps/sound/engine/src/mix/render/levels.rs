//! The Mixer's live meters, analysed once with the render and stored as data beside the mix: each track's,
//! each bus' and the master's peak and RMS per 1/30 s window (`Windows`, fed by stats.rs TrackMeter and bus.rs
//! master on the samples they already measure). `write` puts them in `<mix>.levels.json`, keyed by the mix file's
//! size and modified time so a stale file is never read as the current mix's; `rostrum-sound play` reads them
//! (`Levels::beside`) and prints the window at the speaker's time while it rolls (live/play.rs).

use std::path::{Path, PathBuf};

use serde_json::{json, Value};

/// Windows per second: a meter's refresh.
pub const PER_SECOND: f64 = 30.0;
const CONTRACT: &str = "rostrum-sound-levels/1";
const FLOOR: f64 = -120.0;

fn db(power: f64) -> f32 {
    let d = if power > 0.0 { 10.0 * power.log10() } else { FLOOR };
    ((d.max(FLOOR) * 10.0).round() / 10.0) as f32
}

/// Peak and RMS (dBFS, every channel) per window, frame by frame.
pub struct Windows {
    hop: usize,
    n: usize,
    peak: f64,
    sq: f64,
    pub out: Vec<[f32; 2]>,
}

impl Windows {
    pub fn new(sr: f64) -> Windows {
        Windows { hop: (sr / PER_SECOND).round().max(1.0) as usize, n: 0, peak: 0.0, sq: 0.0, out: vec![] }
    }

    /// One frame: its loudest sample (absolute) and its power (mean square over the channels).
    pub fn frame(&mut self, peak: f64, power: f64) {
        self.peak = self.peak.max(peak);
        self.sq += power;
        self.n += 1;
        if self.n == self.hop {
            self.close();
        }
    }

    fn close(&mut self) {
        self.out.push([db(self.peak * self.peak), db(self.sq / self.n as f64)]);
        (self.peak, self.sq, self.n) = (0.0, 0.0, 0);
    }

    pub fn finish(mut self) -> Vec<[f32; 2]> {
        if self.n > 0 {
            self.close();
        }
        self.out
    }
}

/// The sidecar's path: `<mix>.levels.json`.
pub fn path_of(mix: &Path) -> PathBuf {
    mix.with_extension("levels.json")
}

/// The mix file's key: its size and modified time (seconds).
fn key(mix: &Path) -> Result<(u64, f64), String> {
    let m = std::fs::metadata(mix).map_err(|e| format!("{}: {e}", mix.display()))?;
    let t = m.modified().map_err(|e| e.to_string())?.duration_since(std::time::UNIX_EPOCH).map_err(|e| e.to_string())?;
    Ok((m.len(), t.as_secs_f64()))
}

/// Every strip's windows, in the file's time: the tracks as measured (over the file's frames, placed.rs), the buses
/// (measured in song time) from `from` frames on.
pub struct Levels {
    pub hop: f64,
    pub strips: Vec<(String, Vec<[f32; 2]>)>,
}

impl Levels {
    pub fn of(mix: &super::stats::Mix, sr: f64, from: usize) -> Levels {
        let skip = (from as f64 * PER_SECOND / sr).round() as usize;
        let cut = |w: &[[f32; 2]]| w.get(skip..).unwrap_or(&[]).to_vec();
        let tracks = mix.tracks.iter().map(|t| (t.name.clone(), t.levels.clone()));
        let mut strips: Vec<(String, Vec<[f32; 2]>)> = tracks.chain(mix.buses.iter().map(|t| (t.name.clone(), cut(&t.levels)))).collect();
        strips.push(("master".into(), mix.levels.clone()));
        Levels { hop: 1.0 / PER_SECOND, strips }
    }

    /// Written beside `mix` (its final name), keyed to `whole`: the mix's file as written, before its rename (a rename
    /// keeps its size and time). Written to `.partial` and renamed, so it is never seen half written.
    pub fn write(&self, whole: &Path, mix: &Path) -> Result<(), String> {
        let (bytes, modified) = key(whole)?;
        let strips: serde_json::Map<String, Value> = self.strips.iter().map(|(id, w)| (id.clone(), json!(w.iter().flat_map(|p| [(p[0] * 10.0) as i32, (p[1] * 10.0) as i32]).collect::<Vec<_>>()))).collect();
        let v = json!({ "contract": CONTRACT, "mix": { "bytes": bytes, "modified": modified }, "hop": self.hop, "unit": "dB/10, [peak, rms] per window", "strips": strips });
        let out = path_of(mix);
        let part = PathBuf::from(format!("{}.partial", out.display()));
        std::fs::write(&part, v.to_string()).map_err(|e| format!("{}: {e}", part.display()))?;
        std::fs::rename(&part, &out).map_err(|e| format!("{} → {}: {e}", part.display(), out.display()))
    }

    /// The levels written beside `mix`, or why there are none (missing, unreadable, or for another render of it).
    pub fn beside(mix: &Path) -> Result<Levels, String> {
        let p = path_of(mix);
        let text = std::fs::read_to_string(&p).map_err(|e| format!("{}: {e}", p.display()))?;
        let v: Value = serde_json::from_str(&text).map_err(|e| format!("{}: not JSON ({e})", p.display()))?;
        if v["contract"] != CONTRACT {
            return Err(format!("{}: not {CONTRACT}", p.display()));
        }
        let (bytes, modified) = key(mix)?;
        if v["mix"]["bytes"].as_u64() != Some(bytes) || v["mix"]["modified"].as_f64().is_none_or(|m| (m - modified).abs() > 1e-3) {
            return Err(format!("{}: written for another render of {}", p.display(), mix.display()));
        }
        let strips = v["strips"].as_object().ok_or(format!("{}: no strips", p.display()))?;
        let strips = strips
            .iter()
            .map(|(id, w)| {
                let n: Vec<f32> = w.as_array().map(|a| a.iter().map(|x| x.as_f64().unwrap_or(FLOOR * 10.0) as f32 / 10.0).collect()).unwrap_or_default();
                (id.clone(), n.chunks_exact(2).map(|c| [c[0], c[1]]).collect())
            })
            .collect();
        Ok(Levels { hop: v["hop"].as_f64().unwrap_or(1.0 / PER_SECOND), strips })
    }

    /// The `levels` line for the speaker passing from `a` to `b` (mix seconds): each strip's loudest window in
    /// between (none missed between two lines), [peak dB, RMS dB].
    pub fn line(&self, a: f64, b: f64) -> Value {
        let (i, j) = ((a.max(0.0) / self.hop) as usize, (b.max(0.0) / self.hop) as usize);
        let (i, j) = (i.min(j), j);
        let strips: serde_json::Map<String, Value> = self
            .strips
            .iter()
            .map(|(id, w)| {
                let mut m = [FLOOR as f32; 2];
                for p in w.iter().skip(i).take(j + 1 - i) {
                    m = [m[0].max(p[0]), m[1].max(p[1])];
                }
                (id.clone(), json!(m))
            })
            .collect();
        json!({ "levels": { "t": (b * 1000.0).round() / 1000.0, "strips": strips } })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The meters come from the render: each strip's loudest window is the peak the render measured, a re-render
    /// of the file is not read with the old levels, and a `levels` line names every strip.
    #[test]
    fn the_live_meters_are_the_renders_own_levels() {
        let dir = std::env::temp_dir().join(format!("rostrum-sound-levels-{}", std::process::id()));
        let out = dir.join("mix.wav");
        let req = json!({ "do": "render", "out": out, "schedule": { "contract": "rostrum-sound-schedule/1", "length": 2.0,
            "buses": [{ "id": "music" }],
            "tracks": [{ "id": "keys", "instrument": { "builtIn": "classic.grandPiano" }, "notes": [{ "pitch": "C4", "at": 0.5, "dur": 0.5 }], "output": "music" },
                       { "id": "pad", "instrument": { "builtIn": "warmPad" }, "notes": [{ "pitch": "A3", "at": 1.0, "dur": 0.5 }] }] } });
        let a = crate::contract::answer(&req);
        assert_eq!(a["ok"], json!(true), "{a}");
        let l = Levels::beside(&out).unwrap();
        let peak_of = |id: &str| l.strips.iter().find(|(s, _)| s == id).unwrap_or_else(|| panic!("no {id}")).1.iter().fold(FLOOR as f32, |m, p| m.max(p[0])) as f64;
        let rendered = |v: &Value| 20.0 * v.as_f64().unwrap().log10();
        for (id, v) in [("keys", &a["result"]["tracks"][0]["peak"]), ("pad", &a["result"]["tracks"][1]["peak"]), ("music", &a["result"]["buses"][0]["peak"]), ("master", &a["result"]["peak"])] {
            assert!((peak_of(id) - rendered(v)).abs() < 0.11, "{id}: {} against the render's {}", peak_of(id), rendered(v));
        }
        // Silent before the first note, sounding during it.
        let line = l.line(0.0, 0.1);
        assert_eq!(line["levels"]["strips"]["keys"][0], json!(FLOOR), "{line}");
        assert!(l.line(0.5, 0.7)["levels"]["strips"]["keys"][0].as_f64().unwrap() > -40.0);
        // The same file rendered again elsewhere (another size): its old levels are refused.
        std::fs::write(&out, b"RIFF").unwrap();
        assert!(Levels::beside(&out).err().unwrap().contains("another render"));
        let _ = std::fs::remove_dir_all(&dir);
    }
}
