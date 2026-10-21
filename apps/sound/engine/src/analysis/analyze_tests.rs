use super::*;

/// A test piece: a kick on every beat at 100 BPM under an A-minor triad, 8 s at 22050 Hz.
fn piece() -> Vec<f32> {
    let sr = 22050.0;
    (0..(sr * 8.0) as usize)
        .map(|i| {
            let t = i as f64 / sr;
            let beat = t % 0.6;
            let kick = (2.0 * PI * 55.0 * beat).sin() * (-beat * 25.0).exp() * 0.8;
            let chord: f64 = [220.0, 261.63, 329.63].iter().map(|f| (2.0 * PI * f * t).sin() * 0.15).sum();
            (kick + chord) as f32
        })
        .collect()
}

#[test]
fn hears_the_tempo_key_and_chord_of_a_simple_piece() {
    let a = analyze(&piece(), 22050.0, false);
    let bpm = a["tempo"]["bpm"].as_f64().unwrap();
    assert!((bpm - 100.0).abs() < 2.0, "tempo {bpm}");
    assert_eq!(a["key"]["name"], "A minor");
    let chords: Vec<&str> = a["chords"].as_array().unwrap().iter().map(|c| c[2].as_str().unwrap()).collect();
    assert!(chords.iter().filter(|c| **c == "Am").count() >= 1 && chords.iter().all(|c| ["Am", "N", "Am7", "C"].contains(c)), "{chords:?}");
}

/// A groove: a kick on beats 1 and 3, a snare on 2 and 4, hats on every eighth, over a triad and
/// its root in the bass; `bpm`, 10 s at 22050 Hz.
fn groove(bpm: f64, triad: [f64; 3], bass: f64) -> Vec<f32> {
    let sr = 22050.0;
    let beat = 60.0 / bpm;
    let mut seed = 1u32;
    let mut prev = 0.0;
    (0..(sr * 10.0) as usize)
        .map(|i| {
            let t = i as f64 / sr;
            let in_bar = t % (4.0 * beat);
            let b = t % beat;
            let e = t % (beat / 2.0);
            let kick = if in_bar < beat || (in_bar >= 2.0 * beat && in_bar < 3.0 * beat) { (2.0 * PI * 55.0 * b).sin() * (-b * 30.0).exp() * 0.8 } else { 0.0 };
            seed = seed.wrapping_mul(1664525).wrapping_add(1013904223);
            let noise = (seed >> 9) as f64 / (1u32 << 23) as f64 * 2.0 - 1.0;
            let snare = if (in_bar >= beat && in_bar < 2.0 * beat) || in_bar >= 3.0 * beat { noise * (-b * 25.0).exp() * 0.4 } else { 0.0 };
            // A hat: bright noise (the difference of white noise: its energy mostly above 5 kHz).
            let hat = (noise - prev) * (-e * 120.0).exp() * 0.1;
            prev = noise;
            let chord: f64 = triad.iter().map(|f| (2.0 * PI * f * t).sin() * 0.1).sum::<f64>() + (2.0 * PI * bass * t).sin() * 0.2;
            (kick + snare + hat + chord) as f32
        })
        .collect()
}

#[test]
fn reads_slow_and_fast_grooves_at_their_tempo_not_its_double_or_two_thirds() {
    for bpm in [80.0, 150.0, 72.0] {
        let a = analyze(&groove(bpm, [293.66, 349.23, 440.0], 73.42), 22050.0, false);
        let got = a["tempo"]["bpm"].as_f64().unwrap();
        assert!((got - bpm).abs() < 2.5, "{bpm} BPM read as {got} (alternatives {})", a["tempo"]["alternatives"]);
        assert!(a["tempo"]["firstBeat"].as_f64().unwrap() < 0.05, "the kick at 0 s is the first beat: {}", a["tempo"]["firstBeat"]);
    }
}

#[test]
fn a_slow_ballad_stays_slow() {
    // 66 BPM, no drums (benchmark b9, read as 130.8): a struck tone every two beats over a low root every bar.
    let (sr, beat) = (22050.0, 60.0 / 66.0);
    let x: Vec<f32> = (0..(sr * 20.0) as usize)
        .map(|i| {
            let t = i as f64 / sr;
            let (h, b) = (t % (2.0 * beat), t % (4.0 * beat));
            let melody = [349.23, 440.0, 587.33, 523.25][(t / (2.0 * beat)) as usize % 4];
            ((2.0 * PI * melody * t).sin() * (-h * 2.5).exp() * 0.3 + (2.0 * PI * 73.42 * t).sin() * (-b * 0.8).exp() * 0.3) as f32
        })
        .collect();
    let got = analyze(&x, sr, false)["tempo"]["bpm"].as_f64().unwrap();
    assert!((got - 66.0).abs() < 2.5, "66 BPM read as {got}");
}

#[test]
fn tells_minor_from_major_by_the_third() {
    let minor = analyze(&groove(90.0, [293.66, 349.23, 440.0], 73.42), 22050.0, false);
    assert_eq!(minor["key"]["name"], "D minor");
    let major = analyze(&groove(90.0, [293.66, 369.99, 440.0], 73.42), 22050.0, false);
    assert_eq!(major["key"]["name"], "D major");
}

#[test]
fn follows_the_notes_of_a_bass_line() {
    // A1, C2, E2, A1: 0.4 s each.
    let sr = 22050.0;
    let line = [55.0, 65.41, 82.41, 55.0];
    let x: Vec<f32> = (0..(sr * 1.6) as usize).map(|i| { let t = i as f64 / sr; (2.0 * PI * line[(t / 0.4) as usize % 4] * t).sin() as f32 * 0.6 }).collect();
    let a = analyze(&x, sr, true);
    let names: Vec<&str> = a["notes"].as_array().unwrap().iter().map(|n| n[3].as_str().unwrap()).collect();
    assert_eq!(names.iter().filter(|n| ["A1", "C2", "E2"].contains(n)).count(), names.len(), "{names:?}");
    assert!(names.starts_with(&["A1", "C2", "E2"]), "{names:?}");
}
