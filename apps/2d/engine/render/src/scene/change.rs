//! serve's `change` (ENGINE_CONTRACT.md § 1): a scene where any child (in `layers`, `effects`, `masks`, `rig`,
//! `stops`) may be given as an id, the held scene's item of that id kept exactly as it is, its whole subtree. The load
//! is `scene`'s (Scene::read): `Refs` hands it the kept items. What it then needs checking is only what was given
//! anew (`part`): the top-level layers given as objects, and the siblings they name or that name them.

use std::collections::{HashMap, HashSet};
use std::sync::Arc;

use serde_json::Value;

use super::{Node, Scene};

/// The held scene's items a load may keep by id: each at most once.
pub struct Refs<'a> {
    held: Option<HashMap<&'a str, &'a Node>>,
    taken: HashSet<String>,
    /// The items kept, their subtrees' items counted.
    pub kept: usize,
}

impl<'a> Refs<'a> {
    /// A `scene` load: every item is given whole (an id in a child list is refused).
    pub fn none() -> Refs<'a> {
        Refs { held: None, taken: HashSet::new(), kept: 0 }
    }

    /// A `change` against the held scene.
    pub fn of(held: &'a Scene) -> Refs<'a> {
        let mut all = HashMap::new();
        index(&held.comp, &mut all);
        Refs { held: Some(all), taken: HashSet::new(), kept: 0 }
    }

    /// The held item `id`, kept in `parent`'s children.
    pub fn take(&mut self, id: &str, parent: &str) -> Result<Node, String> {
        let held = self.held.as_ref().ok_or_else(|| format!("{parent}: an item must be an object"))?;
        let n = held.get(id).ok_or_else(|| format!("{parent}: \"{id}\" is not in the held scene (a change keeps by id only items of the scene loaded before it)"))?;
        if !self.taken.insert(id.to_string()) {
            return Err(format!("{id}: kept twice in the change (an item kept by id goes in one place)"));
        }
        let mut count = 0;
        let _ = n.walk(&mut |_| {
            count += 1;
            Ok(())
        });
        self.kept += count;
        Ok((*n).clone())
    }
}

/// Every item of the tree under `n` by id.
fn index<'a>(n: &'a Node, out: &mut HashMap<&'a str, &'a Node>) {
    out.insert(n.id.as_str(), n);
    n.effects.iter().chain(&n.masks).chain(&n.layers).chain(&n.rig).chain(&n.stops).for_each(|c| index(c, out));
}

/// What a load must stage to be checked, given the held scene it kept items from and the ids of the top-level layers
/// it kept whole (`kept_top`): None, the whole comp; else a comp of only the layers given anew, the siblings any of
/// them names (a matte, a path followed or ridden) and those naming them. A kept layer was staged when it was loaded
/// and is the same item, so it would stage the same again: unless what is around it changed (the comp, its frame, the
/// fonts), when the whole comp is staged.
pub fn part(scene: &Scene, held: &Scene, kept_top: &HashSet<&str>) -> Option<Node> {
    let (comp, was) = (&scene.comp, &held.comp);
    let same_around = !kept_top.is_empty() && Arc::ptr_eq(&scene.fonts, &held.fonts) && comp.props == was.props
        && format!("{:?}", comp.anim) == format!("{:?}", was.anim)
        && comp.layers.iter().all(|l| l.kind != "camera" || kept_top.contains(l.id.as_str()));
    if !same_around {
        return None;
    }
    let names = |l: &Node, ids: &HashSet<&str>| l.props.values().any(|v| v.as_str().is_some_and(|s| ids.contains(s)));
    // Given anew, then whatever names one of those, until nothing more does.
    let mut dirty: HashSet<&str> = comp.layers.iter().map(|l| l.id.as_str()).filter(|id| !kept_top.contains(id)).collect();
    loop {
        let more: Vec<&str> = comp.layers.iter().filter(|l| !dirty.contains(l.id.as_str()) && names(l, &dirty)).map(|l| l.id.as_str()).collect();
        if more.is_empty() {
            break;
        }
        dirty.extend(more);
    }
    // With what they name (and what that names), so a matte or path is there to be seen through or followed.
    let mut with = dirty;
    loop {
        let named: HashSet<&str> = comp.layers.iter().filter(|l| with.contains(l.id.as_str())).flat_map(|l| l.props.values().filter_map(Value::as_str)).collect();
        let more: Vec<&str> = comp.layers.iter().map(|l| l.id.as_str()).filter(|id| !with.contains(id) && named.contains(id)).collect();
        if more.is_empty() {
            break;
        }
        with.extend(more);
    }
    let layers = comp.layers.iter().filter(|l| l.kind == "camera" || with.contains(l.id.as_str())).cloned().collect();
    Some(Node {
        id: comp.id.clone(), kind: comp.kind, role: comp.role, props: comp.props.clone(), anim: comp.anim.clone(), layers,
        effects: vec![], masks: vec![], frames: vec![], paint: vec![], paint_inside: true, fill_frames: vec![], rig: vec![], stops: vec![],
    })
}

/// The ids of the top-level layers a `change` keeps whole (given as ids in the comp's `layers`).
pub fn kept_top(v: &Value) -> HashSet<&str> {
    v["comp"]["layers"].as_array().into_iter().flatten().filter_map(Value::as_str).collect()
}
