//! Trails (MOTION.md § Trails): echo copies of a layer drawn just behind it, each the layer itself at an earlier
//! time. Copy i is the whole comp evaluated at t − i·spacing/fps with that layer taken out of it (so a rig-bound or
//! nested layer's copies keep their pose), faded by fade^i. A copy of a layer that wasn't showing then is left out.

use serde_json::Value;

use super::Plan;
use crate::scene::eval::{self, Item};
use crate::scene::Node;

/// A trail copy's id (and its children's): unique in the stage, made once per stage by `Plan::of`.
pub(super) fn copy_id(id: &str, i: usize) -> String {
    format!("{id}~trail{i}")
}

/// Every layer under `it` with a trail gets its copies, oldest first, inserted just before it in its parent's
/// layers (so they draw behind it). Children first, so a trail inside a group is in the group's own frame.
pub(super) fn add<'a>(plan: &'a Plan, root: &'a Node, it: &mut Item<'a>, fps: f64) {
    let mut i = 0;
    while i < it.layers.len() {
        add(plan, root, &mut it.layers[i], fps);
        let copies = echoes(plan, root, &it.layers[i], fps);
        let n = copies.len();
        for (k, c) in copies.into_iter().enumerate() {
            it.layers.insert(i + k, c);
        }
        i += n + 1;
    }
}

/// The layer's trail copies, oldest (faintest) first; none without a trail.
fn echoes<'a>(plan: &'a Plan, root: &'a Node, layer: &Item<'a>, fps: f64) -> Vec<Item<'a>> {
    let Some(trail) = layer.effects.iter().find(|e| e.kind == "trail") else { return vec![] };
    if layer.kind == "camera" {
        return vec![];
    }
    let (n, spacing, fade) = (trail.num("copies") as usize, trail.num("spacing"), trail.num("fade"));
    let mut out = vec![];
    for i in (1..=n).rev() {
        let ti = layer.t - i as f64 * spacing / fps;
        let Some(tree) = eval::at(root, ti) else { continue };
        let Some(found) = super::find(&tree, layer.id) else { continue };
        let mut copy = found.clone();
        if plan.smear {
            // A smearing layer's copies are smeared as it was then.
            if let Some(prev) = eval::at(root, ti - 1.0 / fps) {
                super::smear::measure(&mut copy, &prev);
            }
        }
        rename(&mut copy, plan, i);
        let faded = copy.num("opacity") * fade.powi(i as i32);
        copy.props.insert("opacity".into(), Value::from(faded));
        out.push(copy);
    }
    out
}

/// The copy and everything in it under its copy ids; a copy has no trail of its own.
fn rename<'a>(it: &mut Item<'a>, plan: &'a Plan, i: usize) {
    it.id = plan.names.get(copy_id(it.id, i).as_str()).map(String::as_str).expect("Plan::of names every trail copy");
    it.effects.retain(|e| e.kind != "trail");
    for c in it.effects.iter_mut().chain(&mut it.masks).chain(&mut it.layers) {
        rename(c, plan, i);
    }
}
