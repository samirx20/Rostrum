//! Procedural instruments (no recordings played back): a part's notes rendered together by a physical
//! or learned model — plucked strings by digital waveguides (guitar.rs, string.rs), struck bars, bells
//! and drums by modal synthesis (mallet.rs, kit.rs over modal.rs), and a bowed solo voice by a small
//! learned harmonic-plus-noise decoder (ddsp.rs, ddsp_net.rs). TypeScript decides every note's time,
//! length, velocity and expression (src/core/soundDsl/writing/perform.ts); these only render. A part renders as
//! a whole because the instruments need to see it: a guitar string is cut by the next note on it, a
//! bowed line slurs into the next note, all strings share one body. Deterministic: noise is seeded by
//! where each note starts.

pub mod ddsp;
pub mod ddsp_net;
pub mod guitar;
pub mod kit;
pub mod mallet;
pub mod modal;
pub mod samples;
pub mod string;
#[cfg(test)]
mod tests;

use crate::instruments::expression::Expression;

/// One scheduled note of a part: samples into the clip, its pitch (Hz), 0 … 1 velocity, pan, expression.
#[derive(Clone)]
pub struct Note<'a> {
    pub start: usize,
    pub len: usize,
    pub freq: f64,
    pub velocity: f64,
    pub pan: f64,
    pub expression: Option<&'a Expression>,
    /// The touch: 0 soft … 1 hard (mallet, pick, stick), and where it strikes or plucks (0 … 1).
    pub hardness: Option<f64>,
    pub position: Option<f64>,
    /// Plucked strings: 0 rings open … 1 muted (a palm on the strings), from the note's touch.
    pub damping: Option<f64>,
}

/// The named procedural instruments (the TS side's `instrument: "model.guitar"` …).
pub fn is_model(name: &str) -> bool {
    NAMES.contains(&name)
}

pub const NAMES: [&str; 8] = ["model.guitar", "model.nylonGuitar", "model.marimba", "model.vibraphone", "model.glockenspiel", "model.tubularBell", "model.kit", "ddsp.violin"];

/// A part's notes into the clip's buffers (added to what is there).
pub fn render(name: &str, notes: &[Note], left: &mut [f32], right: &mut [f32], sr: f64) -> Result<(), String> {
    let mut sorted: Vec<Note> = notes.to_vec();
    sorted.sort_by(|a, b| a.start.cmp(&b.start).then(a.freq.total_cmp(&b.freq)));
    match name {
        "model.guitar" => guitar::render(&guitar::STEEL, &sorted, left, right, sr),
        "model.nylonGuitar" => guitar::render(&guitar::NYLON, &sorted, left, right, sr),
        "model.marimba" | "model.vibraphone" | "model.glockenspiel" | "model.tubularBell" => mallet::render(mallet::bar(name), &sorted, left, right, sr),
        "model.kit" => kit::render(&sorted, left, right, sr),
        "ddsp.violin" => ddsp::render(&sorted, left, right, sr)?,
        _ => return Err(format!("no procedural instrument \"{name}\" (have {})", NAMES.join(", "))),
    }
    Ok(())
}

/// Adds a mono signal into the clip at `start`, panned, cut at the clip's end.
pub fn mix_in(sig: &[f64], start: usize, gain: f64, pan: f64, left: &mut [f32], right: &mut [f32]) {
    let (gl, gr) = crate::instruments::pan_gains(pan, 1.0);
    for (i, &s) in sig.iter().enumerate() {
        let k = start + i;
        if k >= left.len() {
            break;
        }
        left[k] = (left[k] as f64 + s * gain * gl) as f32;
        right[k] = (right[k] as f64 + s * gain * gr) as f32;
    }
}

/// Seeded noise in -1 … 1 (splitmix64), the same every render.
pub struct Rng(u64);
impl Rng {
    pub fn new(seed: u64) -> Rng {
        Rng(seed ^ 0x9E37_79B9_7F4A_7C15)
    }
    pub fn next(&mut self) -> f64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^= z >> 31;
        (z >> 11) as f64 / (1u64 << 53) as f64 * 2.0 - 1.0
    }
}

/// Flushes values too small to hear to zero (no denormals in long feedback tails).
#[inline]
pub fn flush(x: f64) -> f64 {
    if x.abs() < 1e-18 { 0.0 } else { x }
}
