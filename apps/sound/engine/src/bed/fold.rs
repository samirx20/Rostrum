//! One mix, every format: a rendered bed folded to a delivery layout — the ITU fold-downs (bed/mod.rs)
//! or binaural for headphones (binaural.rs) — then held to the delivery's ceiling: with the mix's
//! mastering spec, its loudness target and true-peak ceiling again (a fold-down changes both); without,
//! a true-peak limiter at −1 dBTP only where the fold passes it. Reports what it did.
//!   rostrum-sound fold <bed.wav> <stereo | 5.1 | binaural> <out.wav> [--master <json>] [--no-safety-clip]

use crate::bed::{self, Layout};
use crate::analysis::loudness;
use crate::fx::master::{self, MasterSpec};

pub fn run(args: &[String]) -> Result<(), String> {
    let (src, to, out) = (&args[1], args[2].as_str(), &args[3]);
    let spec: Option<MasterSpec> = match args.iter().position(|a| a == "--master") {
        Some(i) => Some(serde_json::from_str(args.get(i + 1).ok_or("--master takes a JSON spec")?).map_err(|e| format!("--master: {e}"))?),
        None => None,
    };
    let (chs, sr) = crate::mix::wavio::read(src)?;
    let from = Layout::of_channels(chs.len())?;
    let Folded { channels: folded, layout, raw_lufs, raw_tp, held, peak, sum_sq, sums, clipped } = fold_bed(&chs, from, to, spec, sr, !args.iter().any(|a| a == "--no-safety-clip"))?;
    let weights = layout.weights();
    let lufs = |c: &[Vec<f32>]| loudness::integrated_lufs_n(&c.iter().map(|v| v.as_slice()).collect::<Vec<_>>(), &weights, sr);
    let tp = |c: &[Vec<f32>]| loudness::true_peak_db_n(&c.iter().map(|v| v.as_slice()).collect::<Vec<_>>());
    let n = folded[0].len().max(1);
    std::fs::write(out, crate::mix::wavio::write(&folded, layout, sr as u32)).map_err(|e| format!("{out}: {e}"))?;
    let refs: Vec<&[f32]> = folded.iter().map(|c| c.as_slice()).collect();
    let loud = crate::analysis::loudstats::stats_n(&refs, &weights, sr);
    let st = crate::mix::render::stats::as_stereo(&folded);
    println!("{}", serde_json::json!({
        "from": from.name(), "to": to, "layout": layout.name(), "channels": folded.len(), "seconds": n as f64 / sr,
        "peak": peak, "lufs": lufs(&folded), "truePeak": tp(&folded), "rawLufs": raw_lufs, "rawTruePeak": raw_tp, "held": held,
        "maxMomentary": loud.max_momentary, "maxShortTerm": loud.max_short_term, "lra": loud.lra,
        "sumSq": sum_sq, "sums": sums, "sumL": sums[0], "sumR": sums.get(1).copied().unwrap_or(0.0), "clipped": clipped, "ducks": [],
        "bands": crate::analysis::balance::bands(&st[0], &st[1], n, sr),
    }));
    Ok(())
}

/// A bed folded to `to` ("stereo", "5.1", "binaural"), held to the delivery's ceiling and safety-clipped:
/// what `fold` writes, and what the live output plays when it monitors a surround mix in stereo or
/// binaurally (monitor.rs), so audition ≡ delivery.
pub struct Folded {
    pub channels: Vec<Vec<f32>>,
    pub layout: Layout,
    pub raw_lufs: f64,
    pub raw_tp: f64,
    pub held: bool,
    pub peak: f64,
    pub sum_sq: f64,
    pub sums: Vec<f64>,
    pub clipped: usize,
}

pub fn fold_bed(chs: &[Vec<f32>], from: Layout, to: &str, spec: Option<MasterSpec>, sr: f64, safety_clip: bool) -> Result<Folded, String> {
    let (mut folded, layout) = if to == "binaural" {
        (crate::bed::binaural::render(chs, from, sr)?.to_vec(), Layout::Stereo)
    } else {
        let target = Layout::parse(to)?;
        (bed::apply(&bed::downmix(from, target)?, chs), target)
    };
    let weights = layout.weights();
    let lufs = |c: &[Vec<f32>]| loudness::integrated_lufs_n(&c.iter().map(|v| v.as_slice()).collect::<Vec<_>>(), &weights, sr);
    let tp = |c: &[Vec<f32>]| loudness::true_peak_db_n(&c.iter().map(|v| v.as_slice()).collect::<Vec<_>>());
    let (raw_lufs, raw_tp) = (lufs(&folded), tp(&folded));
    let held = spec.map(|s| MasterSpec { glue: 0.0, ..s }).or((raw_tp > -1.0).then_some(MasterSpec { loudness: None, true_peak: -1.0, glue: 0.0 }));
    if let Some(s) = &held {
        master::master_n(&mut folded, &weights, s, sr);
    }
    let n = folded[0].len().max(1);
    let (mut peak, mut sum_sq, mut sums, mut clipped) = (0.0001f64, 0.0, vec![0.0; folded.len()], 0usize);
    for i in 0..n.min(folded[0].len()) {
        let mut hot = false;
        let mut sq = 0.0;
        for (c, buf) in folded.iter_mut().enumerate() {
            let raw = buf[i] as f64;
            hot |= raw.abs() >= 0.99;
            let a = if safety_clip { crate::mix::bus::safety_clip(raw) } else { raw };
            buf[i] = a as f32;
            peak = peak.max(a.abs());
            sq += a * a;
            sums[c] += a;
        }
        clipped += hot as usize;
        sum_sq += sq / folded.len() as f64;
    }
    Ok(Folded { channels: folded, layout, raw_lufs, raw_tp, held: held.is_some(), peak, sum_sq, sums, clipped })
}
