//! Time-stretch and pitch-shift of a whole clip, by content: speech through PSOLA (psola.rs: no
//! phasiness, consonants untouched), music through Signalsmith Stretch (MIT, vendored C++,
//! vendor/signalsmith-stretch) driven along a time map, then the source's transients spliced back in
//! (transients.rs). Rendered once and kept in the stretch cache, keyed by the job's version, the
//! source samples, the map and the shift (rule 9): a preview, lint and export read the same result.

pub mod pitchmarks;
pub mod psola;
pub mod speed;
pub mod transients;

use std::hash::{Hash, Hasher};

/// What this job produces; bump on any change to it (the cache key holds it).
pub const VERSION: &str = "signalsmith-1.3.1+psola+rostrum-11";

unsafe extern "C" {
    fn rs_stretch_new(channels: i32, sample_rate: f32) -> *mut std::ffi::c_void;
    fn rs_stretch_free(s: *mut std::ffi::c_void);
    fn rs_stretch_input_latency(s: *mut std::ffi::c_void) -> i32;
    fn rs_stretch_output_latency(s: *mut std::ffi::c_void) -> i32;
    fn rs_stretch_set(s: *mut std::ffi::c_void, transpose: f32, tonality_limit: f32, formant: f32, keep_formants: i32);
    fn rs_stretch_seek(s: *mut std::ffi::c_void, inputs: *const *const f32, n: i32, rate: f64);
    fn rs_stretch_process(s: *mut std::ffi::c_void, inputs: *const *const f32, n_in: i32, outputs: *const *mut f32, n_out: i32);
    fn rs_stretch_flush(s: *mut std::ffi::c_void, outputs: *const *mut f32, n: i32);
}

/// The pitch side of a stretch: a frequency ratio, formants (None: they move with the pitch;
/// Some(ratio): kept where they are, times the ratio — 1 keeps a voice's own), and the content
/// (Some(true): a voice, PSOLA; Some(false): music, Signalsmith; None: listened for, psola::is_speech).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Shift {
    pub ratio: f64,
    pub formant: Option<f64>,
    pub voice: Option<bool>,
}

struct Stretcher(*mut std::ffi::c_void);
impl Drop for Stretcher {
    fn drop(&mut self) {
        unsafe { rs_stretch_free(self.0) }
    }
}

/// Output sample k reads the source at `map(k)` (source samples, monotone; outside the source is silence).
/// Returns the two channels, `out_len` long.
#[cfg(test)]
pub fn render(src: [&[f32]; 2], out_len: usize, map: &dyn Fn(f64) -> f64, shift: &Shift, sr: f64) -> [Vec<f32>; 2] {
    let [l, r]: [Vec<f32>; 2] = render_n(&src, out_len, map, shift, sr).try_into().expect("two channels in, two out");
    [l, r]
}

/// `render` for any number of channels, read along one map (a surround bed stays phase-coherent: one
/// stretcher over all its channels). Only a stereo source can be a voice (PSOLA).
pub fn render_n(src: &[&[f32]], out_len: usize, map: &dyn Fn(f64) -> f64, shift: &Shift, sr: f64) -> Vec<Vec<f32>> {
    let listened = || if src.len() == 2 { crate::stretch::psola::is_speech([src[0], src[1]], sr) } else { false };
    let shift = &Shift { voice: Some(shift.voice.unwrap_or_else(listened)), ..*shift };
    let n = src.len();
    // The map sampled every 256 output samples is its identity in the key (it is piecewise smooth).
    let mut h = std::collections::hash_map::DefaultHasher::new();
    (VERSION, out_len, sr.to_bits(), shift.ratio.to_bits(), shift.formant.map(f64::to_bits), shift.voice, src[0].len()).hash(&mut h);
    (0..=out_len).step_by(256).chain([out_len]).for_each(|k| map(k as f64).to_bits().hash(&mut h));
    src.iter().for_each(|c| c.iter().for_each(|s| s.to_bits().hash(&mut h)));
    let cache = crate::mix::cache::dir("stretch");
    let name = format!("{:016x}.f32", h.finish());
    if let Some(bytes) = cache.as_deref().and_then(|d| crate::mix::cache::read(d, &name)) {
        if bytes.len() == out_len * 4 * n {
            let at = |i: usize| f32::from_le_bytes(bytes[4 * i..4 * i + 4].try_into().unwrap());
            return (0..n).map(|c| (0..out_len).map(|i| at(n * i + c)).collect()).collect();
        }
    }
    let out = process_n(src, out_len, map, shift, sr);
    if let Some(dir) = &cache {
        let bytes: Vec<u8> = (0..out_len).flat_map(|i| out.iter().flat_map(move |c| c[i].to_le_bytes())).collect();
        crate::mix::cache::write(dir, &name, &bytes);
    }
    out
}

/// The stretch itself, uncached: a voice through PSOLA, music through the stretcher along the map;
/// the source's hits (a voice's consonants) spliced back in. (Content not said is music here; render listens for it.)
#[cfg(test)]
pub fn process(src: [&[f32]; 2], out_len: usize, map: &dyn Fn(f64) -> f64, shift: &Shift, sr: f64) -> [Vec<f32>; 2] {
    let [l, r]: [Vec<f32>; 2] = process_n(&src, out_len, map, shift, sr).try_into().expect("two channels in, two out");
    [l, r]
}

fn process_n(src: &[&[f32]], out_len: usize, map: &dyn Fn(f64) -> f64, shift: &Shift, sr: f64) -> Vec<Vec<f32>> {
    let mut out = match (shift.voice, src) {
        (Some(true), [l, r]) => crate::stretch::psola::render([*l, *r], out_len, map, shift, sr).into(),
        _ => stretch(src, out_len, map, shift, sr),
    };
    crate::stretch::transients::splice(&mut out, src, map, shift, sr);
    out
}

/// The stretcher along the map: pre-rolled on the input's first block, fed in 256-sample output
/// blocks (each consuming what the map says), then shifted by its output latency and flushed — what
/// Signalsmith's own `exact` does for one constant rate, here for any map.
fn stretch(src: &[&[f32]], out_len: usize, map: &dyn Fn(f64) -> f64, shift: &Shift, sr: f64) -> Vec<Vec<f32>> {
    let s = Stretcher(unsafe { rs_stretch_new(src.len() as i32, sr as f32) });
    // Kept formants: only the voice's tonal part is transposed (sibilance above 8 kHz stays as it was).
    let limit = if shift.formant.is_some() { (8000.0 / sr) as f32 } else { 0.0 };
    unsafe { rs_stretch_set(s.0, shift.ratio as f32, limit, shift.formant.unwrap_or(1.0) as f32, shift.formant.is_some() as i32) };
    let (in_lat, out_lat) = unsafe { (rs_stretch_input_latency(s.0) as usize, rs_stretch_output_latency(s.0) as usize) };
    let base = map(0.0).round() as i64;
    let read = |from: i64, n: usize| -> Vec<Vec<f32>> {
        let get = |c: &[f32], i: i64| if i >= 0 && (i as usize) < c.len() { c[i as usize] } else { 0.0 };
        src.iter().map(|c| (0..n as i64).map(|i| get(c, from + i)).collect()).collect()
    };
    let ptrs = |b: &[Vec<f32>]| b.iter().map(|c| c.as_ptr()).collect::<Vec<_>>();
    let pre = read(base, in_lat);
    let rate0 = ((map(256.0) - map(0.0)) / 256.0).max(1e-3);
    unsafe { rs_stretch_seek(s.0, ptrs(&pre).as_ptr(), in_lat as i32, rate0) };
    let mut raw = vec![vec![0f32; out_len]; src.len()];
    let (mut j, mut consumed) = (0usize, 0i64);
    while j < out_len {
        let end = (j + 256).min(out_len);
        let upto = (map(end as f64) - map(0.0)).round() as i64;
        let n = (upto - consumed).max(0) as usize;
        let input = read(base + in_lat as i64 + consumed, n);
        let outs: Vec<*mut f32> = raw.iter_mut().map(|c| c[j..].as_mut_ptr()).collect();
        unsafe { rs_stretch_process(s.0, ptrs(&input).as_ptr(), n as i32, outs.as_ptr(), (end - j) as i32) };
        consumed += n as i64;
        j = end;
    }
    if out_len < out_lat * 2 {
        // Too short for the stretcher's latency: what it made, unshifted, is the best there is.
        return raw;
    }
    for ch in raw.iter_mut() {
        // Fold the pre-roll's reflection back, then take the latency out (as `exact` does).
        for i in 0..(out_len - out_lat).min(out_lat) {
            ch[i + out_lat] -= ch[out_lat - 1 - i];
        }
        ch.copy_within(out_lat.., 0);
    }
    let outs: Vec<*mut f32> = raw.iter_mut().map(|c| c[out_len - out_lat..].as_mut_ptr()).collect();
    unsafe { rs_stretch_flush(s.0, outs.as_ptr(), out_lat as i32) };
    raw
}

#[cfg(test)]
mod tests;
