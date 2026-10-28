use super::*;

const SR: f64 = 48000.0;

fn note(freq: f64, start: f64, dur: f64, velocity: f64) -> Note<'static> {
    Note { start: (start * SR) as usize, len: (dur * SR) as usize, freq, velocity, pan: 0.0, expression: None, hardness: None, position: None, damping: None }
}

fn play(name: &str, notes: &[Note], secs: f64) -> Vec<f32> {
    let n = (secs * SR) as usize;
    let (mut l, mut r) = (vec![0.0f32; n], vec![0.0f32; n]);
    render(name, notes, &mut l, &mut r, SR).unwrap();
    l.iter().zip(&r).map(|(a, b)| (a + b) * 0.5).collect()
}

/// The pitch of `x[a..b]` by autocorrelation around `expect` Hz (parabolic peak), in Hz.
fn pitch(x: &[f32], a: usize, b: usize, expect: f64) -> f64 {
    let p = SR / expect;
    let (lo, hi) = ((p * 0.94) as usize, (p * 1.06) as usize + 1);
    let w = &x[a..b];
    let r = |t: usize| (0..w.len() - t).map(|i| w[i] as f64 * w[i + t] as f64).sum::<f64>();
    let rs: Vec<f64> = (lo - 1..=hi + 1).map(r).collect();
    let k = (1..rs.len() - 1).max_by(|&i, &j| rs[i].total_cmp(&rs[j])).unwrap();
    let (y0, y1, y2) = (rs[k - 1], rs[k], rs[k + 1]);
    let t = (lo - 1 + k) as f64 + 0.5 * (y0 - y2) / (y0 - 2.0 * y1 + y2);
    SR / t
}

/// The strongest spectral peak within ±6 % of `expect` (Hann-windowed DTFT scanned in 0.1-cent steps), in Hz:
/// for bars, whose strong inharmonic overtones fool an autocorrelation.
fn peak_freq(x: &[f32], a: usize, b: usize, expect: f64) -> f64 {
    let w = &x[a..b];
    let n = w.len() as f64;
    let mag = |f: f64| {
        let (mut re, mut im) = (0.0, 0.0);
        for (i, &v) in w.iter().enumerate() {
            let h = 0.5 - 0.5 * (2.0 * std::f64::consts::PI * i as f64 / n).cos();
            let ph = 2.0 * std::f64::consts::PI * f * i as f64 / SR;
            re += v as f64 * h * ph.cos();
            im -= v as f64 * h * ph.sin();
        }
        re * re + im * im
    };
    (-1000..=1000).map(|c| expect * 2f64.powf(c as f64 / 12000.0)).max_by(|p, q| mag(*p).total_cmp(&mag(*q))).unwrap()
}

fn cents(a: f64, b: f64) -> f64 {
    1200.0 * (a / b).log2()
}

fn peak(x: &[f32]) -> f64 {
    x.iter().map(|v| v.abs() as f64).fold(0.0, f64::max)
}

fn clean(name: &str, x: &[f32]) {
    assert!(x.iter().all(|v| v.is_finite()), "{name}: NaN or infinity");
    let sub = x.iter().filter(|v| **v != 0.0 && v.abs() < f32::MIN_POSITIVE).count();
    assert_eq!(sub, 0, "{name}: {sub} denormal samples");
}

#[test]
fn every_instrument_renders_the_same_twice_cleanly_and_at_a_sensible_level() {
    let melody = [note(196.0, 0.05, 0.5, 0.8), note(293.66, 0.5, 0.5, 0.8), note(440.0, 1.0, 0.8, 0.8)];
    for name in NAMES {
        let notes: Vec<Note> = if name == "model.kit" { [36.0, 38.0, 42.0, 46.0, 49.0].iter().enumerate().map(|(i, k)| note(440.0 * 2f64.powf((k - 69.0) / 12.0), 0.05 + i as f64 * 0.3, 0.2, 0.8)).collect() } else { melody.to_vec() };
        let a = play(name, &notes, 2.5);
        let b = play(name, &notes, 2.5);
        assert!(a == b, "{name}: not deterministic");
        clean(name, &a);
        let db = 20.0 * peak(&a).log10();
        assert!((-24.0..-0.5).contains(&db), "{name}: peak {db:.1} dBFS");
    }
}

#[test]
fn plucked_strings_are_in_tune_across_the_neck() {
    for g in ["model.guitar", "model.nylonGuitar"] {
        for f in [82.41, 110.0, 196.0, 329.63, 440.0, 659.26] {
            let x = play(g, &[note(f, 0.0, 1.5, 0.7)], 1.0);
            let got = pitch(&x, (0.3 * SR) as usize, (0.6 * SR) as usize, f);
            assert!(cents(got, f).abs() < 4.0, "{g} {f} Hz plays {got:.2} Hz ({:+.1} cents)", cents(got, f));
        }
    }
}

#[test]
fn bars_and_the_bowed_line_are_in_tune() {
    for (name, f) in [("model.marimba", 261.63), ("model.vibraphone", 349.23), ("model.glockenspiel", 1046.5), ("ddsp.violin", 440.0), ("ddsp.violin", 293.66)] {
        let x = play(name, &[note(f, 0.0, 1.2, 0.8)], 1.2);
        let got = if name.starts_with("ddsp") { pitch(&x, (0.4 * SR) as usize, (0.7 * SR) as usize, f) } else { peak_freq(&x, (0.1 * SR) as usize, (0.4 * SR) as usize, f) };
        assert!(cents(got, f).abs() < 5.0, "{name} {f} Hz plays {got:.2} Hz ({:+.1} cents)", cents(got, f));
    }
}

/// The share of energy above 2 kHz (a one-pole split).
fn brightness(x: &[f32]) -> f64 {
    let a = (-2.0 * std::f64::consts::PI * 2000.0 / SR).exp();
    let (mut s, mut hi, mut all) = (0.0, 0.0, 0.0);
    for &v in x {
        s = (1.0 - a) * v as f64 + a * s;
        hi += (v as f64 - s).powi(2);
        all += (v as f64).powi(2);
    }
    hi / all.max(1e-12)
}

#[test]
fn a_harder_mallet_or_pick_is_brighter() {
    for name in ["model.marimba", "model.guitar", "model.kit"] {
        let f = if name == "model.kit" { 440.0 * 2f64.powf((38.0 - 69.0) / 12.0) } else { 392.0 };
        let mut soft = note(f, 0.0, 0.6, 0.7);
        soft.hardness = Some(0.0);
        let mut hard = soft.clone();
        hard.hardness = Some(1.0);
        let (bs, bh) = (brightness(&play(name, &[soft], 0.06)), brightness(&play(name, &[hard], 0.06)));
        assert!(bh > bs * 1.3, "{name}: soft {bs:.4} vs hard {bh:.4}");
    }
}

#[test]
fn a_new_note_on_a_string_stops_the_one_ringing_there() {
    // Two notes on the low E string's range only: the second (a semitone up) must cut the first.
    let x = play("model.guitar", &[note(82.41, 0.0, 3.0, 0.8), note(87.31, 0.5, 0.3, 0.8)], 2.0);
    let late = peak(&x[(1.4 * SR) as usize..]);
    let alone = play("model.guitar", &[note(82.41, 0.0, 3.0, 0.8)], 2.0);
    assert!(late < peak(&alone[(1.4 * SR) as usize..]) * 0.2, "the first note still rings: {late}");
}

#[test]
fn a_slurred_violin_line_never_drops_to_silence_between_notes() {
    let x = play("ddsp.violin", &[note(440.0, 0.0, 0.52, 0.7), note(493.88, 0.5, 0.6, 0.7)], 1.3);
    let rms = |a: f64, b: f64| ((a * SR) as usize..(b * SR) as usize).map(|i| (x[i] as f64).powi(2)).sum::<f64>().sqrt();
    assert!(rms(0.48, 0.54) > rms(0.3, 0.36) * 0.4, "a gap at the slur");
    let detached = play("ddsp.violin", &[note(440.0, 0.0, 0.4, 0.7), note(493.88, 0.8, 0.4, 0.7)], 1.3);
    let quiet = ((0.65 * SR) as usize..(0.75 * SR) as usize).map(|i| (detached[i] as f64).powi(2)).sum::<f64>().sqrt();
    assert!(quiet < rms(0.3, 0.36) * 0.5, "a rest is quieter than a note");
}

#[test]
#[ignore]
fn cost_print() {
    let secs = 10.0;
    let melodic: Vec<Note> = (0..28).map(|i| note(196.0 * 2f64.powf(((i * 5) % 12) as f64 / 12.0), i as f64 * 0.357, 0.7, 0.6)).collect();
    let line: Vec<Note> = (0..10).map(|i| note(440.0 * 2f64.powf(((i * 2) % 7) as f64 / 12.0), i as f64 * 1.0, 1.0, 0.7)).collect();
    let kit: Vec<Note> = (0..56).map(|i| note(440.0 * 2f64.powf(([36.0, 42.0, 38.0, 42.0][i % 4] - 69.0) / 12.0), i as f64 * 0.178, 0.1, 0.7)).collect();
    for name in NAMES {
        let notes = match name { "model.kit" => &kit, "ddsp.violin" => &line, _ => &melodic };
        let t = std::time::Instant::now();
        let _ = play(name, notes, secs + 2.0);
        let wall = t.elapsed().as_secs_f64();
        println!("{name}: {:.1} ms per second of audio ({} notes, wall clock, all cores)", wall * 1000.0 / secs, notes.len());
    }
}

/// A procedural instrument rendered ahead plays live as an SFZ: every region's sample is there and sounds,
/// a key between the rendered ones is repitched from its neighbour, and each velocity layer is its own render.
#[test]
fn a_model_rendered_ahead_plays_as_an_sfz() {
    let dir = std::env::temp_dir().join(format!("rostrum-model-samples-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    for name in ["model.marimba", "model.kit"] {
        let sub = dir.join(name);
        let sfz = super::samples::write(name, &sub, 48000.0).unwrap();
        let (regions, samples) = crate::instruments::sfz::preload(sfz.to_str().unwrap()).unwrap();
        let keys = if name == "model.kit" { 26 } else { 18 };
        assert_eq!(regions.len(), keys * 3, "{name}");
        assert!(samples.values().all(|s| s.frames.iter().any(|f| f[0].abs() > 1e-3)), "{name}: a silent sample");
        let strike = |key: u8, velocity: f64| crate::instruments::sfz::strike(&regions, &samples, key, velocity, 0, false, 0.0, 48000.0);
        if name == "model.marimba" {
            // 61 lies in the region of the sample rendered at 60.
            let r = crate::instruments::sfz::select(&regions, 61, 100, 0, 0.0);
            assert_eq!((r.len(), r[0].keycenter), (1, 60.0));
            let peak = |velocity: f64| {
                let mut v = strike(60, velocity).pop().unwrap();
                (0..4800).filter_map(|_| v.next()).fold(0f32, |m, (l, _)| m.max(l.abs()))
            };
            assert!(peak(0.95) > peak(0.3) * 1.5, "the hard layer is louder: {} vs {}", peak(0.95), peak(0.3));
        } else {
            assert_eq!(strike(36, 0.8).len(), 1, "the kick");
            assert_eq!(strike(70, 0.8).len(), 1, "the shaker");
            assert!(strike(71, 0.8).is_empty(), "no piece past the kit");
        }
    }
    assert!(super::samples::write("model.harp", &dir.join("x"), 48000.0).unwrap_err().contains("no procedural instrument"));
    std::fs::remove_dir_all(&dir).unwrap();
}
