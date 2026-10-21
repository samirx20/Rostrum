use super::*;
use crate::live::wasapi::Source;

#[test]
fn a_held_synth_note_sounds_until_released_and_is_recorded_where_it_was_heard() {
    let (etx, erx) = std::sync::mpsc::channel();
    let (rtx, rrx) = std::sync::mpsc::channel();
    let spec: LiveSpec = serde_json::from_str(r#"{"synth":{"wave":"saw","voices":1,"detune":0,"cutoff":2000,"resonance":0.2,"envAmount":1,"attack":0.005,"decay":0.1,"sustain":0.6,"release":0.05,"octave":0}}"#).unwrap();
    let mut inst = Instrument::new(&spec, 48000, erx, rtx).unwrap();
    let mut block = vec![0f32; 288]; // 144 frames: 3 ms at 48 kHz
    let mut frame = 0u64;
    let mut run = |inst: &mut Instrument, n: usize| -> f32 {
        let mut peak = 0f32;
        for _ in 0..n {
            block.fill(0.0);
            inst.fill(&mut block, frame);
            frame += 144;
            peak = block.iter().fold(peak, |m, s| m.max(s.abs()));
        }
        peak
    };
    assert_eq!(run(&mut inst, 2), 0.0);
    etx.send(Event::On { key: 69, velocity: 0.8, at: 0.0 }).unwrap();
    assert!(run(&mut inst, 100) > 0.05, "a held note keeps sounding");
    etx.send(Event::Off { key: 69 }).unwrap();
    run(&mut inst, 40); // 120 ms: past the 50 ms release
    assert_eq!(run(&mut inst, 2), 0.0, "released and gone");
    let notes: Vec<_> = rrx.try_iter().filter_map(|r| if let Report::Note { key, start, end, .. } = r { Some((key, start, end)) } else { None }).collect();
    assert_eq!(notes, vec![(69, 288, 288 + 100 * 144)]);
}

#[test]
fn an_sfz_key_sustains_until_released_and_a_flood_of_keys_steals_voices_with_a_fade() {
    let dir = std::env::temp_dir().join(format!("rostrum-live-sfz-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    // A 2 s 220 Hz sine, looped over its last second, rooted at A3.
    let pcm: Vec<u8> = (0..96000).flat_map(|i| (((2.0 * std::f64::consts::PI * 220.0 * i as f64 / 48000.0).sin() * 16000.0) as i16).to_le_bytes()).collect();
    let mut w = b"RIFF".to_vec();
    w.extend((36 + pcm.len() as u32).to_le_bytes());
    w.extend(b"WAVEfmt ");
    w.extend(16u32.to_le_bytes());
    w.extend([1u8, 0, 1, 0]);
    w.extend(48000u32.to_le_bytes());
    w.extend(96000u32.to_le_bytes());
    w.extend([2u8, 0, 16, 0]);
    w.extend(b"data");
    w.extend((pcm.len() as u32).to_le_bytes());
    w.extend(&pcm);
    std::fs::write(dir.join("sine.wav"), w).unwrap();
    std::fs::write(dir.join("i.sfz"), "<region> sample=sine.wav lokey=0 hikey=127 pitch_keycenter=57 ampeg_release=0.02 loop_mode=loop_continuous loop_start=48000 loop_end=95999").unwrap();
    let spec: LiveSpec = serde_json::from_str(&format!(r#"{{"sfz":{{"file":{:?}}}}}"#, dir.join("i.sfz").to_string_lossy())).unwrap();
    let (etx, erx) = std::sync::mpsc::channel();
    let (rtx, _rrx) = std::sync::mpsc::channel();
    let mut inst = Instrument::new(&spec, 48000, erx, rtx).unwrap();
    let mut frame = 0u64;
    let mut run = |inst: &mut Instrument, n: usize| -> f32 {
        let mut peak = 0f32;
        for _ in 0..n {
            let mut block = vec![0f32; 288];
            inst.fill(&mut block, frame);
            frame += 144;
            peak = block.iter().fold(peak, |m, s| m.max(s.abs()));
        }
        peak
    };
    etx.send(Event::On { key: 57, velocity: 1.0, at: 0.0 }).unwrap();
    run(&mut inst, 1000); // 3 s: past the sample's end, held by its loop
    assert!(run(&mut inst, 10) > 0.3, "a held key keeps sounding through the loop");
    etx.send(Event::Off { key: 57 }).unwrap();
    run(&mut inst, 10);
    assert_eq!(run(&mut inst, 2), 0.0, "released and gone");
    for k in 0..80u8 {
        etx.send(Event::On { key: 30 + k, velocity: 0.5, at: 0.0 }).unwrap();
    }
    run(&mut inst, 1);
    assert_eq!(inst.playing.len(), MAX_VOICES);
    assert_eq!(inst.stolen.len(), 80 - MAX_VOICES);
    run(&mut inst, 2); // 6 ms: the stolen voices have faded
    assert!(inst.stolen.is_empty());
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn named_instruments_are_refused_live() {
    let (_e, erx) = std::sync::mpsc::channel();
    let (rtx, _r) = std::sync::mpsc::channel();
    let spec: LiveSpec = serde_json::from_str("{}").unwrap();
    assert!(Instrument::new(&spec, 48000, erx, rtx).is_err());
}

#[test]
fn an_analog_pluck_played_live_matches_its_bounce_sample_for_sample_at_any_block_size() {
    // The analogPluck preset (synth.ts): drift and noise make each note's phases and noise depend on its seed.
    let synth = r#"{"wave":"saw","voices":3,"detune":9,"cutoff":520,"resonance":0.22,"envAmount":3.6,"filterEnv":{"attack":0.001,"decay":0.25,"sustain":0,"release":0.2},"filterVelocity":1.2,"attack":0.001,"decay":0.55,"sustain":0,"release":0.3,"octave":0,"pitchEnv":{"semitones":0.4,"time":0.008},"drift":4,"noise":0.015,"curve":"analog","level":6}"#;
    let (rate, key, velocity) = (48000usize, 64u8, 0.8);
    let freq = 440.0 * 2f64.powf((key as f64 - 69.0) / 12.0);
    let window = rate / 100; // the first 10 ms
    for block in [64usize, 144, 512] {
        let (etx, erx) = std::sync::mpsc::channel();
        let (rtx, _r) = std::sync::mpsc::channel();
        let spec: LiveSpec = serde_json::from_str(&format!(r#"{{"synth":{synth}}}"#)).unwrap();
        let mut inst = Instrument::new(&spec, rate as u32, erx, rtx).unwrap();
        // Two silent blocks, then the key: it is heard (and recorded) at the third block's first frame.
        let at = 2 * block;
        let mut live = vec![];
        let mut buf = vec![0f32; block * 2];
        for b in 0..(at + window).div_ceil(block) {
            if b == 2 {
                etx.send(Event::On { key, velocity, at: 0.0 }).unwrap();
            }
            buf.fill(0.0);
            inst.fill(&mut buf, (b * block) as u64);
            live.extend(buf.chunks(2).map(|f| (f[0] as f64, f[1] as f64)));
        }
        // The bounce: the same note scheduled at the frame it was recorded.
        let note: crate::mix::schedule::Voice = serde_json::from_str(&format!(r#"{{"kind":"note","instrument":"synth","synth":{synth},"freqs":[{freq}],"startIdx":{at},"duration":1.0,"velocity":{velocity},"pan":0}}"#)).unwrap();
        let mut voices = vec![];
        crate::instruments::voices::Voice::from_schedule(&note, usize::MAX, rate as f64, &mut voices).unwrap();
        assert_eq!(voices.len(), 1);
        let v = &mut voices[0];
        assert_eq!(v.start, at);
        for i in 0..window {
            let (bl, br) = v.next(i);
            let (ll, lr) = live[at + i];
            assert!((bl - ll).abs() < 1e-5 && (br - lr).abs() < 1e-5, "block {block}, sample {i}: bounce ({bl}, {br}), live ({ll}, {lr})");
        }
        assert!(live[at..at + window].iter().any(|(l, _)| l.abs() > 0.01), "the pluck sounds");
    }
}
