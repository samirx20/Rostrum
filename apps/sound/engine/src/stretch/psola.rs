//! Speech: time-domain pitch-synchronous overlap-add (TD-PSOLA; Moulines & Charpentier 1990), the
//! method Praat and most voice tools use. Each glottal period is cut out (a Hann window two periods
//! wide on its pitch mark, pitchmarks.rs) and laid down again one new period apart: the pitch moves,
//! each grain keeps its spectral shape, so the formants stay (no phase vocoder: no phasiness).
//! Time follows the map: output time t plays the grain of the mark nearest map(t), so grains repeat or
//! drop. Unvoiced sound (consonants, breath) is overlap-added straight from the map, untouched by the pitch.
//! Formants moved (with the pitch, or by a shift) resample each voiced grain.

use crate::stretch::pitchmarks::{marks, track};
use crate::stretch::Shift;

pub fn render(src: [&[f32]; 2], out_len: usize, map: &dyn Fn(f64) -> f64, shift: &Shift, sr: f64) -> [Vec<f32>; 2] {
    let n = src[0].len().min(src[1].len());
    let mono: Vec<f32> = (0..n).map(|i| 0.5 * (src[0][i] + src[1][i])).collect();
    let pm = marks(&mono, sr, &track(&mono, sr));
    let mut out = [vec![0f64; out_len], vec![0f64; out_len]];
    let mut wsum = vec![0f64; out_len];
    if pm.is_empty() {
        return [vec![0f32; out_len], vec![0f32; out_len]];
    }
    // Formants: resampled by this factor inside each voiced grain (1: kept where they are).
    let phi = shift.formant.unwrap_or(shift.ratio);
    let unvoiced_step = 0.005 * sr;
    let read = |c: &[f32], p: f64| {
        let i = p.floor();
        if i < 0.0 || i as usize + 1 >= n {
            return 0.0;
        }
        let f = p - i;
        c[i as usize] as f64 * (1.0 - f) + c[i as usize + 1] as f64 * f
    };
    let (mut t, mut was_voiced) = (0.0f64, false);
    while (t as usize) < out_len {
        let mut s = map(t);
        let k = pm.partition_point(|&(m, _)| (m as f64) < s);
        let k = if k == 0 { 0 } else if k >= pm.len() || s - pm[k - 1].0 as f64 <= pm[k].0 as f64 - s { k - 1 } else { k };
        let (m, p) = pm[k];
        let voiced = p > 0.0;
        if voiced && !was_voiced {
            // A voiced stretch starts on its first pulse where the map puts it, so it meets the
            // unvoiced sound before it in step (no doubled pulse at the seam).
            let rate = (map(t + 64.0) - s) / 64.0;
            let dt = (m as f64 - s) / rate.max(1e-3);
            if dt.abs() < p {
                t = (t + dt).max(0.0);
                s = map(t);
            }
        }
        was_voiced = voiced;
        // Voiced: the period on its mark. Unvoiced: the source right where the map says, so noise
        // (a consonant, a breath) is overlap-added back as it was.
        let centre = if voiced { m as f64 } else { s };
        // Grain half-width in the source, and how fast it is read (formant factor) where voiced.
        // Lowered, a voiced grain reaches over the wider new period (its neighbours' pulses come in at
        // the window's foot) so the periods join without a gap.
        let (half, rate) = if voiced { (p * (1.0 / shift.ratio).max(1.0), phi) } else { (unvoiced_step, 1.0) };
        let reach = half / rate;
        let a = (t - reach).ceil().max(0.0) as usize;
        let b = ((t + reach).floor() as usize).min(out_len - 1);
        for i in a..=b {
            let u = (i as f64 - t) * rate; // source offset from the mark
            let w = 0.5 + 0.5 * (std::f64::consts::PI * u / half).cos();
            for ch in 0..2 {
                out[ch][i] += w * read(src[ch], centre + u);
            }
            wsum[i] += w;
        }
        // The next grain: one new period on where voiced, the unvoiced spacing elsewhere.
        t += if voiced { p / shift.ratio } else { unvoiced_step };
    }
    // Overlapping grains of one period add in phase: dividing by the window sum keeps the level.
    let norm = |i: usize| 1.0 / wsum[i].max(0.5);
    let [l, r] = out;
    [(0..out_len).map(|i| (l[i] * norm(i)) as f32).collect(), (0..out_len).map(|i| (r[i] * norm(i)) as f32).collect()]
}

/// Speech or not, for a clip that does not say: voiced 10-90 % of the time, in stretches under
/// half a second that start at least twice a second (syllables), at a speaking pitch that keeps
/// moving inside each stretch (intonation, over 0.1 semitone: a played note holds its pitch; measured:
/// a spoken line 0.23, a piano melody 0.02).
pub fn is_speech(x: [&[f32]; 2], sr: f64) -> bool {
    let f = speech_features(x, sr);
    (0.1..0.9).contains(&f[0]) && f[1] < 0.5 && f[2] >= 2.0 && (70.0..400.0).contains(&f[3]) && f[4] > 0.1
}

/// Speech mixed with other sound (a voice over a music bed), which the pitch tracker only half
/// follows, so is_speech says no: short voiced stretches (under 0.12 s) starting over 3.5 times a
/// second (syllables), voiced 10–70 % of the time, at a speaking pitch (80–350 Hz). Measured on 8
/// Qwen3-TTS lines over 4 benchmark beds 6 and 12 dB under: music beds alone never pass (their
/// stretches are long, few, or at a bass's pitch). A hint only: the stretcher is chosen by is_speech.
pub fn speech_in_mix(f: &[f64; 5]) -> bool {
    (0.1..0.7).contains(&f[0]) && f[1] < 0.12 && f[2] >= 3.5 && (80.0..350.0).contains(&f[3])
}

/// [voiced share, median voiced stretch (s), stretches per second, median f0 (Hz), median pitch
/// movement inside a stretch (semitones, standard deviation)].
pub fn speech_features(x: [&[f32]; 2], sr: f64) -> [f64; 5] {
    let n = x[0].len().min(x[1].len());
    let mono: Vec<f32> = (0..n).map(|i| 0.5 * (x[0][i] + x[1][i])).collect();
    let tr = track(&mono, sr);
    let hop_s = tr.hop as f64 / sr;
    let runs: Vec<&[f64]> = tr.f0.split(|&f| f <= 0.0).filter(|r| !r.is_empty()).collect();
    if runs.is_empty() {
        return [0.0; 5];
    }
    let median = |mut v: Vec<f64>| {
        v.sort_by(f64::total_cmp);
        v[v.len() / 2]
    };
    let nv: usize = runs.iter().map(|r| r.len()).sum();
    let moving: Vec<f64> = runs.iter().filter(|r| r.len() >= 4).map(|r| {
        let st: Vec<f64> = r.iter().map(|f| 12.0 * f.log2()).collect();
        let mean = st.iter().sum::<f64>() / st.len() as f64;
        (st.iter().map(|s| (s - mean).powi(2)).sum::<f64>() / st.len() as f64).sqrt()
    }).collect();
    let seconds = (tr.f0.len() as f64 * hop_s).max(1e-6);
    [
        nv as f64 / tr.f0.len().max(1) as f64,
        median(runs.iter().map(|r| r.len() as f64 * hop_s).collect()),
        runs.len() as f64 / seconds,
        median(runs.iter().flat_map(|r| r.iter().cloned()).collect()),
        if moving.is_empty() { 0.0 } else { median(moving) },
    ]
}

#[cfg(test)]
#[path = "psola_tests.rs"]
mod tests;
