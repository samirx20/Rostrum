//! Each track's render, kept by content (rule 9): what `render/ track_out` makes from a track's clips
//! (and, for a bus, its feeders) is stored under a key of everything that output depends on — the engine
//! build, the rate, the bed layout, the buffer length, the track-reverb space, the track itself (its name,
//! ducks and "heard" flag left out: they act later), the files it names (size and time) and its feeders'
//! keys — so a one-track change re-renders that track alone and the rest is read back, bit for bit.
//! Stored trimmed to the span that is not silent, in Rostrum's one cache (cache.rs: `sound/tracks`), which
//! the host caps as a whole.

use serde_json::Value;
use std::path::{Path, PathBuf};

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

    /// A stored track: its channels, `len` long, or None (absent or not this length).
    pub fn load(&self, key: &str, len: usize) -> Option<Vec<Vec<f32>>> {
        let bytes = crate::mix::cache::read(&self.dir, &format!("{key}.f32"))?;
        let word = |i: usize| u64::from_le_bytes(bytes.get(8 * i..8 * i + 8)?.try_into().ok()?).try_into().ok();
        let (chs, total, from, n): (usize, usize, usize, usize) = (word(0)?, word(1)?, word(2)?, word(3)?);
        if chs == 0 || total != len || from + n > len || bytes.len() != 32 + chs * n * 4 {
            return None;
        }
        let body = &bytes[32..];
        Some((0..chs).map(|c| {
            let mut v = vec![0.0f32; len];
            for (i, s) in body[c * n * 4..(c + 1) * n * 4].chunks_exact(4).enumerate() {
                v[from + i] = f32::from_le_bytes([s[0], s[1], s[2], s[3]]);
            }
            v
        }).collect())
    }

    /// Stores a track (a cache that cannot be written only costs the next render the same work).
    pub fn store(&self, key: &str, chs: &[Vec<f32>]) {
        let len = chs.first().map_or(0, Vec::len);
        let sounding = |i: &usize| chs.iter().any(|c| c[*i].to_bits() != 0);
        let from = (0..len).find(sounding).unwrap_or(len);
        let to = (from..len).rev().find(sounding).map_or(from, |i| i + 1);
        let mut bytes = Vec::with_capacity(32 + chs.len() * (to - from) * 4);
        for w in [chs.len(), len, from, to - from] {
            bytes.extend_from_slice(&(w as u64).to_le_bytes());
        }
        for c in chs {
            c[from..to].iter().for_each(|s| bytes.extend_from_slice(&s.to_le_bytes()));
        }
        crate::mix::cache::write(&self.dir, &format!("{key}.f32"), &bytes);
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
