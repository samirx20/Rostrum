//! One track from its clips (and the layers feeding it) to its place in the bed: tone, inserts, the
//! fader (the stereo pan law, the panner, or a bed as it is) and its reverb send. Block by block (tape::BLOCK
//! frames): the clips and feeders are summed into the block, every stage keeps its state between blocks (fx/state.rs),
//! and the block goes to the track's tape (tapewriter.rs), so a track's render holds its clips and a block, never
//! a copy of the whole track per stage. A chain with an effect that reads the whole take runs as one block.

use crate::bed::Layout;
use crate::fx::chain::Chain;
use crate::fx::dsp::{self, ToneFilter};
use crate::fx::reverb::BedReverb;
use crate::mix::schedule::{Param, Schedule, Track};
use crate::mix::tape::{Tape, BLOCK};
use crate::mix::tapewriter::TapeWriter;

/// The fader as a parameter: its automation, else its level.
fn fader(track: &Track) -> Param {
    track.automation.volume.clone().map(Param::Envelope).unwrap_or(Param::Value(track.volume))
}

/// The stereo fader: volume and pan (equal power, ×√2 at centre), moving when automated; `t0`: the block's first frame.
fn stereo_fader(track: &Track, l: &mut [f32], r: &mut [f32], sr: f64, t0: usize) {
    let a = &track.automation;
    if a.volume.is_some() || a.pan.is_some() {
        let vol = fader(track);
        let pan = a.pan.clone().map(Param::Envelope).unwrap_or(Param::Value(track.pan));
        dsp::each(l, r, |i, x| {
            let t = (t0 + i) as f64 / sr;
            let ang = (pan.at(t).clamp(-1.0, 1.0) + 1.0) * std::f64::consts::PI / 4.0;
            let v = vol.at(t);
            [x[0] * v * ang.cos() * std::f64::consts::SQRT_2, x[1] * v * ang.sin() * std::f64::consts::SQRT_2]
        });
    } else {
        dsp::fade_gain(l, r, sr, 0.0, 0.0, track.volume, track.pan);
    }
}

/// Frames `t0 .. t0 + n` of the clips (each at its start) and the feeders, summed in a fixed order: feeders, then clips.
fn sum(track: &Track, clips: &[Vec<Vec<f32>>], feeders: &[&Tape], chans: usize, t0: usize, n: usize) -> Result<Vec<Vec<f32>>, String> {
    let mut st = vec![vec![0.0f32; n]; chans];
    for f in feeders {
        for (dst, src) in st.iter_mut().zip(f.read(t0, n)?) {
            dst.iter_mut().zip(&src).for_each(|(d, s)| *d += *s);
        }
    }
    for (clip, c) in track.clips.iter().zip(clips) {
        let at = clip.start_sample;
        // The clip's frames that fall in this block.
        let (a, b) = (t0.max(at), (t0 + n).min(at + c.first().map_or(0, Vec::len)));
        if a >= b {
            continue;
        }
        for (dst, src) in st.iter_mut().zip(c) {
            dst[a - t0..b - t0].iter_mut().zip(&src[a - at..b - at]).for_each(|(d, s)| *d += *s);
        }
    }
    if track.invert {
        crate::mix::buses::invert(&mut st);
    }
    Ok(st)
}

/// One track from its clips (and the layers feeding it) to its place in the bed, reverb send included, on a tape.
/// A feeder stays stereo: its bus places the sum. With it, the tap before the fader when the track sends from
/// there (buses.rs).
/// `span`: a heard stretch (song frames, mix/window.rs): only those frames are worked out; the rest of the tape is silent.
pub(super) fn track_out(s: &Schedule, track: &Track, clips: &[Vec<Vec<f32>>], feeders: Vec<&Tape>, buf: usize, span: Option<(usize, usize)>) -> Result<(TapeWriter, Option<TapeWriter>), String> {
    let (sr, layout) = (s.sample_rate as f64, s.layout);
    let named = |e: String| format!("track \"{}\": {e}", track.name);
    let (chans, chain_layout) = if track.bed { (layout.channels(), layout) } else { (2, Layout::Stereo) };
    let mut chain = Chain::new(&track.effects, chain_layout, sr).map_err(named)?;
    // The bed the track lands in: a feeder's or a stereo song's is stereo; panned or placed, the song's bed.
    let placed = if track.bed || (track.into.is_none() && (track.surround.is_some() || layout != Layout::Stereo)) { layout } else { Layout::Stereo };
    let (lo, hi) = span.filter(|_| !chain.whole()).unwrap_or((0, buf));
    let mut out = TapeWriter::span(placed.channels(), buf, lo, hi)?;
    let mut pre = if crate::mix::buses::has_pre(track) { Some(TapeWriter::span(layout.channels(), buf, lo, hi)?) } else { None };
    let mut tone = ToneFilter::new(&track.tone, sr);
    let neutral = track.tone == "neutral" || track.tone.is_empty();
    let mut panner = match (&track.surround, track.into) {
        (Some(spec), None) if !track.bed => Some(crate::bed::panner::Panner::new(spec, &fader(track), layout, sr)),
        _ => None,
    };
    let mut send = BedReverb::new(placed.channels(), placed, &s.track_reverb_space, track.reverb, sr);
    let vol = fader(track);
    let step = if chain.whole() { buf.max(1) } else { BLOCK };
    for t0 in (lo..hi).step_by(step) {
        let n = step.min(hi - t0);
        // A bed track is played as it is: no layers feed it.
        let mut st = sum(track, clips, if track.bed { &[] } else { &feeders }, chans, t0, n)?;
        if track.bed {
            chain.block(&mut crate::bed::slices(&mut st), t0).map_err(named)?;
            if let Some(p) = &mut pre {
                p.push(&st)?;
            }
            for c in st.iter_mut() {
                c.iter_mut().enumerate().for_each(|(i, v)| *v = (*v as f64 * vol.at((t0 + i) as f64 / sr)) as f32);
            }
            send.block(&mut st);
            out.push(&st)?;
            continue;
        }
        let [mut l, mut r] = [std::mem::take(&mut st[0]), std::mem::take(&mut st[1])];
        if !neutral {
            dsp::each(&mut l, &mut r, |_, x| tone.process(x));
        }
        chain.block(&mut [&mut l, &mut r], t0).map_err(named)?;
        if let Some(p) = &mut pre {
            let mut chs = vec![l.clone(), r.clone()];
            chs.resize(layout.channels(), vec![0.0; n]);
            p.push(&chs)?;
        }
        let mut o = match &mut panner {
            Some(p) => p.block(&l, &r, t0),
            None => {
                stereo_fader(track, &mut l, &mut r, sr, t0);
                let mut bed = vec![l, r];
                // No position on a surround song: the stereo pan law into L / R, the rest of the bed silent.
                bed.resize(placed.channels(), vec![0.0f32; n]);
                bed
            }
        };
        send.block(&mut o);
        out.push(&o)?;
    }
    Ok((out, pre))
}
