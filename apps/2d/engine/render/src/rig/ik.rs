//! Two-bone IK (RIG.md › Evaluation 2): the law of cosines turns the upper and lower bone so the lower tip reaches
//! the target, blended with the FK pose by `mix`; `pin` holds the target from the moment the pin turned on.

use serde_json::Value;

use super::math::{dist, heading, wrap, Pt};
use super::pose::{num, text, Pose};
use crate::scene::eval::{props_at, track_value};
use crate::scene::Node;

/// An IK chain after the solve: its (held) target and where the lower tip ended up, rig px.
pub struct IkOut {
    pub id: String,
    pub target: Pt,
    pub tip: Pt,
}

/// Every chain in the order of its upper bone's depth, each re-posing the bones below it.
pub fn apply(pose: &mut Pose, rig: &Node, t: f64) {
    let mut chains: Vec<(usize, usize, usize, &Node)> = rig.rig.iter().filter(|p| p.kind == "ik").filter_map(|ik| {
        let lo = pose.index(ik.props.get("bone").and_then(Value::as_str).unwrap_or(""))?;
        let up = pose.parent[lo]?;
        Some((pose.depth(up), up, lo, ik))
    }).collect();
    chains.sort_by_key(|c| c.0);
    for (_, up, lo, ik) in chains {
        let p = props_at(ik, t);
        let target = held_target(ik, t, num(&p, "pin") >= 0.5).unwrap_or((num(&p, "targetX"), num(&p, "targetY")));
        if text(&p, "mode") == "ik" {
            solve(pose, up, lo, target, text(&p, "bend") == "clockwise", num(&p, "mix").clamp(0.0, 1.0));
        }
        let tip = pose.tip(lo);
        pose.iks.push(IkOut { id: ik.id.clone(), target, tip });
    }
}

/// Turns `up` and `lo` so `lo`'s tip reaches `target` (straight at it when it is out of reach), by `mix` of the way
/// from the FK pose (shortest angle). Clockwise: the chain turns clockwise on screen at the middle joint.
pub fn solve(pose: &mut Pose, up: usize, lo: usize, target: Pt, clockwise: bool, mix: f64) {
    if mix <= 0.0 {
        return;
    }
    let (a, b, c) = (pose.pivot(up), pose.pivot(lo), pose.tip(lo));
    let (l1, l2) = (dist(a, b), dist(b, c));
    let phi = heading(a, target);
    let d = dist(a, target).clamp((l1 - l2).abs(), l1 + l2);
    let cos_a = if l1 * d > 1e-12 { ((l1 * l1 + d * d - l2 * l2) / (2.0 * l1 * d)).clamp(-1.0, 1.0) } else { 1.0 };
    let side = if clockwise { 1.0 } else { -1.0 };
    let up_ik = phi - side * cos_a.acos();
    let joint = (a.0 + l1 * up_ik.cos(), a.1 + l1 * up_ik.sin());
    let reach = (a.0 + d * phi.cos(), a.1 + d * phi.sin());
    let bend_ik = heading(joint, reach) - up_ik;
    let up_fk = heading(a, b);
    let bend_fk = heading(b, c) - up_fk;
    pose.turn_from(up, (mix * wrap(up_ik - up_fk)).to_degrees(), a);
    let b = pose.pivot(lo);
    pose.turn_from(lo, (mix * wrap(bend_ik - bend_fk)).to_degrees(), b);
}

/// While the pin is on, the target as it was when the pin last turned on (its keys and the body may move on).
/// None when the pin is off.
fn held_target(ik: &Node, t: f64, on_now: bool) -> Option<Pt> {
    if !on_now {
        return None;
    }
    let p = props_at(ik, pin_start(ik, t));
    Some((num(&p, "targetX"), num(&p, "targetY")))
}

/// The start of the stretch of time up to `t` where pin ≥ 0.5 (−∞: on all along). Each stretch between keys is
/// sampled back from `t`; the turn-on found is narrowed by halving, and lands on a key's time when it is one.
fn pin_start(ik: &Node, t: f64) -> f64 {
    let Some((_, keys)) = ik.anim.iter().find(|(f, _)| f == "pin") else { return f64::NEG_INFINITY };
    let on = |s: f64| track_value(keys, s).as_f64().unwrap_or(0.0) >= 0.5;
    let mut hi = t;
    for edge in keys.iter().rev().map(|k| k.t).filter(|&k| k < t) {
        for i in 1..=64 {
            let s = hi - (hi - edge) * i as f64 / 64.0;
            if !on(s) {
                let (mut off, mut lit) = (s, hi - (hi - edge) * (i - 1) as f64 / 64.0);
                for _ in 0..60 {
                    let m = 0.5 * (off + lit);
                    if on(m) { lit = m } else { off = m }
                }
                return keys.iter().map(|k| k.t).find(|&k| (k - lit).abs() < 1e-6 && on(k)).unwrap_or(lit);
            }
        }
        hi = edge;
    }
    f64::NEG_INFINITY
}
