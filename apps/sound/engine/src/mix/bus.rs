//! The master bus, on every channel of the bed (bed/): time warps, the master reverb, the master
//! inserts (fx/chain.rs), the loop wrap, the fader and fades, the mastering stage (fx/master.rs: BS.1770
//! loudness with the layout's channel weights, true peaks linked across the channels), the safety
//! clip (on unless the schedule bypasses it), and what the mix reports.

use crate::bed::{self, Layout};
use crate::mix::render::stats::Mix;
use crate::mix::schedule::Schedule;

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

/// The summed tracks (`bus`, the tail included) to the finished mix.
pub fn master(s: &Schedule, mut bus: Vec<Vec<f32>>) -> Result<Mix, String> {
    let (sr, total, layout) = (s.sample_rate as f64, s.total_samples, s.layout);
    crate::mix::effects::time_warps(&mut bed::slices(&mut bus), sr, &s.time_warps);
    if s.master_reverb != "dry" {
        crate::fx::reverb::reverb_bed(&mut bus, layout, &s.master_reverb, 0.18, sr);
    }
    crate::fx::chain::run(&s.effects, &mut bed::slices(&mut bus), layout, sr).map_err(|e| format!("master: {e}"))?;
    if s.tail_samples > 0 {
        // A loop: the release and reverb tail past the end wraps onto the start, and the last few
        // samples bridge into the first so the seam does not click.
        let tail = s.tail_samples;
        let bridge = 48.min((total as f64 * 0.01).floor() as usize);
        for c in bus.iter_mut() {
            for i in 0..tail {
                let taper = if i as f64 > tail as f64 * 0.85 { (tail - i) as f64 / (tail as f64 * 0.15) } else { 1.0 };
                c[i] = (c[i] as f64 + c[total + i] as f64 * taper) as f32;
            }
            let first = c[0] as f64;
            for k in 0..bridge {
                let idx = total - bridge + k;
                let a = 0.5 * (1.0 - (std::f64::consts::PI * ((k + 1) as f64 / bridge as f64)).cos());
                c[idx] = (c[idx] as f64 * (1.0 - a) + first * a) as f32;
            }
        }
    }
    // The fader and the fades, then the mastering stage when there is one, then the safety clip.
    let (fi, fo) = (s.fade_in_samples, s.fade_out_samples);
    let env: Vec<f64> = (0..total)
        .map(|i| {
            let mut env = 1.0;
            if fi > 0 && i < fi {
                env = 0.5 * (1.0 - (std::f64::consts::PI * (i as f64 / fi.max(1) as f64)).cos());
            }
            if fo > 0 && i + fo >= total {
                let rem = (total as f64 - 1.0 - i as f64) / (fo.max(2) - 1) as f64;
                env = f64::min(env, (0.5 * (1.0 - (std::f64::consts::PI * rem).cos())).powf(2.2));
            }
            env
        })
        .collect();
    // The master fader: its lane when it has one (buses.rs), else its level.
    let fader = crate::mix::buses::master_fader(s);
    let mut out: Vec<Vec<f32>> = bus.iter().map(|c| (0..total).map(|i| (c[i] as f64 * fader.at(i as f64 / sr) * env[i]) as f32).collect()).collect();
    let weights = layout.weights();
    if let Some(m) = &s.master {
        crate::fx::master::master_n(&mut out, &weights, m, sr);
    }
    let nch = out.len();
    let mut mix = Mix { layout, channels: vec![vec![0.0; total]; nch], peak: 0.0001, sum_sq: 0.0, sums: vec![0.0; nch], clipped: 0, lufs: -70.0, true_peak: -120.0, true_peak_series: vec![], ducks: vec![], tracks: vec![], buses: vec![], stems: vec![], bands: [-140.0; 5] };
    for i in 0..total {
        let (mut hot, mut sq) = (false, 0.0);
        for c in 0..nch {
            let raw = out[c][i] as f64;
            hot |= raw.abs() >= 0.99;
            let a = if s.safety_clip { safety_clip(raw) } else { raw };
            mix.channels[c][i] = a as f32;
            mix.peak = mix.peak.max(a.abs());
            sq += a * a;
            mix.sums[c] += a;
        }
        mix.clipped += hot as usize;
        mix.sum_sq += sq / nch as f64;
    }
    // The file's measures, each on its own core.
    let chs: Vec<&[f32]> = mix.channels.iter().map(|c| c.as_slice()).collect();
    let (lufs, true_peak, bands) = std::thread::scope(|sc| {
        let lufs = sc.spawn(|| crate::analysis::loudness::integrated_lufs_n(&chs, &weights, sr));
        // One 4x pass gives the file's true peak and its series per 100 ms.
        let peak = sc.spawn(|| {
            let per = crate::analysis::loudness::sample_peaks(&chs);
            let hop = (sr * 0.1).round().max(1.0) as usize;
            let db = |m: f64| 20.0 * m.max(1e-9).log10();
            (db(per.iter().copied().fold(1e-9, f64::max)), per.chunks(hop).map(|c| db(c.iter().copied().fold(0.0, f64::max))).collect::<Vec<f64>>())
        });
        let st = crate::mix::render::stats::as_stereo(&mix.channels);
        let bands = crate::analysis::balance::bands(&st[0], &st[1], total, sr);
        (lufs.join().unwrap(), peak.join().unwrap(), bands)
    });
    (mix.lufs, mix.bands) = (lufs, bands);
    (mix.true_peak, mix.true_peak_series) = true_peak;
    Ok(mix)
}

/// What a surround bed says about itself (main.rs prints it): each channel's peak, RMS and true peak,
/// the LFE's level against the mains and its share above 120 Hz, and the stereo fold-down's health —
/// its loudness against the bed's and the 400 ms windows where it loses more than 3 dB against the
/// power its channels carry (out-of-phase content cancelling when summed).
pub fn surround_report(mix: &Mix, sr: f64) -> serde_json::Value {
    let layout = mix.layout;
    if layout == Layout::Stereo {
        return serde_json::Value::Null;
    }
    let db = crate::analysis::balance::db;
    let n = mix.channels[0].len().max(1);
    let channels: Vec<serde_json::Value> = layout
        .speakers()
        .iter()
        .zip(&mix.channels)
        .map(|(sp, c)| {
            let peak = c.iter().fold(0.0f64, |m, v| m.max((*v as f64).abs()));
            let ms = c.iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / n as f64;
            serde_json::json!({ "name": sp.name, "peakDb": db(peak * peak), "rmsDb": db(ms), "truePeakDb": (crate::analysis::loudness::true_peak_db_n(&[c]) * 10.0).round() / 10.0 })
        })
        .collect();
    let power = |c: &[f32]| c.iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / n as f64;
    let lfe = layout.lfe().map(|k| {
        let c = &mix.channels[k];
        let mains = layout.speakers().iter().enumerate().filter(|(i, _)| *i != k).map(|(i, _)| power(&mix.channels[i])).sum::<f64>();
        let mut high = c.clone();
        let hp = crate::fx::eq::biquad("highpass", 120.0, 0.0, std::f64::consts::FRAC_1_SQRT_2, sr);
        hp.run(&mut high);
        hp.run(&mut high);
        serde_json::json!({ "levelDb": db(power(c)), "againstMainsDb": ((db(power(c)) - db(mains)) * 10.0).round() / 10.0, "above120HzShare": if power(c) > 1e-14 { ((power(&high) / power(c)) * 1000.0).round() / 1000.0 } else { 0.0 } })
    });
    let m = bed::downmix(layout, Layout::Stereo).expect("a surround bed folds to stereo");
    let fold = bed::apply(&m, &mix.channels);
    let fold_lufs = crate::analysis::loudness::integrated_lufs_n(&[&fold[0], &fold[1]], &[1.0, 1.0], sr);
    // Window by window: the fold-down's power against what its channels would give uncorrelated.
    let win = (sr * 0.4) as usize;
    let mut losses = vec![];
    for (w, start) in (0..n.saturating_sub(win - 1)).step_by(win).enumerate() {
        let span = start..start + win;
        let got: f64 = fold.iter().map(|o| o[span.clone()].iter().map(|v| (*v as f64).powi(2)).sum::<f64>()).sum();
        let expected: f64 = m.iter().map(|row| row.iter().zip(&mix.channels).map(|(g, c)| g * g * c[span.clone()].iter().map(|v| (*v as f64).powi(2)).sum::<f64>()).sum::<f64>()).sum();
        if expected > 1e-6 * win as f64 && got < expected * 0.5 {
            losses.push(serde_json::json!({ "at": (w as f64 * 0.4 * 100.0).round() / 100.0, "lossDb": db(got / expected) }));
        }
    }
    serde_json::json!({ "layout": layout.name(), "channels": channels, "lfe": lfe, "foldDown": { "lufs": (fold_lufs * 10.0).round() / 10.0, "againstBedLu": ((fold_lufs - mix.lufs) * 10.0).round() / 10.0, "cancellations": losses } })
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
        let mix = Mix { layout: Layout::Surround51, channels, peak: 0.5, sum_sq: 0.0, sums: vec![0.0; 6], clipped: 0, lufs: -20.0, true_peak: -6.0, true_peak_series: vec![], ducks: vec![], tracks: vec![], buses: vec![], stems: vec![], bands: [-140.0; 5] };
        let r = surround_report(&mix, sr);
        let losses = r["foldDown"]["cancellations"].as_array().unwrap();
        assert!(!losses.is_empty() && losses.iter().all(|l| l["at"].as_f64().unwrap() >= 0.8), "{losses:?}");
        assert!(losses.iter().any(|l| l["lossDb"].as_f64().unwrap() < -20.0), "{losses:?}");
        assert_eq!(r["lfe"]["levelDb"].as_f64().unwrap(), -140.0);
    }
}
