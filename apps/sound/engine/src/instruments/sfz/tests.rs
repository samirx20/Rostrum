//! sfz.rs tests: parsing, selection, rendering (pitch, legato, loops, one-shots, chokes, release samples).
use super::*;

const VSCO_LIKE: &str = "<control>\ndefault_path=Strings\\Violin Section\\Spic\\\n<global> ampeg_attack=0.001 ampeg_release=4 ampeg_dynamic=1 // comment\n<group> seq_length=2 seq_position=1 group_label=gr_1\n<region> sample=Vln A3 rr1.wav lokey=68 hikey=70 pitch_keycenter=69 lovel=0 hivel=62 volume=17\n<region> sample=Vln_A3_v2_rr1.wav lokey=68 hikey=70 pitch_keycenter=a4 lovel=63 hivel=127\n/* block */<group> seq_length=2 seq_position=2\n<region> sample=Vln_A3_rr2.wav key=69\n";

#[test]
fn parses_regions_with_inherited_opcodes_and_paths() {
    let r = parse(VSCO_LIKE, Path::new("lib")).unwrap();
    assert_eq!(r.len(), 3);
    assert_eq!(r[0].sample, Path::new("lib").join("Strings/Violin Section/Spic/Vln A3 rr1.wav"));
    assert_eq!((r[0].lokey, r[0].hikey, r[0].keycenter, r[0].hivel, r[0].volume), (68, 70, 69.0, 62, 17.0));
    assert_eq!((r[0].release, r[0].seq_length, r[0].seq_position), (4.0, 2, 1));
    assert_eq!(r[1].keycenter, 69.0); // a4 = 69
    assert_eq!((r[2].lokey, r[2].hikey, r[2].seq_position, r[2].volume), (69, 69, 2, 0.0)); // a group resets the one before
}

#[test]
fn selects_by_key_velocity_and_round_robin() {
    let r = parse(VSCO_LIKE, Path::new("")).unwrap();
    let names = |v: Vec<&Region>| v.iter().map(|r| r.sample.file_name().unwrap().to_string_lossy().into_owned()).collect::<Vec<_>>();
    assert_eq!(names(select(&r, 69, 40, 0, 0.3)), ["Vln A3 rr1.wav"]);
    assert_eq!(names(select(&r, 69, 100, 0, 0.3)), ["Vln_A3_v2_rr1.wav"]);
    assert_eq!(names(select(&r, 69, 100, 1, 0.3)), ["Vln_A3_rr2.wav"]); // the second strike alternates
    assert!(select(&r, 72, 100, 0, 0.3).is_empty());
    let rand = parse("<group> lorand=0 hirand=0.5 <region> sample=a.wav <group> lorand=0.5 hirand=1 <region> sample=b.wav", Path::new("")).unwrap();
    assert_eq!(names(select(&rand, 60, 90, 0, 0.2)), ["a.wav"]);
    assert_eq!(names(select(&rand, 60, 90, 0, 0.7)), ["b.wav"]);
}

#[test]
fn refuses_what_it_does_not_play() {
    assert!(parse("<region> sample=a.wav fil_type=lpf_2p", Path::new("")).unwrap_err().contains("fil_type"));
    assert!(parse("<group> sw_lokey=c6 <region> sample=a.wav", Path::new("")).unwrap_err().contains("keyswitch"));
    assert_eq!(note("c#4").unwrap(), 61.0);
    assert_eq!(note("db4").unwrap(), 61.0);
}

#[test]
fn a_note_longer_than_its_sample_holds_on_a_crossfaded_loop() {
    // A 3 s sustained sample with no loop of its own; an 8 s note keeps sounding, steadily.
    let dir = std::env::temp_dir().join(format!("rostrum-sfz-loop-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let sr = 44100.0;
    let pcm: Vec<u8> = (0..44100 * 3).flat_map(|i| (((2.0 * std::f64::consts::PI * 220.0 * i as f64 / sr).sin() * 12000.0) as i16).to_le_bytes()).collect();
    let mut w = b"RIFF".to_vec();
    w.extend((36 + pcm.len() as u32).to_le_bytes()); w.extend(b"WAVEfmt "); w.extend(16u32.to_le_bytes());
    w.extend([1u8, 0, 1, 0]); w.extend(44100u32.to_le_bytes()); w.extend(88200u32.to_le_bytes()); w.extend([2u8, 0, 16, 0]);
    w.extend(b"data"); w.extend((pcm.len() as u32).to_le_bytes()); w.extend(&pcm);
    std::fs::write(dir.join("long.wav"), w).unwrap();
    std::fs::write(dir.join("i.sfz"), "<region> sample=long.wav lokey=0 hikey=127 pitch_keycenter=57 ampeg_release=0.05").unwrap();
    let file = dir.join("i.sfz").to_string_lossy().into_owned();
    let n = (sr * 8.0) as usize;
    let (mut l, mut r) = (vec![0.0f32; n + 4410], vec![0.0f32; n + 4410]);
    render(&SfzSpec { file, legato: false, swell: false, even: false, gains: vec![], key_offset: 0, velocity_tone: 0.0 }, &[Note { start: 0, len: n, freqs: &[220.0], velocity: 1.0, pan: 0.0, expression: None }], &mut l, &mut r, sr, None).unwrap();
    let rms = |a: f64, b: f64| { let s = &l[(a * sr) as usize..(b * sr) as usize]; (s.iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / s.len() as f64).sqrt() };
    let (early, late) = (rms(1.0, 2.0), rms(6.5, 7.5));
    assert!(early > 0.05 && late > early * 0.7, "early {early}, late {late}");
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn renders_at_pitch_with_legato_handover() {
    let dir = std::env::temp_dir().join(format!("rostrum-sfz-test-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    // A 1 s 220 Hz sine at 44.1 kHz, mono 16-bit, rooted at A3 (57).
    let sr = 44100.0;
    let pcm: Vec<u8> = (0..44100).flat_map(|i| (((2.0 * std::f64::consts::PI * 220.0 * i as f64 / sr).sin() * 16000.0) as i16).to_le_bytes()).collect();
    let mut w = b"RIFF".to_vec();
    w.extend((36 + pcm.len() as u32).to_le_bytes()); w.extend(b"WAVEfmt "); w.extend(16u32.to_le_bytes());
    w.extend([1u8, 0, 1, 0]); w.extend(44100u32.to_le_bytes()); w.extend(88200u32.to_le_bytes()); w.extend([2u8, 0, 16, 0]);
    w.extend(b"data"); w.extend((pcm.len() as u32).to_le_bytes()); w.extend(&pcm);
    std::fs::write(dir.join("sine.wav"), w).unwrap();
    std::fs::write(dir.join("i.sfz"), "<region> sample=sine.wav lokey=0 hikey=127 pitch_keycenter=57 ampeg_release=0.01").unwrap();
    let file = dir.join("i.sfz").to_string_lossy().into_owned();
    let crossings = |x: &[f32]| x.windows(2).filter(|w| w[0] <= 0.0 && w[1] > 0.0).count();
    // An octave up plays at 440 Hz: about 44 rising crossings in 0.1 s.
    let (mut l, mut r) = (vec![0.0f32; 4410], vec![0.0f32; 4410]);
    render(&SfzSpec { file: file.clone(), legato: false, swell: false, even: false, gains: vec![], key_offset: 0, velocity_tone: 0.0 }, &[Note { start: 0, len: 4410, freqs: &[440.0], velocity: 1.0, pan: 0.0, expression: None }], &mut l, &mut r, sr, None).unwrap();
    assert!((43..=45).contains(&crossings(&l)), "{}", crossings(&l));
    // A file that names the sample an octave above what it sounds (as Growlybass does), with its key offset: as written.
    std::fs::write(dir.join("high.sfz"), "<region> sample=sine.wav lokey=0 hikey=127 pitch_keycenter=69 ampeg_release=0.01").unwrap();
    let (mut l, mut r) = (vec![0.0f32; 4410], vec![0.0f32; 4410]);
    render(&SfzSpec { file: dir.join("high.sfz").to_string_lossy().into_owned(), legato: false, swell: false, even: false, gains: vec![], key_offset: 12, velocity_tone: 0.0 }, &[Note { start: 0, len: 4410, freqs: &[440.0], velocity: 1.0, pan: 0.0, expression: None }], &mut l, &mut r, sr, None).unwrap();
    assert!((43..=45).contains(&crossings(&l)), "{}", crossings(&l));
    // Legato: the first note fades out over the handover instead of ringing to its release.
    let n = [Note { start: 0, len: 22050, freqs: &[220.0], velocity: 1.0, pan: 0.0, expression: None }, Note { start: 11025, len: 11025, freqs: &[330.0], velocity: 1.0, pan: 0.0, expression: None }];
    let (mut l1, mut r1) = (vec![0.0f32; 22050], vec![0.0f32; 22050]);
    render(&SfzSpec { file: file.clone(), legato: true, swell: false, even: false, gains: vec![], key_offset: 0, velocity_tone: 0.0 }, &n[..1], &mut l1, &mut r1, sr, None).unwrap();
    let (mut l2, mut r2) = (vec![0.0f32; 22050], vec![0.0f32; 22050]);
    render(&SfzSpec { file, legato: true, swell: false, even: false, gains: vec![], key_offset: 0, velocity_tone: 0.0 }, &n, &mut l2, &mut r2, sr, None).unwrap();
    let tail = |x: &[f32]| x[16000..18000].iter().map(|v| v.abs()).fold(0.0f32, f32::max);
    // After the handover only the second note sounds: 330 Hz, not the 220 Hz first note added on top.
    assert!(tail(&l1) > 0.3 && (14..=16).contains(&crossings(&l2[16000..18000])), "{} {}", tail(&l1), crossings(&l2[16000..18000]));
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn one_shots_ring_past_the_note_chokes_stop_them_and_release_samples_follow_the_note() {
    let dir = std::env::temp_dir().join(format!("rostrum-sfz-kit-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let sr = 44100.0;
    let pcm: Vec<u8> = (0..44100).flat_map(|i| (((2.0 * std::f64::consts::PI * 440.0 * i as f64 / sr).sin() * 16000.0) as i16).to_le_bytes()).collect();
    let mut w = b"RIFF".to_vec();
    w.extend((36 + pcm.len() as u32).to_le_bytes()); w.extend(b"WAVEfmt "); w.extend(16u32.to_le_bytes());
    w.extend([1u8, 0, 1, 0]); w.extend(44100u32.to_le_bytes()); w.extend(88200u32.to_le_bytes()); w.extend([2u8, 0, 16, 0]);
    w.extend(b"data"); w.extend((pcm.len() as u32).to_le_bytes()); w.extend(&pcm);
    std::fs::write(dir.join("t.wav"), w).unwrap();
    // Key 42 (closed hat) is group 1; key 46 (open hat) a one-shot choked by group 1; key 60 a note with a release sample at a fixed pitch.
    std::fs::write(dir.join("k.sfz"), "<region> sample=t.wav key=42 group=1 loop_mode=one_shot\n<region> sample=t.wav key=46 group=2 off_by=1 loop_mode=one_shot\n<region> sample=t.wav key=60 ampeg_release=0.01\n<region> sample=t.wav key=60 trigger=release pitch_keytrack=0 pitch_keycenter=69 rt_decay=20 loop_mode=one_shot\n<group> on_locc64=126 lokey=-1 hikey=-1\n<region> sample=t.wav").unwrap();
    let file = dir.join("k.sfz").to_string_lossy().into_owned();
    let f = |k: f64| 440.0 * 2f64.powf((k - 69.0) / 12.0);
    let (oh, ch, c4) = ([f(46.0)], [f(42.0)], [f(60.0)]);
    let play = |notes: &[Note]| { let (mut l, mut r) = (vec![0.0f32; 44100], vec![0.0f32; 44100]); render(&SfzSpec { file: file.clone(), legato: false, swell: false, even: false, gains: vec![], key_offset: 0, velocity_tone: 0.0 }, notes, &mut l, &mut r, sr, None).unwrap(); l };
    let peak = |x: &[f32], a: f64, b: f64| x[(a * sr) as usize..(b * sr) as usize].iter().fold(0.0f32, |m, v| m.max(v.abs()));
    // A one-shot open hat held 0.1 s still rings at 0.5 s; a closed hat at 0.3 s chokes it.
    let open = play(&[Note { start: 0, len: 4410, freqs: &oh, velocity: 1.0, pan: 0.0, expression: None }]);
    assert!(peak(&open, 0.5, 0.6) > 0.2);
    let choked = play(&[Note { start: 0, len: 4410, freqs: &oh, velocity: 1.0, pan: 0.0, expression: None }, Note { start: 13230, len: 100, freqs: &ch, velocity: 0.0001, pan: 0.0, expression: None }]);
    assert!(peak(&choked, 0.5, 0.6) < 0.01, "{}", peak(&choked, 0.5, 0.6));
    // The release sample sounds after the note ends, at its own pitch (440 Hz), softer for a longer note.
    let short = play(&[Note { start: 0, len: 2205, freqs: &c4, velocity: 1.0, pan: 0.0, expression: None }]);
    let long = play(&[Note { start: 0, len: 13230, freqs: &c4, velocity: 1.0, pan: 0.0, expression: None }]);
    let crossings = |x: &[f32]| x.windows(2).filter(|w| w[0] <= 0.0 && w[1] > 0.0).count();
    assert!((43..=45).contains(&crossings(&short[8820..13230])), "{}", crossings(&short[8820..13230]));
    assert!(peak(&long, 0.5, 0.6) < 0.5 * peak(&short, 0.5, 0.6));
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn a_slow_attack_note_is_heard_on_its_time() {
    // A horn-like sample whose level rises over 240 ms (heard ~60 ms in): a note at 1 s is heard within 10 ms of 1 s.
    let dir = std::env::temp_dir().join(format!("rostrum-sfz-attack-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let sr = 48000.0;
    let pcm: Vec<u8> = (0..48000).flat_map(|i| ((((i as f64 / (0.24 * sr)).min(1.0)) * (2.0 * std::f64::consts::PI * 220.0 * i as f64 / sr).sin() * 16000.0) as i16).to_le_bytes()).collect();
    let mut w = b"RIFF".to_vec();
    w.extend((36 + pcm.len() as u32).to_le_bytes()); w.extend(b"WAVEfmt "); w.extend(16u32.to_le_bytes());
    w.extend([1u8, 0, 1, 0]); w.extend(48000u32.to_le_bytes()); w.extend(96000u32.to_le_bytes()); w.extend([2u8, 0, 16, 0]);
    w.extend(b"data"); w.extend((pcm.len() as u32).to_le_bytes()); w.extend(&pcm);
    std::fs::write(dir.join("slow.wav"), w).unwrap();
    std::fs::write(dir.join("i.sfz"), "<region> sample=slow.wav lokey=0 hikey=127 pitch_keycenter=57 ampeg_release=0.05").unwrap();
    let file = dir.join("i.sfz").to_string_lossy().into_owned();
    let (mut l, mut r) = (vec![0.0f32; 96000], vec![0.0f32; 96000]);
    render(&SfzSpec { file, legato: false, swell: false, even: false, gains: vec![], key_offset: 0, velocity_tone: 0.0 }, &[Note { start: 48000, len: 24000, freqs: &[220.0], velocity: 1.0, pan: 0.0, expression: None }], &mut l, &mut r, sr, None).unwrap();
    let frames: Vec<[f32; 2]> = l.iter().zip(&r).map(|(a, b)| [*a, *b]).collect();
    let heard = (36000 + onset::find(&frames, sr, 36000)) as f64 / sr;
    assert!((heard - 1.0).abs() <= 0.010, "heard at {heard:.3} s");
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn a_note_outside_the_samples_plays_from_the_nearest_one_at_its_written_pitch() {
    // Vault r2: a viola A2 (the samples start at C3) stopped the whole mix; it plays as written now, stretched.
    let dir = std::env::temp_dir().join(format!("rostrum-sfz-range-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let sr = 44100.0;
    let pcm: Vec<u8> = (0..44100).flat_map(|i| (((2.0 * std::f64::consts::PI * 440.0 * i as f64 / sr).sin() * 16000.0) as i16).to_le_bytes()).collect();
    let mut w = b"RIFF".to_vec();
    w.extend((36 + pcm.len() as u32).to_le_bytes()); w.extend(b"WAVEfmt "); w.extend(16u32.to_le_bytes());
    w.extend([1u8, 0, 1, 0]); w.extend(44100u32.to_le_bytes()); w.extend(88200u32.to_le_bytes()); w.extend([2u8, 0, 16, 0]);
    w.extend(b"data"); w.extend((pcm.len() as u32).to_le_bytes()); w.extend(&pcm);
    std::fs::write(dir.join("a.wav"), w).unwrap();
    std::fs::write(dir.join("r.sfz"), "<region> sample=a.wav lokey=69 hikey=81 pitch_keycenter=69").unwrap();
    let (mut l, mut r) = (vec![0.0f32; 44100], vec![0.0f32; 44100]);
    let low = [220.0];                                   // A3: an octave under the lowest sample
    render(&SfzSpec { file: dir.join("r.sfz").to_string_lossy().into_owned(), legato: false, swell: false, even: false, gains: vec![], key_offset: 0, velocity_tone: 0.0 },
           &[Note { start: 0, len: 22050, freqs: &low, velocity: 1.0, pan: 0.0, expression: None }], &mut l, &mut r, sr, None).unwrap();
    let crossings = l[4410..13230].windows(2).filter(|w| w[0] <= 0.0 && w[1] > 0.0).count();
    assert!((43..=45).contains(&crossings), "{crossings}");   // 0.2 s at 220 Hz
    assert_eq!(nearest_key(&instrument(&dir.join("r.sfz").to_string_lossy()).unwrap(), 57), Some(69));
    std::fs::remove_dir_all(&dir).ok();
}
