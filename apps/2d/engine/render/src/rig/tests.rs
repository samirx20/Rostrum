//! What agents and people rely on and would break silently: an IK tip lands on its target on the asked-for side,
//! an unreachable target straightens the chain at it, a pinned foot stays planted, a bound layer follows its bone.

use serde_json::{json, Map, Value};

use super::math::{dist, Pt};
use super::pose::Pose;
use crate::scene::fields::{self, Kind};
use crate::scene::{eval, Scene, FORMAT, VERSION};

/// A scene item with every field present: neutral defaults, then `props`.
fn item(id: &str, ty: &str, props: Value) -> Value {
    let mut p = Map::new();
    for (name, kind) in fields::of(ty).unwrap().1 {
        let v = match (name, kind) {
            ("scale" | "scaleX" | "scaleY" | "opacity" | "mix", _) => json!(1.0),
            ("end", _) => json!(1e9),
            ("w" | "h" | "length", _) => json!(100.0),
            ("width" | "height", _) => json!(400.0),
            ("fps", _) => json!(30.0),
            ("duration", _) => json!(3.0),
            ("grid", _) => json!(16.0),
            ("soft", _) => json!(20.0),
            ("chain", _) => json!(2.0),
            (_, Kind::Number) => json!(0.0),
            (_, Kind::Toggle) => json!(false),
            (_, Kind::Text) => json!(""),
            (_, Kind::Color) => json!("#000000"),
            (_, Kind::Choice(o)) => json!(o[0]),
        };
        p.insert(name.to_string(), v);
    }
    p.extend(props.as_object().unwrap().clone());
    json!({ "id": id, "type": ty, "props": p })
}

fn keys(ks: &[(f64, f64)], ease: &str) -> Value {
    Value::from(ks.iter().map(|&(t, v)| json!({ "t": t, "v": v, "ease": ease })).collect::<Vec<_>>())
}

/// A two-bone arm in a rig: thigh pivot (100, 100) pointing right, shin from (200, 100), both 100 px long.
fn scene(layers: Vec<Value>, mut parts: Vec<Value>) -> Scene {
    let mut bones = vec![
        item("thigh", "bone", json!({ "x": 100.0, "y": 100.0 })),
        item("shin", "bone", json!({ "parent": "thigh", "x": 200.0, "y": 100.0 })),
    ];
    bones.append(&mut parts);
    let mut rig = item("puppet", "rig", json!({ "w": 400.0, "h": 400.0 }));
    rig["layers"] = Value::from(layers);
    rig["rig"] = Value::from(bones);
    let mut comp = item("main", "comp", json!({}));
    comp["layers"] = json!([rig]);
    Scene::load(&json!({ "format": FORMAT, "version": VERSION, "comp": comp })).unwrap()
}

fn chain(pose: &Pose) -> (Pt, Pt, Pt) {
    let (up, lo) = (pose.index("thigh").unwrap(), pose.index("shin").unwrap());
    (pose.pivot(up), pose.pivot(lo), pose.tip(lo))
}

#[test]
fn ik_reaches_a_reachable_target_on_its_bend_side() {
    let target = (250.0, 180.0);
    for (bend, side) in [("clockwise", 1.0), ("counterclockwise", -1.0)] {
        let ik = item("leg", "ik", json!({ "bone": "shin", "targetX": target.0, "targetY": target.1, "bend": bend }));
        let s = scene(vec![], vec![ik]);
        let (a, b, c) = chain(&Pose::solve(&s.comp.layers[0], 0.0));
        assert!(dist(c, target) < 1e-6, "{bend}: the tip is at {c:?}, the target at {target:?}");
        assert!((dist(a, b) - 100.0).abs() < 1e-9 && (dist(b, c) - 100.0).abs() < 1e-9, "{bend}: the bones changed length");
        let turn = (b.0 - a.0) * (c.1 - b.1) - (b.1 - a.1) * (c.0 - b.0);
        assert!(turn * side > 1.0, "{bend}: the knee bends the wrong way (turn {turn})");
    }
}

#[test]
fn an_unreachable_target_straightens_the_chain_at_it() {
    let target = (600.0, 400.0);
    let ik = item("leg", "ik", json!({ "bone": "shin", "targetX": target.0, "targetY": target.1 }));
    let s = scene(vec![], vec![ik]);
    let (a, b, c) = chain(&Pose::solve(&s.comp.layers[0], 0.0));
    let d = dist(a, target);
    let toward = |l: f64| (a.0 + (target.0 - a.0) * l / d, a.1 + (target.1 - a.1) * l / d);
    assert!(dist(b, toward(100.0)) < 1e-6 && dist(c, toward(200.0)) < 1e-6, "joint {b:?}, tip {c:?}");
}

#[test]
fn a_pinned_target_stays_put_while_its_keys_and_the_body_move() {
    let mut ik = item("leg", "ik", json!({ "bone": "shin", "targetY": 120.0 }));
    ik["anim"] = json!({ "targetX": keys(&[(0.0, 300.0), (2.0, 200.0)], "smooth"), "pin": keys(&[(0.0, 0.0), (1.0, 1.0)], "hold") });
    let mut s = scene(vec![], vec![ik]);
    s.edit(&json!([{ "id": "thigh", "anim": { "moveX": keys(&[(0.0, 0.0), (2.0, 40.0)], "linear") } }])).unwrap();
    let rig = &s.comp.layers[0];
    let ik_node = rig.rig.iter().find(|p| p.id == "leg").unwrap();
    let at = |t: f64| {
        let p = eval::props_at(ik_node, t);
        (p["targetX"].as_f64().unwrap(), p["targetY"].as_f64().unwrap())
    };
    let free = Pose::solve(rig, 0.5);
    assert!(dist(free.iks[0].target, at(0.5)) < 1e-9, "before the pin the target follows its keys");
    let planted = at(1.0);
    for t in [1.0, 1.5, 1.9] {
        let pose = Pose::solve(rig, t);
        assert!(dist(pose.iks[0].target, planted) < 1e-9, "t={t}: the held target moved to {:?}", pose.iks[0].target);
        assert!(dist(chain(&pose).2, planted) < 1e-6, "t={t}: the foot left the ground");
    }
    let moved = dist(chain(&Pose::solve(rig, 1.9)).0, chain(&Pose::solve(rig, 1.0)).0);
    assert!(moved > 10.0 && dist(at(1.9), planted) > 10.0, "the check would prove nothing: the body and the keys must move");
}

#[test]
fn a_long_chain_reaches_its_target_on_top_of_the_two_bone_chain_above_it() {
    // Three 60 px bones hang from the shin's tip; the leg's two-bone IK moves the shin, the long chain poses after it.
    let mut parts: Vec<Value> = ["a", "b", "c"].iter().enumerate().map(|(i, id)| {
        let parent = if i == 0 { "shin" } else { ["a", "b"][i - 1] };
        item(id, "bone", json!({ "parent": parent, "x": 300.0 + 60.0 * i as f64, "y": 100.0, "length": 60.0 }))
    }).collect();
    parts.push(item("leg", "ik", json!({ "bone": "shin", "targetX": 180.0, "targetY": 120.0 })));
    let target = (260.0, 200.0);
    parts.push(item("tail", "ik", json!({ "bone": "c", "chain": 3.0, "targetX": target.0, "targetY": target.1 })));
    let s = scene(vec![], parts);
    let pose = Pose::solve(&s.comp.layers[0], 0.0);
    let ix = |id: &str| pose.index(id).unwrap();
    assert!(dist(pose.pivot(ix("a")), chain(&pose).2) < 1e-6, "the long chain's base left the shin's tip");
    assert!(dist(chain(&pose).2, (180.0, 120.0)) < 1e-6, "the leg's IK did not pose first");
    assert!(dist(pose.tip(ix("c")), target) < 0.05, "the tail's tip is at {:?}", pose.tip(ix("c")));
    for id in ["a", "b", "c"] {
        assert!((dist(pose.pivot(ix(id)), pose.tip(ix(id))) - 60.0).abs() < 1e-9, "{id} changed length");
    }
    assert_eq!(pose.iks[1].bones, ["a", "b", "c"]);
}

#[test]
fn a_rigid_bound_layer_follows_its_turned_bone() {
    let hand = item("hand", "shape", json!({ "x": 200.0, "y": 100.0, "rotation": 10.0 }));
    let bind = item("hand_bind", "bind", json!({ "layer": "hand", "bone": "thigh" }));
    let mut s = scene(vec![hand], vec![bind]);
    s.edit(&json!([{ "id": "thigh", "anim": { "rotation": keys(&[(0.0, 90.0)], "smooth") } }])).unwrap();
    let comp = eval::at(&s.comp, 0.0).unwrap();
    let hand = &comp.layers[0].layers[0];
    assert!(dist((hand.num("x"), hand.num("y")), (100.0, 200.0)) < 1e-9, "the hand is at ({}, {})", hand.num("x"), hand.num("y"));
    assert!((hand.num("rotation") - 100.0).abs() < 1e-9 && (hand.num("scale") - 1.0).abs() < 1e-9);
}
