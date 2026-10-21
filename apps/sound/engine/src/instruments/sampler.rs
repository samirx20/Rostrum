//! The sampler (src/core/soundDsl/instruments/sampler.ts decides the preset): a SoundFont played by
//! rustysynth (MIT). A drum kit is one synthesizer per clip, so its hits share polyphony and choke
//! like a kit. A melodic note renders on its own (the synthesizer reset between notes), so it can
//! carry its own expression (glide, vibrato through pitch bend; a dynamic shape) and humanizing: a
//! low-pass that opens with velocity, a softer attack when soft, and its own micro-variation
//! (detune, a later start into the sample, a small body peak). Pitch moves on the synthesizer's
//! 64-sample blocks (1.5 ms at 44.1 kHz), the same every render. Fonts load once per process.

use std::collections::HashMap;
use std::fs::File;
use std::io::BufReader;
use std::sync::{Arc, Mutex, OnceLock};

use rustysynth::{SoundFont, Synthesizer, SynthesizerSettings};
use serde::Deserialize;

use crate::instruments::expression::{Expression, Variation};

#[derive(Deserialize, Clone, Debug)]
pub struct SamplerSpec {
    pub font: String,
    pub program: i32,
    pub bank: i32,
    pub drums: bool,
    /// Velocity opens a low-pass and rounds soft attacks (TypeScript resolves it; off for kits).
    #[serde(default)]
    pub humanize: bool,
}

/// A sampled note: start (samples into the clip), length (samples), its pitches, velocity 0..1,
/// and what shapes it.
pub struct Note<'a> {
    pub start: usize,
    pub len: usize,
    pub freqs: &'a [f64],
    pub velocity: f64,
    pub expression: Option<&'a Expression>,
    pub variation: Option<&'a Variation>,
}

fn font(path: &str) -> Result<Arc<SoundFont>, String> {
    static FONTS: OnceLock<Mutex<HashMap<String, Arc<SoundFont>>>> = OnceLock::new();
    let mut fonts = FONTS.get_or_init(Default::default).lock().unwrap();
    if let Some(f) = fonts.get(path) {
        return Ok(f.clone());
    }
    let mut reader = BufReader::new(File::open(path).map_err(|e| format!("{path}: {e}"))?);
    let f = Arc::new(SoundFont::new(&mut reader).map_err(|e| format!("{path}: not a readable SoundFont ({e:?})"))?);
    fonts.insert(path.to_string(), f.clone());
    Ok(f)
}

/// MIDI key nearest a frequency.
fn key(freq: f64) -> i32 {
    (69.0 + 12.0 * (freq / 440.0).log2()).round().clamp(0.0, 127.0) as i32
}

/// Adds the clip's sampled notes into its buffers.
pub fn render(spec: &SamplerSpec, notes: &[Note], left: &mut [f32], right: &mut [f32], sr: f64) -> Result<(), String> {
    let (mut synth, ch) = synthesizer(spec, sr)?;
    if !spec.drums {
        for n in notes {
            note(&mut synth, spec, n, left, right, sr);
        }
        return Ok(());
    }
    // A kit: (sample, 0 = off / 1 = on, key, velocity): offs first at the same sample, so a repeat re-strikes.
    let mut events: Vec<(usize, u8, i32, i32)> = vec![];
    for n in notes {
        for &f in n.freqs {
            events.push((n.start, 1, key(f), midi_velocity(n.velocity)));
            events.push((n.start + n.len, 0, key(f), 0));
        }
    }
    play(&mut synth, ch, events, left, right);
    Ok(())
}

fn midi_velocity(v: f64) -> i32 {
    (v.clamp(0.0, 1.0) * 127.0).round().max(1.0) as i32
}

const BLOCK: usize = 64;
/// The longest a released note rings (its release ends sooner: the synthesizer then outputs zeros).
const MAX_RING: f64 = 8.0;

/// One melodic note, rendered alone and mixed in at its start.
fn note(synth: &mut Synthesizer, spec: &SamplerSpec, n: &Note, left: &mut [f32], right: &mut [f32], sr: f64) {
    let room = left.len().min(right.len()).saturating_sub(n.start);
    if room == 0 || n.freqs.is_empty() {
        return;
    }
    synth.reset();
    synth.process_midi_message(0, 0xB0, 0x00, spec.bank);
    synth.process_midi_message(0, 0xC0, spec.program, 0);
    // A pitch between keys (a layer's fine detune, a fractional transpose) is the nearest key bent the rest of the way.
    let fine = n.freqs.first().map_or(0.0, |&f| 1200.0 * (f / (440.0 * 2f64.powf((key(f) - 69) as f64 / 12.0))).log2());
    let var_cents = n.variation.map_or(0.0, |v| v.cents) + fine;
    let reach = n.expression.map_or(0.0, |e| e.reach()) + var_cents.abs();
    // Pitch bend range (RPN 0) wide enough for the note's glide and vibrato, in whole semitones.
    let range = ((reach / 100.0).ceil() as i32 + 1).clamp(2, 96);
    for (cc, v) in [(0x65, 0), (0x64, 0), (0x06, range), (0x26, 0)] {
        synth.process_midi_message(0, 0xB0, cc, v);
    }
    let bend = |cents: f64| (8192.0 + cents / (range as f64 * 100.0) * 8192.0).round().clamp(0.0, 16383.0) as i32;
    // The variation's later start: that much of the rendered note is dropped.
    let skip = n.variation.map_or(0, |v| (v.offset.max(0.0) * sr).round() as usize);
    let off_at = n.len + skip;
    let limit = (room + skip).min(off_at + (MAX_RING * sr) as usize);
    let (mut bl, mut br) = (Vec::with_capacity(limit), Vec::with_capacity(limit));
    for &f in n.freqs {
        synth.note_on(0, key(f), midi_velocity(n.velocity));
    }
    let mut pos = 0;
    while pos < limit {
        let end = if pos < off_at { (pos + BLOCK).min(off_at) } else { pos + BLOCK }.min(limit);
        let t = (pos as f64 - skip as f64) / sr;
        let cents = var_cents + n.expression.map_or(0.0, |e| e.cents(t.max(0.0)));
        let b = bend(cents);
        synth.process_midi_message(0, 0xE0, b & 0x7F, b >> 7);
        let at = bl.len();
        bl.resize(end, 0.0);
        br.resize(end, 0.0);
        synth.render(&mut bl[at..], &mut br[at..]);
        if end == off_at {
            for &f in n.freqs {
                synth.note_off(0, key(f));
            }
        }
        // Released and silent: the note has ended.
        if end > off_at && bl[at..].iter().chain(&br[at..]).all(|v| v.abs() < 1e-7) {
            break;
        }
        pos = end;
    }
    let (mut l, mut r) = (bl.split_off(skip.min(bl.len())), br.split_off(skip.min(br.len())));
    shape(spec, n, &mut l, &mut r, sr);
    for (i, (a, b)) in l.iter().zip(&r).enumerate() {
        left[n.start + i] += a;
        right[n.start + i] += b;
    }
}

/// A rendered note's tone and level: the velocity low-pass, the body peak, the soft attack, its shape.
fn shape(spec: &SamplerSpec, n: &Note, l: &mut [f32], r: &mut [f32], sr: f64) {
    use crate::instruments::expression::{soft_attack, velocity_cutoff};
    if spec.humanize {
        let top = n.freqs.iter().cloned().fold(0.0, f64::max);
        let lp = crate::fx::eq::biquad("lowpass", velocity_cutoff(n.velocity, top, sr), 0.0, 0.707, sr);
        lp.run(l);
        lp.run(r);
    }
    if let Some(v) = n.variation.filter(|v| v.formant_db != 0.0) {
        let peak = crate::fx::eq::biquad("peak", v.formant_hz, v.formant_db, 1.2, sr);
        peak.run(l);
        peak.run(r);
    }
    let attack = if spec.humanize { soft_attack(n.velocity) * sr } else { 0.0 };
    let dur = n.len as f64 / sr;
    for i in 0..l.len() {
        let mut g = n.expression.map_or(1.0, |e| e.gain(i as f64 / sr, dur));
        if (i as f64) < attack {
            g *= 0.5 - 0.5 * (std::f64::consts::PI * i as f64 / attack).cos();
        }
        l[i] = (l[i] as f64 * g) as f32;
        r[i] = (r[i] as f64 * g) as f32;
    }
}

/// A synthesizer set to the spec's preset, and the MIDI channel its notes go to (offline and live alike).
pub fn synthesizer(spec: &SamplerSpec, sr: f64) -> Result<(Synthesizer, i32), String> {
    let mut settings = SynthesizerSettings::new(sr as i32);
    settings.enable_reverb_and_chorus = false; // the track's own effects and sends do that
    let mut synth = Synthesizer::new(&font(&spec.font)?, &settings).map_err(|e| format!("{}: {e:?}", spec.font))?;
    // rustysynth's default master volume is 0.5; at 1.0 a General MIDI preset sits near the built-in instruments' level.
    synth.set_master_volume(1.0);
    let ch = if spec.drums { 9 } else { 0 };
    if !spec.drums {
        synth.process_midi_message(ch, 0xB0, 0x00, spec.bank); // bank select
        synth.process_midi_message(ch, 0xC0, spec.program, 0); // program change
    }
    Ok((synth, ch))
}

/// Plays timed (sample, on/off, key, velocity) events into the buffers.
fn play(synth: &mut Synthesizer, ch: i32, mut events: Vec<(usize, u8, i32, i32)>, left: &mut [f32], right: &mut [f32]) {
    events.sort();
    let total = left.len().min(right.len());
    let (mut bl, mut br) = (vec![0.0f32; total], vec![0.0f32; total]);
    let mut pos = 0;
    for (at, kind, k, vel) in events {
        let at = at.min(total);
        if at > pos {
            synth.render(&mut bl[pos..at], &mut br[pos..at]);
            pos = at;
        }
        if kind == 1 {
            synth.note_on(ch, k, vel);
        } else {
            synth.note_off(ch, k);
        }
    }
    if pos < total {
        synth.render(&mut bl[pos..], &mut br[pos..]);
    }
    for i in 0..total {
        left[i] += bl[i];
        right[i] += br[i];
    }
}

#[cfg(test)]
#[path = "sampler_tests.rs"]
mod tests;
