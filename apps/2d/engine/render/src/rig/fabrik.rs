//! Long IK chains (RIG.md › Long chains): an ik whose `chain` is more than two bones (a spine, a tail, an arm with a
//! hand) is solved by FABRIK (forward and backward reaching) on the posed joints, the turns found blended with the
//! pose by `mix` (shortest angle). A chain that starts straight curls `bend`'s way first: it has no way to fold else.

use std::f64::consts::FRAC_PI_2;

use super::math::{dist, heading, wrap, Pt};
use super::pose::Pose;

/// FABRIK passes at most, and the tip's distance from the target that ends them early, px.
const TRIES: usize = 24;
const CLOSE: f64 = 0.01;
/// A joint turning less than this is straight: it is pushed sideways by `CURL` of the bone above it.
const STRAIGHT_DEG: f64 = 2.0;
const CURL: f64 = 0.02;

/// Turns the bones of `chain` (top first) so the last one's tip reaches `target`, by `mix` of the way.
pub fn solve(pose: &mut Pose, chain: &[usize], target: Pt, clockwise: bool, mix: f64) {
    if mix <= 0.0 {
        return;
    }
    let last = chain[chain.len() - 1];
    let joints: Vec<Pt> = chain.iter().map(|&b| pose.pivot(b)).chain([pose.tip(last)]).collect();
    let solved = reach(&joints, target, clockwise);
    let mut before = 0.0;
    for (i, &b) in chain.iter().enumerate() {
        let world = mix * wrap(heading(solved[i], solved[i + 1]) - heading(joints[i], joints[i + 1]));
        let p = pose.pivot(b);
        pose.turn_from(b, (world - before).to_degrees(), p);  // a bone turned already by its parent's turn: only the rest
        before = world;
    }
}

/// The joints (base first) moved so the last reaches `goal`, the bone lengths kept, the base fixed.
pub fn reach(joints: &[Pt], goal: Pt, clockwise: bool) -> Vec<Pt> {
    let mut pts = joints.to_vec();
    let lens: Vec<f64> = pts.windows(2).map(|w| dist(w[0], w[1])).collect();
    let side = if clockwise { 1.0 } else { -1.0 };
    for i in 1..pts.len() - 1 {
        let (a, b) = (heading(pts[i - 1], pts[i]), heading(pts[i], pts[i + 1]));
        if wrap(b - a).abs() < STRAIGHT_DEG.to_radians() {
            let n = a + side * FRAC_PI_2;
            pts[i].0 += CURL * lens[i - 1] * n.cos();
            pts[i].1 += CURL * lens[i - 1] * n.sin();
        }
    }
    let base = pts[0];
    if dist(base, goal) >= lens.iter().sum::<f64>() {
        let h = heading(base, goal);
        for (i, l) in lens.iter().enumerate() {
            pts[i + 1] = (pts[i].0 + l * h.cos(), pts[i].1 + l * h.sin());
        }
        return pts;
    }
    let n = pts.len();
    for _ in 0..TRIES {
        pts[n - 1] = goal;
        for i in (0..n - 1).rev() {
            pts[i] = toward(pts[i + 1], pts[i], lens[i]);
        }
        pts[0] = base;
        for i in 0..n - 1 {
            pts[i + 1] = toward(pts[i], pts[i + 1], lens[i]);
        }
        if dist(pts[n - 1], goal) < CLOSE {
            break;
        }
    }
    pts
}

/// `free` moved along the line from `fixed` to be `length` away from it.
fn toward(fixed: Pt, free: Pt, length: f64) -> Pt {
    let d = dist(fixed, free).max(1e-9);
    (fixed.0 + (free.0 - fixed.0) * length / d, fixed.1 + (free.1 - fixed.1) * length / d)
}
