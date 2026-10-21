//! What would break silently: a trail's copies are the layer at the right earlier times (none before it starts),
//! a trailing smear keeps its front edge where it is, and the shutter's sub-frames are centred on the frame.

use serde_json::{json, Map, Value};

use super::Plan;
use crate::scene::fields::{self, Kind};
use crate::scene::{eval, Scene, FORMAT, VERSION};

/// A scene item with every field present: neutral defaults, then `props`.
fn item(id: &str, ty: &str, props: Value) -> Value {
    let mut p = Map::new();
    for (name, kind) in fields::of(ty).unwrap().1 {
        let v = match (name, kind) {
            ("scale" | "scaleX" | "scaleY" | "opacity", _) => json!(1.0),
            ("end", _) => json!(1e9),
            ("width" | "height", _) => json!(400.0),
            ("fps", _) => json!(30.0),
            ("duration", _) => json!(3.0),
            ("anchorX" | "anchorY", _) => json!(0.5),
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

/// A 100 × 50 shape moving right at `speed` px per frame from x = 0 (30 fps), with one effect.
fn moving(speed: f64, effect: Value) -> Scene {
    let mut s = item("s", "shape", json!({ "w": 100.0, "h": 50.0 }));
    s["anim"] = json!({ "x": [{ "t": 0.0, "v": 0.0, "ease": "linear" }, { "t": 1.0, "v": speed * 30.0, "ease": "linear" }] });
    s["effects"] = json!([effect]);
    let mut comp = item("c", "comp", json!({}));
    comp["layers"] = json!([s]);
    Scene::load(&json!({ "format": FORMAT, "version": VERSION, "comp": comp })).unwrap()
}

fn at<'a>(scene: &'a Scene, plan: &'a Plan, t: f64) -> eval::Item<'a> {
    let mut comp = eval::at(&scene.comp, t).unwrap();
    plan.apply(&scene.comp, &mut comp);
    comp
}

#[test]
fn trail_copies_are_the_layer_earlier() {
    let scene = moving(10.0, item("tr", "trail", json!({ "copies": 3.0, "spacing": 3.0, "fade": 0.5 })));
    let plan = Plan::of(&scene.comp).unwrap();
    let comp = at(&scene, &plan, 0.5);
    let got: Vec<(&str, f64, f64)> = comp.layers.iter().map(|l| (l.id, l.num("x"), l.num("opacity"))).collect();
    let want = [("s~trail3", 60.0, 0.125), ("s~trail2", 90.0, 0.25), ("s~trail1", 120.0, 0.5), ("s", 150.0, 1.0)];
    assert_eq!(got.len(), 4, "{got:?}");
    for (g, w) in got.iter().zip(want) {
        assert!(g.0 == w.0 && (g.1 - w.1).abs() < 1e-6 && (g.2 - w.2).abs() < 1e-9, "{got:?}");
    }
    assert!(comp.layers[0].effects.iter().all(|e| e.kind != "trail"), "a copy has no trail of its own");
    // At 0.15 s, copies 2 and 3 would be before the layer starts (t < 0): left out.
    let early: Vec<&str> = at(&scene, &plan, 0.15).layers.iter().map(|l| l.id).collect();
    assert_eq!(early, ["s~trail1", "s"]);
}

#[test]
fn a_trailing_smear_keeps_its_front_edge() {
    let smear = item("sm", "smear", json!({ "amount": 1.0, "max": 10.0, "minSpeed": 0.0, "stretch": "behind", "keepArea": false }));
    let scene = moving(60.0, smear);
    let plan = Plan::of(&scene.comp).unwrap();
    let comp = at(&scene, &plan, 0.5);
    let m = &comp.layers[0].props["~smear"];
    let n = |f: &str| m[f].as_f64().unwrap();
    // 60 px this frame over its 100 px length: k = 1.6. The front edge (50 px ahead of the anchor) stays at 50.
    assert!((n("k") - 1.6).abs() < 1e-9 && n("angle").abs() < 1e-9 && n("across") == 1.0, "{m}");
    assert!((50.0 * n("k") + n("dx") - 50.0).abs() < 1e-9, "{m}");
    // Under minSpeed: no smear.
    let slow = moving(1.0, item("sm", "smear", json!({ "minSpeed": 2.0, "amount": 1.0, "max": 4.0 })));
    let plan = Plan::of(&slow.comp).unwrap();
    assert!(at(&slow, &plan, 0.5).layers[0].props.get("~smear").is_none());
}

#[test]
fn shutter_samples_are_centred_on_the_frame() {
    let ts = super::sample_times(1.0, 30.0, 180.0, 4);
    let mean = ts.iter().sum::<f64>() / 4.0;
    assert!((mean - 1.0).abs() < 1e-12 && (ts[3] - ts[0] - 0.75 / 60.0).abs() < 1e-12, "{ts:?}");
}
