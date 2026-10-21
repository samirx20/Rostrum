//! The stretch measured: pitch, length, level and alignment kept; hits sharp; formants kept or moved.

use super::*;

const SR: f64 = 44100.0;
const KEEP: Shift = Shift { ratio: 1.0, formant: None, voice: Some(false) };

fn sine(f: f64, secs: f64) -> Vec<f32> {
    (0..(secs * SR) as usize).map(|i| (0.5 * (2.0 * std::f64::consts::PI * f * i as f64 / SR).sin()) as f32).collect()
}

/// Frequency from upward zero crossings over the middle half.
fn freq(x: &[f32]) -> f64 {
    let (a, b) = (x.len() / 4, 3 * x.len() / 4);
    let ups: Vec<usize> = (a + 1..b).filter(|&i| x[i - 1] < 0.0 && x[i] >= 0.0).collect();
    (ups.len() - 1) as f64 * SR / (ups[ups.len() - 1] - ups[0]) as f64
}

fn rms(x: &[f32]) -> f64 {
    (x.iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / x.len() as f64).sqrt()
}

#[test]
fn slower_and_faster_keep_the_pitch_and_level() {
    let x = sine(440.0, 3.0);
    for rate in [0.5, 0.75, 1.25, 2.0] {
        let n = (x.len() as f64 / rate) as usize - 4410;
        let [l, r] = process([&x, &x], n, &|k| k * rate, &KEEP, SR);
        assert!((freq(&l) / 440.0 - 1.0).abs() < 0.003, "rate {rate}: {} Hz", freq(&l));
        let lv = 20.0 * (rms(&l[n / 4..3 * n / 4]) / rms(&x)).log10();
        assert!(lv.abs() < 1.0, "rate {rate}: level {lv:.2} dB");
        let diff = l.iter().zip(&r).map(|(a, b)| (a - b).abs()).fold(0f32, f32::max);
        assert!(diff < 1e-3, "rate {rate}: channels differ by {diff}");
    }
}

#[test]
fn a_pitch_shift_keeps_the_length() {
    let x = sine(220.0, 2.0);
    for st in [-5.0, 5.0, 12.0] {
        let shift = Shift { ratio: 2f64.powf(st / 12.0), formant: None, voice: Some(false) };
        let [l, _] = process([&x, &x], x.len(), &|k| k, &shift, SR);
        let got = 12.0 * (freq(&l) / 220.0).log2();
        assert!((got - st).abs() < 0.05, "{st} st: got {got:.3}");
        assert!(rms(&l[l.len() - 4410..]) > 0.2, "{st} st: the end is there");
    }
}

/// A click every 250 ms, stretched to 0.8x speed: each click lands where the map puts it (±0.5 ms), as
/// sharp as the source's, with no pre-echo before it.
#[test]
fn hits_land_on_time_and_stay_sharp() {
    let mut x = vec![0f32; (2.0 * SR) as usize];
    let hits: Vec<usize> = (1..8).map(|k| (k as f64 * 0.25 * SR) as usize).collect();
    for &h in &hits {
        for i in 0..400 {
            x[h + i] += (0.8 * (-(i as f64) / 60.0).exp() * if i % 2 == 0 { 1.0 } else { -1.0 }) as f32; // a bright, fast-decaying hit
        }
    }
    let rate = 0.8;
    let n = (x.len() as f64 / rate) as usize;
    let [l, _] = process([&x, &x], n, &|k| k * rate, &KEEP, SR);
    for &h in &hits {
        let at = (h as f64 / rate) as usize;
        let peak = (at - 200..at + 200).max_by(|&a, &b| l[a].abs().total_cmp(&l[b].abs())).unwrap();
        assert!((peak as i64 - at as i64).abs() <= 22, "hit at {at}: peak at {peak}");
        assert!(l[peak].abs() > 0.7, "hit at {at}: peak {}", l[peak]);
        let pre = rms(&l[at - 1300..at - 100]);
        assert!(pre < 0.004, "hit at {at}: pre-echo rms {pre}");
    }
}

/// A vowel (100 Hz pulses through resonances at 700 and 1100 Hz, 130 / 150 Hz wide) up 5 semitones: the spectral
/// centroid over 200 … 2500 Hz (where the formants are) stays with formants kept, and rises with the pitch
/// when they move.
#[test]
fn formants_kept_or_moved() {
    let mut x = vec![0f32; (2.0 * SR) as usize];
    for (f, bw) in [(700.0, 130.0), (1100.0, 150.0)] {
        let r: f64 = (-std::f64::consts::PI * bw / SR).exp(); // a spoken vowel's bandwidths
        let (c, mut y1, mut y2) = (2.0 * r * (2.0 * std::f64::consts::PI * f / SR).cos(), 0.0, 0.0);
        for i in 0..x.len() {
            let pulse = if i % (SR / 100.0) as usize == 0 { 1.0 } else { 0.0 };
            let y = pulse + c * y1 - r * r * y2;
            (y2, y1) = (y1, y);
            x[i] += (y * 0.01) as f32;
        }
    }
    let centroid = |y: &[f32]| {
        let seg = &y[y.len() / 3..y.len() / 3 + 8192];
        let (mut num, mut den) = (0.0, 0.0);
        for k in 0..230 {
            let f = 200.0 + k as f64 * 10.0;
            let (mut re, mut im) = (0.0, 0.0);
            for (i, s) in seg.iter().enumerate() {
                let w = 2.0 * std::f64::consts::PI * f * i as f64 / SR;
                (re, im) = (re + *s as f64 * w.cos(), im + *s as f64 * w.sin());
            }
            let p = re * re + im * im;
            (num, den) = (num + f * p, den + p);
        }
        num / den
    };
    let src = centroid(&x);
    let up = |formant| process([&x, &x], x.len(), &|k| k, &Shift { ratio: 2f64.powf(5.0 / 12.0), formant, voice: Some(false) }, SR)[0].clone();
    let (kept, moved) = (centroid(&up(Some(1.0))), centroid(&up(None)));
    let st = |f: f64| 12.0 * (f / src).log2();
    assert!(st(kept).abs() < 1.0, "kept: {kept:.0} Hz, {:+.2} st (source {src:.0} Hz)", st(kept));
    assert!(st(moved) > 2.5, "moved: {moved:.0} Hz, {:+.2} st (source {src:.0} Hz)", st(moved));
}

#[test]
fn the_same_input_renders_the_same_samples() {
    let x: Vec<f32> = (0..44100).map(|i| ((i as f64 * 0.37).sin() * (i as f64 * 0.0013).cos()) as f32 * 0.4).collect();
    let a = process([&x, &x], 50000, &|k| k * 0.88, &Shift { ratio: 1.1, formant: Some(1.0), voice: Some(false) }, SR);
    let b = process([&x, &x], 50000, &|k| k * 0.88, &Shift { ratio: 1.1, formant: Some(1.0), voice: Some(false) }, SR);
    assert!(a == b);
    // And the cache hands back exactly what was made.
    let c = render([&x, &x], 50000, &|k| k * 0.88, &Shift { ratio: 1.1, formant: Some(1.0), voice: Some(false) }, SR);
    let d = render([&x, &x], 50000, &|k| k * 0.88, &Shift { ratio: 1.1, formant: Some(1.0), voice: Some(false) }, SR);
    assert!(c == a && d == a);
}

fn rate(from: f64, to: Option<f64>, preserve_pitch: bool) -> crate::mix::schedule::Rate {
    crate::mix::schedule::Rate { from, to, preserve_pitch, warp: None, semitones: 0.0, formant: None, content: Some("music".into()) }
}

/// A clip's rate through speed::time_stretch: a ramp keeps the pitch when asked (it fell back to tape
/// before), tape follows the speed and can be pitched on top; warp markers put a hit where they say.
#[test]
fn clip_rates_ramp_tape_and_warp() {
    let x = sine(440.0, 4.0);
    let n = (2.5 * SR) as usize;
    let near = |y: &[f32], at: f64| freq(&y[(at * SR) as usize - 4410..(at * SR) as usize + 4410]);
    let (mut l, mut r) = (vec![0f32; n], vec![0f32; n]);
    crate::stretch::speed::time_stretch(&mut l, &mut r, SR, &rate(1.0, Some(2.0), true), Some((&x, &x)));
    assert!((near(&l, 0.3) - 440.0).abs() < 2.0 && (near(&l, 2.2) - 440.0).abs() < 2.0, "{} / {} Hz", near(&l, 0.3), near(&l, 2.2));
    let (mut l, mut r) = (vec![0f32; n], vec![0f32; n]);
    crate::stretch::speed::time_stretch(&mut l, &mut r, SR, &rate(1.0, Some(0.5), false), Some((&x, &x)));
    assert!(near(&l, 2.2) < 290.0, "tape slows down: {} Hz", near(&l, 2.2));
    let (mut l, mut r) = (vec![0f32; n], vec![0f32; n]);
    crate::stretch::speed::time_stretch(&mut l, &mut r, SR, &crate::mix::schedule::Rate { semitones: 12.0, ..rate(1.25, None, false) }, Some((&x, &x)));
    assert!((near(&l, 1.2) / 1100.0 - 1.0).abs() < 0.01, "tape 1.25x then up an octave: {} Hz", near(&l, 1.2));
    // A click at source 1.0 s, warped to land at clip 1.6 s.
    let mut c = vec![0f32; (3.0 * SR) as usize];
    for i in 0..300 {
        c[SR as usize + i] = (0.9 * (-(i as f64) / 40.0).exp() * if i % 2 == 0 { 1.0 } else { -1.0 }) as f32;
    }
    let (mut l, mut r) = (vec![0f32; n], vec![0f32; n]);
    let warp = crate::mix::schedule::Rate { warp: Some(vec![[0.0, 0.0], [1.0, 1.6], [2.0, 2.4]]), ..rate(1.0, None, false) };
    crate::stretch::speed::time_stretch(&mut l, &mut r, SR, &warp, Some((&c, &c)));
    let peak = (0..n).max_by(|&a, &b| l[a].abs().total_cmp(&l[b].abs())).unwrap();
    assert!((peak as f64 / SR - 1.6).abs() < 0.001, "the warped hit lands at {:.4} s", peak as f64 / SR);
}
