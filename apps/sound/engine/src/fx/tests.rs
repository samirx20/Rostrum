use std::f64::consts::PI;

use super::eq::eq;
use super::inserts::{compressor, delay, limiter};
use crate::mix::schedule::{EqBand, Param};

fn tone(hz: f64, n: usize, sr: f64) -> Vec<f32> {
    (0..n).map(|i| (2.0 * PI * hz * i as f64 / sr).sin() as f32 * 0.5).collect()
}
fn rms(x: &[f32]) -> f64 {
    (x.iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / x.len() as f64).sqrt()
}

#[test]
fn a_lowpass_cuts_the_highs_and_keeps_the_lows() {
    let sr = 44100.0;
    let band = |f: f64| vec![EqBand { shape: "lowpass".into(), freq: Param::Value(f), gain: Param::Value(0.0), q: Param::Value(0.707) }];
    let (mut hl, mut hr) = (tone(8000.0, 44100, sr), tone(8000.0, 44100, sr));
    eq(&band(500.0), &mut [&mut hl[..], &mut hr[..]], sr);
    let (mut ll, mut lr) = (tone(100.0, 44100, sr), tone(100.0, 44100, sr));
    eq(&band(500.0), &mut [&mut ll[..], &mut lr[..]], sr);
    assert!(rms(&hl[4410..]) < 0.01, "8 kHz through a 500 Hz low-pass: {}", rms(&hl[4410..]));
    assert!((rms(&ll[4410..]) - 0.3535).abs() < 0.02, "100 Hz passes: {}", rms(&ll[4410..]));
}

#[test]
fn an_automated_filter_opens_over_time() {
    let sr = 44100.0;
    let bands = vec![EqBand { shape: "lowpass".into(), freq: Param::Envelope(vec![[0.0, 300.0], [1.0, 18000.0]]), gain: Param::Value(0.0), q: Param::Value(0.707) }];
    let (mut l, mut r) = (tone(4000.0, 44100, sr), tone(4000.0, 44100, sr));
    eq(&bands, &mut [&mut l[..], &mut r[..]], sr);
    assert!(rms(&l[0..4410]) < 0.05 && rms(&l[39690..]) > 0.3, "{} then {}", rms(&l[0..4410]), rms(&l[39690..]));
}

#[test]
fn the_compressor_brings_loud_down_by_its_ratio_and_the_limiter_holds_the_ceiling() {
    let sr = 44100.0;
    let (mut l, mut r) = (tone(200.0, 44100, sr), tone(200.0, 44100, sr)); // peak 0.5 = -6 dBFS
    compressor(&Param::Value(-18.0), &Param::Value(4.0), 1.0, 50.0, &Param::Value(0.0), 0.0, &mut [&mut l[..], &mut r[..]], sr);
    // 12 dB over at 4:1 leaves 3 dB over: peaks about -15 dBFS.
    let peak = l[22050..].iter().fold(0.0f32, |m, v| m.max(v.abs())) as f64;
    assert!((20.0 * peak.log10() + 15.0).abs() < 1.0, "{}", 20.0 * peak.log10());
    let (mut l, mut r) = (tone(200.0, 44100, sr), tone(200.0, 44100, sr));
    for v in l.iter_mut().chain(r.iter_mut()) {
        *v *= 4.0;
    }
    limiter(-1.0, 80.0, &mut [&mut l[..], &mut r[..]], sr);
    let ceiling = 10f32.powf(-1.0 / 20.0);
    assert!(l.iter().all(|v| v.abs() <= ceiling + 1e-6));
}

#[test]
fn a_delay_repeats_after_its_time() {
    let sr = 1000.0;
    let mut l = vec![0.0f32; 1000];
    l[0] = 1.0;
    let mut r = l.clone();
    delay(0.25, &Param::Value(0.5), &Param::Value(1.0), false, 20000.0, &mut l, &mut r, sr);
    assert!(l[250] > 0.3 && l[500] > 0.1 && l[100].abs() < 1e-6, "{} {} {}", l[250], l[500], l[100]);
}
