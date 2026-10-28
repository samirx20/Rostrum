//! The insert chain over any bed (bed/): a clip's or track's stereo signal, or a surround master.
//! Each effect runs the way it means on several channels:
//! - linked (one gain for every channel, so the image does not shift): compressor, limiter, gate,
//!   de-esser, leveller (its loudness BS.1770-weighted);
//! - per channel: EQ, saturation, tape (its record surface drawn apart on each channel), declip, declick;
//! - per left/right pair, a centre channel alone: delay (ping-pong bounces inside a pair), convolution
//!   (the IR's left side on the left speaker), dehum, dereverb; time-based effects leave the LFE dry;
//! - the reverb insert: one reverb over the mains (dsp.rs);
//! - a CLAP / VST3 effect is stereo: on a surround bed it is an error naming it.
//! A chain is built once (`Chain::new`) and run block by block, each effect keeping its state (state.rs). The
//! effects that read the whole take at once (the dialogue repairs and dynamics with their look-ahead, a plugin
//! rendered offline) make the chain `whole`: its owner then runs it over the whole signal as one block.

use crate::bed::Layout;
use crate::fx::convolve::Conv;
use crate::fx::eq::Eq;
use crate::fx::inserts::{Compressor, Delay, Limiter, ReverbInsert, Saturate};
use crate::fx::state::{two, Insert, Pairwise};
use crate::fx::stereo::Width;
use crate::fx::tapefx::TapeFx;
use crate::mix::schedule::Effect;

/// Runs a chain of inserts over a stereo buffer, in order.
pub fn stereo(effects: &[Effect], l: &mut [f32], r: &mut [f32], sr: f64) -> Result<(), String> {
    run(effects, &mut [l, r], Layout::Stereo, sr)
}

/// Runs a chain of inserts over the whole of the bed's channels, in order.
pub fn run(effects: &[Effect], chs: &mut [&mut [f32]], layout: Layout, sr: f64) -> Result<(), String> {
    if chs.len() != layout.channels() {
        return Err(format!("{} channels on a {} bus", chs.len(), layout.name()));
    }
    Chain::new(effects, layout, sr)?.block(chs, 0)
}

pub struct Chain {
    stages: Vec<Box<dyn Insert>>,
    whole: bool,
}

impl Chain {
    /// The chain's effects with fresh state (a stereo plugin on a surround bed is an error naming it).
    pub fn new(effects: &[Effect], layout: Layout, sr: f64) -> Result<Chain, String> {
        let n = layout.channels();
        let mut whole = false;
        let mut stages: Vec<Box<dyn Insert>> = vec![];
        for e in effects {
            let stage: Box<dyn Insert> = match e {
                Effect::Eq { bands } => Box::new(Eq::new(bands, n, sr)),
                Effect::Compressor { threshold, ratio, attack, release, makeup, knee } => Box::new(Compressor::new(threshold, ratio, *attack, *release, makeup, *knee, sr)),
                Effect::Delay { time, feedback, mix, ping_pong, damp } => {
                    let mut p = Pairwise::new(layout, n, false, || Delay::new(*time, feedback, mix, *ping_pong, *damp, sr));
                    Box::new(Each(move |chs: &mut [&mut [f32]], t0| p.run(chs, |d, l, r| Ok(d.pair(l, r, t0)))))
                }
                Effect::Reverb { space, mix, decay, damping, size } => Box::new(ReverbInsert::new(space, mix, crate::fx::reverb::Shape { decay: *decay, damping: *damping, size: *size }, n, layout, sr)),
                Effect::Saturate { drive, mix } => Box::new(Saturate { drive: drive.clone(), mix: mix.clone(), sr }),
                Effect::Tape { wow, flutter, age, hiss, crackle } => Box::new(TapeFx::new([wow, flutter, age, hiss, crackle], n, sr)),
                Effect::Limiter { ceiling, release } => Box::new(Limiter::new(*ceiling, *release, sr)),
                Effect::Width { width, mono_below } => {
                    let mut p = Pairwise::new(layout, n, false, || Width::new(width, *mono_below, sr));
                    Box::new(Each(move |chs: &mut [&mut [f32]], t0| p.run(chs, |w, l, r| Ok(w.pair(l, r, t0)))))
                }
                Effect::Convolution { ir, mix } => {
                    let sides = crate::fx::convolve::sides(ir, sr)?;
                    let mut p = Pairwise::new(layout, n, false, || Conv::new(sides.clone(), mix, sr));
                    Box::new(Each(move |chs: &mut [&mut [f32]], t0| p.run(chs, |c, l, r| Ok(c.pair(l, r, t0)))))
                }
                Effect::Plugin { plugin } if layout != Layout::Stereo => {
                    return Err(format!("the plugin {} ({}) is a stereo effect and this bus is {}: put it on a track (before the panner)", plugin.id, plugin.path, layout.name()));
                }
                _ => {
                    whole = true;
                    Box::new(Whole { effect: e.clone(), layout, sr, ran: false })
                }
            };
            stages.push(stage);
        }
        Ok(Chain { stages, whole })
    }

    /// The chain reads the whole signal at once: run it as one block.
    pub fn whole(&self) -> bool {
        self.whole
    }

    /// One block of every channel, in place (`t0`: its first frame).
    pub fn block(&mut self, chs: &mut [&mut [f32]], t0: usize) -> Result<(), String> {
        for s in self.stages.iter_mut() {
            s.block(chs, t0)?;
        }
        Ok(())
    }
}

/// A stage from a closure (the pair effects over a bed).
struct Each<F>(F);

impl<F: FnMut(&mut [&mut [f32]], usize) -> Result<(), String> + Send> Insert for Each<F> {
    fn block(&mut self, chs: &mut [&mut [f32]], t0: usize) -> Result<(), String> {
        (self.0)(chs, t0)
    }
}

/// An effect that reads the whole take (look-ahead dynamics, the repairs, an offline plugin): one block only.
struct Whole {
    effect: Effect,
    layout: Layout,
    sr: f64,
    ran: bool,
}

impl Insert for Whole {
    fn block(&mut self, chs: &mut [&mut [f32]], _t0: usize) -> Result<(), String> {
        if std::mem::replace(&mut self.ran, true) {
            return Err("an effect that reads the whole take was run in blocks (an engine fault)".into());
        }
        whole_effect(&self.effect, chs, self.layout, self.sr)
    }
}

fn whole_effect(e: &Effect, chs: &mut [&mut [f32]], layout: Layout, sr: f64) -> Result<(), String> {
    let n = layout.channels();
    match e {
        Effect::Plugin { plugin } => {
            let (l, r) = two(chs, 0, 1);
            crate::plugins::clap::render::rendered(plugin, &[], l, r, sr, true)?
        }
        Effect::Deess { freq, threshold, range } => crate::dialogue::dynamics::deess(chs, sr, *freq, *threshold, *range),
        Effect::Gate { threshold, ratio, range, attack, hold, release } => crate::dialogue::dynamics::gate(chs, sr, *threshold, *ratio, *range, *attack, *hold, *release),
        Effect::Leveller { target, max_gain, max_cut, speed, floor } => crate::dialogue::dynamics::leveller(chs, &layout.weights(), sr, *target, *max_gain, *max_cut, *speed, *floor),
        // What each repair found (the hum, the runs, the room) is reported by `inspect`, not here.
        Effect::Dehum { freq, harmonics, width } => Pairwise::new(layout, n, true, || ()).run(chs, |_, l, r| {
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
        Effect::Dereverb { amount, reduction, time } => Pairwise::new(layout, n, false, || ()).run(chs, |_, l, r| {
            let _ = crate::dialogue::dereverb::dereverb(l, r, sr, *amount, *reduction, *time);
            Ok(())
        })?,
        _ => unreachable!("block effects are built in Chain::new"),
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
