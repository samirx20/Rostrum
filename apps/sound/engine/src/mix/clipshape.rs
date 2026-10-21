//! A clip's fades with a shape (`fadeInCurve` / `fadeOutCurve`), its own volume and pan lanes (clip
//! seconds: they move with the clip) and its polarity (`invert`). A clip with none of them takes the old
//! path (dsp::fade_gain, the equal-power quarter sine), sample for sample.

use std::f64::consts::{PI, SQRT_2};

use crate::fx::dsp;
use crate::mix::schedule::{Clip, Param};

/// A fade's gain at `x` (0 → 1 over the fade) for a named shape.
pub fn curve(name: &str, x: f64) -> f64 {
    let x = x.clamp(0.0, 1.0);
    match name {
        "linear" => x,
        // dB-linear over 60 dB: slow, then fast.
        "exponential" => (1000f64.powf(x) - 1.0) / 999.0,
        // Its mirror: fast, then slow.
        "logarithmic" => 1.0 - (1000f64.powf(1.0 - x) - 1.0) / 999.0,
        "sCurve" => 0.5 - 0.5 * (PI * x).cos(),
        // Below a straight line: x^1.5 (0.354 at the middle). Two identical signals crossing over with
        // it sum to -3.01 dB at the midpoint (the Editor's transition "-3" curve, `attenuated`).
        "attenuated" => x.powf(1.5),
        // "equalPower", the default: a quarter sine.
        _ => (x * PI / 2.0).sin(),
    }
}

/// The fade envelope of a clip `len` samples long, with its shapes.
pub struct Shape {
    len: usize,
    fade_in: usize,
    fade_out: usize,
    shape_in: String,
    shape_out: String,
}

impl Shape {
    /// None when the clip's fades have no shape (the old envelope applies).
    pub fn of(c: &Clip, len: usize, sr: f64) -> Option<Shape> {
        if c.fade_in_curve.is_none() && c.fade_out_curve.is_none() {
            return None;
        }
        let n = |s: f64| (s * sr).floor().max(0.0) as usize;
        let named = |s: &Option<String>| s.clone().unwrap_or_else(|| "equalPower".into());
        Some(Shape { len, fade_in: n(c.fade_in), fade_out: n(c.fade_out), shape_in: named(&c.fade_in_curve), shape_out: named(&c.fade_out_curve) })
    }

    pub fn env(&self, i: usize) -> f64 {
        let mut env = 1.0;
        if self.fade_in > 0 && i < self.fade_in {
            env *= curve(&self.shape_in, i as f64 / self.fade_in as f64);
        }
        if self.fade_out > 0 && i + self.fade_out >= self.len {
            env *= curve(&self.shape_out, ((self.len as f64 - 1.0 - i as f64) / self.fade_out as f64).max(0.0));
        }
        env
    }
}

/// A clip's fades, gain and pan (a stereo clip), its lanes when it has them.
pub fn fade_gain(c: &Clip, l: &mut [f32], r: &mut [f32], sr: f64) {
    let shape = Shape::of(c, l.len(), sr);
    let a = &c.automation;
    if shape.is_none() && a.volume.is_none() && a.pan.is_none() {
        dsp::fade_gain(l, r, sr, c.fade_in, c.fade_out, c.volume, c.pan);
        return;
    }
    let old = dsp::FadeGain::new(l.len(), sr, c.fade_in, c.fade_out, c.volume, c.pan);
    let vol = a.volume.clone().map(Param::Envelope);
    let pan = a.pan.clone().map(Param::Envelope).unwrap_or(Param::Value(c.pan));
    dsp::each(l, r, |i, x| {
        let t = i as f64 / sr;
        let env = shape.as_ref().map_or_else(|| old.env(i), |s| s.env(i)) * c.volume * vol.as_ref().map_or(1.0, |v| v.at(t));
        let ang = (pan.at(t).clamp(-1.0, 1.0) + 1.0) * PI / 4.0;
        [x[0] * env * ang.cos() * SQRT_2, x[1] * env * ang.sin() * SQRT_2]
    });
}

/// A bed clip's envelope at sample i (fades in their shape, its volume lane), without its volume.
pub fn bed_env(c: &Clip, old: &dsp::FadeGain, shape: &Option<Shape>, i: usize, sr: f64) -> f64 {
    let fade = shape.as_ref().map_or_else(|| old.env(i), |s| s.env(i));
    match &c.automation.volume {
        Some(v) => fade * Param::Envelope(v.clone()).at(i as f64 / sr),
        None => fade,
    }
}

/// The clip's polarity flipped when it asks.
pub fn invert(c: &Clip, chs: &mut [&mut [f32]]) {
    if c.invert {
        chs.iter_mut().for_each(|ch| ch.iter_mut().for_each(|v| *v = -*v));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_shape_runs_from_silence_to_full_and_equal_power_is_the_old_fade() {
        for name in ["linear", "equalPower", "exponential", "logarithmic", "sCurve", "attenuated"] {
            assert!(curve(name, 0.0).abs() < 1e-12 && (curve(name, 1.0) - 1.0).abs() < 1e-12, "{name}");
            let mut prev = -1.0;
            for k in 0..=100 {
                let v = curve(name, k as f64 / 100.0);
                assert!(v >= prev, "{name} rises");
                prev = v;
            }
        }
        // Halfway: exponential is quiet, logarithmic loud, linear and the s-curve at a half.
        assert!(curve("exponential", 0.5) < 0.05 && curve("logarithmic", 0.5) > 0.95);
        assert!((curve("linear", 0.5) - 0.5).abs() < 1e-12 && (curve("sCurve", 0.5) - 0.5).abs() < 1e-12);
        let old = dsp::FadeGain::new(1000, 1000.0, 0.2, 0.3, 1.0, 0.0);
        let s = Shape { len: 1000, fade_in: 200, fade_out: 300, shape_in: "equalPower".into(), shape_out: "equalPower".into() };
        for i in (0..1000).step_by(7) {
            assert_eq!(s.env(i).to_bits(), old.env(i).to_bits(), "{i}");
        }
    }
}
