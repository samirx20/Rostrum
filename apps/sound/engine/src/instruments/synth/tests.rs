use super::spec::*;
use super::*;

fn spec() -> SynthSpec {
    SynthSpec { wave: "saw".into(), voices: 3, detune: 15.0, cutoff: 1200.0, resonance: 0.3, env_amount: 2.0, attack: 0.01, decay: 0.2, sustain: 0.6, release: 0.4, octave: 0.0, glide: 0.0, filter_velocity: 0.0, drive: 0.0, lfo: None, filter_env: None, pitch_env: None, level: 0.0, width: 1.0, drift: 0.0, noise: 0.0, sub: 0.0, curve: String::new() }
}

#[test]
fn analog_drift_makes_each_note_different_and_without_it_notes_repeat_exactly() {
    let sr = 44100.0;
    let note = |spec: &SynthSpec, seed: u64| { let mut v = SynthVoice::new(spec, 220.0, 0.3, 0.8, 0.0, sr).seeded(seed); (0..8000).map(|i| v.next(i).0).collect::<Vec<f64>>() };
    let plain = spec();
    assert_eq!(note(&plain, 1), note(&plain, 2), "no analog fields: the seed changes nothing");
    let analog = SynthSpec { drift: 6.0, noise: 0.05, sub: 0.4, curve: "analog".into(), ..spec() };
    let (a, b) = (note(&analog, 1), note(&analog, 2));
    assert_ne!(a, b);
    assert_eq!(a, note(&analog, 1), "seeded: the same note renders the same");
    assert!(a.iter().all(|x| x.is_finite() && x.abs() < 1.5));
}

#[test]
fn the_envelope_attacks_decays_sustains_and_releases() {
    let s = spec();
    assert!((s.envelope(0.005, 1.0) - 0.5).abs() < 1e-9);
    assert!((s.envelope(0.5, 1.0) - 0.6).abs() < 1e-9);
    assert!((s.envelope(1.2, 1.0) - 0.3).abs() < 1e-9);
    assert_eq!(s.envelope(1.5, 1.0), 0.0);
}

/// Upward zero crossings per second over [a, b) seconds.
fn pitch(x: &[f64], sr: f64, a: f64, b: f64) -> f64 {
    let s = &x[(a * sr) as usize..(b * sr) as usize];
    s.windows(2).filter(|w| w[0] < 0.0 && w[1] >= 0.0).count() as f64 / (b - a)
}

/// How bright: the second difference's energy over the signal's (each harmonic counts by its frequency⁴).
fn brightness(x: &[f64], sr: f64, a: f64, b: f64) -> f64 {
    let s = &x[(a * sr) as usize..(b * sr) as usize];
    s.windows(3).map(|w| (w[2] - 2.0 * w[1] + w[0]).powi(2)).sum::<f64>() / s.iter().map(|v| v * v).sum::<f64>()
}

fn render(spec: &SynthSpec, f: f64, dur: f64, velocity: f64, from: Option<f64>) -> Vec<f64> {
    let sr = 44100.0;
    let v = SynthVoice::new(spec, f, dur, velocity, 0.0, sr);
    let mut v = match from {
        Some(g) => v.gliding_from(g, f),
        None => v,
    };
    (0..(sr * dur) as usize).map(|i| v.next(i).0).collect()
}

fn plain() -> SynthSpec {
    SynthSpec { wave: "sine".into(), voices: 1, detune: 0.0, cutoff: 8000.0, resonance: 0.0, env_amount: 0.0, attack: 0.002, decay: 0.1, sustain: 1.0, release: 0.05, ..spec() }
}

#[test]
fn a_notes_own_glide_and_shape_move_its_pitch_and_level() {
    use crate::instruments::expression::{Expression, Glide};
    let sr = 44100.0;
    let e = Expression { glide: Some(Glide { cents: 1200.0, at: 0.3, duration: 0.05 }), shape: Some(vec![[0.0, 1.0], [1.0, 0.25]]), ..Default::default() };
    let mut v = SynthVoice::new(&plain(), 220.0, 0.8, 0.8, 0.0, sr).with_expression(Some(e));
    let x: Vec<f64> = (0..(sr * 0.8) as usize).map(|i| v.next(i).0).collect();
    let (before, after) = (pitch(&x, sr, 0.05, 0.25), pitch(&x, sr, 0.45, 0.75));
    assert!((before - 220.0).abs() < 10.0 && (after - 440.0).abs() < 12.0, "{before:.0} → {after:.0} Hz");
    let peak = |a: f64, b: f64| x[(a * sr) as usize..(b * sr) as usize].iter().fold(0.0f64, |m, v| m.max(v.abs()));
    assert!(peak(0.7, 0.78) < 0.45 * peak(0.05, 0.15), "the shape fades the note");
}

#[test]
fn a_gliding_note_slides_from_the_previous_pitch() {
    let x = render(&SynthSpec { glide: 0.2, ..plain() }, 440.0, 0.6, 0.8, Some(220.0));
    let (start, end) = (pitch(&x, 44100.0, 0.0, 0.04), pitch(&x, 44100.0, 0.3, 0.6));
    assert!(start < 270.0 && (end - 440.0).abs() < 8.0, "slides {start:.0} → {end:.0} Hz");
    // Without glide (or from nowhere) it starts at its own pitch.
    assert!((pitch(&render(&plain(), 440.0, 0.3, 0.8, Some(220.0)), 44100.0, 0.0, 0.1) - 440.0).abs() < 15.0);
}

#[test]
fn the_filter_envelope_squelches_while_the_note_sustains_and_velocity_opens_it() {
    let acid = SynthSpec { wave: "saw".into(), cutoff: 300.0, resonance: 0.6, env_amount: 4.0, filter_env: Some(Adsr { attack: 0.002, decay: 0.12, sustain: 0.0, release: 0.05 }), ..plain() };
    let x = render(&acid, 110.0, 0.6, 1.0, None);
    assert!(brightness(&x, 44100.0, 0.005, 0.03) > 1.6 * brightness(&x, 44100.0, 0.4, 0.55), "bright at the attack, dark once the filter envelope has decayed");
    let loud = |v: f64| { let x = render(&acid, 110.0, 0.6, v, None); (x[(0.4 * 44100.0) as usize..].iter().map(|s| s * s).sum::<f64>()).sqrt() };
    assert!(loud(1.0) > 0.0, "the amplitude sustains after the filter closes");
    let soft = SynthSpec { filter_velocity: 2.0, env_amount: 0.0, filter_env: None, cutoff: 2000.0, ..acid.clone() };
    assert!(brightness(&render(&soft, 110.0, 0.3, 1.0, None), 44100.0, 0.1, 0.3) > 1.3 * brightness(&render(&soft, 110.0, 0.3, 0.3, None), 44100.0, 0.1, 0.3));
}

#[test]
fn the_lfo_wobbles_the_pitch_and_drive_adds_harmonics() {
    let vib = SynthSpec { lfo: Some(Lfo { wave: "square".into(), rate: 2.0, pitch: 1200.0, cutoff: 0.0, amp: 0.0, delay: 0.0 }), ..plain() };
    let x = render(&vib, 220.0, 0.5, 0.8, None);
    // A square LFO at 2 Hz: an octave up for the first quarter second, an octave down for the next.
    assert!((pitch(&x, 44100.0, 0.02, 0.23) / pitch(&x, 44100.0, 0.27, 0.48) - 4.0).abs() < 0.3);
    let clean = render(&plain(), 220.0, 0.3, 0.8, None);
    let driven = render(&SynthSpec { drive: 6.0, ..plain() }, 220.0, 0.3, 0.8, None);
    assert!(brightness(&driven, 44100.0, 0.1, 0.3) > 1.3 * brightness(&clean, 44100.0, 0.1, 0.3), "saturation adds upper harmonics to a sine");
}

#[test]
fn a_held_unison_note_does_not_sweep_up_the_harmonics() {
    // Evenly spaced detunes and phases made the loudest harmonic climb 3f → 4f → … → 12f within a second.
    let sr = 44100.0;
    let spec = SynthSpec { voices: 5, detune: 18.0, cutoff: 8000.0, resonance: 0.0, env_amount: 0.0, attack: 0.005, sustain: 1.0, ..spec() };
    let mut v = SynthVoice::new(&spec, 110.0, 2.0, 0.8, 0.0, sr);
    let x: Vec<f64> = (0..(sr * 2.0) as usize).map(|i| v.next(i).0).collect();
    let (mut fundamental_on_top, mut highest) = (0, 0);
    for w in 0..13 {
        let (a, n) = (((0.1 + w as f64 * 0.15) * sr) as usize, (0.08 * sr) as usize);
        let amp = |m: f64| {
            let (mut re, mut im) = (0.0, 0.0);
            for i in 0..n {
                let (win, p) = (0.5 - 0.5 * (2.0 * PI * i as f64 / n as f64).cos(), 2.0 * PI * m * 110.0 * (a + i) as f64 / sr);
                re += x[a + i] * win * p.cos();
                im += x[a + i] * win * p.sin();
            }
            re.hypot(im)
        };
        let amps: Vec<f64> = (1..=25).map(|m| amp(m as f64)).collect();
        let top = (0..25).max_by(|&i, &j| amps[i].total_cmp(&amps[j])).unwrap();
        let top_upper = (2..25).max_by(|&i, &j| amps[i].total_cmp(&amps[j])).unwrap() + 1;
        fundamental_on_top += (top == 0) as usize;
        highest = highest.max(top_upper);
    }
    assert!(fundamental_on_top >= 10, "the fundamental leads in {fundamental_on_top}/13 windows");
    assert!(highest <= 6, "the loudest upper harmonic reached {highest}f");
}

#[test]
fn a_note_sounds_at_its_pitch_and_stays_bounded() {
    let sr = 44100.0;
    let mut v = SynthVoice::new(&SynthSpec { voices: 1, resonance: 0.0, ..spec() }, 220.0, 1.0, 0.8, 0.0, sr);
    let samples: Vec<f64> = (0..v.len()).map(|i| v.next(i).0).collect();
    assert!(samples.iter().all(|x| x.abs() < 1.0));
    // Zero crossings upward over the sustained second: about 220.
    let ups = samples[4410..44100].windows(2).filter(|w| w[0] < 0.0 && w[1] >= 0.0).count() as f64 / 0.9;
    assert!((ups - 220.0).abs() < 6.0, "{ups}");
}

#[test]
fn a_pitch_envelope_punches_down_to_the_note_and_level_and_width_apply() {
    let sr = 44100.0;
    let punch = SynthSpec { pitch_env: Some(PitchEnv { semitones: 12.0, time: 0.02 }), ..plain() };
    let x = render(&punch, 55.0, 1.0, 1.0, None);
    // An octave up at the start, the note itself once the envelope has fallen.
    // The first cycle is short (it starts an octave up); 55 Hz is 18.2 ms.
    let first = (20..x.len()).find(|&i| x[i - 1] < 0.0 && x[i] >= 0.0).unwrap() as f64 / sr;
    assert!(first < 0.8 / 55.0, "first cycle {first}");
    assert!((pitch(&x, sr, 0.4, 0.9) - 55.0).abs() < 3.0);
    let loud = render(&SynthSpec { level: 6.0, ..plain() }, 220.0, 0.5, 1.0, None);
    let soft = render(&plain(), 220.0, 0.5, 1.0, None);
    let peak = |v: &[f64]| v.iter().fold(0.0f64, |m, s| m.max(s.abs()));
    assert!((20.0 * (peak(&loud) / peak(&soft)).log10() - 6.0).abs() < 0.1);
    // Width 0: every oscillator in the centre, the channels identical.
    let mono = SynthSpec { voices: 4, detune: 20.0, width: 0.0, ..plain() };
    let mut v = SynthVoice::new(&mono, 110.0, 0.3, 1.0, 0.0, sr);
    assert!((0..2000).all(|i| { let (l, r) = v.next(i); (l - r).abs() < 1e-12 }));
}
