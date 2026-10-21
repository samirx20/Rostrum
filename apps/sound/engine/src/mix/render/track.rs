//! One track from its clips (and the layers feeding it) to its place in the bed: tone, inserts, the
//! fader (the stereo pan law, the panner, or a bed as it is) and its reverb send.

use crate::bed::Layout;
use crate::fx;
use crate::fx::dsp;
use crate::fx::reverb;
use crate::mix::schedule::{Param, Schedule, Track};

/// The fader as a parameter: its automation, else its level.
fn fader(track: &Track) -> Param {
    track.automation.volume.clone().map(Param::Envelope).unwrap_or(Param::Value(track.volume))
}

/// The stereo fader: volume and pan (equal power, ×√2 at centre), moving when automated.
fn stereo_fader(track: &Track, l: &mut [f32], r: &mut [f32], sr: f64) {
    let a = &track.automation;
    if a.volume.is_some() || a.pan.is_some() {
        let vol = fader(track);
        let pan = a.pan.clone().map(Param::Envelope).unwrap_or(Param::Value(track.pan));
        dsp::each(l, r, |i, x| {
            let t = i as f64 / sr;
            let ang = (pan.at(t).clamp(-1.0, 1.0) + 1.0) * std::f64::consts::PI / 4.0;
            let v = vol.at(t);
            [x[0] * v * ang.cos() * std::f64::consts::SQRT_2, x[1] * v * ang.sin() * std::f64::consts::SQRT_2]
        });
    } else {
        dsp::fade_gain(l, r, sr, 0.0, 0.0, track.volume, track.pan);
    }
}

/// One track from its clips (and the layers feeding it) to its place in the bed, reverb send included.
/// A feeder stays stereo: its bus places the sum. With it, the tap before the fader when the track sends
/// from there (buses.rs).
pub(super) fn track_out(s: &Schedule, track: &Track, clips: Vec<Vec<Vec<f32>>>, feeders: Vec<&Vec<Vec<f32>>>, buf: usize) -> Result<(Vec<Vec<f32>>, Option<Vec<Vec<f32>>>), String> {
    let (sr, layout) = (s.sample_rate as f64, s.layout);
    let add = |into: &mut [Vec<f32>], from: &[Vec<f32>], at: usize| {
        for (dst, src) in into.iter_mut().zip(from) {
            let n = src.len().min(buf.saturating_sub(at));
            for i in 0..n {
                dst[at + i] += src[i];
            }
        }
    };
    if track.bed {
        let mut bed = vec![vec![0.0f32; buf]; layout.channels()];
        for (clip, c) in track.clips.iter().zip(&clips) {
            add(&mut bed, c, clip.start_sample);
        }
        if track.invert {
            crate::mix::buses::invert(&mut bed);
        }
        crate::fx::chain::run(&track.effects, &mut crate::bed::slices(&mut bed), layout, sr).map_err(|e| format!("track \"{}\": {e}", track.name))?;
        let pre = crate::mix::buses::has_pre(track).then(|| bed.clone());
        let vol = fader(track);
        for c in bed.iter_mut() {
            c.iter_mut().enumerate().for_each(|(i, v)| *v = (*v as f64 * vol.at(i as f64 / sr)) as f32);
        }
        reverb::reverb_bed(&mut bed, layout, &s.track_reverb_space, track.reverb, sr);
        return Ok((bed, pre));
    }
    let mut st = vec![vec![0.0f32; buf]; 2];
    // A bus: its feeders' outputs (after their own effects, level and pan) are its input.
    for f in feeders {
        add(&mut st, f, 0);
    }
    for (clip, c) in track.clips.iter().zip(&clips) {
        add(&mut st, c, clip.start_sample);
    }
    if track.invert {
        crate::mix::buses::invert(&mut st);
    }
    let [mut l, mut r] = [std::mem::take(&mut st[0]), std::mem::take(&mut st[1])];
    dsp::tone(&mut l, &mut r, &track.tone, sr);
    fx::chain::stereo(&track.effects, &mut l, &mut r, sr).map_err(|e| format!("track \"{}\": {e}", track.name))?;
    let pre = crate::mix::buses::pre_tap(track, &l, &r, layout);
    let mut out = match (&track.surround, track.into, layout) {
        (Some(spec), None, _) => crate::bed::panner::pan(&l, &r, spec, &fader(track), layout, sr),
        (None, None, Layout::Surround51 | Layout::Surround71) => {
            // No position: the stereo pan law into L / R, the rest of the bed silent.
            stereo_fader(track, &mut l, &mut r, sr);
            let mut bed = vec![l, r];
            bed.resize(layout.channels(), vec![0.0f32; buf]);
            bed
        }
        _ => {
            stereo_fader(track, &mut l, &mut r, sr);
            vec![l, r]
        }
    };
    let placed = if out.len() == 2 { Layout::Stereo } else { layout };
    reverb::reverb_bed(&mut out, placed, &s.track_reverb_space, track.reverb, sr);
    Ok((out, pre))
}
