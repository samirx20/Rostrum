//! A rig's parts checked when the scene loads or is edited (RIG.md › Scene description): every bone, layer and
//! parent they name exists, no parents go round in a circle, a layer has one bind, a bend's `bone2` is a child of
//! its `bone`. The message names the item and field.

use std::collections::HashMap;

use super::pose::{num, text};
use crate::scene::Node;

type R = Result<(), String>;

/// Every rig in the scene.
pub fn scene(comp: &Node) -> R {
    comp.walk(&mut |n| if n.kind == "rig" { rig(n) } else { Ok(()) })
}

fn rig(r: &Node) -> R {
    let bones: HashMap<&str, &Node> = r.rig.iter().filter(|p| p.kind == "bone").map(|b| (b.id.as_str(), b)).collect();
    let parent = |b: &Node| text(&b.props, "parent").to_string();
    for b in r.rig.iter().filter(|p| p.kind == "bone") {
        let p = parent(b);
        if !p.is_empty() && !bones.contains_key(p.as_str()) {
            return Err(format!("{}.parent: no bone \"{p}\" in rig {}", b.id, r.id));
        }
        if num(&b.props, "length") < 0.0 {
            return Err(format!("{}.length: {} is below 0", b.id, num(&b.props, "length")));
        }
    }
    for b in r.rig.iter().filter(|p| p.kind == "bone") {
        let mut cur = parent(b);
        for _ in 0..=bones.len() {
            if cur.is_empty() {
                break;
            }
            if cur == b.id {
                return Err(format!("{}.parent: the bones' parents go round in a circle back to {}", b.id, b.id));
            }
            cur = parent(bones[cur.as_str()]);
        }
    }
    let mut chains: HashMap<&str, &str> = HashMap::new();
    for ik in r.rig.iter().filter(|p| p.kind == "ik") {
        let lo = bone(&bones, r, ik, "bone")?;
        if parent(lo).is_empty() {
            return Err(format!("{}.bone: {} has no parent bone (an ik names the chain's lower bone; its parent is the upper)", ik.id, lo.id));
        }
        let n = num(&ik.props, "chain");
        if !(2.0..=32.0).contains(&n) || n.fract() != 0.0 {
            return Err(format!("{}.chain: {n} is not a whole number of bones from 2 to 32", ik.id));
        }
        let (mut have, mut cur) = (1, parent(lo));
        while !cur.is_empty() && have < n as usize {
            have += 1;
            cur = parent(bones[cur.as_str()]);
        }
        if have < n as usize {
            return Err(format!("{}.chain: {n} bones from {} up, but the rig has only {have} there", ik.id, lo.id));
        }
        if let Some(other) = chains.insert(lo.id.as_str(), ik.id.as_str()) {
            return Err(format!("{}.bone: {} already ends the chain {other}", ik.id, lo.id));
        }
    }
    let mut bound: HashMap<&str, &str> = HashMap::new();
    for bind in r.rig.iter().filter(|p| p.kind == "bind") {
        let id = text(&bind.props, "layer");
        let layer = r.layers.iter().find(|l| l.id == id).ok_or_else(|| format!("{}.layer: no layer \"{id}\" in rig {}'s layers", bind.id, r.id))?;
        if let Some(other) = bound.insert(layer.id.as_str(), bind.id.as_str()) {
            return Err(format!("{}.layer: {id} already has a bind ({other})", bind.id));
        }
        let b1 = bone(&bones, r, bind, "bone")?;
        if text(&bind.props, "bone2").is_empty() {
            continue;
        }
        let b2 = bone(&bones, r, bind, "bone2")?;
        if parent(b2) != b1.id {
            return Err(format!("{}.bone2: {} is not a child bone of {}", bind.id, b2.id, b1.id));
        }
        if !layer.props.contains_key("w") {
            return Err(format!("{}.bone2: a bend bind needs a layer with a box (w, h); {id} is a {} and has none", bind.id, layer.kind));
        }
        let grid = num(&bind.props, "grid");
        if !(4.0..=64.0).contains(&grid) || grid.fract() != 0.0 {
            return Err(format!("{}.grid: {grid} is not a whole number from 4 to 64", bind.id));
        }
        if num(&bind.props, "soft") < 0.0 {
            return Err(format!("{}.soft: {} is below 0", bind.id, num(&bind.props, "soft")));
        }
    }
    Ok(())
}

/// The bone an ik or bind names in `field`.
fn bone<'a>(bones: &HashMap<&str, &'a Node>, r: &Node, owner: &Node, field: &str) -> Result<&'a Node, String> {
    let id = text(&owner.props, field);
    bones.get(id).copied().ok_or_else(|| format!("{}.{field}: no bone \"{id}\" in rig {}", owner.id, r.id))
}
