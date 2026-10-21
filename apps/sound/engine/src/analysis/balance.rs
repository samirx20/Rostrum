//! A mix's balance, measured for the readout (agents cannot hear): energy per band — the same bands
//! as `analyze` (sub, bass, lowMid, mid, high) — over where a track sounds, and its level in the
//! speech band (300 Hz – 3.4 kHz) every 100 ms, so TypeScript can tell when a voice is masked by the
//! bed, a lead is buried, or a mix is heavy in the lows or dull on top (src/engine/sound/checks/balance.ts).

use crate::fx::eq::biquad;

pub const BANDS: [(&str, f64, f64); 5] = [("sub", 20.0, 60.0), ("bass", 60.0, 250.0), ("lowMid", 250.0, 1000.0), ("mid", 1000.0, 4000.0), ("high", 4000.0, 16000.0)];
/// The speech band's step (seconds).
pub const SPEECH_STEP: f64 = 0.1;

/// The mono sum through a band-pass (two high-passes at `lo`, two low-passes at `hi`: 24 dB / octave
/// each side), streamed: `each` gets the filtered signal `chunk` samples at a time, in order.
fn band(mono: &[f64], lo: f64, hi: f64, sr: f64, chunk: usize, mut each: impl FnMut(&[f64])) {
    let stages = [biquad("highpass", lo, 0.0, 0.707, sr), biquad("highpass", lo, 0.0, 0.707, sr), biquad("lowpass", hi, 0.0, 0.707, sr), biquad("lowpass", hi, 0.0, 0.707, sr)];
    let mut z = [[0.0f64; 2]; 4];
    let mut out = Vec::with_capacity(chunk);
    for c in mono.chunks(chunk) {
        out.clear();
        out.extend(c.iter().map(|&x| {
            let mut y = x;
            for (s, zz) in stages.iter().zip(z.iter_mut()) {
                y = s.tick(zz, y);
            }
            y
        }));
        each(&out);
    }
}

fn mono(l: &[f32], r: &[f32], total: usize) -> Vec<f64> {
    (0..total.min(l.len()).min(r.len())).map(|i| (l[i] as f64 + r[i] as f64) * 0.5).collect()
}

/// A mean power in dB, to a tenth (−140 for silence): what every readout reports.
pub fn db(power: f64) -> f64 {
    if power > 1e-14 { ((10.0 * power.log10()) * 10.0).round() / 10.0 } else { -140.0 }
}

/// Energy per band (dB, mean power) over the 10 ms frames where the signal sounds (above −50 dBFS).
pub fn bands(l: &[f32], r: &[f32], total: usize, sr: f64) -> [f64; 5] {
    bands_of(&mono(l, r, total), sr)
}

/// `bands` and `speech` of one signal, its mono sum made once (a track's measures, mix/render/).
pub fn bands_and_speech(l: &[f32], r: &[f32], total: usize, sr: f64) -> ([f64; 5], Vec<f64>) {
    let m = mono(l, r, total);
    (bands_of(&m, sr), speech_of(&m, sr))
}

fn bands_of(m: &[f64], sr: f64) -> [f64; 5] {
    let frame = (sr * 0.01).round().max(1.0) as usize;
    let floor = 10f64.powf(-50.0 / 10.0);
    let sounding: Vec<bool> = m.chunks(frame).map(|c| c.iter().map(|x| x * x).sum::<f64>() / c.len() as f64 > floor).collect();
    // The five bands at once, each on its own core.
    let level = |&(_, lo, hi): &(&str, f64, f64)| {
        let (mut sum, mut n, mut f) = (0.0, 0usize, 0);
        band(m, lo, hi.min(sr * 0.45), sr, frame, |c| {
            if sounding[f] {
                sum += c.iter().map(|x| x * x).sum::<f64>();
                n += c.len();
            }
            f += 1;
        });
        if n > 0 { db(sum / n as f64) } else { -140.0 }
    };
    std::thread::scope(|s| {
        let level = &level;
        let jobs: Vec<_> = BANDS.iter().map(|b| s.spawn(move || level(b))).collect();
        let mut out = [-140.0; 5];
        for (k, j) in jobs.into_iter().enumerate() {
            out[k] = j.join().unwrap();
        }
        out
    })
}

/// The speech band's level (dB) every 100 ms.
#[cfg(test)]
pub fn speech(l: &[f32], r: &[f32], total: usize, sr: f64) -> Vec<f64> {
    speech_of(&mono(l, r, total), sr)
}

fn speech_of(m: &[f64], sr: f64) -> Vec<f64> {
    let step = (sr * SPEECH_STEP).round().max(1.0) as usize;
    let mut out = vec![];
    band(m, 300.0, 3400.0, sr, step, |c| out.push(db(c.iter().map(|x| x * x).sum::<f64>() / c.len() as f64)));
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_low_tone_lands_in_the_bass_band_and_a_high_one_up_top() {
        let sr = 44100.0;
        let tone = |hz: f64| -> Vec<f32> { (0..44100).map(|i| (0.5 * (2.0 * std::f64::consts::PI * hz * i as f64 / sr).sin()) as f32).collect() };
        let low = tone(110.0);
        let b = bands(&low, &low, low.len(), sr);
        assert!(b[1] > b[3] + 30.0, "{b:?}");
        let high = tone(6000.0);
        let b = bands(&high, &high, high.len(), sr);
        assert!(b[4] > b[1] + 30.0, "{b:?}");
        let s = speech(&high, &high, high.len(), sr);
        assert_eq!(s.len(), 10);
    }
}
