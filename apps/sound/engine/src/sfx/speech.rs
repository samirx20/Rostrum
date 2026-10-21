//! Voice clips: synthesized speech through the broadcast-mic chain, the formant sketch voice when no
//! speech synthesizer exists, and a waveform-shaped placeholder tone. A port of
//! renderVocalPhraseStereo (src/engine/sound/voiceAndWarpDsp.ts) and the mixdown's waveform branch.

use std::f64::consts::PI;

use crate::mix::schedule::{Pcm, SpeechToken};

/// Mono speech at `pitch_ratio` speed: chest warmth, soft saturation, a 0.4 ms Haas width.
pub fn render_speech(pcm: &Pcm, pitch_ratio: f64, left: &mut [f32], right: &mut [f32], sr: f64) -> Result<(), String> {
    let mono = pcm.read()?;
    if mono.len() < 2 {
        return Ok(());
    }
    let haas = (0.0004 * sr).floor() as usize;
    let alpha = (1.0 / sr) / (1.0 / (2.0 * PI * 240.0) + 1.0 / sr);
    let mut chest = 0.0f64;
    let max_out = left.len().min((mono.len() as f64 / pitch_ratio).floor() as usize);
    for i in 0..max_out {
        let pos = i as f64 * pitch_ratio;
        let idx = (mono.len() - 2).min(pos.floor() as usize);
        let frac = pos - idx as f64;
        let raw = mono[idx] as f64 * (1.0 - frac) + mono[idx + 1] as f64 * frac;
        chest += alpha * (raw - chest);
        let warm = ((raw * 0.9 + chest * 0.45) * 1.45).tanh() * 0.92;
        left[i] = (left[i] as f64 + warm) as f32;
        let r_idx = i.saturating_sub(haas);
        let add = if r_idx < i { left[r_idx] as f64 * 0.98 } else { warm };
        right[i] = (right[i] as f64 + add) as f32;
    }
    Ok(())
}

/// A voice paced by the words (each token's share of the clip), with two moving formants.
pub fn render_voice_sketch(tokens: &[SpeechToken], base_f0: f64, left: &mut [f32], right: &mut [f32], sr: f64) {
    let len = left.len();
    let total_weight = {
        let w: f64 = tokens.iter().map(|t| t.weight).sum();
        if w == 0.0 { 1.0 } else { w }
    };
    let total_dur = len as f64 / sr;
    const FORMANTS: [(f64, f64); 4] = [(680.0, 1150.0), (520.0, 1750.0), (340.0, 2100.0), (560.0, 920.0)];
    let (mut cursor, mut phase) = (0.0f64, 0.0f64);
    let (mut bp1, mut lp1, mut bp2, mut lp2) = (0.0f64, 0.0f64, 0.0f64, 0.0f64);
    let n_tokens = tokens.len() as f64;
    for (k, tok) in tokens.iter().enumerate() {
        let seg = tok.weight / total_weight * total_dur;
        if tok.punct {
            cursor += seg;
            continue;
        }
        let start = (cursor * sr).floor() as usize;
        let seg_samples = (len as i64 - start as i64).min((seg * 0.86 * sr).floor() as i64).max(0) as usize;
        let (f1, f2) = FORMANTS[k % 4];
        let fc1 = 2.0 * (PI * f1 / sr).sin();
        let fc2 = 2.0 * (PI * f2 / sr).sin();
        for i in 0..seg_samples {
            let u = i as f64 / seg_samples as f64;
            let f0 = base_f0 * (1.0 + 0.04 * (PI * u).sin() - 0.04 * (k as f64 / n_tokens));
            phase += 2.0 * PI * f0 / sr;
            let glottal = phase.sin() * 0.5 + (phase * 2.0).sin() * 0.28 + (phase * 3.0).sin() * 0.14 + (phase * 4.0).sin() * 0.08;
            bp1 += fc1 * (glottal - lp1 - 0.25 * bp1);
            lp1 += fc1 * bp1;
            bp2 += fc2 * (glottal - lp2 - 0.3 * bp2);
            lp2 += fc2 * bp2;
            let env = (PI * u.powf(0.7)).sin() * (1.0 - 0.15 * u);
            let s = (bp1 * 0.65 + bp2 * 0.35) * env * 0.75;
            left[start + i] = (left[start + i] as f64 + s) as f32;
            right[start + i] = (right[start + i] as f64 + s) as f32;
        }
        cursor += seg;
    }
}

/// A 220 + 330 Hz tone shaped by the clip's waveform outline (a clip with no audio of its own).
pub fn render_waveform(peaks: &[f64], duration: f64, left: &mut [f32], right: &mut [f32], sr: f64) {
    let n = (duration * sr).floor() as usize;
    for i in 0..n.min(left.len()) {
        let u = i as f64 / (duration * sr);
        let b = (peaks.len() - 1).min((u * peaks.len() as f64).floor() as usize);
        let env = peaks.get(b).copied().unwrap_or(0.3);
        let t = i as f64 / sr;
        let s = (2.0 * PI * 220.0 * t).sin() * 0.5 + (2.0 * PI * 330.0 * t).sin() * 0.3;
        left[i] = (s * env * 0.6) as f32;
        right[i] = (s * env * 0.6) as f32;
    }
}
