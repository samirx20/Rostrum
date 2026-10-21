//! The dialogue repairs, each on a signal whose damage is known exactly.

use std::f64::consts::PI;

const SR: f64 = 48000.0;

struct Rng(u64);
impl Rng {
    fn next(&mut self) -> f64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        (self.0 >> 11) as f64 / (1u64 << 53) as f64 * 2.0 - 1.0
    }
}

fn rms(x: &[f32]) -> f64 {
    (x.iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / x.len().max(1) as f64).sqrt()
}
fn err(a: &[f32], b: &[f32]) -> f64 {
    (a.iter().zip(b).map(|(x, y)| ((x - y) as f64).powi(2)).sum::<f64>() / a.len() as f64).sqrt()
}
fn db(x: f64) -> f64 {
    20.0 * x.max(1e-12).log10()
}
/// A voice-like tone: harmonics of a gliding 140–180 Hz fundamental.
fn voice(n: usize) -> Vec<f32> {
    let mut ph = 0.0;
    (0..n).map(|i| {
        let f0 = 160.0 + 20.0 * (2.0 * PI * 3.0 * i as f64 / SR).sin();
        ph += 2.0 * PI * f0 / SR;
        ((1..12).map(|h| (h as f64 * ph).sin() / h as f64).sum::<f64>() * 0.25) as f32
    }).collect()
}

#[test]
fn declip_redraws_a_clipped_voice_close_to_the_original() {
    let clean = voice(48000);
    // A hot take: its peaks cut 4 dB down.
    let top = clean.iter().fold(0.0f32, |m, v| m.max(v.abs()));
    let mut clipped: Vec<f32> = clean.iter().map(|v| v.clamp(-0.63 * top, 0.63 * top)).collect();
    let before = err(&clipped, &clean);
    let runs = crate::dialogue::lsar::declip(&mut clipped, 0.999);
    let after = err(&clipped, &clean);
    eprintln!("declip: {runs} runs, error {before:.5} → {after:.5}");
    assert!(runs > 50, "runs {runs}");
    // A pulse-like voice is the hard case (its peaks are sharp): half the error goes. A sine comes back exactly.
    assert!(after < before * 0.6, "error {before} → {after}");
    let sine: Vec<f32> = (0..48000).map(|i| (0.5 * (2.0 * PI * 440.0 * i as f64 / SR).sin()) as f32).collect();
    let mut c: Vec<f32> = sine.iter().map(|v| v.clamp(-0.35, 0.35)).collect();
    crate::dialogue::lsar::declip(&mut c, 0.999);
    assert!(err(&c, &sine) < 0.001, "sine error {}", err(&c, &sine));
}

#[test]
fn declick_removes_clicks_and_leaves_a_clean_voice_alone() {
    let mut rng = Rng(7);
    let clean: Vec<f32> = voice(48000).iter().map(|v| v + 0.002 * rng.next() as f32).collect();
    let mut x = clean.clone();
    let mut untouched = clean.clone();
    for k in 0..10 {
        x[3000 + k * 4500] += if k % 2 == 0 { 0.6 } else { -0.6 };
    }
    let before = err(&x, &clean);
    let n = crate::dialogue::declick::declick(&mut x, 5.0, 96);
    assert!(n >= 10, "found {n}");
    assert!(err(&x, &clean) < before * 0.2, "{before} → {}", err(&x, &clean));
    crate::dialogue::declick::declick(&mut untouched, 5.0, 96);
    assert!(err(&untouched, &clean) < 0.002, "a clean voice changed by {}", err(&untouched, &clean));
}

#[test]
fn dehum_finds_a_drifting_50_hz_hum_and_notches_it_out() {
    let mut rng = Rng(3);
    let n = (SR * 6.0) as usize;
    let noise: Vec<f32> = (0..n).map(|_| (0.05 * rng.next()) as f32).collect();
    let hum = |i: usize| (1..6).map(|h| (2.0 * PI * h as f64 * 50.2 * i as f64 / SR).sin() * 0.05 / h as f64).sum::<f64>() as f32;
    let (mut l, mut r): (Vec<f32>, Vec<f32>) = (0..n).map(|i| (noise[i] + hum(i), noise[i] + hum(i))).unzip();
    let found = crate::dialogue::dehum::dehum(&mut l, &mut r, SR, 0.0, 8, 2.0).expect("hum found");
    assert!((found.f0 - 50.2).abs() < 0.1, "f0 {}", found.f0);
    let left: Vec<f32> = l.iter().zip(&noise).map(|(a, b)| a - b).collect();
    let hum_before = rms(&(0..n).map(hum).collect::<Vec<_>>());
    assert!(db(rms(&left[n / 3..]) / hum_before) < -20.0, "hum down {} dB", db(rms(&left[n / 3..]) / hum_before));
    // A recording with no hum is left as it is.
    let (mut a, mut b) = (noise.clone(), noise.clone());
    assert!(crate::dialogue::dehum::dehum(&mut a, &mut b, SR, 0.0, 8, 2.0).is_none());
    assert_eq!(a, noise);
}

#[test]
fn the_deesser_cuts_sibilant_bursts_and_not_the_voice() {
    let mut rng = Rng(11);
    let n = 48000;
    let v = voice(n);
    // Hiss bursts (high-passed noise) in 100 ms of every 400 ms.
    let mut prev = 0.0;
    let hiss: Vec<f32> = (0..n).map(|i| { let w = rng.next(); let h = w - prev; prev = w; if (i / 4800) % 4 == 1 { (h * 0.3) as f32 } else { 0.0 } }).collect();
    let (mut l, mut r): (Vec<f32>, Vec<f32>) = (0..n).map(|i| (v[i] + hiss[i], v[i] + hiss[i])).unzip();
    crate::dialogue::dynamics::deess(&mut [&mut l[..], &mut r[..]], SR, 5000.0, -30.0, 12.0);
    let burst = 4800..9600;
    let quiet = 14400..19200;
    let after_hiss: Vec<f32> = burst.clone().map(|i| l[i] - v[i]).collect();
    let before = rms(&hiss[burst.clone()]);
    assert!(db(rms(&after_hiss) / before) < -4.0, "sibilance down {} dB", db(rms(&after_hiss) / before));
    assert!(err(&l[quiet.clone()], &v[quiet]) < 0.005, "the voice alone changed");
}

#[test]
fn the_gate_closes_on_room_noise_and_opens_for_speech() {
    let mut rng = Rng(5);
    let n = 96000;
    let v = voice(n);
    let src: Vec<f32> = (0..n).map(|i| (if (i / 24000) % 2 == 0 { v[i] } else { 0.0 }) + (0.001 * rng.next()) as f32).collect();
    let (mut l, mut r) = (src.clone(), src.clone());
    crate::dialogue::dynamics::gate(&mut [&mut l[..], &mut r[..]], SR, -45.0, 10.0, 40.0, 2.0, 50.0, 100.0);
    assert!(db(rms(&l[30000..46000]) / rms(&src[30000..46000])) < -25.0, "noise only {} dB down", db(rms(&l[30000..46000]) / rms(&src[30000..46000])));
    assert!(err(&l[2000..22000], &src[2000..22000]) < 0.002, "speech changed");
}

#[test]
fn the_leveller_rides_a_quiet_and_a_loud_phrase_to_one_level() {
    let n = 48000 * 8;
    let v = voice(n);
    let src: Vec<f32> = (0..n).map(|i| v[i] * if i < n / 2 { 0.1 } else { 0.8 }).collect();
    let (mut l, mut r) = (src.clone(), src.clone());
    crate::dialogue::dynamics::leveller(&mut [&mut l[..], &mut r[..]], &[1.0, 1.0], SR, -20.0, 18.0, 18.0, 0.4, -55.0);
    let q = crate::analysis::loudness::integrated_lufs(&l[48000..n / 2 - 48000], &r[48000..n / 2 - 48000], SR);
    let lo = crate::analysis::loudness::integrated_lufs(&l[n / 2 + 48000..n - 48000], &r[n / 2 + 48000..n - 48000], SR);
    assert!((q + 20.0).abs() < 1.5 && (lo + 20.0).abs() < 1.5, "quiet {q} LUFS, loud {lo} LUFS");
}

/// Noise bursts in a room: each followed by an exponential tail of decay time `rt60`.
fn roomy(rt60: f64, seconds: f64) -> (Vec<f32>, Vec<f32>) {
    let mut rng = Rng(9);
    let n = (SR * seconds) as usize;
    let dry: Vec<f32> = (0..n).map(|i| if (i as f64 / SR) % 1.0 < 0.25 { (0.3 * rng.next()) as f32 } else { 0.0 }).collect();
    let ir: Vec<f64> = (0..(SR * rt60 * 1.2) as usize).map(|i| if i == 0 { 1.0 } else { 0.08 * rng.next() * (-6.9 * i as f64 / (SR * rt60)).exp() }).collect();
    let wet = crate::fx::convolve::convolve(&dry, &ir);
    (dry, wet.iter().map(|v| *v as f32).collect())
}

#[test]
fn dereverb_measures_the_room_and_shortens_its_tail() {
    let (dry, wet) = roomy(0.8, 6.0);
    let rt = crate::dialogue::dereverb::decay_time(&wet, &wet, SR).expect("a decay");
    assert!((rt - 0.8).abs() < 0.25, "rt60 {rt}");
    let (mut l, mut r) = (wet.clone(), wet.clone());
    crate::dialogue::dereverb::dereverb(&mut l, &mut r, SR, 1.0, 20.0, 0.0).unwrap();
    // The tail 100–600 ms after each burst ends.
    let tail = |x: &[f32]| rms(&(0..5).flat_map(|s| ((s as f64 + 0.35) * SR) as usize..((s as f64 + 0.85) * SR) as usize).map(|i| x[i]).collect::<Vec<_>>());
    assert!(db(tail(&l) / tail(&wet)) < -6.0, "tail down {} dB", db(tail(&l) / tail(&wet)));
    let _ = dry;
}

#[test]
fn spectral_repair_takes_a_burst_down_to_its_surroundings() {
    let mut rng = Rng(13);
    let n = 48000 * 2;
    let floor: Vec<f32> = (0..n).map(|_| (0.01 * rng.next()) as f32).collect();
    // A 1.5 kHz tone burst ("a squeak") at 0.8–1.0 s.
    let x: Vec<f32> = (0..n).map(|i| floor[i] + if (38400..48000).contains(&i) { (0.3 * (2.0 * PI * 1500.0 * i as f64 / SR).sin()) as f32 } else { 0.0 }).collect();
    let (mut l, mut r) = (x.clone(), x.clone());
    crate::dialogue::dereverb::repair(&mut l, &mut r, SR, &[crate::mix::schedule::Repair { at: 0.8, duration: 0.2, low_hz: 1300.0, high_hz: 1700.0 }]);
    let span = 39000..47000;
    assert!(rms(&l[span.clone()]) < 2.0 * rms(&floor[span.clone()]), "{} vs floor {}", rms(&l[span.clone()]), rms(&floor[span]));
    assert!(err(&l[0..30000], &x[0..30000]) < 1e-4, "outside the region nothing changes");
}

#[test]
fn match_eq_applies_its_curve_in_either_phase_without_delay_in_linear() {
    let n = 48000;
    let sine: Vec<f32> = (0..n).map(|i| (0.25 * (2.0 * PI * 1000.0 * i as f64 / SR).sin()) as f32).collect();
    let curve = [[100.0, 0.0], [700.0, 0.0], [1000.0, 6.0], [1400.0, 0.0]];
    for phase in ["linear", "minimum"] {
        let (mut l, mut r) = (sine.clone(), sine.clone());
        crate::fx::matcheq::apply(&mut l, &mut r, &curve, phase, SR);
        let g = db(rms(&l[8000..40000]) / rms(&sine[8000..40000]));
        assert!((g - 6.0).abs() < 0.5, "{phase}: {g} dB");
        if phase == "linear" {
            let scaled: Vec<f32> = sine.iter().map(|v| v * 10f32.powf(g as f32 / 20.0)).collect();
            assert!(err(&l[8000..40000], &scaled[8000..40000]) < 0.01, "linear phase shifted the signal");
        }
    }
}

#[test]
fn loudness_stats_read_a_steady_tone_as_bs1770_says() {
    let n = 48000 * 10;
    let x: Vec<f32> = (0..n).map(|i| (0.1 * (2.0 * PI * 1000.0 * i as f64 / SR).sin()) as f32).collect();
    let s = crate::analysis::loudstats::stats(&x, &x, SR);
    // Peak 0.1 (−23 dB RMS) in both channels: −23 + 3.01 (two channels) − 0.69 + K-weighting at 1 kHz (≈ +0.69) ≈ −20 LUFS.
    assert!((s.max_momentary + 20.0).abs() < 0.3 && (s.max_short_term + 20.0).abs() < 0.3, "{} {}", s.max_momentary, s.max_short_term);
    assert!(s.lra < 0.2, "lra {}", s.lra);
}

#[test]
fn loudness_series_has_one_short_term_value_per_hop_and_a_windowed_correlation() {
    // 6 s: the same tone in both channels for 3 s, then the right channel inverted, then 1 s of silence is not needed.
    let n = 48000 * 6;
    let l: Vec<f32> = (0..n).map(|i| (0.1 * (2.0 * PI * 1000.0 * i as f64 / SR).sin()) as f32).collect();
    let r: Vec<f32> = l.iter().enumerate().map(|(i, v)| if i < n / 2 { *v } else { -*v }).collect();
    let s = crate::analysis::loudstats::stats(&l, &r, SR);
    assert_eq!(s.short_term.len(), 60 - 30 + 1, "windows from the first full 3 s on, hop 100 ms");
    assert_eq!(s.correlation.len(), 60 - 4 + 1);
    assert!((s.short_term[0] + 20.0).abs() < 0.3 && (s.short_term.iter().copied().fold(-99.0, f64::max) - s.max_short_term).abs() < 1e-9);
    assert!(s.correlation[0].unwrap() > 0.999, "{:?}", s.correlation[0]);
    assert!(s.correlation.last().unwrap().unwrap() < -0.999);
    let min = s.correlation.iter().flatten().copied().fold(1.0, f64::min);
    assert!(min < -0.999, "{min}");
    let mono = crate::analysis::loudstats::stats_n(&[&l], &[1.0], SR);
    assert!(mono.correlation.is_empty());
}
