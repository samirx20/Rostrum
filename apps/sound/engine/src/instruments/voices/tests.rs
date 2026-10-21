use super::*;
use crate::mix::schedule::{Pcm, Voice as V};

fn hit(voice: &str, tune: f64, decay: f64, sample: Option<Pcm>) -> Vec<f64> {
    let sr = 44100.0;
    let mut out = vec![];
    Voice::from_schedule(&V::Drum { voice: voice.into(), start_idx: 0, velocity: 1.0, pan: 0.0, tune, decay, sample, model: None }, usize::MAX, sr, &mut out).unwrap();
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
