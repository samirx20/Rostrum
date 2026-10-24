//! The engine's `bones` request (RIG.md › Agents' eyes): every rig's posed bones and IK targets at t, in screen px,
//! where they are drawn: through the rig's and its parents' 2D transforms (tilt left out) and the comp's camera
//! (crate::frame; at home, screen px are comp px). Each rig also gives `frame`: the matrix [a, b, c, d, e, f] that took its comp px to
//! the screen (the identity without a camera), so a check that must ignore the camera (a pinned foot) can undo it.

use serde_json::{json, Map, Value};

use super::math::{dist, heading, layer_map, Aff};
use super::pose::Pose;
use crate::scene::eval::{self, Item};
use crate::scene::Node;

/// `{"rigs": {"<rig id>": {"bones": {…}, "iks": {…}}}}` at `t` (rigs not showing included).
pub fn bones(comp: &Node, t: f64) -> Value {
    let mut rigs = Map::new();
    let top = eval::whole(comp, t);
    let view = match crate::frame::View::of(&top) {
        Ok(v) => v,
        Err(e) => return json!({ "error": e }),
    };
    for l in top.layers.iter().filter(|l| l.kind != "camera") {
        let cam = view.map(l);
        walk(l, cam, cam, &mut rigs);
    }
    json!({ "ok": true, "rigs": rigs })
}

fn walk(it: &Item, outer: Aff, cam: Aff, rigs: &mut Map<String, Value>) {
    let m = outer * layer_map(&it.props);
    if it.kind == "rig" {
        let mut r = rig(&Pose::solve(it.node, it.t), m);
        r["frame"] = json!([cam.a, cam.b, cam.c, cam.d, cam.e, cam.f]);
        rigs.insert(it.id.to_string(), r);
    }
    for l in &it.layers {
        walk(l, m, cam, rigs);
    }
}

fn rig(pose: &Pose, m: Aff) -> Value {
    let mut bones = Map::new();
    for (i, id) in pose.ids.iter().enumerate() {
        let (p, tip) = (m.apply(pose.pivot(i)), m.apply(pose.tip(i)));
        let frame = m * pose.world[i];
        let angle = heading(frame.origin(), frame.apply((1.0, 0.0))).to_degrees();
        bones.insert(id.clone(), json!({ "x": p.0, "y": p.1, "tipX": tip.0, "tipY": tip.1, "angle": angle }));
    }
    let mut iks = Map::new();
    for ik in &pose.iks {
        let (target, tip) = (m.apply(ik.target), m.apply(ik.tip));
        iks.insert(ik.id.clone(), json!({ "targetX": target.0, "targetY": target.1, "gap": dist(target, tip), "bones": ik.bones }));
    }
    json!({ "bones": bones, "iks": iks })
}
