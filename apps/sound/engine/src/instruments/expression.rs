//! Per-note expression (src/core/soundDsl/writing/noteExpression.ts checks it, scoreVoices.ts resolves it):
//! a glide to another pitch inside the note, vibrato, and the note's own dynamic shape. Every voice
//! kind reads the same curves (named instruments, synths, the sampler), so a slide sounds the same
//! on each. And a sampler's humanizing: the filter that opens with velocity, a softer attack when
//! played softly, and each note's own seeded micro-variation (TypeScript picks the values).

use serde::Deserialize;

#[derive(Deserialize, Clone, Debug, Default)]
#[serde(rename_all = "camelCase")]
pub struct Expression {
    #[serde(default)]
    pub glide: Option<Glide>,
    #[serde(default)]
    pub vibrato: Option<Vibrato>,
    /// (fraction of the note 0…1, level): straight lines between, held before and after.
    #[serde(default)]
    pub shape: Option<Vec<[f64; 2]>>,
    /// The pitch wheel (R24: a track's bend lane, scaled by its bend range in TypeScript): (seconds into the note,
    /// cents), straight lines between, held before and after.
    #[serde(default)]
    pub bend: Option<Vec<[f64; 2]>>,
    /// The volume / expression controllers (CC 7 × CC 11 lanes): (seconds into the note, gain), multiplied into the level.
    #[serde(default)]
    pub level: Option<Vec<[f64; 2]>>,
    /// The mod wheel (CC 1 lane): vibrato whose depth follows the wheel.
    #[serde(default)]
    pub modulation: Option<Modulation>,
}

/// ±`depth` cents at `rate` Hz at the wheel's top; `points` (seconds into the note, 0…1) is the wheel.
#[derive(Deserialize, Clone, Debug)]
pub struct Modulation {
    pub rate: f64,
    pub depth: f64,
    pub points: Vec<[f64; 2]>,
}

/// A lane's value at `t`: straight lines between its points, held before the first and after the last.
pub fn lane_at(pts: &[[f64; 2]], t: f64) -> f64 {
    let Some(first) = pts.first() else { return 0.0 };
    if t <= first[0] {
        return first[1];
    }
    for w in pts.windows(2) {
        let ([x0, v0], [x1, v1]) = (w[0], w[1]);
        if t <= x1 {
            return if x1 > x0 { v0 + (v1 - v0) * (t - x0) / (x1 - x0) } else { v1 };
        }
    }
    pts[pts.len() - 1][1]
}

/// The pitch moves `cents` away, starting `at` seconds into the note, over `duration` seconds.
#[derive(Deserialize, Clone, Debug)]
pub struct Glide {
    pub cents: f64,
    pub at: f64,
    pub duration: f64,
}

/// ±`depth` cents at `rate` Hz, starting `delay` seconds into the note and fading in over a quarter second.
#[derive(Deserialize, Clone, Debug)]
pub struct Vibrato {
    pub rate: f64,
    pub depth: f64,
    pub delay: f64,
}

/// A sampled note's own micro-variation: detune (cents), how far into the sample it starts
/// (seconds), and a small peak in the body (`formant_hz`, `formant_db`).
#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Variation {
    pub cents: f64,
    pub offset: f64,
    pub formant_hz: f64,
    pub formant_db: f64,
}

const VIBRATO_FADE: f64 = 0.25;

impl Expression {
    /// The pitch offset in cents at `t` seconds into the note.
    pub fn cents(&self, t: f64) -> f64 {
        let mut c = 0.0;
        if let Some(g) = &self.glide {
            let u = if g.duration > 0.0 { ((t - g.at) / g.duration).clamp(0.0, 1.0) } else if t >= g.at { 1.0 } else { 0.0 };
            c += g.cents * u * u * (3.0 - 2.0 * u); // eased: a finger's slide, not a ramp
        }
        if let Some(v) = &self.vibrato {
            if t > v.delay {
                let s = t - v.delay;
                c += v.depth * (s / VIBRATO_FADE).min(1.0) * (2.0 * std::f64::consts::PI * v.rate * s).sin();
            }
        }
        if let Some(b) = self.bend.as_deref() {
            c += lane_at(b, t);
        }
        if let Some(m) = &self.modulation {
            c += m.depth * lane_at(&m.points, t).clamp(0.0, 1.0) * (2.0 * std::f64::consts::PI * m.rate * t).sin();
        }
        c
    }

    /// The pitch ratio at `t`.
    pub fn ratio(&self, t: f64) -> f64 {
        2f64.powf(self.cents(t) / 1200.0)
    }

    /// The note's level at `t` for a note `dur` seconds long (1 without a shape; the release holds the last point).
    pub fn gain(&self, t: f64, dur: f64) -> f64 {
        let level = self.level.as_deref().filter(|p| !p.is_empty()).map_or(1.0, |p| lane_at(p, t).max(0.0));
        level * self.shape_gain(t, dur)
    }

    fn shape_gain(&self, t: f64, dur: f64) -> f64 {
        let Some(pts) = self.shape.as_deref().filter(|p| !p.is_empty()) else { return 1.0 };
        let x = t / dur.max(1e-6);
        if x <= pts[0][0] {
            return pts[0][1];
        }
        for w in pts.windows(2) {
            let ([x0, v0], [x1, v1]) = (w[0], w[1]);
            if x <= x1 {
                return if x1 > x0 { v0 + (v1 - v0) * (x - x0) / (x1 - x0) } else { v1 };
            }
        }
        pts[pts.len() - 1][1]
    }

    /// The most the pitch moves away from the note, in cents.
    pub fn reach(&self) -> f64 {
        self.glide.as_ref().map_or(0.0, |g| g.cents.abs())
            + self.vibrato.as_ref().map_or(0.0, |v| v.depth.abs())
            + self.bend.as_deref().map_or(0.0, |b| b.iter().fold(0.0, |m, p| f64::max(m, p[1].abs())))
            + self.modulation.as_ref().map_or(0.0, |m| m.depth.abs())
    }
}

/// The low-pass a sampled note plays through: it opens with velocity (≈ 3 kHz at 0.2, 6 kHz at 0.5,
/// 18 kHz at 1: 300 Hz × 60^(0.45 + 0.55·v)), never below the note's fourth harmonic.
pub fn velocity_cutoff(velocity: f64, top_freq: f64, sr: f64) -> f64 {
    (300.0 * 60f64.powf(0.45 + 0.55 * velocity.clamp(0.0, 1.0))).max(4.0 * top_freq).min(sr * 0.45)
}

/// A soft note's attack is rounded over up to 6 ms (none at full velocity).
pub fn soft_attack(velocity: f64) -> f64 {
    0.006 * (1.0 - velocity.clamp(0.0, 1.0))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_glide_eases_to_its_target_and_holds_it() {
        let e = Expression { glide: Some(Glide { cents: 200.0, at: 0.1, duration: 0.1 }), ..Default::default() };
        assert_eq!(e.cents(0.05), 0.0);
        assert!((e.cents(0.15) - 100.0).abs() < 1e-9, "halfway: {}", e.cents(0.15));
        assert_eq!(e.cents(0.5), 200.0);
        assert!((e.ratio(0.5) - 2f64.powf(2.0 / 12.0)).abs() < 1e-12);
    }

    #[test]
    fn vibrato_waits_for_its_delay_then_fades_in_to_its_depth() {
        let e = Expression { vibrato: Some(Vibrato { rate: 5.0, depth: 20.0, delay: 0.3 }), ..Default::default() };
        assert_eq!(e.cents(0.2), 0.0);
        let peak = (0..2000).map(|i| e.cents(1.0 + i as f64 / 2000.0).abs()).fold(0.0, f64::max);
        assert!((peak - 20.0).abs() < 0.05, "{peak}");
    }

    #[test]
    fn a_shape_follows_its_points_over_the_note_and_holds_the_last() {
        let e = Expression { shape: Some(vec![[0.0, 0.2], [0.5, 1.0], [1.0, 0.4]]), ..Default::default() };
        assert!((e.gain(0.0, 2.0) - 0.2).abs() < 1e-9);
        assert!((e.gain(1.0, 2.0) - 1.0).abs() < 1e-9);
        assert!((e.gain(1.5, 2.0) - 0.7).abs() < 1e-9);
        assert!((e.gain(3.0, 2.0) - 0.4).abs() < 1e-9, "the release holds the last level");
        assert_eq!(Expression::default().gain(0.3, 1.0), 1.0);
    }

    #[test]
    fn a_bend_lane_moves_the_pitch_and_holds_its_ends() {
        let e = Expression { bend: Some(vec![[0.1, 0.0], [0.3, 200.0]]), ..Default::default() };
        assert_eq!(e.cents(0.0), 0.0);
        assert!((e.cents(0.2) - 100.0).abs() < 1e-9);
        assert_eq!(e.cents(1.0), 200.0);
        assert_eq!(e.reach(), 200.0);
    }

    #[test]
    fn a_level_lane_scales_the_shape() {
        let e = Expression { level: Some(vec![[0.0, 1.0], [1.0, 0.5]]), shape: Some(vec![[0.0, 0.5], [1.0, 0.5]]), ..Default::default() };
        assert!((e.gain(0.0, 2.0) - 0.5).abs() < 1e-9);
        assert!((e.gain(1.0, 2.0) - 0.25).abs() < 1e-9);
    }

    #[test]
    fn the_mod_wheel_scales_vibrato_from_none_to_its_depth() {
        let e = Expression { modulation: Some(Modulation { rate: 5.0, depth: 40.0, points: vec![[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]] }), ..Default::default() };
        assert!((0..100).all(|i| e.cents(i as f64 / 100.0).abs() < 1e-9), "the wheel at 0: no vibrato");
        let peak = (0..2000).map(|i| e.cents(2.0 + i as f64 / 2000.0).abs()).fold(0.0, f64::max);
        assert!((peak - 40.0).abs() < 0.1, "{peak}");
    }

    #[test]
    fn the_filter_opens_with_velocity() {
        let (soft, mid, hard) = (velocity_cutoff(0.2, 220.0, 44100.0), velocity_cutoff(0.5, 220.0, 44100.0), velocity_cutoff(1.0, 220.0, 44100.0));
        assert!(soft < mid && mid < hard, "{soft} {mid} {hard}");
        assert!((2500.0..3500.0).contains(&soft) && hard > 17000.0);
        assert!(velocity_cutoff(0.0, 2000.0, 44100.0) >= 8000.0, "never below the fourth harmonic");
        assert!(soft_attack(0.2) > soft_attack(0.9) && soft_attack(1.0) == 0.0);
    }
}
