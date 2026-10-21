//! Struck bars and tubes by modal synthesis (modal.rs): a marimba's tuned rosewood bars over resonator
//! tubes, a vibraphone's aluminium bars (a damper when the note ends), a glockenspiel's steel bars
//! (untuned, bright overtones) and a tubular bell (a tube whose low modes sound below the heard note:
//! the "strike note" is the ear's, from modes 4 … 6). Each mode is struck as hard as the bar moves at the
//! strike point (the middle leaves out the modes with a node there), and the mallet's contact time —
//! soft yarn or hard plastic, shorter when played harder — decides how far up the strike reaches.

use super::modal::{bar_shape, one_pole, pulse, ring, Mode};
use super::{mix_in, Note, Rng};

pub struct Bar {
    /// Mode frequencies over the heard pitch, and each one's level.
    pub ratios: &'static [(f64, f64)],
    /// The fundamental's ring (s) at C4 and how it shortens per octave up; higher modes ring shorter by ratio^`mode_decay`.
    pub t60: f64,
    pub per_octave: f64,
    pub mode_decay: f64,
    /// Mallet contact (s) for the softest and the hardest mallet.
    pub soft: f64,
    pub hard: f64,
    /// Where the player strikes (0: bar end, 0.5: middle) when the note does not say.
    pub position: f64,
    /// The bar's shape decides each mode's level at the strike point (a tube's does not).
    pub shaped: bool,
    /// A damper stops the note when it ends (vibraphone pedal up), else it rings out.
    pub damper: Option<f64>,
    pub level: f64,
}

const MARIMBA: Bar = Bar { ratios: &[(1.0, 1.0), (3.99, 3.0), (10.1, 1.0), (16.4, 0.2)], t60: 2.6, per_octave: 0.7, mode_decay: 0.9, soft: 0.0019, hard: 0.0004, position: 0.42, shaped: true, damper: None, level: 0.4 };
const VIBRAPHONE: Bar = Bar { ratios: &[(1.0, 1.0), (4.0, 0.45), (10.0, 0.15)], t60: 7.0, per_octave: 0.7, mode_decay: 0.6, soft: 0.0018, hard: 0.0005, position: 0.4, shaped: true, damper: Some(0.22), level: 0.5 };
const GLOCKENSPIEL: Bar = Bar { ratios: &[(1.0, 1.0), (1.06, 0.05), (2.77, 12.0), (5.26, 6.0), (8.6, 0.8), (12.7, 0.3)], t60: 2.4, per_octave: 0.8, mode_decay: 0.45, soft: 0.0008, hard: 0.00015, position: 0.4, shaped: true, damper: None, level: 0.08 };
const TUBULAR: Bar = Bar { ratios: &[(0.62, 0.04), (1.24, 0.12), (2.01, 1.0), (2.016, 0.45), (2.93, 1.0), (2.94, 0.4), (3.98, 0.85), (5.12, 0.8), (5.135, 0.3), (6.4, 0.45), (7.8, 0.2)], t60: 24.0, per_octave: 0.8, mode_decay: 0.35, soft: 0.0015, hard: 0.0003, position: 0.05, shaped: false, damper: None, level: 0.32 };

pub fn bar(name: &str) -> &'static Bar {
    match name {
        "model.vibraphone" => &VIBRAPHONE,
        "model.glockenspiel" => &GLOCKENSPIEL,
        "model.tubularBell" => &TUBULAR,
        _ => &MARIMBA,
    }
}

/// One strike: its modes rung by the mallet's force, plus a little contact noise from a hard mallet.
pub fn strike(b: &Bar, n: &Note, sr: f64) -> Vec<f64> {
    let v = n.velocity.clamp(0.02, 1.0);
    let hardness = n.hardness.unwrap_or(0.5).clamp(0.0, 1.0);
    let contact = b.soft * (b.hard / b.soft).powf(hardness) * (1.25 - 0.45 * v);
    let pos = n.position.unwrap_or(b.position);
    let octave = (n.freq / 261.63).log2();
    let t60 = b.t60 * b.per_octave.powf(octave);
    let mut rng = Rng::new(n.start as u64 * 131 + (n.freq * 10.0) as u64);
    let modes: Vec<Mode> = b.ratios.iter().enumerate().map(|(k, &(r, a))| {
        let shape = if b.shaped { bar_shape(k, pos).abs().max(0.05) } else { 1.0 };
        // Each strike's modes sit a hair apart (the bar warms, the tube swings): never two hits alike.
        let detune = 1.0 + 0.0004 * rng.next() * k as f64;
        Mode { freq: n.freq * r * detune, t60: t60 / r.max(1.0).powf(b.mode_decay), amp: a * shape }
    }).collect();
    let exc = pulse(contact, sr);
    let held = n.len;
    let ring_len = match b.damper {
        Some(d) => held + (d * 1.7 * sr) as usize,
        None => (t60 * 1.7 * sr) as usize,
    };
    let mut out = ring(&modes, &exc, ring_len, b.damper.map(|_| held), b.damper.unwrap_or(1.0), sr);
    // Contact noise: a few ms of the mallet itself, louder and brighter when hard.
    let nlen = (0.006 * sr) as usize;
    let mut noise: Vec<f64> = (0..nlen).map(|i| rng.next() * (1.0 - i as f64 / nlen as f64).powi(2)).collect();
    one_pole(&mut noise, 1500.0 + 6000.0 * hardness, false, sr);
    one_pole(&mut noise, 400.0, true, sr);
    for (o, x) in out.iter_mut().zip(&noise) {
        *o += x * 0.12 * hardness * v;
    }
    let gain = v.powf(1.2) * b.level;
    out.iter_mut().enumerate().for_each(|(i, s)| *s *= gain * n.expression.map_or(1.0, |e| e.gain(i as f64 / sr, held as f64 / sr)));
    out
}

pub fn render(b: &Bar, notes: &[Note], left: &mut [f32], right: &mut [f32], sr: f64) {
    let hits = crate::mix::par::map(notes.to_vec(), |n| (n.start, n.pan, strike(b, &n, sr)));
    for (start, pan, s) in hits {
        mix_in(&s, start, 1.0, pan, left, right);
    }
}
