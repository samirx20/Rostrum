//! Motion blur, smears and trails (apps/2d/MOTION.md). All three read the layer's real motion: the comp evaluated
//! at other times (eval.rs `at`), so a rig-bound layer's motion is its posed motion. The shutter (shutter.rs) picks
//! the sub-frame times scene_serve.rs `stage_at` writes a stage for, as many as the motion on screen needs (steps.rs); trails (trail.rs) and smears (smear.rs) are a
//! post-pass on the evaluated tree, run by scene_serve.rs `markup` between `eval::at` and `stage::stage`.

mod shutter;
mod smear;
mod steps;
mod trail;
#[cfg(test)]
mod tests;

use std::collections::HashSet;

use crate::scene::eval::Item;
use crate::scene::fields::Field;
use crate::scene::fields::Kind::{Choice, Number, Toggle};
use crate::scene::Node;

pub use shutter::{sample_times, shutter};
pub use smear::smear_css;

/// The comp's shutter fields (motion blur). The comp is never keyed (fields.rs `animatable`).
pub const COMP: &[Field] = &[("shutter", Number), ("shutterSamples", Number)];

pub const TRAIL: &[Field] = &[("copies", Number), ("spacing", Number), ("fade", Number)];
pub const SMEAR: &[Field] = &[
    ("amount", Number), ("max", Number), ("minSpeed", Number), ("stretch", Choice(&["behind", "both"])), ("keepArea", Toggle),
];

/// A motion effect's fields; None for any other type.
pub fn fields(kind: &str) -> Option<&'static [Field]> {
    match kind {
        "trail" => Some(TRAIL),
        "smear" => Some(SMEAR),
        _ => None,
    }
}

/// Whether keys may drive the field (true for every other type): a trail's number of copies describes the
/// item (the copies' ids are made from it), so it is still.
pub fn animatable(kind: &str, name: &str) -> bool {
    !(kind == "trail" && name == "copies")
}

/// What the post-pass needs, read once per stage: the trail copies' ids (owned here, so the evaluated tree can
/// borrow them as it borrows the scene's ids) and whether any layer smears.
pub struct Plan {
    names: HashSet<String>,
    smear: bool,
}

impl Plan {
    /// The scene's motion effects, checked: a trail's copies a whole number 1..=32.
    pub fn of(comp: &Node) -> Result<Plan, String> {
        let mut names = HashSet::new();
        let mut smear = false;
        comp.walk(&mut |n| {
            for e in &n.effects {
                match e.kind {
                    "smear" => smear = true,
                    "trail" => {
                        let c = e.props["copies"].as_f64().unwrap_or(0.0);
                        if c.fract() != 0.0 || !(1.0..=32.0).contains(&c) {
                            return Err(format!("{}.copies: {c} is not a whole number from 1 to 32", e.id));
                        }
                        for i in 1..=c as usize {
                            n.walk(&mut |d| {
                                names.insert(trail::copy_id(&d.id, i));
                                Ok(())
                            })?;
                        }
                    }
                    _ => {}
                }
            }
            Ok(())
        })?;
        Ok(Plan { names, smear })
    }

    /// The comp at its time (`eval::at`) → its trail copies added and its smears measured.
    pub fn apply<'a>(&'a self, root: &'a Node, comp: &mut Item<'a>) {
        let fps = fps(root);
        if self.smear {
            if let Some(prev) = crate::scene::eval::at(root, comp.t - 1.0 / fps) {
                smear::measure(comp, &prev);
            }
        }
        if !self.names.is_empty() {
            trail::add(self, root, comp, fps);
        }
    }
}

/// The sub-frame times of the frame at `t` (none: no motion blur), and how many of them need a stage of their own. The
/// comp's `shutterSamples` (Blur steps) is the fewest: a frame whose layers move further on screen gets more (steps.rs).
/// A request's own `shutterSamples` is the exact count (1 = a fast preview while playing, or a timing test).
/// How many need a stage of their own (MOTION.md › Motion blur › Steps follow the motion):
/// the steps the layers' own moves need (steps.rs `own_steps`). When the frame's move needs more sub-frames than that,
/// the sub-frames fall into that many equal groups, in order; within a group the layers are as at the group's middle
/// sub-frame and only the frame moves (scene_serve.rs `stage_at`), so serve.rs draws each layer once per group and
/// moves the picture. Equal to the sub-frames' count when nothing is grouped (a request's own `shutterSamples` too).
pub fn sub_frames_grouped(comp: &Node, req: &serde_json::Value, t: f64) -> Result<(Vec<f64>, usize), String> {
    let (angle, n) = shutter(comp, req)?;
    if angle <= 0.0 || n < 2 {
        return Ok((vec![], 0));
    }
    if !req["shutterSamples"].is_null() {
        return Ok((sample_times(t, fps(comp), angle, n), n));
    }
    let all = steps::steps(comp, t, fps(comp), angle, n);
    let own = if all > n { steps::own_steps(comp, t, fps(comp), angle, n).min(all) } else { all };
    Ok((sample_times(t, fps(comp), angle, all), own))
}

/// Load-time check (scene_serve.rs `check`): the trails' copies and the comp's shutter.
pub fn check(comp: &Node) -> Result<(), String> {
    Plan::of(comp)?;
    shutter(comp, &serde_json::Value::Null).map(|_| ())
}

fn fps(comp: &Node) -> f64 {
    comp.props.get("fps").and_then(serde_json::Value::as_f64).unwrap_or(30.0)
}

/// The layer with this id in the evaluated tree (ids are unique in a scene).
fn find<'t, 'a>(it: &'t Item<'a>, id: &str) -> Option<&'t Item<'a>> {
    if it.id == id {
        return Some(it);
    }
    it.layers.iter().find_map(|l| find(l, id))
}
