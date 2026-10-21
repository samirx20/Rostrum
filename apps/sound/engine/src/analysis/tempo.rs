//! The tempo of a recording (analyze.rs): the beat, its grid, and the other readings it could be.
//! Onset strength is spectral flux in three bands — all of it, the lows (kicks, under 200 Hz) and the
//! body (under 4 kHz: kicks, snares, chords; not the hats between beats). Then, in order:
//! 1. Periodicity: each period (fractional frames, 50 … 220 BPM) is scored by the autocorrelation at
//!    it and at 2, 3 and 4 of it (a beat repeats over the bar), preferring 70 … 180 BPM.
//! 2. The period is refined by fitting a grid of beats to the whole recording (a long piece pins it).
//! 3. The metrical level (meter.rs): which of the related tempos (half, double, 2/3, 3/2) is the
//!    beat, judged by where the kicks, snares and chords fall, not by periodicity alone.
//! 4. The phase: where the beats land on the most onset strength, the lows counting double.

use crate::analysis::meter::{self, Choice};

/// A tempo reading: the beat (BPM), the first beat (s), how clearly the onsets repeat at it (0 … 1),
/// the beat times, the other tempos it could be (half, double, 2/3, 3/2 …) with their support relative
/// to the chosen one (1 = as strong), and `unsure`: the other reading when the choice was close.
pub struct Tempo {
    pub bpm: f64,
    pub first: f64,
    pub clarity: f64,
    pub beats: Vec<f64>,
    pub alternatives: Vec<(f64, f64)>,
    pub unsure: Option<f64>,
}

/// Spectral flux of the frames (bins `lo .. hi`): the onset strength. The first frame counts from silence.
fn flux(spec: &[Vec<f64>], lo: usize, hi: usize) -> Vec<f64> {
    let mut out = vec![0.0; spec.len()];
    for f in 0..spec.len() {
        let hi = hi.min(spec[f].len());
        out[f] = (lo..hi).map(|k| ((1.0 + spec[f][k]).ln() - if f > 0 { (1.0 + spec[f - 1][k]).ln() } else { 0.0 }).max(0.0)).sum();
    }
    let mean = out.iter().sum::<f64>() / out.len().max(1) as f64;
    out.iter().map(|v| (v - mean).max(0.0)).collect()
}

/// The onset envelopes of a recording and their autocorrelation (frames at `rate` a second).
pub struct Onsets {
    pub o: Vec<f64>,
    pub low: Vec<f64>,
    pub body: Vec<f64>,
    /// 200 Hz … 4 kHz: snares, claps, chords — the body without the kick.
    pub mid: Vec<f64>,
    /// Over 5 kHz: hats, shakers, the top of snares.
    pub hi: Vec<f64>,
    pub rate: f64,
    acs: Vec<f64>,
    low_max: f64,
    body_max: f64,
    mid_max: f64,
}

impl Onsets {
    fn new(spec: &[Vec<f64>], rate: f64, bin_hz: f64) -> Onsets {
        let o = flux(spec, 0, usize::MAX);
        let low = flux(spec, 0, (200.0 / bin_hz).ceil() as usize);
        let body = flux(spec, 0, (4000.0 / bin_hz).ceil() as usize);
        let mid = flux(spec, (200.0 / bin_hz).ceil() as usize, (4000.0 / bin_hz).ceil() as usize);
        let hi = flux(spec, (5000.0 / bin_hz).ceil() as usize, usize::MAX);
        // The autocorrelation at whole lags, up to four bars of the slowest beat (read between them).
        let longest = ((rate * 60.0 / 40.0) * 4.0).ceil() as usize + 2;
        let acs = (0..=longest).map(|l| if l >= o.len() { 0.0 } else { o.iter().zip(&o[l..]).map(|(a, b)| a * b).sum::<f64>() }).collect();
        let max = |v: &[f64]| v.iter().cloned().fold(1e-12, f64::max);
        Onsets { low_max: max(&low), body_max: max(&body), mid_max: max(&mid), o, low, body, mid, hi, rate, acs }
    }

    pub fn len(&self) -> usize {
        self.o.len()
    }

    pub fn lag(&self, bpm: f64) -> f64 {
        self.rate * 60.0 / bpm
    }

    pub fn bpm(&self, lag: f64) -> f64 {
        self.rate * 60.0 / lag
    }

    /// The autocorrelation at a fractional lag.
    pub fn ac(&self, lag: f64) -> f64 {
        if lag < 0.5 || lag >= (self.acs.len() - 1) as f64 || lag >= self.o.len() as f64 {
            return 0.0;
        }
        let (i, f) = (lag.floor() as usize, lag.fract());
        self.acs[i] * (1.0 - f) + self.acs[i + 1] * f
    }

    /// How strongly the onsets repeat at `lag` and at 2, 3 and 4 of it (a repeat a frame early or late still counts).
    pub fn support(&self, lag: f64) -> f64 {
        let near = |x: f64| self.ac(x - 1.0).max(self.ac(x)).max(self.ac(x + 1.0));
        self.ac(lag) + (2..=4).map(|k| near(lag * k as f64) / k as f64).sum::<f64>()
    }

    /// The lows and the body of the sound at frame `t` (each 0 … 1 of its loudest onset).
    pub fn weight(&self, t: f64) -> f64 {
        let i = t.round() as usize;
        self.low.get(i).copied().unwrap_or(0.0) / self.low_max + self.body.get(i).copied().unwrap_or(0.0) / self.body_max
    }

    /// The snares, claps and chords at frame `t` (0 … 1 of the loudest).
    pub fn snare(&self, t: f64) -> f64 {
        self.mid.get(t.round() as usize).copied().unwrap_or(0.0) / self.mid_max
    }

    /// The beats of a grid: from `p`, every `period` frames, to the end.
    pub fn grid(&self, p: f64, period: f64) -> impl Iterator<Item = f64> + '_ {
        (0..).map(move |k| p + k as f64 * period).take_while(|&t| t < self.o.len() as f64)
    }

    /// The grid's phase (whole frames) that lands on the most lows and body.
    pub fn phase(&self, period: f64) -> f64 {
        let sum = |p: usize| self.grid(p as f64, period).map(|t| self.weight(t)).sum::<f64>();
        (0..period.round().max(1.0) as usize).max_by(|&a, &b| sum(a).total_cmp(&sum(b))).unwrap_or(0) as f64
    }

    /// The period that lines a grid up best with the onsets over the whole recording, within ±3 %
    /// of `period` (the autocorrelation reads it to a frame; forty beats pin it to a hundredth).
    fn refine(&self, period: f64) -> f64 {
        let at = |t: f64| {
            let (i, f) = (t.floor() as usize, t.fract());
            let v = |j: usize| self.o.get(j).copied().unwrap_or(0.0) + 2.0 * self.low.get(j).copied().unwrap_or(0.0);
            v(i) * (1.0 - f) + v(i + 1) * f
        };
        let fit = |p: f64| {
            let phases = (2.0 * p).ceil() as usize;
            (0..phases).map(|q| self.grid(q as f64 * 0.5, p).map(at).sum::<f64>() / self.grid(q as f64 * 0.5, p).count().max(1) as f64).fold(0.0, f64::max)
        };
        let mut best = (period, fit(period));
        for s in -30..=30 {
            let p = period * (1.0 + s as f64 * 0.001);
            let f = fit(p);
            if f > best.1 * 1.0001 {
                best = (p, f);
            }
        }
        best.0
    }
}

/// Tempo from the fine spectra (`frame_rate` frames a second, `bin_hz` per bin).
pub fn tempo(spec: &[Vec<f64>], frame_rate: f64, bin_hz: f64) -> Tempo {
    let on = Onsets::new(spec, frame_rate, bin_hz);
    let zero = on.o.iter().map(|v| v * v).sum::<f64>().max(1e-12);
    let pref = |bpm: f64| if (70.0..=180.0).contains(&bpm) { 1.0 } else { (-0.5 * ((bpm / bpm.clamp(70.0, 180.0)).log2() / 0.35).powi(2)).exp() };
    // 1. Every period from 50 to 220 BPM in quarter frames.
    let (lo, hi) = (on.lag(220.0).max(1.0), on.lag(50.0));
    let mut best = (lo, f64::MIN);
    let mut lag = lo;
    while lag <= hi {
        let s = on.support(lag) * pref(on.bpm(lag));
        if s > best.1 {
            best = (lag, s);
        }
        lag += 0.25;
    }
    // 2. Pinned by the grid over the whole piece.
    let period = on.refine(best.0);
    // 3. The metrical level.
    let Choice { period, unsure } = meter::choose(&on, period);
    let bpm = on.bpm(period);
    let mut alternatives: Vec<(f64, f64)> = [0.5, 2.0, 2.0 / 3.0, 1.5, 0.75, 4.0 / 3.0]
        .iter()
        .map(|k| bpm * k)
        .filter(|t| (40.0..=240.0).contains(t))
        .map(|t| (t, (on.support(on.lag(t)) / on.support(period).max(1e-12)).min(1.5)))
        .collect();
    alternatives.sort_by(|x, y| y.1.total_cmp(&x.1));
    // The close call first: it is the reading to check.
    if let Some(u) = unsure {
        alternatives.retain(|(t, _)| (t - u).abs() > 0.5);
        alternatives.insert(0, (u, (on.support(on.lag(u)) / on.support(period).max(1e-12)).min(1.5)));
    }
    // 4. The phase: the beats on the most onset strength, the lows counting double. A grid point just
    //    before the end of the first period is the beat at 0 s (a slightly long period drifts).
    let at = |t: f64| { let i = t.round() as usize; if i < on.len() { on.o[i] + 2.0 * on.low[i] } else { 0.0 } };
    let strength = |p: usize| on.grid(p as f64, period).map(at).sum::<f64>();
    let phase = (0..period.round().max(1.0) as usize).max_by(|&p, &q| strength(p).total_cmp(&strength(q))).unwrap_or(0) as f64;
    let phase = if phase > 0.8 * period { 0.0 } else { phase };
    // Each beat on its own onset when one is there (within two frames, read between frames): a
    // grid alone drifts by its period's error (a 4.8 s loop read at 99.4 BPM ends 30 ms late).
    let loud = (0..on.len()).map(|i| at(i as f64)).fold(0.0, f64::max);
    let snap = |t: f64| {
        let i = t.round() as isize;
        let peak = (i - 2..=i + 2).filter(|&j| j >= 1).map(|j| j as usize).filter(|&j| at(j as f64) > 0.15 * loud && at(j as f64) >= at(j as f64 - 1.0) && at(j as f64) >= at(j as f64 + 1.0)).max_by(|&a, &b| at(a as f64).total_cmp(&at(b as f64)));
        peak.map_or(t, |j| { let (a, b, c) = (at(j as f64 - 1.0), at(j as f64), at(j as f64 + 1.0)); j as f64 + if a - 2.0 * b + c < 0.0 { (0.5 * (a - c) / (a - 2.0 * b + c)).clamp(-0.5, 0.5) } else { 0.0 } })
    };
    let beats: Vec<f64> = on.grid(phase, period).map(|t| (if t < 0.5 { t } else { snap(t) }) / frame_rate).collect();
    Tempo { bpm, first: phase / frame_rate, clarity: (on.ac(period) / zero).clamp(0.0, 1.0), beats, alternatives, unsure }
}

#[cfg(test)]
mod tests {
    /// A beat is where its onset is (frames were read 63 ms early before the onset frames were led).
    #[test]
    fn beats_land_on_their_onsets() {
        let sr = 22050.0;
        let mut x = vec![0f32; (sr * 12.0) as usize];
        for k in 0..20 {
            let s = ((0.3 + k as f64 * 0.6) * sr) as usize;
            for i in 0..2000.min(x.len() - s) {
                let t = i as f64 / sr;
                x[s + i] += ((2.0 * std::f64::consts::PI * 60.0 * t).sin() * (-t * 30.0).exp() * 0.8) as f32;
            }
        }
        let a = crate::analysis::analyze::analyze(&x, sr, false);
        let beats: Vec<f64> = a["beats"].as_array().unwrap().iter().map(|b| b.as_f64().unwrap()).collect();
        assert!((a["tempo"]["bpm"].as_f64().unwrap() - 100.0).abs() < 0.2, "{}", a["tempo"]);
        assert!(beats.iter().enumerate().all(|(k, b)| (b - (0.3 + k as f64 * 0.6)).abs() <= 0.015), "{beats:?}");
    }
}
