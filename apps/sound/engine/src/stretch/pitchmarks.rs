//! A voice's pitch and its pitch marks, for PSOLA (psola.rs). Pitch: YIN (de Cheveigné & Kawahara
//! 2002) every 5 ms on the signal decimated to ~11 kHz, voiced where the cumulative-mean difference
//! dips under 0.15 and the frame is within 35 dB of the loudest, octave slips smoothed by a median.
//! Marks: one per period in voiced stretches, on the waveform's peak (of the low band, one polarity),
//! every 5 ms elsewhere (period 0: unvoiced).

/// f0 (Hz, 0 = unvoiced) every `hop` samples of the source.
pub struct Track {
    pub hop: usize,
    pub f0: Vec<f64>,
}

pub fn track(x: &[f32], sr: f64) -> Track {
    let d = ((sr / 11025.0).round() as usize).max(1);
    let y: Vec<f64> = x.chunks(d).map(|c| c.iter().map(|&v| v as f64).sum::<f64>() / c.len() as f64).collect();
    let sd = sr / d as f64;
    let (w, hop) = ((0.03 * sd) as usize, (0.005 * sr) as usize);
    let (tmin, tmax) = ((sd / 500.0) as usize, (sd / 60.0) as usize);
    let frames = x.len() / hop;
    let rms: Vec<f64> = (0..frames).map(|f| {
        let a = (f * hop / d).min(y.len());
        let s = &y[a..(a + w).min(y.len())];
        (s.iter().map(|v| v * v).sum::<f64>() / s.len().max(1) as f64).sqrt()
    }).collect();
    let loudest = rms.iter().cloned().fold(0.0, f64::max);
    let mut f0 = vec![0.0; frames];
    let mut diff = vec![0.0; tmax + 2];
    for f in 0..frames {
        let a = f * hop / d;
        if a + w + tmax + 1 >= y.len() || rms[f] < loudest * 0.018 {
            continue;
        }
        for t in 1..=tmax + 1 {
            diff[t] = (0..w).map(|j| (y[a + j] - y[a + j + t]).powi(2)).sum();
        }
        // Cumulative mean normalised difference; the first dip under the threshold, then its bottom.
        let mut sum = 0.0;
        let cmnd: Vec<f64> = (0..=tmax + 1).map(|t| if t == 0 { 1.0 } else { sum += diff[t]; diff[t] * t as f64 / sum.max(1e-12) }).collect();
        let Some(mut t) = (tmin..=tmax).find(|&t| cmnd[t] < 0.15) else { continue };
        while t < tmax && cmnd[t + 1] < cmnd[t] {
            t += 1;
        }
        let (a0, b0, c0) = (cmnd[t - 1], cmnd[t], cmnd[t + 1]);
        let shift = 0.5 * (a0 - c0) / (a0 - 2.0 * b0 + c0).max(1e-12);
        f0[f] = sd / (t as f64 + shift.clamp(-0.5, 0.5));
    }
    // A median of five voiced neighbours undoes single-frame octave slips.
    let raw = f0.clone();
    for f in 0..frames {
        if raw[f] > 0.0 {
            let mut v: Vec<f64> = raw[f.saturating_sub(2)..(f + 3).min(frames)].iter().cloned().filter(|&p| p > 0.0).collect();
            v.sort_by(f64::total_cmp);
            f0[f] = v[v.len() / 2];
        }
    }
    Track { hop, f0 }
}

/// Pitch marks: (sample, period in samples — to the next pulse; 0 where unvoiced), in order.
pub fn marks(x: &[f32], sr: f64, tr: &Track) -> Vec<(usize, f64)> {
    // The low band, zero-phase (one pole each way at 900 Hz): its peaks are the glottal pulses.
    let a = (-2.0 * std::f64::consts::PI * 900.0 / sr).exp();
    let mut lp: Vec<f64> = Vec::with_capacity(x.len());
    let mut s = 0.0;
    for &v in x {
        s = a * s + (1.0 - a) * v as f64;
        lp.push(s);
    }
    s = 0.0;
    for v in lp.iter_mut().rev() {
        s = a * s + (1.0 - a) * *v;
        *v = s;
    }
    // One polarity: the one whose peaks are larger.
    let (pos, neg) = lp.iter().fold((0.0f64, 0.0f64), |(p, n), &v| (p.max(v), n.max(-v)));
    if neg > pos {
        lp.iter_mut().for_each(|v| *v = -*v);
    }
    let f0_at = |i: usize| tr.f0.get(i / tr.hop).copied().unwrap_or(0.0);
    let step = 0.005 * sr;
    let (mut out, mut t): (Vec<(usize, f64)>, f64) = (vec![], 0.0);
    while (t as usize) < x.len() {
        let f = f0_at(t as usize);
        if f <= 0.0 {
            out.push((t as usize, 0.0));
            t += step;
            continue;
        }
        let p = sr / f;
        // The next pulse: one period on from a voiced mark, else the first peak of this stretch.
        let (lo, hi) = match out.last() {
            Some(&(m, pm)) if pm > 0.0 => ((m as f64 + 0.75 * p) as usize, (m as f64 + 1.25 * p) as usize),
            _ => (t as usize, (t + p) as usize),
        };
        let hi = hi.min(x.len() - 1);
        if lo >= hi {
            break;
        }
        let m = (lo..=hi).max_by(|&i, &j| lp[i].total_cmp(&lp[j])).unwrap();
        out.push((m, p));
        t = m as f64 + 0.5 * p;
    }
    // A voiced mark's period is the real distance to the next pulse (what PSOLA lays down again), so
    // an unchanged voice is rebuilt pulse for pulse.
    for k in 0..out.len().saturating_sub(1) {
        let (m, p) = out[k];
        let (next, pn) = out[k + 1];
        if p > 0.0 && pn > 0.0 {
            out[k].1 = ((next - m) as f64).clamp(0.7 * p, 1.4 * p);
        }
    }
    out
}
