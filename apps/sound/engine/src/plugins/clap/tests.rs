use super::render::render;
use super::*;

/// Surge XT, when installed (the S4 test plugin); the test is skipped otherwise.
fn surge() -> Option<(String, String)> {
    let p = folders().into_iter().map(|d| d.join("Surge XT.clap")).find(|p| p.exists())?;
    Some((p.to_string_lossy().into_owned(), "org.surge-synth-team.surge-xt".into()))
}

#[test]
fn automation_follows_song_time() {
    let Some((path, id)) = surge() else {
        eprintln!("Surge XT not installed: skipped");
        return;
    };
    let rms = |x: &[f32]| (x.iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / x.len() as f64).sqrt();
    // Global Volume silent until 0.5 s of song, then up to 0.9 at 1 s.
    let env = crate::mix::schedule::Param::Envelope(vec![[0.0, 0.0], [0.5, 0.0], [1.0, 0.9]]);
    let run = |at: f64| {
        let spec = PluginSpec { format: "clap".into(), path: path.clone(), id: id.clone(), params: vec![(3484083994, env.clone())], state: None, at, cc: vec![] };
        let (mut l, mut r) = (vec![0f32; 48000], vec![0f32; 48000]);
        render(&spec, &[Note { start: 0, end: 48000, key: 57, velocity: 0.8 }], &mut l, &mut r, 48000.0, false).unwrap();
        l
    };
    let clip_at_0 = run(0.0);
    assert!(rms(&clip_at_0[2400..21600]) < 1e-3, "silent while the envelope holds 0: {}", rms(&clip_at_0[2400..21600]));
    assert!(rms(&clip_at_0[40000..]) > 0.01, "up by the end: {}", rms(&clip_at_0[40000..]));
    // The same clip starting at 1 s of song: the envelope is already at the top.
    let clip_at_1 = run(1.0);
    assert!(rms(&clip_at_1[2400..21600]) > 0.01, "{}", rms(&clip_at_1[2400..21600]));
}

#[test]
fn a_third_party_instrument_plays_notes_at_their_pitch_and_renders_the_same_twice() {
    let Some((path, id)) = surge() else {
        eprintln!("Surge XT not installed: skipped");
        return;
    };
    let sr = 48000.0;
    let spec = PluginSpec { format: "clap".into(), path, id, params: vec![], state: None, at: 0.0, cc: vec![] };
    let notes = [Note { start: 4800, end: 4800 + 24000, key: 57, velocity: 0.8 }]; // A3, 0.5 s from 0.1 s
    let run = || {
        let (mut l, mut r) = (vec![0f32; 48000], vec![0f32; 48000]);
        render(&spec, &notes, &mut l, &mut r, sr, false).unwrap();
        l
    };
    let a = run();
    let peak = a.iter().fold(0f32, |m, v| m.max(v.abs()));
    assert!(peak > 0.01, "the note sounds (peak {peak})");
    assert!(a[..4800].iter().all(|v| v.abs() < 1e-4), "silent before the note");
    // About 220 Hz: upward zero crossings over 0.2 … 0.5 s.
    let ups = a[9600..24000].windows(2).filter(|w| w[0] < 0.0 && w[1] >= 0.0).count() as f64 / 0.3;
    assert!((ups - 220.0).abs() < 25.0, "{ups} crossings a second");
    let b = run();
    let diff = a.iter().zip(&b).map(|(x, y)| (x - y).abs()).fold(0f32, f32::max);
    eprintln!("render twice: largest difference {diff}");
}

#[test]
fn cc_lanes_become_midi_messages_sent_when_they_change() {
    let lanes = vec![CcLane { cc: 1, points: vec![[1.0, 0.0], [2.0, 1.0]] }, CcLane { cc: 128, points: vec![[0.0, 0.0], [0.5, 1.0]] }];
    let sr = 1000.0;
    let mut last = vec![];
    let first = cc_events(&lanes, &mut last, 0.0, sr, 0, 256);
    assert_eq!(first[0], (0, [0xB0, 1, 0]), "the mod wheel at its start");
    assert!(first.contains(&(0, [0xE0, 0, 64])), "the pitch wheel centred: {first:?}");
    let held = cc_events(&lanes, &mut last, 0.0, sr, 512, 256);
    assert!(held.iter().all(|e| e.1[0] == 0xE0), "an unchanged mod wheel is not sent again: {held:?}");
    let top = cc_events(&lanes, &mut last, 0.0, sr, 2048, 64);
    assert_eq!(top, vec![(0, [0xB0, 1, 127])], "the wheel at its top; the bend already sent");
    assert_eq!(CcLane { cc: 128, points: vec![[0.0, -1.0]] }.midi(0.0), [0xE0, 0, 0]);
    assert_eq!(CcLane { cc: 128, points: vec![[0.0, 1.0]] }.midi(0.0), [0xE0, 0x7f, 0x7f]);
}

#[test]
fn a_unit_is_read_off_the_display_text() {
    assert_eq!(unit_of("-60.0 dB"), Some("dB"));
    assert_eq!(unit_of("1.2 kHz"), Some("kHz"));
    assert_eq!(unit_of("440Hz"), Some("Hz"));
    assert_eq!(unit_of("10 ms"), Some("ms"));
    assert_eq!(unit_of("0.5 s"), Some("s"));
    assert_eq!(unit_of("50 %"), Some("%"));
    assert_eq!(unit_of("Saw"), None);
    assert_eq!(unit_of("Off"), None);
}
