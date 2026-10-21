//! The sampler's level against velocity, on the installed General MIDI font.

use super::*;

/// The installed "gm" font (`rostrum assets install sounds:musescore-general`), when it is there.
fn gm() -> Option<String> {
    let home = std::env::var("USERPROFILE").or_else(|_| std::env::var("HOME")).ok()?;
    let p = std::path::Path::new(&home).join(".rostrum/assets/sounds/musescore-general/MuseScore_General.sf2");
    p.exists().then(|| p.to_string_lossy().into_owned())
}

fn level(font: &str, program: i32, velocity: f64) -> f64 {
    let spec = SamplerSpec { font: font.into(), program, bank: 0, drums: false, humanize: true };
    let sr = 44100.0;
    let (mut l, mut r) = (vec![0.0f32; 66150], vec![0.0f32; 66150]);
    let n = Note { start: 0, len: 44100, freqs: &[261.63], velocity, expression: None, variation: None };
    render(&spec, &[n], &mut l, &mut r, sr).unwrap();
    let e: f64 = l.iter().chain(&r).map(|v| (*v as f64).powi(2)).sum::<f64>() / (2.0 * l.len() as f64);
    10.0 * e.max(1e-20).log10()
}

/// Louder as it is played harder, for every melodic General MIDI program (SoundFont modulators,
/// vendor/PATCHES.md: MuseScore General's pianos were 0.3 louder than 0.6 and +20 dB above 0.85).
#[test]
fn gm_level_rises_with_velocity() {
    let Some(font) = gm() else { return eprintln!("skipped: MuseScore General is not installed") };
    let mut bad = vec![];
    for program in 0..128 {
        let levels: Vec<f64> = (1..=10).map(|i| level(&font, program, i as f64 / 10.0)).collect();
        if levels.windows(2).any(|w| w[1] < w[0] - 0.5) || levels[9] - levels[0] < 3.0 {
            bad.push(format!("{program}: {:?}", levels.iter().map(|v| v.round() as i32).collect::<Vec<_>>()));
        }
    }
    assert!(bad.is_empty(), "level not rising with velocity:\n{}", bad.join("\n"));
}
