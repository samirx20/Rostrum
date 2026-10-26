//! sfzctl.rs / sfzpre.rs tests: the preprocessor, controller defaults (gates, modulations, curves),
//! crossfades, velocity curves, per-note controllers, note_polyphony and the extensible WAV format.
use crate::instruments::sfz::{parse, read_wav, render, select, Note, SfzSpec};
use std::path::Path;

fn tmp(name: &str) -> std::path::PathBuf {
    let d = std::env::temp_dir().join(format!("rostrum-sfzctl-{name}-{}", std::process::id()));
    std::fs::create_dir_all(&d).unwrap();
    d
}

#[test]
fn defines_and_includes_expand() {
    let d = tmp("pre");
    std::fs::write(d.join("part.sfz"), "<region> sample=$NAME.$EXT key=60 // a comment\n").unwrap();
    let r = parse("#define $EXT flac\n#define $NAME piano\n#include \"part.sfz\"\n#define $NAME other\n#include \"part.sfz\"", &d).unwrap();
    assert_eq!(r.iter().map(|r| r.sample.file_name().unwrap().to_string_lossy().into_owned()).collect::<Vec<_>>(), ["piano.flac", "other.flac"]);
    assert!(parse("#pragma once", &d).unwrap_err().contains("#pragma"));
    // A line of slashes and stars is a line comment, not the start of a block.
    assert_eq!(parse("//******\n<region> sample=a.wav /* a block */ key=60", &d).unwrap().len(), 1);
    std::fs::remove_dir_all(&d).ok();
}

#[test]
fn controllers_sit_at_their_defaults() {
    let text = "<control> set_cc100=127 set_hdcc72=0.5 label_cc100=Blend\n<curve> curve_index=8 v000=0 v127=0.5\n\
        <group> locc100=1 ampeg_release=0.25 ampeg_release_oncc72=2 amplitude_oncc7=100 amplitude_curvecc7=4 pan_oncc10=100 pan_curvecc10=1 <region> sample=a.wav\n\
        <group> hicc100=126 <region> sample=electric.wav\n\
        <group> ampeg_hold=5 ampeg_holdcc133=-5 volume_oncc1=6 volume_curvecc1=8 lfo01_pitch_oncc1=20 <region> sample=b.wav";
    let r = parse(text, Path::new("")).unwrap();
    // The electric region (hicc100=126) is gated off by cc100 = 127.
    assert_eq!(r.len(), 2);
    assert!((r[0].release - 1.25).abs() < 1e-9, "{}", r[0].release); // 0.25 + 2 × 0.5
    assert!((r[0].ext.gain - (100.0f64 / 127.0).powi(2)).abs() < 1e-9); // CC 7 at 100, curve 4 (x²)
    assert!(r[0].pan.abs() < 1e-9); // CC 10 at 64, bipolar: centred
    assert_eq!(r[1].volume, 0.0); // CC 1 at 0 through curve 8; its LFO modulation is zero too
    assert_eq!(r[1].ext.per_note, vec![("ampeg_hold".to_string(), -5.0, 133, 0)]);
    assert!(parse("<control> set_cc1=64 <region> sample=a.wav lfo01_pitch_oncc1=20", Path::new("")).unwrap_err().contains("lfo01_pitch"));
}

#[test]
fn crossfades_and_velocity_curves_shape_the_gain() {
    let r = parse("<region> sample=a.wav xfin_lovel=0 xfin_hivel=64 amp_velcurve_64=0.5 amp_velcurve_127=1", Path::new("")).unwrap();
    let g = |v: f64| r[0].ext.note_gain(1.0, 60.0, v, 0.0);
    assert!((g(32.0 / 127.0) - (0.5f64).sqrt() * 0.25).abs() < 0.01, "{}", g(32.0 / 127.0)); // half-way into the fade, a quarter up the curve
    assert!((g(1.0) - 1.0).abs() < 1e-9);
    assert_eq!(select(&r, 60, 1, 0, 0.5).len(), 1);
}

#[test]
fn reads_extensible_float_wavs_and_note_polyphony_stops_a_restruck_key() {
    let d = tmp("wav");
    let sr = 44100.0;
    let pcm: Vec<u8> = (0..44100).flat_map(|i| ((2.0 * std::f64::consts::PI * 440.0 * i as f64 / sr).sin() as f32 * 0.5).to_le_bytes()).collect();
    let mut w = b"RIFF".to_vec();
    w.extend((60 + pcm.len() as u32).to_le_bytes()); w.extend(b"WAVEfmt "); w.extend(40u32.to_le_bytes());
    w.extend([0xFEu8, 0xFF, 1, 0]); w.extend(44100u32.to_le_bytes()); w.extend((44100u32 * 4).to_le_bytes()); w.extend([4u8, 0, 32, 0]);
    w.extend([22u8, 0, 32, 0, 4, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0x10, 0, 0x80, 0, 0, 0xAA, 0, 0x38, 0x9B, 0x71]);
    w.extend(b"data"); w.extend((pcm.len() as u32).to_le_bytes()); w.extend(&pcm);
    std::fs::write(d.join("f.wav"), w).unwrap();
    let s = read_wav(&d.join("f.wav")).unwrap();
    assert!((s.frames[25][0] - (2.0 * std::f64::consts::PI * 440.0 * 25.0 / sr).sin() as f32 * 0.5).abs() < 1e-6);
    std::fs::write(d.join("p.sfz"), "<region> sample=f.wav key=69 loop_mode=one_shot note_polyphony=1 off_time=0.01").unwrap();
    let file = d.join("p.sfz").to_string_lossy().into_owned();
    let (mut l, mut r) = (vec![0.0f32; 44100], vec![0.0f32; 44100]);
    let n = |start| Note { start, len: 2000, freqs: &[440.0], velocity: 1.0, pan: 0.0, expression: None };
    render(&SfzSpec { file, legato: false, swell: false, even: false, gains: vec![], key_offset: 0 }, &[n(0), n(22050)], &mut l, &mut r, sr).unwrap();
    // After the second strike only one voice sounds (the first stopped), not two summed.
    let peak = l[30000..34000].iter().fold(0.0f32, |m, v| m.max(v.abs()));
    assert!(peak < 0.6, "{peak}");
    std::fs::remove_dir_all(&d).ok();
}

