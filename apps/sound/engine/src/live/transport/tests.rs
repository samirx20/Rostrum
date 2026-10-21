//! The transport's tests (transport.rs): sample-accurate play and loop, the metronome, count-in,
//! overdub inside a punch, the clock and resampling.

use super::*;
use crate::live::wasapi::Source;
use std::sync::mpsc::channel;

/// A transport at 1 kHz over a ramp (frame k holds k / 10⁶), and its channels.
fn rig(bpm: f64) -> (Transport, Sender<Cmd>, Sender<Event>, Receiver<Out>) {
    let mix: Vec<[f32; 2]> = (0..3000).map(|k| [k as f32 / 1e6, 0.0]).collect();
    let (c, cr) = channel();
    let (n, nr) = channel();
    let (o, or) = channel();
    (Transport::new(Arc::new(Frames::stereo(&mix)), 1000, bpm, 4, None, cr, nr, o), c, n, or)
}

/// Runs `blocks` blocks of 7 frames; returns the left channel.
fn run(t: &mut Transport, frame: &mut u64, blocks: usize) -> Vec<f32> {
    let mut left = vec![];
    for _ in 0..blocks {
        let mut b = vec![0f32; 14];
        t.fill(&mut b, *frame);
        *frame += 7;
        left.extend(b.iter().step_by(2));
    }
    left
}

#[test]
fn plays_from_a_point_and_loops_sample_accurately() {
    let (mut t, c, _n, o) = rig(120.0);
    c.send(Cmd::Loop(Some((1.0, 1.5)))).unwrap();
    c.send(Cmd::Play(Some(1.0))).unwrap();
    let mut frame = 0;
    let out = run(&mut t, &mut frame, 172); // 1204 frames
    for (k, v) in out.iter().enumerate() {
        assert_eq!(*v, (1000 + k % 500) as f32 / 1e6, "frame {k}");
    }
    assert_eq!(o.try_iter().filter(|m| *m == Out::Wrapped).count(), 2);
    // Stop holds the place; play carries on from it.
    c.send(Cmd::Stop).unwrap();
    assert!(run(&mut t, &mut frame, 3).iter().all(|v| *v == 0.0));
    c.send(Cmd::Loop(None)).unwrap();
    c.send(Cmd::Play(None)).unwrap();
    assert_eq!(run(&mut t, &mut frame, 1)[0], (1000 + 1204 % 500) as f32 / 1e6);
    // To the end: it stops there and says so.
    c.send(Cmd::Seek(2.99)).unwrap();
    let tail = run(&mut t, &mut frame, 3);
    assert_eq!(tail[9], 2999.0 / 1e6);
    assert_eq!(tail[10], 0.0);
    assert!(o.try_iter().any(|m| m == Out::End));
}

/// A song whose tempo changes: the metronome clicks on the beats it is given (a ramp's beats come closer).
#[test]
fn the_metronome_follows_the_beat_times_of_a_tempo_map() {
    let (t, c, _n, _o) = rig(60.0);
    let mut t = t.with_beats(&[0.0, 1.0, 1.8, 2.4]);
    c.send(Cmd::Metronome(true)).unwrap();
    c.send(Cmd::Play(Some(0.0))).unwrap();
    let mut frame = 0;
    let out = run(&mut t, &mut frame, 400); // 2800 frames
    let clicks: Vec<usize> = (0..2800).filter(|&k| out[k].abs() > 0.01 && (k == 0 || out[k - 1].abs() <= 0.01)).collect();
    assert!([0, 1000, 1800, 2400].iter().all(|b| clicks.iter().any(|c| c.abs_diff(*b) <= 2)), "{clicks:?}");
}

#[test]
fn a_count_in_clicks_a_bar_then_the_mix_rolls_on_the_frame() {
    let (mut t, c, _n, o) = rig(120.0); // a beat is 500 frames, a bar 2000
    c.send(Cmd::CountIn(1)).unwrap();
    c.send(Cmd::Play(Some(0.5))).unwrap();
    let mut frame = 0;
    let out = run(&mut t, &mut frame, 400); // 2800 frames
    let clicks: Vec<usize> = (0..2000).filter(|&k| out[k] != 0.0 && (k == 0 || out[k - 1] == 0.0)).collect();
    assert_eq!(clicks.len(), 4, "{clicks:?}");
    assert!(clicks.iter().zip([0, 500, 1000, 1500]).all(|(&a, b)| a.abs_diff(b) <= 1), "{clicks:?}");
    for k in 2000..2800 {
        assert_eq!(out[k], (500 + k - 2000) as f32 / 1e6, "frame {k}");
    }
    assert!(o.try_iter().any(|m| m == Out::Rolling(0.5)));
}

#[test]
fn overdubbed_notes_land_at_the_mix_time_heard_with_them_inside_the_punch() {
    let (mut t, c, n, o) = rig(120.0);
    c.send(Cmd::Record(Some(Some((1.2, 1.4))))).unwrap();
    c.send(Cmd::Loop(Some((1.0, 1.5)))).unwrap();
    c.send(Cmd::Play(Some(1.0))).unwrap();
    let mut frame = 0;
    let on = |k: u8| Event::On { key: k, velocity: 0.7, at: 0.0 };
    run(&mut t, &mut frame, 10); // mix 1.000 … 1.070
    n.send(on(60)).unwrap(); // before the punch: not kept
    run(&mut t, &mut frame, 30); // … 1.280
    n.send(on(62)).unwrap(); // at 1.280
    run(&mut t, &mut frame, 5); // … 1.315
    n.send(Event::Off { key: 62 }).unwrap(); // at 1.315
    n.send(Event::Off { key: 60 }).unwrap();
    n.send(on(64)).unwrap(); // at 1.315, held past the punch-out and the loop's end
    run(&mut t, &mut frame, 40);
    let notes: Vec<(u8, f64, f64)> = o.try_iter().filter_map(|m| if let Out::Note { key, start, end, .. } = m { Some((key, start, end)) } else { None }).collect();
    assert_eq!(notes, vec![(62, 1.28, 1.315), (64, 1.315, 1.4)]);
}

#[test]
fn the_clock_maps_speaker_time_to_mix_time() {
    let mut c = Clock::default();
    c.push(10.0, Some(1.0));
    c.push(10.003, Some(1.003));
    c.push(10.006, None);
    assert_eq!(c.mix_at(9.0), None);
    assert!((c.mix_at(10.0015).unwrap() - 1.0015).abs() < 1e-12);
    assert!((c.mix_at(10.004).unwrap() - 1.004).abs() < 1e-12);
    assert_eq!(c.mix_at(10.01), None);
}

#[test]
fn resampling_keeps_a_tone_at_its_pitch() {
    let src: Vec<[f32; 2]> = (0..44100).map(|k| { let v = (2.0 * std::f64::consts::PI * 441.0 * k as f64 / 44100.0).sin() as f32; [v, v] }).collect();
    let out = resample(&src, 44100.0, 48000.0);
    assert_eq!(out.len(), 48000);
    let ups = out.windows(2).filter(|w| w[0][0] < 0.0 && w[1][0] >= 0.0).count();
    assert!((440..=442).contains(&ups), "{ups}");
}
