//! Rigs (apps/2d/RIG.md): a layer holding layers plus bones, IK chains and binds. Each frame the bones are posed
//! (pose.rs FK, ik.rs) and the bound layers moved (bind.rs) from the rig's parts and t alone, so the canvas, the look
//! tools and the export see the same pose (preview ≡ export). check.rs refuses a broken rig when the scene loads.

pub mod fields;
mod bind;
mod bones;
mod check;
mod fabrik;
mod ik;
pub mod math;
mod pose;
#[cfg(test)]
mod tests;

pub use bind::warp_markup;
pub use bones::bones;
pub use check::scene as check;

use crate::scene::eval::Item;

/// eval.rs: a rig at its time, its layers evaluated → its bound layers moved, turned, scaled or bent.
pub fn pose(rig: &mut Item) {
    let node = rig.node;
    let pose = pose::Pose::solve(node, rig.t);
    bind::apply(&pose, node, rig.t, &mut rig.layers);
}
