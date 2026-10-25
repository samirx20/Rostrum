//! The master bus, on every channel of the bed (bed/): time warps, the master reverb, the master
//! inserts (fx/chain.rs), the loop wrap, the fader and fades, the mastering stage (fx/master.rs: BS.1770
//! loudness with the layout's channel weights, true peaks linked across the channels), the safety
//! clip (on unless the schedule bypasses it), and what the mix reports. Block by block from the tracks' tapes to
//! the mix's own tape, so a long song's master stage holds a few blocks, never the song.

use std::sync::Arc;

use crate::analysis::balance::Balance;
use crate::analysis::loudness::{Lufs, Peaks};
use crate::bed::{self, Layout};
use crate::mix::render::stats::Mix;
use crate::mix::schedule::Schedule;
use crate::mix::spool::CHUNK;
use crate::mix::tape::{Tape, BLOCK};
use crate::mix::tapewriter::TapeWriter;

/// The last stage: untouched up to −1 dBFS, a soft knee above it that never passes full scale, so a
/// limiter's ceiling (or any level under −1 dB) is what the file holds.
pub fn safety_clip(x: f64) -> f64 {
    const KNEE: f64 = 0.891; // −1 dBFS
    if x.abs() <= KNEE {
        x
    } else {
        x.signum() * (KNEE + (1.0 - KNEE) * ((x.abs() - KNEE) / (1.0 - KNEE)).tanh())
    }
}

/// The master bus before its gain: `inputs` (the direct tracks in schedule order, then the buses that reach the
/// master) summed, the tail included, then the time warps, the master reverb and the master inserts. Block by block
/// onto a tape; time warps or a whole-take insert need the whole bus, so with one of those it is summed in memory.
fn summed(s: &Schedule, inputs: &[Arc<Tape>]) -> Result<Tape, String> {
    let (sr, layout) = (s.sample_rate as f64, s.layout);
    let buf = s.total_samples + s.tail_samples;
    let nch = layout.channels();
    let mut chain = crate::fx::chain::Chain::new(&s.effects, layout, sr).map_err(|e| format!("master: {e}"))?;
    let mut reverb = crate::fx::reverb::BedReverb::new(nch, layout, &s.master_reverb, 0.18, sr);
    if !s.time_warps.is_empty() || chain.whole() {
        let mut bus = vec![vec![0.0f32; buf]; nch];
        for t in inputs {
            t.add_into(&mut bus)?;
        }
        crate::mix::effects::time_warps(&mut bed::slices(&mut bus), sr, &s.time_warps);
        reverb.block(&mut bus);
        chain.block(&mut bed::slices(&mut bus), 0).map_err(|e| format!("master: {e}"))?;
        return Tape::spill(&bus);
    }
    let mut out = TapeWriter::new(nch, buf)?;
    for t0 in (0..buf).step_by(BLOCK) {
        let n = BLOCK.min(buf - t0);
        let mut block = vec![vec![0.0f32; n]; nch];
        for t in inputs {
            for (dst, src) in block.iter_mut().zip(t.read(t0, n)?) {
                dst.iter_mut().zip(&src).for_each(|(d, s)| *d += *s);
            }
        }
        reverb.block(&mut block);
        chain.block(&mut bed::slices(&mut block), t0).map_err(|e| format!("master: {e}"))?;
        out.push(&block)?;
    }
    out.finish(None)
}

/// The bus at song frames `at .. at + n` with a loop's wrap: the release and reverb tail past the end wraps onto
/// the start, and the last few samples bridge into the first so the seam does not click.
fn wrapped(s: &Schedule, pre: &Tape, at: usize, n: usize) -> Result<Vec<Vec<f32>>, String> {
    let mut b = pre.read(at, n)?;
    let (tail, total) = (s.tail_samples, s.total_samples);
    if tail == 0 {
        return Ok(b);
    }
    let taper = |i: usize| if i as f64 > tail as f64 * 0.85 { (tail - i) as f64 / (tail as f64 * 0.15) } else { 1.0 };
    let wrap = |b: &mut [Vec<f32>], from: Vec<Vec<f32>>, at: usize| {
        for (c, w) in b.iter_mut().zip(&from) {
            for i in at..(at + c.len()).min(tail) {
                c[i - at] = (c[i - at] as f64 + w[i - at] as f64 * taper(i)) as f32;
            }
        }
    };
    if at < tail {
        wrap(&mut b, pre.read(total + at, n)?, at);
    }
    let bridge = 48.min((total as f64 * 0.01).floor() as usize);
    if at + n > total - bridge && at < total {
        let mut first = pre.read(0, 1)?;
        wrap(&mut first, pre.read(total, 1)?, 0);
        for (c, f) in b.iter_mut().zip(&first) {
            let first = f[0] as f64;
            for k in 0..bridge {
                let idx = total - bridge + k;
                if idx >= at && idx < at + n {
                    let a = 0.5 * (1.0 - (std::f64::consts::PI * ((k + 1) as f64 / bridge as f64)).cos());
                    c[idx - at] = (c[idx - at] as f64 * (1.0 - a) + first * a) as f32;
                }
            }
        }
    }
    Ok(b)
}

/// The summed tracks (`inputs`: on tapes, in the order they sum) to the finished mix, on a tape of its own: the
/// master bus (summed), the fader and the fades (the master's linear gain, one source for the mix and the stems,
/// mastergain.rs), the mastering stage when there is one, then the safety clip, and the file's measures on the way.
/// A range: the file is that stretch of the song (the stages before the gain ran over the song, so it starts with
/// their state: a reverb tail, a compressor's gain), mastered and measured on its own. Block by block throughout.
pub fn master(s: &Schedule, inputs: &[Arc<Tape>]) -> Result<Mix, String> {
    let (sr, layout) = (s.sample_rate as f64, s.layout);
    let nch = layout.channels();
    let pre = summed(s, inputs)?;
    let mut gain = crate::mix::mastergain::MasterGain::new(s);
    let (from, total) = (gain.offset, gain.total);
    let lin = gain.clone();
    let gained = |at: usize, n: usize| -> Result<Vec<Vec<f32>>, String> {
        let mut b = wrapped(s, &pre, from + at, n)?;
        for c in b.iter_mut() {
            c.iter_mut().enumerate().for_each(|(i, v)| *v = (*v as f64 * lin.lin(at + i)) as f32);
        }
        Ok(b)
    };
    let weights = layout.weights();
    let (mastered, report) = match &s.master {
        Some(m) => {
            let (sp, r, d) = crate::fx::master::master_blocks(&gained, nch, total, &weights, m, sr, true)?;
            gain.dynamics = Some(Arc::new(d));
            (Some(sp), r)
        }
        None => (None, Default::default()),
    };
    gain.norm = 10f64.powf(report.gain_db / 20.0);
    let mut mix = Mix { layout, out: None, peak: 0.0001, sum_sq: 0.0, sums: vec![0.0; nch], clipped: 0, safety_clipped: 0, lufs: -70.0, true_peak: -120.0, true_peak_series: vec![], reduction_series: vec![], ducks: vec![], tracks: vec![], buses: vec![], stems: vec![], bus_stems: vec![], gain: None, master: report, bands: [-140.0; 5], loud: None, levels: vec![], inputs: vec![] };
    let mut win = crate::mix::render::levels::Windows::new(sr);
    let mut file = TapeWriter::new(nch, total)?;
    let (mut lufs, mut peaks, mut balance, mut loud) = (Lufs::new(nch, &weights, sr), Peaks::new(nch), Balance::new(sr, false), crate::analysis::loudstats::Meter::new(nch, &weights, sr));
    // The true peak of each 100 ms hop: the hop's loudest so far, and its frames.
    let hop = (sr * 0.1).round().max(1.0) as usize;
    let (mut hop_max, mut hop_n, mut most) = (0.0f64, 0usize, 1e-9f64);
    let db = |m: f64| 20.0 * m.max(1e-9).log10();
    let mut series = vec![];
    // The mastering stage's reduction (dB, ≥ 0: glue and limiter, the target gain taken out) of each 100 ms hop: its deepest.
    let (mut red_min, mut red_n) = (1.0f64, 0usize);
    let mut take_peaks = |per: Vec<f64>, series: &mut Vec<f64>| {
        for p in per {
            most = most.max(p);
            hop_max = hop_max.max(p);
            hop_n += 1;
            if hop_n == hop {
                series.push(db(hop_max));
                (hop_max, hop_n) = (0.0, 0);
            }
        }
    };
    for at in (0..total).step_by(CHUNK) {
        let n = CHUNK.min(total - at);
        let mut out = match &mastered {
            Some(sp) => sp.read(at, n)?,
            None => gained(at, n)?,
        };
        if mastered.is_some() {
            for m in gain.mastering(at, n)? {
                red_min = red_min.min(m / gain.norm);
                red_n += 1;
                if red_n == hop {
                    mix.reduction_series.push(-db(red_min).min(0.0));
                    (red_min, red_n) = (1.0, 0);
                }
            }
        }
        for i in 0..n {
            let (mut hot, mut sq, mut top) = (false, 0.0, 0.0f64);
            for (c, ch) in out.iter_mut().enumerate() {
                let raw = ch[i] as f64;
                hot |= raw.abs() >= 0.99;
                mix.safety_clipped += (s.safety_clip && raw.abs() > 0.891) as usize;
                let a = if s.safety_clip { safety_clip(raw) } else { raw };
                ch[i] = a as f32;
                top = top.max(a.abs());
                sq += a * a;
                mix.sums[c] += a;
            }
            mix.peak = mix.peak.max(top);
            win.frame(top, sq / nch as f64);
            mix.clipped += hot as usize;
            mix.sum_sq += sq / nch as f64;
        }
        let refs: Vec<&[f32]> = out.iter().map(|c| c.as_slice()).collect();
        let st = crate::mix::render::stats::as_stereo(&out);
        // The file's measures, each on a core of its own.
        let (lufs, loud, balance, peaks) = (&mut lufs, &mut loud, &mut balance, &mut peaks);
        let per = std::thread::scope(|sc| {
            sc.spawn(|| lufs.push(&refs));
            sc.spawn(|| loud.push(&refs));
            sc.spawn(|| balance.push(&st[0], &st[1]));
            peaks.push(&refs)
        });
        take_peaks(per, &mut series);
        file.push(&out)?;
    }
    take_peaks(peaks.finish(), &mut series);
    if hop_n > 0 {
        series.push(db(hop_max));
    }
    if red_n > 0 {
        mix.reduction_series.push(-db(red_min).min(0.0));
    }
    mix.levels = win.finish();
    mix.lufs = lufs.finish();
    mix.true_peak = db(most);
    mix.true_peak_series = series;
    mix.bands = balance.finish().0;
    mix.loud = Some(loud.finish());
    mix.out = Some(file.finish(None)?);
    mix.gain = Some(gain);
    Ok(mix)
}

/// What a surround bed says about itself (main.rs prints it): each channel's peak, RMS and true peak,
/// the LFE's level against the mains and its share above 120 Hz, and the stereo fold-down's health —
/// its loudness against the bed's and the 400 ms windows where it loses more than 3 dB against the
/// power its channels carry (out-of-phase content cancelling when summed).
pub fn surround_report(layout: Layout, chs: &[Vec<f32>], lufs: f64, sr: f64) -> serde_json::Value {
    if layout == Layout::Stereo {
        return serde_json::Value::Null;
    }
    let db = crate::analysis::balance::db;
    let n = chs[0].len().max(1);
    let channels: Vec<serde_json::Value> = layout
        .speakers()
        .iter()
        .zip(chs)
        .map(|(sp, c)| {
            let peak = c.iter().fold(0.0f64, |m, v| m.max((*v as f64).abs()));
            let ms = c.iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / n as f64;
            serde_json::json!({ "name": sp.name, "peakDb": db(peak * peak), "rmsDb": db(ms), "truePeakDb": (crate::analysis::loudness::true_peak_db_n(&[c]) * 10.0).round() / 10.0 })
        })
        .collect();
    let power = |c: &[f32]| c.iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / n as f64;
    let lfe = layout.lfe().map(|k| {
        let c = &chs[k];
        let mains = layout.speakers().iter().enumerate().filter(|(i, _)| *i != k).map(|(i, _)| power(&chs[i])).sum::<f64>();
        let mut high = c.clone();
        let hp = crate::fx::eq::biquad("highpass", 120.0, 0.0, std::f64::consts::FRAC_1_SQRT_2, sr);
        hp.run(&mut high);
        hp.run(&mut high);
        serde_json::json!({ "levelDb": db(power(c)), "againstMainsDb": ((db(power(c)) - db(mains)) * 10.0).round() / 10.0, "above120HzShare": if power(c) > 1e-14 { ((power(&high) / power(c)) * 1000.0).round() / 1000.0 } else { 0.0 } })
    });
    let m = bed::downmix(layout, Layout::Stereo).expect("a surround bed folds to stereo");
    let fold = bed::apply(&m, &chs);
    let fold_lufs = crate::analysis::loudness::integrated_lufs_n(&[&fold[0], &fold[1]], &[1.0, 1.0], sr);
    // Window by window: the fold-down's power against what its channels would give uncorrelated.
    let win = (sr * 0.4) as usize;
    let mut losses = vec![];
    for (w, start) in (0..n.saturating_sub(win - 1)).step_by(win).enumerate() {
        let span = start..start + win;
        let got: f64 = fold.iter().map(|o| o[span.clone()].iter().map(|v| (*v as f64).powi(2)).sum::<f64>()).sum();
        let expected: f64 = m.iter().map(|row| row.iter().zip(chs).map(|(g, c)| g * g * c[span.clone()].iter().map(|v| (*v as f64).powi(2)).sum::<f64>()).sum::<f64>()).sum();
        if expected > 1e-6 * win as f64 && got < expected * 0.5 {
            losses.push(serde_json::json!({ "at": (w as f64 * 0.4 * 100.0).round() / 100.0, "lossDb": db(got / expected) }));
        }
    }
    serde_json::json!({ "layout": layout.name(), "channels": channels, "lfe": lfe, "foldDown": { "lufs": (fold_lufs * 10.0).round() / 10.0, "againstBedLu": ((fold_lufs - lufs) * 10.0).round() / 10.0, "cancellations": losses } })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_safety_clip_leaves_everything_under_minus_one_db_alone() {
        assert_eq!(safety_clip(0.5), 0.5);
        assert_eq!(safety_clip(-0.89), -0.89);
        assert!(safety_clip(1.5) < 1.0 && safety_clip(1.5) > 0.95);
        assert!(safety_clip(0.95) > 0.9 && safety_clip(0.95) < 0.95);
    }

    #[test]
    fn the_fold_down_report_finds_out_of_phase_surrounds() {
        // L carries a tone, Ls the same tone inverted at 1/0.7071: the ITU fold-down's left sums to nothing from 1 s.
        let sr = 48000.0;
        let n = 96000;
        let tone: Vec<f32> = (0..n).map(|i| (0.3 * (2.0 * std::f64::consts::PI * 440.0 * i as f64 / sr).sin()) as f32).collect();
        let mut channels = vec![vec![0.0f32; n]; 6];
        channels[0] = tone.clone();
        channels[4] = tone.iter().enumerate().map(|(i, v)| if i >= 48000 { -v / std::f32::consts::FRAC_1_SQRT_2 } else { 0.0 }).collect();
        let r = surround_report(Layout::Surround51, &channels, -20.0, sr);
        let losses = r["foldDown"]["cancellations"].as_array().unwrap();
        assert!(!losses.is_empty() && losses.iter().all(|l| l["at"].as_f64().unwrap() >= 0.8), "{losses:?}");
        assert!(losses.iter().any(|l| l["lossDb"].as_f64().unwrap() < -20.0), "{losses:?}");
        assert_eq!(r["lfe"]["levelDb"].as_f64().unwrap(), -140.0);
    }
}
