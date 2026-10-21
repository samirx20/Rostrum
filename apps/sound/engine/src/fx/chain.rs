//! The insert chain over any bed (bed/): a clip's or track's stereo signal, or a surround master.
//! Each effect runs the way it means on several channels:
//! - linked (one gain for every channel, so the image does not shift): compressor, limiter, gate,
//!   de-esser, leveller (its loudness BS.1770-weighted);
//! - per channel: EQ, saturation, tape, declip, declick;
//! - per left/right pair, a centre channel alone: delay (ping-pong bounces inside a pair), convolution
//!   (the IR's left side on the left speaker), dehum, dereverb; time-based effects leave the LFE dry;
//! - the reverb insert: one reverb over the mains (dsp.rs);
//! - a CLAP / VST3 effect is stereo: on a surround bed it is an error naming it.

use crate::bed::Layout;
use crate::fx::eq::eq;
use crate::fx::inserts;
use crate::mix::schedule::Effect;

/// Runs a chain of inserts over a stereo buffer, in order.
pub fn stereo(effects: &[Effect], l: &mut [f32], r: &mut [f32], sr: f64) -> Result<(), String> {
    run(effects, &mut [l, r], Layout::Stereo, sr)
}

/// Two channels of the bed, mutably (i < j).
fn two<'a>(chs: &'a mut [&mut [f32]], i: usize, j: usize) -> (&'a mut [f32], &'a mut [f32]) {
    let (a, b) = chs.split_at_mut(j);
    (&mut *a[i], &mut *b[0])
}

/// `f` over each left/right pair, then over each lone channel (with a scratch partner it discards);
/// the LFE only when `lfe`.
fn pairwise(chs: &mut [&mut [f32]], layout: Layout, lfe: bool, mut f: impl FnMut(&mut [f32], &mut [f32]) -> Result<(), String>) -> Result<(), String> {
    let pairs = layout.pairs();
    for &(i, j) in &pairs {
        let (l, r) = two(chs, i, j);
        f(l, r)?;
    }
    for c in 0..chs.len() {
        let paired = pairs.iter().any(|&(i, j)| i == c || j == c);
        if paired || (!lfe && Some(c) == layout.lfe()) {
            continue;
        }
        let mut scratch = chs[c].to_vec();
        f(&mut *chs[c], &mut scratch)?;
    }
    Ok(())
}

/// Runs a chain of inserts over the bed's channels, in order.
pub fn run(effects: &[Effect], chs: &mut [&mut [f32]], layout: Layout, sr: f64) -> Result<(), String> {
    if chs.len() != layout.channels() {
        return Err(format!("{} channels on a {} bus", chs.len(), layout.name()));
    }
    for e in effects {
        match e {
            Effect::Eq { bands } => eq(bands, chs, sr),
            Effect::Compressor { threshold, ratio, attack, release, makeup, knee } => inserts::compressor(threshold, ratio, *attack, *release, makeup, *knee, chs, sr),
            Effect::Delay { time, feedback, mix, ping_pong, damp } => pairwise(chs, layout, false, |l, r| Ok(inserts::delay(*time, feedback, mix, *ping_pong, *damp, l, r, sr)))?,
            Effect::Reverb { space, mix, decay, damping, size } => inserts::reverb(space, mix, crate::fx::reverb::Shape { decay: *decay, damping: *damping, size: *size }, chs, layout, sr),
            Effect::Saturate { drive, mix } => inserts::saturate(drive, mix, chs, sr),
            Effect::Tape { wow, flutter, age } => inserts::tape(wow, flutter, age, chs, sr),
            Effect::Limiter { ceiling, release } => inserts::limiter(*ceiling, *release, chs, sr),
            Effect::Width { width, mono_below } => pairwise(chs, layout, false, |l, r| Ok(crate::fx::stereo::width(width, *mono_below, l, r, sr)))?,
            Effect::Convolution { ir, mix } => pairwise(chs, layout, false, |l, r| crate::fx::convolve::run(ir, mix, l, r, sr))?,
            Effect::Plugin { plugin } => {
                if layout != Layout::Stereo {
                    return Err(format!("the plugin {} ({}) is a stereo effect and this bus is {}: put it on a track (before the panner)", plugin.id, plugin.path, layout.name()));
                }
                let (l, r) = two(chs, 0, 1);
                crate::plugins::clap::render::rendered(plugin, &[], l, r, sr, true)?
            }
            Effect::Deess { freq, threshold, range } => crate::dialogue::dynamics::deess(chs, sr, *freq, *threshold, *range),
            Effect::Gate { threshold, ratio, range, attack, hold, release } => crate::dialogue::dynamics::gate(chs, sr, *threshold, *ratio, *range, *attack, *hold, *release),
            Effect::Leveller { target, max_gain, max_cut, speed, floor } => crate::dialogue::dynamics::leveller(chs, &layout.weights(), sr, *target, *max_gain, *max_cut, *speed, *floor),
            // What each repair found (the hum, the runs, the room) is reported by `inspect`, not here.
            Effect::Dehum { freq, harmonics, width } => pairwise(chs, layout, true, |l, r| {
                let _ = crate::dialogue::dehum::dehum(l, r, sr, *freq, *harmonics, *width);
                Ok(())
            })?,
            Effect::Declip { threshold } => chs.iter_mut().for_each(|c| {
                let _ = crate::dialogue::lsar::declip(c, *threshold);
            }),
            Effect::Declick { sensitivity, max_length } => {
                let n = ((max_length * sr / 1000.0) as usize).max(2);
                chs.iter_mut().for_each(|c| {
                    let _ = crate::dialogue::declick::declick(c, *sensitivity, n);
                })
            }
            Effect::Dereverb { amount, reduction, time } => pairwise(chs, layout, false, |l, r| {
                let _ = crate::dialogue::dereverb::dereverb(l, r, sr, *amount, *reduction, *time);
                Ok(())
            })?,
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::mix::schedule::Param;

    fn bed(n: usize) -> Vec<Vec<f32>> {
        (0..6).map(|c| (0..n).map(|i| (0.5 * ((i as f64) * (0.01 + 0.003 * c as f64)).sin()) as f32).collect()).collect()
    }

    #[test]
    fn a_surround_limiter_is_linked_and_time_effects_leave_the_lfe_dry() {
        let mut b = bed(9600);
        b[2].iter_mut().for_each(|v| *v *= 1.8); // a loud centre
        let before = b.clone();
        let fx = vec![Effect::Limiter { ceiling: -6.0, release: 50.0 }, Effect::Delay { time: 0.05, feedback: Param::Value(0.3), mix: Param::Value(0.5), ping_pong: true, damp: 8000.0 }];
        run(&fx, &mut crate::bed::slices(&mut b), Layout::Surround51, 48000.0).unwrap();
        let ceiling = 10f32.powf(-6.0 / 20.0);
        // The LFE got the limiter's gain only (no echo): its ratio to the source is the gain everywhere.
        let gain_at = |c: usize, i: usize| b[c][i] / before[c][i];
        for i in [1000, 4000, 9000] {
            if before[3][i].abs() > 0.05 && before[0][i].abs() > 0.05 {
                assert!(gain_at(3, i) <= 1.0 + 1e-4, "{}", gain_at(3, i));
            }
        }
        assert!(b[2][..2400].iter().all(|v| v.abs() <= ceiling * 1.0001), "the centre held at the ceiling before its echo starts");
        let stereo_plugin = Effect::Plugin { plugin: serde_json::from_str(r#"{"format":"clap","path":"x.clap","id":"x"}"#).unwrap() };
        let err = run(&[stereo_plugin], &mut crate::bed::slices(&mut b), Layout::Surround51, 48000.0).unwrap_err();
        assert!(err.contains("stereo effect") && err.contains("5.1"), "{err}");
    }
}
