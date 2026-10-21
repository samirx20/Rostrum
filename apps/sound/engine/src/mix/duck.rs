//! Sidechain ducking: music dips under the dialogue / sfx level, or pumps under a kick. A port of
//! masteringDsp.ts (applySidechainDucking); buffers hold f32 like the TS ones did.

use std::f64::consts::PI;

use crate::sfx::js_round;

/// The follower's exponential tail never reaches 0; below this share of the full level it counts as 0 (the curve stays
/// continuous), so a track that is not dipping is the source exactly, not 0.05 dB under it.
const TAIL: f64 = 0.01;

/// A dip of ducked music: [start s, end s, deepest gain dB].
pub type DuckSpan = (f64, f64, f64);

fn fixed2(x: f64) -> f64 {
    js_round(x * 100.0) / 100.0
}

/// Ducks music under the trigger (voice / sfx level, 18 ms lookahead): mids and highs by `depth`
/// from a third of the trigger's speaking level, the sub below 90 Hz by about half, nothing added in
/// the gaps. Returns where it dipped below âˆ’3 dB.
#[cfg(test)]
pub fn duck(left: &mut [f32], right: &mut [f32], trigger: &[f32], sr: f64, d: &crate::mix::schedule::Duck) -> Vec<DuckSpan> {
    duck_n(&mut [left, right], trigger, sr, d)
}

/// The same over every channel of a bed, one gain curve (each channel keeps its own low band).
pub fn duck_n(chs: &mut [&mut [f32]], trigger: &[f32], sr: f64, d: &crate::mix::schedule::Duck) -> Vec<DuckSpan> {
    let len = chs.iter().map(|c| c.len()).min().unwrap_or(0).min(trigger.len());
    if len == 0 {
        return vec![];
    }
    let depth = d.depth;
    let lookahead = (d.lookahead * sr).floor() as usize;
    let attack = (-1.0 / (d.attack.max(1e-4) * sr)).exp();
    let release = (-1.0 / (d.release.max(1e-3) * sr)).exp();
    let dt = 1.0 / sr;
    let sub_alpha = dt / (1.0 / (2.0 * PI * 90.0) + dt);
    let mut envs = vec![0.0f32; len];
    let mut env = 0.0f64;
    // Hold: the follower keeps the loudest level of the last `hold` seconds (a running peak), then releases.
    let hold_n = (d.hold.max(0.0) * sr) as usize;
    let (mut held, mut held_for) = (0.0f64, 0usize);
    for i in 0..len {
        let mut trig = trigger[(len - 1).min(i + lookahead)] as f64;
        if hold_n > 0 {
            if trig >= held {
                held = trig;
                held_for = 0;
            } else if held_for < hold_n {
                held_for += 1;
            } else {
                held = trig;
            }
            trig = trig.max(held);
        }
        let c = if trig > env { attack } else { release };
        env = c * env + (1.0 - c) * trig;
        envs[i] = env as f32;
    }
    let mut sounding: Vec<f32> = (0..len).step_by(64).map(|i| envs[i]).filter(|&e| e as f64 > 0.001).collect();
    sounding.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let speaking = if sounding.is_empty() { 0.0 } else { sounding[(sounding.len() as f64 * 0.9).floor() as usize] as f64 };
    let any = speaking > 0.0;
    let full_at = speaking / 3.0;
    let dip_gain = 10f64.powf(-3.0 / 20.0);
    // A pump (not under a voice) is shaped per hit, as a sidechain pump is: down over the attack,
    // back to full over the release (smoothstep), whatever the trigger's own tail does, so a long
    // 808 kick does not hold the track down. A hit is the trigger rising through the full level.
    let pump: Option<Vec<f32>> = (!d.voice && any).then(|| {
        let (a_n, r_n) = ((d.attack.max(1e-4) * sr) as usize, (d.release.max(1e-3) * sr) as usize);
        let mut shape = vec![0.0f32; len];
        let (mut armed, mut last) = (true, usize::MAX);
        for i in 0..len {
            let e = envs[i] as f64;
            if armed && e >= full_at && (last == usize::MAX || i - last > (0.04 * sr) as usize) {
                armed = false;
                last = i;
                for k in 0..(a_n + r_n).min(len - i) {
                    let v = if k < a_n { k as f64 / a_n as f64 } else { let x = (k - a_n) as f64 / r_n as f64; 1.0 - x * x * (3.0 - 2.0 * x) };
                    shape[i + k] = shape[i + k].max(v as f32);
                }
            } else if e < full_at * 0.5 {
                armed = true;
            }
        }
        shape
    });
    let mut subs = vec![0.0f64; chs.len()];
    let mut spans = vec![];
    let (mut from, mut deepest): (i64, f64) = (-1, 1.0);
    for i in 0..len {
        let ratio = match &pump { Some(p) => p[i] as f64, None if any => ((envs[i] as f64 / full_at).min(1.0) - TAIL).max(0.0) / (1.0 - TAIL), None => 0.0 };
        // Under a voice the music keeps its bass; a pump moves it all. Outside a dip the gain is exactly 1 (there was
        // a +12 % "bloom" in the gaps: up to +0.98 dB over the track's own stem, measured 2026-10-17, removed).
        let mid = (1.0 - depth).max(1.0 - ratio * depth);
        let sub = if d.voice { (1.0 - depth * 0.55).max(1.0 - ratio * depth * 0.55) } else { mid };
        let dipping = mid < dip_gain;
        if dipping && from < 0 {
            from = i as i64;
            deepest = 1.0;
        }
        if dipping {
            deepest = deepest.min(mid);
        }
        if from >= 0 && (!dipping || i == len - 1) {
            spans.push((fixed2(from as f64 / sr), fixed2(i as f64 / sr), js_round(20.0 * deepest.log10())));
            from = -1;
        }
        for (c, s) in chs.iter_mut().zip(subs.iter_mut()) {
            let x = c[i] as f64;
            *s += sub_alpha * (x - *s);
            c[i] = (*s * sub + (x - *s) * mid) as f32;
        }
    }
    spans
}

#[cfg(test)]
mod tests {
    use std::f64::consts::SQRT_2;

    use super::*;
    use crate::mix::schedule::Duck;

    fn voice_duck() -> Duck {
        Duck { from: vec![], depth: 0.78, attack: 0.012, release: 0.26, lookahead: 0.018, hold: 0.0, voice: true, report: true }
    }

    #[test]
    fn a_track_that_is_not_dipping_equals_its_own_stem() {
        // A tone ducked by a 1 s voice burst: before it, after its release, and under a trigger that never sounds,
        // the music is the source to the last digit once the release has run out (1.5 s; the old "bloom" left it +0.98 dB in the gaps).
        let sr = 22050.0;
        let n = 22050 * 4;
        let src: Vec<f32> = (0..n).map(|i| ((i as f64 * 0.06).sin() * 0.3) as f32).collect();
        let voice: Vec<f32> = (0..n).map(|i| if (22050..44100).contains(&i) { (0.5 * (i as f64 * 0.09).sin()).abs() as f32 } else { 0.0 }).collect();
        let level_db = |a: &[f32], b: &[f32], from: usize, to: usize| {
            let rms = |x: &[f32]| (x[from..to].iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / (to - from) as f64).sqrt();
            20.0 * (rms(a) / rms(b)).log10()
        };
        let (mut l, mut r) = (src.clone(), src.clone());
        duck(&mut l, &mut r, &voice, sr, &voice_duck());
        let (before, after) = (level_db(&l, &src, 2000, 20000), level_db(&l, &src, 82000, 88000));
        assert!(before.abs() < 0.01 && after.abs() < 0.01, "outside the dip the track is {before:.3} / {after:.3} dB from its source");
        let (mut l, mut r) = (src.clone(), src.clone());
        duck(&mut l, &mut r, &vec![0.0; n], sr, &voice_duck());
        assert!(level_db(&l, &src, 0, n).abs() < 0.01, "a silent trigger changes nothing");
    }

    #[test]
    fn a_kick_pumps_a_held_pad_on_every_hit() {
        // A steady tone; a kick every 0.5 s: the tone dips about 8 dB on each hit and is back before the next.
        let sr = 22050.0;
        let n = (sr * 2.0) as usize;
        let mut l: Vec<f32> = (0..n).map(|i| (i as f32 * 0.05).sin() * 0.5).collect();
        let mut r = l.clone();
        let kick: Vec<f32> = (0..n).map(|i| { let t = (i as f64 / sr) % 0.5; if t < 0.08 { (0.9 * (-t * 40.0).exp()) as f32 } else { 0.0 } }).collect();
        let pump = Duck { from: vec![], depth: 1.0 - 10f64.powf(-8.0 / 20.0), attack: 0.003, release: 0.15, lookahead: 0.0, hold: 0.0, voice: false, report: true };
        let spans = duck(&mut l, &mut r, &kick, sr, &pump);
        let rms = |a: f64, b: f64| { let s = &l[(a * sr) as usize..(b * sr) as usize]; (s.iter().map(|x| (*x as f64).powi(2)).sum::<f64>() / s.len() as f64).sqrt() };
        let (hit, between) = (rms(1.01, 1.04), rms(1.40, 1.48));
        let db = 20.0 * (hit / between).log10();
        assert!(db < -6.0 && db > -9.0, "the pad dips {db:.1} dB on a hit");
        assert_eq!(spans.len(), 4, "one dip per kick: {spans:?}");
    }

    #[test]
    fn a_held_duck_stays_down_through_a_short_pause_between_phrases() {
        // Two 1 s phrases with a 0.6 s pause: without a hold the music swells back in it; held 0.7 s, one dip.
        let sr = 8000.0;
        let n = 8000 * 4;
        let voice: Vec<f32> = (0..n).map(|i| { let t = i as f64 / sr; if (0.5..1.5).contains(&t) || (2.1..3.1).contains(&t) { (0.5 * (2.0 * PI * 200.0 * t).sin()).abs() as f32 } else { 0.0 } }).collect();
        let dips = |hold: f64| {
            let mut l: Vec<f32> = (0..n).map(|i| (0.3 * (2.0 * PI * 440.0 * i as f64 / sr).sin()) as f32).collect();
            let mut r = l.clone();
            duck(&mut l, &mut r, &voice, sr, &Duck { hold, ..voice_duck() })
        };
        assert_eq!(dips(0.0).len(), 2, "without a hold the music swells in the pause");
        let held = dips(0.7);
        assert_eq!(held.len(), 1, "{held:?}");
        assert!(held[0].1 > 3.1, "{held:?}");
    }

    #[test]
    fn a_click_dips_the_music_once_and_says_where() {
        let sr = 22050.0;
        let n = 22050 * 4;
        let mut l: Vec<f32> = (0..n).map(|i| ((i as f64 / 7.0).sin() * 0.3) as f32).collect();
        let mut r = l.clone();
        let mut trigger = vec![0.0f32; n];
        for i in 0..2205 {
            trigger[2 * 22050 + i] = 0.8; // a 100 ms click at 2 s
        }
        let spans = duck(&mut l, &mut r, &trigger, sr, &voice_duck());
        assert_eq!(spans.len(), 1, "{spans:?}");
        let (a, b, db) = spans[0];
        assert!(a > 1.9 && a < 2.05 && b > 2.1 && db <= -12.0, "{spans:?}");
    }

    #[test]
    fn ducks_as_deep_under_a_quiet_voice_as_a_loud_one() {
        let sr = 8000.0;
        let depth_under = |amp: f64| {
            let n = 8000 * 4;
            let mut l: Vec<f32> = (0..n).map(|i| (0.3 * (2.0 * PI * 440.0 * i as f64 / sr).sin()) as f32).collect();
            let mut r = l.clone();
            let voice: Vec<f32> = (0..n).map(|i| if (8000..24000).contains(&i) { (amp * (2.0 * PI * 200.0 * i as f64 / sr).sin()).abs() as f32 } else { 0.0 }).collect();
            duck(&mut l, &mut r, &voice, sr, &voice_duck());
            let seg = &l[12000..20000];
            let rms = (seg.iter().map(|x| (*x as f64).powi(2)).sum::<f64>() / seg.len() as f64).sqrt();
            20.0 * (rms / (0.3 / SQRT_2)).log10()
        };
        let (quiet, loud) = (depth_under(0.04), depth_under(0.5));
        assert!(quiet < -10.0, "{quiet}");
        assert!((quiet - loud).abs() < 0.5, "{quiet} vs {loud}");
    }
}
