//! What happens at the song's end, in one place (ENGINE_CONTRACT § Top level: `length`, `ringOut`). A given `length`
//! is where the music stops being played: a note held past it is let go there, and anything starting at or after it
//! is not heard. With `ringOut` (agent pieces 2026-10-25, finding 3: a last chord cut at -33 dBFS) the song renders on
//! past the length until what was still ringing (releases, decays, reverb) has died away, up to `RING_MAX` s, and the
//! file ends there; without it the song ends at the length, cut. Either way the render answers `ending` and says in
//! `warnings` when the given length and the heard end differ, so a cut is never mistaken for a clean ending.

use crate::mix::render::stats::Mix;
use serde_json::{json, Value};

/// How long past the length a ring-out may run (seconds).
pub const RING_MAX: f64 = 6.0;
/// Quieter than this (dBFS, the mix's peak in 10 ms) has died away.
const RUNG_OUT_DB: f64 = -60.0;
/// Still this loud (dBFS) just before the length: an ending without ring-out is cut.
const CUT_DB: f64 = -50.0;
/// A master fade-out at least this long (s) is a deliberate fade, not a cut.
const FADE_S: f64 = 0.5;

/// With ring-out: notes held past the song's `song` frame are let go at it, voices that start there or later (written
/// after the end, or performed onto its last frame) are left out, and recorded clips stop at it with a 50 ms fade.
/// Returns how many notes and clips were held past the end (said in both modes; without ring-out the end cuts them).
pub fn hold_to(voices: &mut Vec<Value>, clips: &mut Vec<Value>, song: usize, sr: f64, ring: bool) -> usize {
    let end = song as f64 / sr;
    let start = |v: &Value, k: &str| v[k].as_u64().unwrap_or(0) as usize;
    let mut past = 0;
    if ring {
        voices.retain(|v| start(v, "startIdx") + 1 < song);
        clips.retain(|c| start(c, "startSample") < song);
    }
    for v in voices.iter_mut() {
        let (at, dur) = (start(v, "startIdx") as f64 / sr, v["duration"].as_f64().unwrap_or(0.0));
        if at < end && at + dur > end + 1e-6 {
            past += 1;
            if ring {
                v["duration"] = json!(end - at);
            }
        }
    }
    for c in clips.iter_mut() {
        let (at, n) = (start(c, "startSample"), start(c, "samples"));
        if at + n > song {
            past += 1;
            if ring {
                c["samples"] = json!(song - at);
                c["fadeOut"] = json!(c["fadeOut"].as_f64().unwrap_or(0.0).max(0.05).min((song - at) as f64 / sr));
            }
        }
    }
    past
}

/// How the song ended, as the render answers it.
pub struct Ending {
    /// The given length and where the file ends (seconds).
    pub length: f64,
    pub end: f64,
    pub ring: bool,
    /// The mix's peak (dBFS) in the 50 ms before the length (before the master's own fade-out).
    pub level_db: f64,
    /// Notes and clips held past the length.
    pub held: usize,
    /// Still sounding `RING_MAX` s past the length: cut there.
    pub ran_out: bool,
    pub faded: bool,
    /// The length was given (else it is the last note's end, and the song simply rings out from there).
    pub given: bool,
}

fn peak_db(mix: &Mix, a: usize, b: usize) -> Result<f64, String> {
    let top = mix.read(a, b.saturating_sub(a))?.iter().flatten().fold(0.0f32, |m, v| m.max(v.abs()));
    Ok(20.0 * (top as f64).max(1e-9).log10())
}

/// After the render: the level at the length; with ring-out, the file cut where the ring has died away (its measures
/// and series with it; nothing past there is above -60 dBFS, so the loudness and peaks are the file's).
pub fn finish(mix: &mut Mix, song: usize, ring: bool, fade_out: usize, held: usize, given: bool, sr: f64) -> Result<Ending, String> {
    let total = mix.frames();
    let block = (0.01 * sr) as usize;
    let before = song.min(total).saturating_sub(fade_out);
    let level_db = peak_db(mix, before.saturating_sub(5 * block), before)?;
    let mut end = song.min(total);
    if ring && total > song {
        let mut at = song;
        while at < total {
            let n = block.min(total - at);
            if peak_db(mix, at, at + n)? >= RUNG_OUT_DB {
                end = at + n;
            }
            at += n;
        }
        trim(mix, end, sr);
    }
    let ran_out = ring && total > song && end + block >= total;
    Ok(Ending { length: song as f64 / sr, end: end as f64 / sr, ring, level_db, held, ran_out, faded: fade_out as f64 >= FADE_S * sr, given })
}

/// The file and every series the answer carries, cut to `end` frames.
fn trim(mix: &mut Mix, end: usize, sr: f64) {
    if let Some(g) = mix.gain.as_mut() {
        g.total = end.min(g.total);
    }
    let hops = |per_second: f64| (end as f64 / sr * per_second).ceil() as usize;
    mix.true_peak_series.truncate(hops(10.0));
    mix.reduction_series.truncate(hops(10.0));
    if let Some(l) = mix.loud.as_mut() {
        l.momentary.truncate(hops(10.0));
        l.short_term.truncate(hops(10.0));
        l.correlation.truncate(hops(10.0));
    }
    mix.levels.truncate(hops(30.0));
    for t in mix.tracks.iter_mut().chain(mix.buses.iter_mut()) {
        t.levels.truncate(hops(30.0));
    }
}

impl Ending {
    pub fn to_json(&self) -> Value {
        let r = |v: f64| (v * 100.0).round() / 100.0;
        json!({ "length": r(self.length), "end": r(self.end), "ringOut": self.ring, "levelAtLengthDb": r(self.level_db.max(-120.0)),
                "heldPastLength": self.held, "cut": self.cut() })
    }

    /// The ending was cut while still sounding: no ring-out, no deliberate fade, and loud at the length.
    pub fn cut(&self) -> bool {
        (!self.ring && !self.faded && self.level_db > CUT_DB) || self.ran_out
    }

    /// What a person must know about the ending, in plain words (empty: it ended where it was given).
    pub fn warnings(&self) -> Vec<String> {
        let mut out = vec![];
        if self.held > 0 {
            out.push(format!("{} note(s) or clip(s) are held past the song's end ({:.2} s): they are let go there{}.", self.held, self.length,
                             if self.ring { " and ring out" } else { " and cut off" }));
        }
        if self.ran_out && !self.given {
            out.push(format!("The last sounds still ring {RING_MAX:.0} s after the last note ends ({:.2} s): the song fades out there, ending at {:.2} s. Shorten or choke the last notes, or give the song a length.", self.length, self.end));
        } else if !self.given {
        } else if self.ran_out {
            out.push(format!("The last sounds still ring {RING_MAX:.0} s past the song's length ({:.2} s): the song fades out there, ending at {:.2} s. End the music earlier or shorten its last notes.", self.length, self.end));
        } else if self.ring && self.end > self.length + 0.05 {
            out.push(format!("The song's length is {:.2} s; its last sounds ring out until {:.2} s, so the song ends there. For a hard stop at {:.2} s, turn Ring out off (ringOut: false).", self.length, self.end, self.length));
        } else if self.cut() {
            out.push(format!("The ending is cut: the sound is still at {:.0} dBFS at the song's length ({:.2} s) and stops there. Turn Ring out on (ringOut: true) to let it die away, end the music earlier, or fade the master out.", self.level_db, self.length));
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    #[test]
    fn a_cut_ending_is_flagged_and_a_ring_out_ends_after_the_ring() {
        // A sine held to 1 s with a 1 s release, the song's length at 1.2 s: the release is still loud there.
        let dir = std::env::temp_dir().join(format!("rostrum-sound-ending-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let render = |ring: bool| {
            let a = super::super::answer(&json!({ "do": "render", "out": dir.join(format!("mix{ring}.wav")), "schedule": { "contract": "rostrum-sound-schedule/1",
                "length": 1.2, "ringOut": ring, "tracks": [{ "id": "a", "instrument": { "synth": "sine", "attack": 0.01, "release": 1.0 }, "perform": false,
                "notes": [{ "pitch": "A3", "at": 0, "dur": 1.0 }, { "pitch": "E4", "at": 0.5, "dur": 2.0 }] }] } }));
            assert_eq!(a["ok"], json!(true), "{a}");
            a["result"].clone()
        };
        let cut = render(false);
        assert_eq!(cut["ending"]["cut"], json!(true), "{}", cut["ending"]);
        assert!(cut["warnings"].to_string().contains("ending is cut") && cut["warnings"].to_string().contains("held past"), "{}", cut["warnings"]);
        let rung = render(true);
        let end = rung["seconds"].as_f64().unwrap();
        assert!(rung["ending"]["cut"] == json!(false) && end > 1.6 && end < 1.2 + super::RING_MAX, "{}", rung["ending"]);
        let _ = std::fs::remove_dir_all(&dir);
    }
}
