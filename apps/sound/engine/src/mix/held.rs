//! What a run of `measure` requests keeps in memory between them (contract/measure.rs): each track's instrument
//! render (its clips, keyed by `clip_keys`) and each unchanged track's measures (keyed by its render-cache key). A
//! loudness search renders the same song dozens of times changing only a compressor, a fader or the master: the
//! instruments and the untouched tracks' meters are the same every time, so only what changed is worked out again.
//! The result is the very same numbers a `render` gives (the same stages, on the same samples).
//!
//! Bounded: at most `MOST_BYTES` of clips (the oldest dropped first); any request that is not a `measure` lets
//! everything go (`clear`), so an engine holds this only while a search runs.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use crate::mix::render::stats::TrackStats;

/// Rendered clips: per clip, its channels.
pub type Clips = Arc<Vec<Vec<Vec<f32>>>>;

const MOST_BYTES: usize = 1 << 30;

#[derive(Default)]
struct Held {
    clips: HashMap<String, (Clips, usize, u64)>,   // key -> (clips, bytes, last used)
    stats: HashMap<String, TrackStats>,
    bytes: usize,
    clock: u64,
}

static HELD: Mutex<Option<Held>> = Mutex::new(None);

fn with<R>(f: impl FnOnce(&mut Held) -> R) -> R {
    let mut g = HELD.lock().unwrap_or_else(|p| p.into_inner());
    f(g.get_or_insert_with(Held::default))
}

/// A track's clips rendered before in this run of `measure` requests.
pub fn clips(key: &str) -> Option<Clips> {
    with(|h| {
        h.clock += 1;
        let now = h.clock;
        h.clips.get_mut(key).map(|e| {
            e.2 = now;
            e.0.clone()
        })
    })
}

/// Keeps a track's rendered clips (dropping the least recently used past the budget).
pub fn keep_clips(key: &str, clips: Clips) {
    let bytes: usize = clips.iter().flatten().map(|c| c.len() * 4).sum();
    if bytes > MOST_BYTES {
        return;
    }
    with(|h| {
        h.clock += 1;
        let now = h.clock;
        if let Some(old) = h.clips.insert(key.to_string(), (clips, bytes, now)) {
            h.bytes -= old.1;
        }
        h.bytes += bytes;
        while h.bytes > MOST_BYTES {
            let Some(oldest) = h.clips.iter().min_by_key(|(_, e)| e.2).map(|(k, _)| k.clone()) else { break };
            if let Some(e) = h.clips.remove(&oldest) {
                h.bytes -= e.1;
            }
        }
    });
}

/// An unchanged track's measures (its render-cache key: the same tape, the same numbers).
pub fn stats(key: &str) -> Option<TrackStats> {
    with(|h| h.stats.get(key).cloned())
}

pub fn keep_stats(key: &str, st: &TrackStats) {
    with(|h| {
        h.stats.insert(key.to_string(), st.clone());
    });
}

/// Lets everything go (any request other than `measure`).
pub fn clear() {
    let mut g = HELD.lock().unwrap_or_else(|p| p.into_inner());
    *g = None;
}
