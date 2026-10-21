//! PSOLA measured on a synthetic voice: the pitch it is asked for, periodic (no roughness), the
//! length kept, formants kept or moved, and a noise burst (a consonant) passed through.

use super::*;

const SR: f64 = 44100.0;

/// A vowel: pulses at f0 (with a ±3 % vibrato, as a voice moves) through resonances at 700 and 1200 Hz.
fn vowel(f0: f64, secs: f64) -> Vec<f32> {
    let n = (secs * SR) as usize;
    let mut x = vec![0f32; n];
    let (mut phase, mut next) = (0.0, 0.0);
    let mut pulses = vec![0.0; n];
    for i in 0..n {
        phase += f0 * (1.0 + 0.03 * (2.0 * std::f64::consts::PI * 5.0 * i as f64 / SR).sin()) / SR;
        if phase >= next {
            pulses[i] = 1.0;
            next += 1.0;
        }
    }
    for (f, bw) in [(700.0, 130.0), (1200.0, 150.0)] {
        let r: f64 = (-std::f64::consts::PI * bw / SR).exp();
        let (c, mut y1, mut y2) = (2.0 * r * (2.0 * std::f64::consts::PI * f / SR).cos(), 0.0, 0.0);
        for i in 0..n {
            let y = pulses[i] + c * y1 - r * r * y2;
            (y2, y1) = (y1, y);
            x[i] += (y * 0.02) as f32;
        }
    }
    x
}

/// Median f0 and how periodic it is (the share of voiced frames) by the same tracker.
fn pitch(x: &[f32]) -> (f64, f64) {
    let tr = crate::stretch::pitchmarks::track(x, SR);
    let mut v: Vec<f64> = tr.f0.iter().cloned().filter(|&f| f > 0.0).collect();
    let share = v.len() as f64 / tr.f0.len() as f64;
    v.sort_by(f64::total_cmp);
    (v[v.len() / 2], share)
}

#[test]
fn shifts_the_pitch_and_stays_periodic() {
    let x = vowel(140.0, 2.0);
    let (f, share0) = pitch(&x);
    assert!((f / 140.0 - 1.0).abs() < 0.01, "tracker: {f} Hz");
    for st in [-5.0, 5.0] {
        let shift = Shift { ratio: 2f64.powf(st / 12.0), formant: Some(1.0), voice: Some(true) };
        let [l, _] = render([&x, &x], x.len(), &|k| k, &shift, SR);
        let (g, share) = pitch(&l);
        let got = 12.0 * (g / 140.0).log2();
        assert!((got - st).abs() < 0.15, "{st} st: got {got:.2}");
        assert!(share > share0 - 0.05, "{st} st: voiced {share:.2} (source {share0:.2})");
        let lv = |y: &[f32]| (y.iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / y.len() as f64).sqrt();
        let db = 20.0 * (lv(&l[4410..l.len() - 4410]) / lv(&x[4410..x.len() - 4410])).log10();
        assert!(db.abs() < 1.5, "{st} st: level {db:.2} dB");
    }
}

#[test]
fn stretches_with_the_pitch_kept() {
    let x = vowel(140.0, 2.0);
    for rate in [0.75, 1.25] {
        let n = (x.len() as f64 / rate) as usize;
        let [l, _] = render([&x, &x], n, &|k| k * rate, &Shift { ratio: 1.0, formant: Some(1.0), voice: Some(true) }, SR);
        let (g, _) = pitch(&l[..n - 2205]);
        assert!((g / 140.0 - 1.0).abs() < 0.01, "rate {rate}: {g} Hz");
    }
}

#[test]
fn a_consonant_passes_through_untouched() {
    // Silence, a 40 ms noise burst at 0.5 s, silence: pitched up, the burst is where it was, as it was.
    let mut x = vec![0f32; SR as usize];
    let mut seed = 1u32;
    for i in 22050..23814 {
        seed = seed.wrapping_mul(1664525).wrapping_add(1013904223);
        x[i] = ((seed >> 8) as f32 / (1u32 << 24) as f32 - 0.5) * 0.6;
    }
    let [l, _] = render([&x, &x], x.len(), &|k| k, &Shift { ratio: 1.5, formant: Some(1.0), voice: Some(true) }, SR);
    let err: f64 = (22300..23500).map(|i| ((l[i] - x[i]) as f64).powi(2)).sum::<f64>() / (22300..23500).map(|i| (x[i] as f64).powi(2)).sum::<f64>();
    assert!(err < 0.01, "burst changed: error {:.1} dB", 10.0 * err.log10());
}

#[test]
fn hears_speech_and_not_a_melody() {
    // Syllables: 200 ms vowels (their pitch moving) and 150 ms gaps.
    let syl = vowel(130.0, 0.2);
    let mut speech = vec![];
    for _ in 0..8 {
        speech.extend_from_slice(&syl);
        speech.extend(std::iter::repeat(0f32).take((0.15 * SR) as usize));
    }
    // A melody: 250 ms notes of steady pitch, played legato-ish with short gaps.
    let mut tune = vec![];
    for f in [262.0, 294.0, 330.0, 349.0, 392.0, 349.0, 330.0, 294.0] {
        let note: Vec<f32> = (0..(0.25 * SR) as usize).map(|i| (0.3 * (2.0 * std::f64::consts::PI * f * i as f64 / SR).sin() * (-(i as f64) / SR / 0.2).exp()) as f32).collect();
        tune.extend_from_slice(&note);
        tune.extend(std::iter::repeat(0f32).take((0.1 * SR) as usize));
    }
    assert!(is_speech([&speech, &speech], SR), "{:?}", speech_features([&speech, &speech], SR));
    assert!(!is_speech([&tune, &tune], SR), "{:?}", speech_features([&tune, &tune], SR));
}
