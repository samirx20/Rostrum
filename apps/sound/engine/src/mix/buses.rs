//! Buses, aux sends and routing (docs/NATIVE_ENGINE.md § Buses, sends and routing). A track reaches the
//! master directly or through a bus (`output`), and sends copies of itself to buses (`sends`: post-fader,
//! its final output; pre-fader, the tap before its fader). Buses run children before parents: their
//! inputs summed, their inserts on the bed, their fader and pan, then their output (a parent bus or the
//! master). A schedule without buses never comes here (the master sum in render/ is the old one).

use serde::Deserialize;

use crate::bed::{self, Layout};
use crate::mix::render::stats::{track_stats, TrackStats};
use crate::mix::schedule::{Automation, Effect, Param, Schedule, Track};

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Bus {
    pub name: String,
    pub volume: f64,
    pub pan: f64,
    /// Inserts on the summed input, before the fader (the one effect table).
    #[serde(default)]
    pub effects: Vec<Effect>,
    #[serde(default)]
    pub automation: Automation,
    /// The bus it feeds (an index in `buses`); None: the master.
    #[serde(default)]
    pub output: Option<usize>,
    /// Silent: its inputs still render (they drive ducks), nothing leaves it.
    #[serde(default)]
    pub muted: bool,
}

/// A copy of a track into a bus: `level` (a number or an envelope), from before the fader when `pre`.
#[derive(Deserialize, Clone, Debug)]
pub struct Send {
    pub bus: usize,
    pub level: Param,
    #[serde(default)]
    pub pre: bool,
}

/// A bus stem: the master hears only bus `bus`'s output, or (None) only the tracks routed straight to it.
#[derive(Deserialize, Clone, Copy, Debug)]
pub struct Tap {
    pub bus: Option<usize>,
}

/// The master fader: its lane, else its level (a constant reads back exactly, so a mix without a lane is unchanged).
pub fn master_fader(s: &Schedule) -> Param {
    s.master_automation.clone().map(Param::Envelope).unwrap_or(Param::Value(s.master_volume))
}

/// Whether a track's output is summed into the master directly (always so without buses or a tap).
pub fn direct(s: &Schedule, t: &Track) -> bool {
    t.output.is_none() && s.tap.map_or(true, |tap| tap.bus.is_none())
}

/// Whether a track feeds any bus (its output kept for the buses).
pub fn feeds_buses(t: &Track) -> bool {
    t.output.is_some() || !t.sends.is_empty()
}

/// Whether a track sends from before its fader (its tap is rendered, so it is never read from the cache).
pub fn has_pre(t: &Track) -> bool {
    t.sends.iter().any(|x| x.pre)
}

/// The buses children first (each after every bus feeding it); a loop of outputs or an index that is not a
/// bus is an error naming it.
pub fn order(s: &Schedule) -> Result<Vec<usize>, String> {
    let n = s.buses.len();
    let bad = |what: String, k: usize| if k >= n { Err(format!("{what} goes to bus {k}; there are {n} buses")) } else { Ok(()) };
    for t in &s.tracks {
        if let Some(k) = t.output {
            bad(format!("track \"{}\"", t.name), k)?;
        }
        for x in &t.sends {
            bad(format!("a send of track \"{}\"", t.name), x.bus)?;
        }
    }
    let mut depth = vec![0usize; n];
    for b in 0..n {
        let mut path = vec![b];
        let mut at = b;
        while let Some(next) = s.buses[at].output {
            bad(format!("bus \"{}\"", s.buses[at].name), next)?;
            if path.contains(&next) {
                path.push(next);
                let names: Vec<String> = path[path.iter().position(|&p| p == next).unwrap()..].iter().map(|&p| format!("\"{}\"", s.buses[p].name)).collect();
                return Err(format!("bus routing loops: {}", names.join(" → ")));
            }
            path.push(next);
            at = next;
        }
        depth[b] = path.len() - 1;
    }
    let mut out: Vec<usize> = (0..n).collect();
    out.sort_by(|a, b| depth[*b].cmp(&depth[*a]));
    Ok(out)
}

/// The stereo tap before a track's fader, on the bed's front pair (L / R) — for its pre-fader sends.
pub fn pre_tap(t: &Track, l: &[f32], r: &[f32], layout: Layout) -> Option<Vec<Vec<f32>>> {
    has_pre(t).then(|| {
        let mut chs = vec![l.to_vec(), r.to_vec()];
        chs.resize(layout.channels(), vec![0.0; l.len()]);
        chs
    })
}

/// Polarity flipped (phase invert).
pub fn invert(chs: &mut [Vec<f32>]) {
    chs.iter_mut().for_each(|c| c.iter_mut().for_each(|v| *v = -*v));
}

/// A track's output summed into the master, as the master sum does it.
pub fn add_into(master: &mut [Vec<f32>], chs: &[Vec<f32>]) {
    add(master, chs, None, 0.0);
}

fn add(into: &mut [Vec<f32>], from: &[Vec<f32>], level: Option<&Param>, sr: f64) {
    for (dst, src) in into.iter_mut().zip(from) {
        match level {
            None => dst.iter_mut().zip(src).for_each(|(d, s)| *d += *s),
            Some(Param::Value(g)) => dst.iter_mut().zip(src).for_each(|(d, s)| *d = (*d as f64 + *s as f64 * g) as f32),
            Some(p) => dst.iter_mut().zip(src).enumerate().for_each(|(i, (d, s))| *d = (*d as f64 + *s as f64 * p.at(i as f64 / sr)) as f32),
        }
    }
}

/// A bus' fader: its volume (or its automation) on every channel, its pan (the equal-power law, ×√2 at
/// centre) on the front pair.
fn fader(bus: &Bus, chs: &mut [Vec<f32>], sr: f64) {
    let vol = bus.automation.volume.clone().map(Param::Envelope).unwrap_or(Param::Value(bus.volume));
    let pan = bus.automation.pan.clone().map(Param::Envelope).unwrap_or(Param::Value(bus.pan));
    for (c, ch) in chs.iter_mut().enumerate() {
        ch.iter_mut().enumerate().for_each(|(i, v)| {
            let t = i as f64 / sr;
            let g = vol.at(t);
            let side = if c < 2 {
                let ang = (pan.at(t).clamp(-1.0, 1.0) + 1.0) * std::f64::consts::PI / 4.0;
                std::f64::consts::SQRT_2 * if c == 0 { ang.cos() } else { ang.sin() }
            } else {
                1.0
            };
            *v = (*v as f64 * g * side) as f32;
        });
    }
}

/// The buses mixed and their outputs added into `master` (the summed direct tracks): `outs[k]` is track k's
/// output when it feeds a bus, `pres[k]` its pre-fader tap. Returns each bus' figures, in schedule order.
pub fn mix(s: &Schedule, outs: Vec<Option<Vec<Vec<f32>>>>, pres: &[Option<Vec<Vec<f32>>>], master: &mut [Vec<f32>]) -> Result<Vec<TrackStats>, String> {
    if s.buses.is_empty() || matches!(s.tap, Some(Tap { bus: None })) {
        return Ok(vec![]);
    }
    let (sr, layout, buf) = (s.sample_rate as f64, s.layout, master[0].len());
    let order = order(s)?;
    let mut inputs: Vec<Vec<Vec<f32>>> = s.buses.iter().map(|_| vec![vec![0.0f32; buf]; layout.channels()]).collect();
    for (k, t) in s.tracks.iter().enumerate() {
        let Some(chs) = &outs[k] else { continue };
        if let Some(b) = t.output {
            add(&mut inputs[b], chs, None, sr);
        }
        for x in &t.sends {
            let src = if x.pre { pres[k].as_ref().ok_or_else(|| format!("track \"{}\": its pre-fader send has no tap", t.name))? } else { chs };
            add(&mut inputs[x.bus], src, Some(&x.level), sr);
        }
    }
    let mut stats: Vec<Option<TrackStats>> = s.buses.iter().map(|_| None).collect();
    for b in order {
        let bus = &s.buses[b];
        let mut chs = std::mem::take(&mut inputs[b]);
        if bus.muted {
            chs.iter_mut().for_each(|c| c.fill(0.0));
        } else {
            crate::fx::chain::run(&bus.effects, &mut bed::slices(&mut chs), layout, sr).map_err(|e| format!("bus \"{}\": {e}", bus.name))?;
            fader(bus, &mut chs, sr);
        }
        stats[b] = Some(track_stats(&bus.name, &chs, s.total_samples, sr, layout));
        match (s.tap, bus.output) {
            (Some(Tap { bus: Some(tapped) }), _) if tapped == b => add(master, &chs, None, sr),
            (Some(_), None) => {}
            (None, None) => add(master, &chs, None, sr),
            (_, Some(parent)) => add(&mut inputs[parent], &chs, None, sr),
        }
    }
    Ok(stats.into_iter().flatten().collect())
}
