//! The score's instruments and drums, sample by sample: a port of src/engine/sound/instruments.ts
//! (same formulas, same deterministic phases and noise), sample by sample so a live instrument can
//! play the same voices.

pub mod score;
#[cfg(test)]
mod tests;
mod tones;

use std::collections::HashMap;
use std::f64::consts::PI;
use std::sync::{Arc, Mutex, OnceLock};

use crate::instruments::pan_gains;
use tones::Inst;

/// A one-shot's samples (stereo, interleaved), read once per process however many hits play it.
fn one_shot(p: &crate::mix::schedule::Pcm) -> Result<Arc<Vec<f32>>, String> {
    static CACHE: OnceLock<Mutex<HashMap<String, Arc<Vec<f32>>>>> = OnceLock::new();
    let mut cache = CACHE.get_or_init(Default::default).lock().unwrap();
    if let Some(d) = cache.get(&p.file) {
        return Ok(d.clone());
    }
    let raw = p.read()?;
    let stereo: Vec<f32> = if p.channels == 1 { raw.iter().flat_map(|&s| [s, s]).collect() } else { raw };
    let d = Arc::new(stereo);
    cache.insert(p.file.clone(), d.clone());
    Ok(d)
}

/// Seconds a hit cut short fades out over, ending at its cut (so nothing of it sounds after, and it does not click).
pub const CUT_FADE: f64 = 0.01;

/// A hit's length and end fade (samples) from its own length: `cut` (seconds from its start) ends it sooner; `gated`:
/// its own length already stops it short (a one-shot's decay under 1), so it fades as a cut does.
pub fn cut_len(own: usize, cut: Option<f64>, gated: bool, sr: f64) -> (usize, usize) {
    let fade = (CUT_FADE * sr) as usize;
    match cut.map(|c| (c.max(0.0) * sr).round() as usize) {
        Some(c) if c < own => (c, fade),
        _ => (own, if gated { fade } else { 0 }),
    }
}

pub fn fast_noise(idx: f64) -> f64 {
    let x = (idx * 12.9898 + 78.233).sin() * 43758.5453;
    (x - x.floor()) * 2.0 - 1.0
}

/// One sounding partial of a note (a chord is one per pitch) or one drum hit.
pub struct Voice {
    kind: Kind,
    /// Start, in samples into its clip; it sounds for `len` samples.
    pub start: usize,
    pub len: usize,
    /// Samples before `len` over which it fades to silence (0: none): a hit cut short or gated, so it does not click.
    fade: usize,
    sr: f64,
    gain_l: f64,
    gain_r: f64,
    p: [f64; 3],
    lp: [f64; 2],
    bp: [f64; 2],
    formant: [f64; 4],
}

enum Kind {
    /// expr: the note's own glide, vibrato and shape.
    Note { inst: Inst, f: f64, v: f64, dur: f64, expr: Option<crate::instruments::expression::Expression> },
    /// tune: a pitch ratio; decay: a factor of the hit's length.
    Drum { voice: &'static str, tune: f64, decay: f64 },
    /// A one-shot: its samples, read `step` frames per output sample (the tune).
    Hit { data: Arc<Vec<f32>>, step: f64 },
    Synth(Box<crate::instruments::synth::SynthVoice>),
    /// A kit preset's hit (drumsynth.rs).
    Model(Box<crate::instruments::drumsynth::DrumHit>),
}

impl Voice {
    /// The voices of one scheduled note or hit, cut at the clip's end (`clip_len` samples).
    pub fn from_schedule(v: &crate::mix::schedule::Voice, clip_len: usize, sr: f64, out: &mut Vec<Voice>) -> Result<(), String> {
        let blank = |kind, start, len, gl, gr| Voice { kind, start, len, fade: 0, sr, gain_l: gl, gain_r: gr, p: [0.0; 3], lp: [0.0; 2], bp: [0.0; 2], formant: [0.0; 4] };
        match v {
            crate::mix::schedule::Voice::Note { synth: Some(spec), freqs, start_idx, duration, velocity, pan, glide_from, expression, .. } => {
                // A synth: one voice per pitch, panned across the chord like the named instruments.
                let n = freqs.len() as f64;
                for (i, &f) in freqs.iter().enumerate() {
                    let spread = if freqs.len() > 1 { (i as f64 / (n - 1.0) - 0.5) * 0.4 } else { 0.0 };
                    let sv = crate::instruments::synth::SynthVoice::new(spec, f, *duration, velocity / n.powf(0.55), (pan + spread).clamp(-1.0, 1.0), sr);
                    let sv = match glide_from {
                        Some(from) => sv.gliding_from(*from, f),
                        None => sv,
                    };
                    let sv = sv.with_expression(expression.clone()).seeded(crate::instruments::synth::note_seed(*start_idx as u64, f));
                    let len = clip_len.saturating_sub(*start_idx).min(sv.len());
                    if len > 0 {
                        out.push(blank(Kind::Synth(Box::new(sv)), *start_idx, len, 1.0, 1.0));
                    }
                }
            }
            crate::mix::schedule::Voice::Note { instrument, freqs, start_idx, duration, velocity, pan, expression, .. } => {
                let inst = Inst::parse(instrument);
                let total = (duration + inst.release_tail()).max(0.05);
                let len = clip_len.saturating_sub(*start_idx).min((total * sr).floor() as usize);
                if len == 0 || freqs.is_empty() {
                    return Ok(());
                }
                let n = freqs.len() as f64;
                let scale = velocity / n.powf(0.55) * 0.42;
                for (i, &f) in freqs.iter().enumerate() {
                    let vi = i as f64;
                    let spread = if freqs.len() > 1 { (vi / (n - 1.0) - 0.5) * 0.4 } else { 0.0 };
                    let (gl, gr) = pan_gains(pan.clamp(-1.0, 1.0) + spread, scale);
                    let mut voice = blank(Kind::Note { inst, f, v: vi, dur: *duration, expr: expression.clone() }, *start_idx, len, gl, gr);
                    voice.p = [((vi * 1.73 + f * 0.013) % 1.0) * 2.0 * PI, ((vi * 2.91 + f * 0.029) % 1.0) * 2.0 * PI, ((vi * 4.17 + f * 0.043) % 1.0) * 2.0 * PI];
                    out.push(voice);
                }
            }
            crate::mix::schedule::Voice::Drum { voice, start_idx, velocity, pan, tune, decay, cut, sample, model } => {
                let (gl, gr) = pan_gains(*pan, *velocity);
                // Every hit, whichever kit plays it: its own length, then `cut` (cut()) and the clip's end.
                let mut push = |kind, own: usize, gated: bool| {
                    let (len, fade) = cut_len(own, *cut, gated, sr);
                    let len = clip_len.saturating_sub(*start_idx).min(len);
                    if len > 0 {
                        out.push(Voice { fade: fade.min(len / 4), ..blank(kind, *start_idx, len, gl, gr) });
                    }
                };
                if let (Some(m), None) = (model, sample) {
                    let hit = crate::instruments::drumsynth::DrumHit::new(m, *tune, *decay, *start_idx as u64 ^ (voice.len() as u64) << 40, sr);
                    let own = hit.len();
                    push(Kind::Model(Box::new(hit)), own, false);
                    return Ok(());
                }
                if let Some(p) = sample {
                    // A one-shot: its own length at the tuned speed; a decay under 1 gates it (with the cut's fade).
                    let data = one_shot(p)?;
                    let frames = (data.len() / 2) as f64 / tune.max(0.01);
                    push(Kind::Hit { data, step: *tune }, (frames * decay.min(1.0)).floor() as usize, *decay < 1.0);
                    return Ok(());
                }
                let dur = decay * match voice.as_str() {
                    "kick" => 0.42,
                    "snare" | "clap" => 0.26,
                    "openHat" | "cymbal" => 0.55,
                    "tom" => 0.36,
                    _ => 0.08,
                };
                let own = (dur * sr).floor() as usize;
                let voice: &'static str = match voice.as_str() {
                    "kick" => "kick",
                    "snare" => "snare",
                    "clap" => "clap",
                    "hat" => "hat",
                    "openHat" => "openHat",
                    "cymbal" => "cymbal",
                    "tom" => "tom",
                    _ => "rim",
                };
                push(Kind::Drum { voice, tune: *tune, decay: *decay }, own, false);
            }
        }
        Ok(())
    }

    /// The voice's sample at `i` samples after its start.
    pub fn next(&mut self, i: usize) -> (f64, f64) {
        let (l, r) = self.sound(i);
        let left = self.len.saturating_sub(i);
        if left >= self.fade {
            return (l, r);
        }
        let g = left as f64 / self.fade as f64;
        (l * g, r * g)
    }

    fn sound(&mut self, i: usize) -> (f64, f64) {
        let sr = self.sr;
        let t = i as f64 / sr;
        if let Kind::Synth(sv) = &mut self.kind {
            return sv.next(i);
        }
        if let Kind::Model(h) = &mut self.kind {
            let s = h.next(i);
            return (s * self.gain_l, s * self.gain_r);
        }
        match &self.kind {
            Kind::Synth(_) | Kind::Model(_) => unreachable!(),
            Kind::Drum { voice, tune, decay } => {
                let (voice, tune, decay) = (*voice, *tune, *decay);
                let s = self.drum(voice, i, t, tune, decay);
                (s * self.gain_l, s * self.gain_r)
            }
            Kind::Hit { data, step } => {
                // Linear interpolation at the tuned speed.
                let x = i as f64 * step;
                let (k, frac) = (x as usize, x.fract());
                let at = |n: usize, ch: usize| data.get(2 * n + ch).copied().unwrap_or(0.0) as f64;
                let (l, r) = (at(k, 0) * (1.0 - frac) + at(k + 1, 0) * frac, at(k, 1) * (1.0 - frac) + at(k + 1, 1) * frac);
                (l * self.gain_l, r * self.gain_r)
            }
            Kind::Note { inst, f, v, dur, expr } => {
                let (ratio, gain) = expr.as_ref().map_or((1.0, 1.0), |e| (e.ratio(t), e.gain(t, *dur)));
                let (inst, f, v, dur) = (*inst, *f, *v, *dur);
                let (raw_l, raw_r, cutoff, q) = self.note(inst, f * ratio, v, dur, i, t);
                let (raw_l, raw_r) = (raw_l * gain, raw_r * gain);
                let fc = (2.0 * (PI * cutoff.min(sr * 0.38) / sr).sin()).min(0.75);
                let hp_l = raw_l - self.lp[0] - q * self.bp[0];
                self.bp[0] += fc * hp_l;
                self.lp[0] += fc * self.bp[0];
                let hp_r = raw_r - self.lp[1] - q * self.bp[1];
                self.bp[1] += fc * hp_r;
                self.lp[1] += fc * self.bp[1];
                (self.lp[0] * self.gain_l, self.lp[1] * self.gain_r)
            }
        }
    }
}
