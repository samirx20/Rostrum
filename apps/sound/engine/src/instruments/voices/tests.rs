use super::*;
use crate::mix::schedule::{Pcm, Voice as V};

fn hit(voice: &str, tune: f64, decay: f64, sample: Option<Pcm>) -> Vec<f64> {
    let sr = 44100.0;
    let mut out = vec![];
    Voice::from_schedule(&V::Drum { voice: voice.into(), start_idx: 0, velocity: 1.0, pan: 0.0, tune, decay, cut: None, sample, model: None }, usize::MAX, sr, &mut out).unwrap();
    let v = &mut out[0];
    (0..v.len).map(|i| v.next(i).0).collect()
}

fn crossings(x: &[f64], a: usize, b: usize) -> usize {
    x[a..b.min(x.len())].windows(2).filter(|w| w[0] < 0.0 && w[1] >= 0.0).count()
}

#[test]
fn a_kit_voice_is_tuned_and_its_decay_stretched_or_gated() {
    let (kick, low, short) = (hit("kick", 1.0, 1.0, None), hit("kick", 0.5, 1.0, None), hit("kick", 1.0, 0.4, None));
    // An octave down: about half the cycles in the body.
    let (c, cl) = (crossings(&kick, 2000, 12000), crossings(&low, 2000, 12000));
    assert!((c as f64 / cl as f64 - 2.0).abs() < 0.25, "{c} vs {cl} cycles");
    assert_eq!(short.len(), (0.42 * 0.4 * 44100.0) as usize, "a gated kick is cut at its decay");
    assert!(kick.len() > short.len());
}

#[test]
fn a_one_shot_plays_instead_of_the_synthesized_hit_at_its_tuned_speed() {
    // A 100-frame one-shot (stereo f32): a ramp on the left.
    let file = std::env::temp_dir().join("rostrum-oneshot-test.f32");
    let data: Vec<u8> = (0..100).flat_map(|i| { let v = i as f32 / 100.0; [v.to_le_bytes(), 0f32.to_le_bytes()].concat() }).collect();
    std::fs::write(&file, data).unwrap();
    let p = || Some(Pcm { file: file.to_string_lossy().into(), channels: 2, frames: 100 });
    let plain = hit("snare", 1.0, 1.0, p());
    assert_eq!(plain.len(), 100, "its own length");
    let up = hit("snare", 2.0, 1.0, p());
    assert_eq!(up.len(), 50, "an octave up plays twice as fast");
    assert!((up[10] - plain[20]).abs() < 1e-3, "frame 10 an octave up is the one-shot's frame 20");
}

#[test]
fn a_cut_stops_every_kind_of_hit_there_with_a_fade_ending_on_it() {
    // The classic kit's synthesized hit, a one-shot and a kit preset's hit, each cut 0.1 s after it is struck.
    let sr = 44100.0;
    let file = std::env::temp_dir().join(format!("rostrum-cut-test-{}.f32", std::process::id()));
    let data: Vec<u8> = (0..44100).flat_map(|i| { let v = (i as f32 * 0.05).sin() * 0.5; [v.to_le_bytes(), v.to_le_bytes()].concat() }).collect();
    std::fs::write(&file, data).unwrap();
    let crash = crate::instruments::drumsynth::DrumModel { length: 1.5, metal: 1.0, metal_hp: 6000.0, noise_decay: 0.8, ..Default::default() };
    let kinds = [("cymbal", None, None), ("cymbal", Some(Pcm { file: file.to_string_lossy().into(), channels: 2, frames: 44100 }), None), ("cymbal", None, Some(crash))];
    for (voice, sample, model) in kinds {
        let is_sample = sample.is_some();
        let play = |cut| {
            let mut out = vec![];
            Voice::from_schedule(&V::Drum { voice: voice.into(), start_idx: 0, velocity: 1.0, pan: 0.0, tune: 1.0, decay: 1.0, cut, sample: sample.clone(), model }, usize::MAX, sr, &mut out).unwrap();
            let v = &mut out[0];
            (0..v.len).map(|i| v.next(i).0).collect::<Vec<f64>>()
        };
        let (whole, cut) = (play(None), play(Some(0.1)));
        assert!(whole.len() > 8820, "{voice} sample {is_sample}: rings past the cut on its own ({})", whole.len());
        assert_eq!(cut.len(), 4410, "{voice} sample {is_sample}: stops on the cut");
        // Up to the fade it is the same hit; the fade's last sample is near silence (no click).
        assert!(cut[..3900].iter().zip(&whole).all(|(a, b)| (a - b).abs() < 1e-12));
        let peak = |x: &[f64]| x.iter().fold(0.0f64, |m, v| m.max(v.abs()));
        assert!(peak(&cut[4400..]) <= 0.03 * peak(&whole), "{voice} sample {is_sample}: fades out");
    }
    std::fs::remove_file(&file).ok();
}
