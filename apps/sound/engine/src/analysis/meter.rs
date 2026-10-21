//! Which metrical level is the beat (tempo.rs step 3). Periodicity alone cannot tell a tempo from its
//! half, double, 2/3 or 3/2: a groove repeats at all of them. The beat is where the kicks, snares and
//! chords fall, so each rule reads the lows and the body of the sound on a grid's beats:
//! - octave up or down by periodicity, when a related tempo in 70 … 180 repeats clearly more;
//! - too slow: the half-beats as strong as the beats (a backbeat: the snare is a beat), or under 70
//!   BPM with something on most beats of the doubled grid (trap hats at 140 felt in half time);
//! - too fast: every other beat much weaker in both the lows and the body (an off-beat holds only a hat);
//! - 3:2 (a 120 BPM four-on-the-floor read as 80: an arpeggio's three-note cycle repeats too): the
//!   level whose beats land on more of the strong onsets, a grid of the other tempo falling between them.
//! Each rule reports a close call: the reading it nearly chose (`unsure`).

use crate::analysis::tempo::Onsets;

pub struct Choice {
    pub period: f64,
    /// The other reading, when the evidence for this one was close.
    pub unsure: Option<f64>,
}

/// The half-beats' weight over the beats', the grid phased on its strongest beats (by `w`).
fn half_ratio(on: &Onsets, period: f64, w: &dyn Fn(f64) -> f64) -> f64 {
    let p = on.phase(period);
    on.grid(p + period / 2.0, period).map(w).sum::<f64>() / on.grid(p, period).map(w).sum::<f64>().max(1e-12)
}

/// The half-beats' kicks, snares and chords (lows + body) over the beats'.
fn mid_ratio(on: &Onsets, period: f64) -> f64 {
    half_ratio(on, period, &|t| on.weight(t))
}

/// The half-beats' snares and chords alone (200 Hz … 4 kHz, the best of a frame either side): a
/// backbeat's snare there says the beat is twice as fast; a syncopated kick does not.
fn backbeat(on: &Onsets, period: f64) -> f64 {
    half_ratio(on, period, &|t| on.snare(t - 1.0).max(on.snare(t)).max(on.snare(t + 1.0)))
}

/// The share of a grid's beats that hold an onset (over a fifth of the loud onsets' strength, within a frame).
fn filled(on: &Onsets, period: f64) -> f64 {
    let loud = {
        let mut s: Vec<f64> = on.o.iter().cloned().filter(|v| *v > 0.0).collect();
        s.sort_by(|a, b| a.total_cmp(b));
        s.get(s.len() * 95 / 100).copied().unwrap_or(1e-12).max(1e-12)
    };
    let p = on.phase(period);
    let pts: Vec<f64> = on.grid(p, period).map(|t| { let i = t.round() as usize; (i.saturating_sub(1)..=i + 1).map(|j| on.o.get(j).copied().unwrap_or(0.0)).fold(0.0, f64::max) }).collect();
    pts.iter().filter(|v| **v > 0.2 * loud).count() as f64 / pts.len().max(1) as f64
}

/// Whether the hats (over 5 kHz) tick on nearly every half-beat of `period`: hats in eighths say the
/// beat is `period` (a groove at 150 with eighth hats, read at 75, has hats on every quarter of it).
fn hats_halve(on: &Onsets, period: f64) -> bool {
    let mut s: Vec<f64> = on.hi.iter().cloned().filter(|v| *v > 0.0).collect();
    s.sort_by(|a, b| a.total_cmp(b));
    let loud = s.get(s.len() * 9 / 10).copied().unwrap_or(0.0);
    if loud <= 1e-9 {
        return false;
    }
    let hit = |t: f64| { let i = t.round() as usize; (i.saturating_sub(1)..=i + 1).any(|j| on.hi.get(j).is_some_and(|v| *v > 0.25 * loud)) };
    let half = period / 2.0;
    (0..half.round().max(1.0) as usize).any(|p| { let (n, k) = on.grid(p as f64, half).fold((0, 0), |(n, k), t| (n + 1, k + hit(t) as usize)); n > 8 && k as f64 >= 0.8 * n as f64 })
}

/// The beats' mean weight (lows + body, the best of a frame either side), the grid on its best phase:
/// how much of the strong onsets a beat of this tempo lands on.
fn salience(on: &Onsets, period: f64) -> f64 {
    let w = |t: f64| on.weight(t - 1.0).max(on.weight(t)).max(on.weight(t + 1.0));
    let mean = |p: f64| { let (s, n) = on.grid(p, period).fold((0.0, 0), |(s, n), t| (s + w(t), n + 1)); s / n.max(1) as f64 };
    (0..period.round().max(1.0) as usize).map(|p| mean(p as f64)).fold(0.0, f64::max)
}

/// Even beats against odd beats of a grid, lows + body.
fn parity(on: &Onsets, period: f64) -> (f64, f64) {
    let p = on.phase(period);
    on.grid(p, period).enumerate().fold((0.0, 0.0), |(e, o), (k, t)| if k % 2 == 0 { (e + on.weight(t), o) } else { (e, o + on.weight(t)) })
}

pub fn choose(on: &Onsets, mut period: f64) -> Choice {
    let bpm = |p: f64| on.bpm(p);
    // An octave by periodicity: never a slower one whose half-beats hold kicks or snares too.
    for k in [0.5, 2.0] {
        let t = bpm(period) * k;
        if (70.0..=180.0).contains(&t) && on.support(on.lag(t)) > 1.08 * on.support(period) && (k > 1.0 || mid_ratio(on, on.lag(t)) < 0.6) {
            period = on.lag(t);
        }
    }
    // Too slow by an octave: a backbeat on the half-beats (kicks, snares, chords), or hats in eighths of the doubled beat.
    // A slow piece whose half-beats are mostly empty stays slow (a 66 BPM ballad).
    let slow = bpm(period) < 70.0;
    if bpm(period) * 2.0 <= 181.0 && (mid_ratio(on, period) >= 0.6 || hats_halve(on, period / 2.0) || (slow && filled(on, period / 2.0) >= 0.65) || bpm(period) < 50.0) {
        period /= 2.0;
    }
    // Too fast by an octave.
    let (even, odd) = parity(on, period);
    if bpm(period) / 2.0 >= 70.0 && even.min(odd) < 0.45 * even.max(odd) {
        period *= 2.0;
    }
    // 3:2: the level whose beats land on clearly more of the strong onsets.
    let here = salience(on, period);
    if let Some(t) = [1.5, 2.0 / 3.0].iter().map(|k| bpm(period) * k).filter(|t| (60.0..=200.0).contains(t)).find(|t| salience(on, on.lag(*t)) > 1.15 * here) {
        period = on.lag(t);
    }
    Choice { period, unsure: close_call(on, period) }
}

/// The reading that nearly won, when one did: a 3:2 level landing on nearly as much; a fast beat
/// (over 160, or over 120 with no snare between its half-time beats: a half-time groove, or an even
/// stream of notes) whose half repeats nearly as clearly; a slow one with something on its half-beats;
/// every other beat much weaker (under 0.4 of the others, short of the 0.45 that halves it in choose:
/// a trap groove's snare once a bar).
fn close_call(on: &Onsets, period: f64) -> Option<f64> {
    let (bpm, here) = (on.bpm(period), salience(on, period));
    let rival = [1.5, 2.0 / 3.0].iter().map(|k| bpm * k).filter(|t| (60.0..=200.0).contains(t)).find(|t| salience(on, on.lag(*t)) > 0.92 * here);
    let half = on.support(2.0 * period) / on.support(period).max(1e-12);
    let (even, odd) = parity(on, period);
    let uneven = even.min(odd) / even.max(odd).max(1e-12);
    if rival.is_some() {
        rival
    } else if bpm / 2.0 >= 50.0 && ((bpm > 160.0 && half >= 0.6) || (bpm > 120.0 && half >= 0.75 && backbeat(on, 2.0 * period) < 0.5) || uneven < 0.4) {
        Some(bpm / 2.0)
    } else if bpm < 80.0 && bpm * 2.0 <= 181.0 && mid_ratio(on, period) >= 0.4 {
        Some(bpm * 2.0)
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use std::f64::consts::PI;

    fn tempo_of(x: &[f32]) -> serde_json::Value {
        crate::analysis::analyze::analyze(x, 22050.0, false)["tempo"].clone()
    }

    /// Benchmark b12 (a 120 BPM menu loop read as 80, its 2/3): a kick on every beat, a hat between,
    /// a snare on beat 3, an arpeggio in 16ths and a bass in 8ths.
    #[test]
    fn a_four_on_the_floor_menu_loop_is_not_read_at_two_thirds() {
        let sr = 22050.0;
        let mut seed = 7u32;
        let x: Vec<f32> = (0..(sr * 16.0) as usize)
            .map(|i| {
                let t = i as f64 / sr;
                let (b, h, s, e, bar) = (t % 0.5, (t + 0.25) % 0.5, t % 0.125, t % 0.25, t % 2.0);
                let kick = (2.0 * PI * 55.0 * b).sin() * (-b * 30.0).exp() * 0.8;
                seed = seed.wrapping_mul(1664525).wrapping_add(1013904223);
                let noise = (seed >> 9) as f64 / (1u32 << 23) as f64 - 1.0;
                let hat = noise * (-h * 150.0).exp() * 0.08;
                let snare = if (1.0..1.5).contains(&bar) { noise * (-(bar - 1.0) * 25.0).exp() * 0.3 } else { 0.0 };
                let note = [220.0, 261.63, 329.63, 261.63][(t / 0.125) as usize % 4];
                let arp = (2.0 * PI * note * t).sin() * (-s * 20.0).exp() * 0.2;
                let bass = (2.0 * PI * 55.0 * t).sin() * (-e * 6.0).exp() * 0.25;
                (kick + hat + snare + arp + bass) as f32
            })
            .collect();
        let got = tempo_of(&x);
        assert!((got["bpm"].as_f64().unwrap() - 120.0).abs() < 1.0, "{got}");
    }

    /// Benchmark b5 (a 90 BPM ostinato of even eighths read as 187.8): a stream of equal notes every
    /// third of a second reads at 180 or 90 — exactly, and said as unsure, the other reading named.
    #[test]
    fn an_even_stream_of_notes_is_read_exactly_and_said_unsure() {
        let sr = 22050.0;
        let x: Vec<f32> = (0..(sr * 24.0) as usize)
            .map(|i| {
                let t = i as f64 / sr;
                let s = t % (1.0 / 3.0);
                let note = [130.81, 196.0, 155.56, 196.0][(t * 3.0) as usize % 4];
                ((2.0 * PI * note * t).sin() * (-s * 6.0).exp() * 0.5) as f32
            })
            .collect();
        let got = tempo_of(&x);
        let (bpm, other) = (got["bpm"].as_f64().unwrap(), got["unsure"].as_f64().unwrap_or(0.0));
        assert!([(bpm, other), (other, bpm)].iter().any(|(a, b)| (a - 180.0).abs() < 1.0 && (b - 90.0).abs() < 1.0), "{got}");
    }
}
