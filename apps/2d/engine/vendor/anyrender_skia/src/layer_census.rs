//! Rostrum patch (export speed, measurement only): which code opens each offscreen layer or surface, and how big it is.
//! On only while the engine profiles (`ROSTRUM2D_PROFILE`); the render's profile reads and clears it after each paint.

use std::collections::BTreeMap;
use std::sync::{Mutex, OnceLock};

fn on() -> bool {
    static ON: OnceLock<bool> = OnceLock::new();
    *ON.get_or_init(|| std::env::var_os("ROSTRUM2D_PROFILE").is_some_and(|v| !v.is_empty()))
}

/// (site, size bucket) → (count, summed px).
static SEEN: Mutex<BTreeMap<(&'static str, &'static str), (u64, u64)>> = Mutex::new(BTreeMap::new());

fn bucket(w: i32, h: i32) -> &'static str {
    match w as i64 * h as i64 {
        a if a >= 1_900_000 => "frame+",
        a if a >= 500_000 => "quarter+",
        a if a >= 50_000 => "medium",
        _ => "small",
    }
}

/// A layer or surface of w × h px opened at `site`.
pub fn note(site: &'static str, w: i32, h: i32) {
    if on() {
        let mut s = SEEN.lock().unwrap();
        let e = s.entry((site, bucket(w, h))).or_default();
        e.0 += 1;
        e.1 += (w.max(0) as u64) * (h.max(0) as u64);
    }
}

/// A layer just opened on `canvas` at `site` (its size: the canvas's device clip now).
pub fn note_layer(site: &'static str, canvas: &skia_safe::Canvas) {
    if on() {
        let r = canvas.device_clip_bounds().unwrap_or_default();
        note(site, r.width(), r.height());
    }
}

/// What was seen since the last call: (site, bucket, count, megapixels).
pub fn take() -> Vec<(&'static str, &'static str, u64, f64)> {
    std::mem::take(&mut *SEEN.lock().unwrap()).into_iter().map(|((s, b), (n, px))| (s, b, n, px as f64 / 1e6)).collect()
}
