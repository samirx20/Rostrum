//! Each track's render, kept by content (rule 9): what `render/ track_out` makes from a track's clips
//! (and, for a bus, its feeders) is stored under a key of everything that output depends on — the engine
//! build, the rate, the bed layout, the buffer length, the track-reverb space, the track itself (its name,
//! ducks and "heard" flag left out: they act later), the files it names (size and time) and its feeders'
//! keys — so a one-track change re-renders that track alone and the rest is read back, bit for bit.
//! Stored as a tape (tape.rs: trimmed to the span that is not silent, read in blocks), in Rostrum's one cache
//! (cache.rs: `sound/tracks`), which the host caps as a whole (rostrum_sound/cache_cap.py).

use serde_json::Value;
use std::path::{Path, PathBuf};

use crate::mix::tape::Tape;

/// What a stored file holds; bump on any change to the layout of the file or to what is keyed.
const FORMAT: &str = "track-cache-1";

pub struct TrackCache {
    dir: PathBuf,
}

impl TrackCache {
    /// The engine's cache folder, unless nothing is kept (cache.rs). Tests use `at` (their own folder).
    pub fn default_dir() -> Option<TrackCache> {
        crate::mix::cache::dir("tracks").map(|dir| TrackCache { dir })
    }

    #[cfg(test)]
    pub fn at(dir: PathBuf) -> TrackCache {
        TrackCache { dir }
    }

    /// A stored track, `len` frames long, as a tape (marked as just used), or None (absent or not this length).
    pub fn tape(&self, key: &str, len: usize) -> Option<Tape> {
        let name = format!("{key}.f32");
        crate::mix::cache::touch(&self.dir, &name);
        Tape::open(&self.dir.join(name), len)
    }

    /// Stores a track and hands back its tape; None when the cache cannot be written (the render then keeps
    /// the track in a scratch tape of its own, and the next render does the same work).
    pub fn store(&self, key: &str, chs: &[Vec<f32>]) -> Option<Tape> {
        let name = format!("{key}.f32");
        if !crate::mix::cache::write_with(&self.dir, &name, |w| crate::mix::tape::write_to(w, chs)) {
            return None;
        }
        Tape::open(&self.dir.join(name), chs.first().map_or(0, Vec::len))
    }
}

/// The engine build: its file's size and time (any rebuild is a new engine).
fn build_stamp() -> String {
    std::env::current_exe().ok().map(|p| stamp(&p)).unwrap_or_default()
}

fn stamp(p: &Path) -> String {
    match std::fs::metadata(p) {
        Ok(m) => format!("{}:{:?}", m.len(), m.modified().ok().and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())),
        Err(_) => "missing".into(),
    }
}

/// Every absolute file path the track names (PCM, SoundFonts, SFZ, plugins, impulse responses), stamped.
fn file_stamps(v: &Value, out: &mut Vec<String>) {
    match v {
        Value::String(s) if Path::new(s).is_absolute() => out.push(format!("{s}={}", stamp(Path::new(s)))),
        Value::Array(a) => a.iter().for_each(|x| file_stamps(x, out)),
        Value::Object(o) => o.values().for_each(|x| file_stamps(x, out)),
        _ => {}
    }
}

/// Each track's key (`tracks`: the schedule's raw tracks, in order).
pub fn keys(tracks: &[Value], sample_rate: u32, layout: &str, buf: usize, reverb_space: &str) -> Vec<String> {
    let common = format!("{FORMAT}|{}|{sample_rate}|{layout}|{buf}|{reverb_space}", build_stamp());
    let into = |t: &Value| t.get("into").and_then(Value::as_u64).map(|k| k as usize);
    let own = |t: &Value| {
        let mut t = t.clone();
        if let Some(o) = t.as_object_mut() {
            o.remove("name");
            o.remove("ducks");
            o.remove("mix");
            let feeds = o.get("into").is_some_and(|v| !v.is_null());
            o.insert("into".into(), Value::Bool(feeds));
        }
        let mut files = vec![];
        file_stamps(&t, &mut files);
        format!("{common}|{t}|{}", files.join("|"))
    };
    let mut keys: Vec<String> = tracks.iter().map(|t| blake3::hash(own(t).as_bytes()).to_hex().to_string()).collect();
    // A bus: its own content and its feeders' keys, in order (feeders feed one level up only).
    for k in 0..tracks.len() {
        let feeders: Vec<&str> = tracks.iter().enumerate().filter(|(_, t)| into(t) == Some(k)).map(|(j, _)| keys[j].as_str()).collect();
        if !feeders.is_empty() {
            keys[k] = blake3::hash(format!("{}|{}", keys[k], feeders.join(",")).as_bytes()).to_hex().to_string();
        }
    }
    keys
}
