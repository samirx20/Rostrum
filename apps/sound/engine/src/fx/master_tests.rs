use super::*;
use crate::analysis::loudness::{integrated_lufs, true_peak_db};

fn sine(f: f64, db: f64, secs: f64, sr: f64) -> (Vec<f32>, Vec<f32>) {
    let a = 10f64.powf(db / 20.0);
    let x: Vec<f32> = (0..(secs * sr) as usize).map(|i| (a * (2.0 * std::f64::consts::PI * f * i as f64 / sr).sin()) as f32).collect();
    (x.clone(), x)
}

#[test]
fn a_full_scale_1k_sine_in_both_channels_reads_as_bs1770_says() {
    // A 0 dBFS 997 Hz sine in one channel is −3.01 LUFS; in both, +3 dB: about 0.
    let (l, r) = sine(997.0, -20.0, 5.0, 48000.0);
    let got = integrated_lufs(&l, &r, 48000.0);
    assert!((got - -20.0).abs() < 0.15, "{got}");
    assert!((integrated_lufs(&l, &r, 44100.0) - -20.0).abs() < 0.2);
}

#[test]
fn the_true_peak_of_an_inter_sample_peak_is_found() {
    // A sine at fs/4 sampled at 45°: every sample is at 0.707 of the real peak.
    let sr = 48000.0;
    let x: Vec<f32> = (0..4800).map(|i| (0.9 * (std::f64::consts::PI / 2.0 * i as f64 + std::f64::consts::PI / 4.0).sin()) as f32).collect();
    let sample_peak = 20.0 * (x.iter().fold(0.0f32, |m, v| m.max(v.abs())) as f64).log10();
    let tp = true_peak_db(&x, &x);
    assert!(tp > sample_peak + 2.5, "{tp} vs {sample_peak}");
    assert!((tp - 20.0 * 0.9f64.log10()).abs() < 0.3, "{tp}");
    let _ = sr;
}

#[test]
fn a_click_too_short_to_measure_still_stays_under_the_ceiling() {
    // 80 ms at full scale: no integrated loudness (under the 400 ms gate), but the limiter still holds −1 dBTP.
    let sr = 44100.0;
    let l: Vec<f32> = (0..3528).map(|i| ((i as f64 * 0.3).sin() * 0.99) as f32).collect();
    let r = l.clone();
    let mut chs = [l, r];
    master_n(&mut chs, &[1.0, 1.0], &MasterSpec { loudness: Some(-18.0), true_peak: -1.0, glue: 0.5, max_limit: None }, sr);
    let [l, r] = chs;
    assert!(true_peak_db(&l, &r) <= -1.0, "{}", true_peak_db(&l, &r));
}

#[test]
fn mastering_reaches_the_target_without_passing_the_ceiling() {
    let sr = 44100.0;
    // A quiet, peaky signal: a sine with hard clicks.
    let (mut l, mut r) = sine(110.0, -30.0, 6.0, sr);
    for k in 0..30 {
        let i = k * 8000 + 100;
        l[i] = 0.9;
        r[i] = -0.9;
    }
    let spec = MasterSpec { loudness: Some(-14.0), true_peak: -1.0, glue: 0.5, max_limit: None };
    let mut chs = [l, r];
    master_n(&mut chs, &[1.0, 1.0], &spec, sr);
    let (lufs, tp) = (integrated_lufs(&chs[0], &chs[1], sr), true_peak_db(&chs[0], &chs[1]));
    assert!((lufs - -14.0).abs() <= 0.3, "lufs {lufs}");
    assert!(tp <= -0.95, "true peak {tp}");
}
