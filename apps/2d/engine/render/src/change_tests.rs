//! `change` (scene/change.rs) must hold exactly the scene a full `scene` load of the same scene holds, so the next
//! frame draws the same; a refused change leaves the held scene as it was.

use serde_json::{json, Value};

use super::{load, read, Held};
use crate::scene::{eval, stage, FORMAT, VERSION};

fn item(id: &str, ty: &str, props: Value) -> Value {
    let mut p = crate::scene::measure::neutral(ty);
    p.extend(props.as_object().unwrap().clone());
    json!({ "id": id, "type": ty, "props": p })
}

fn shape(id: &str, x: f64, fill: &str) -> Value {
    let mut s = item(id, "shape", json!({ "x": x, "y": 40.0, "w": 60.0, "h": 40.0, "fill": fill }));
    s["anim"] = json!({ "x": [{ "t": 0.0, "v": x }, { "t": 1.0, "v": x + 80.0 }] });
    s
}

fn text(id: &str, features: &str) -> Value {
    item(id, "text", json!({ "body": "Hello", "font": "Inter", "size": 40.0, "weight": 600.0, "x": 20.0, "y": 120.0, "features": features }))
}

fn group(id: &str, x: f64, layers: Vec<Value>) -> Value {
    let mut g = item(id, "group", json!({ "x": x, "w": 300.0, "h": 200.0 }));
    g["layers"] = Value::from(layers);
    g
}

fn scene(layers: Vec<Value>) -> Value {
    let mut comp = item("main", "comp", json!({ "width": 320.0, "height": 240.0, "fps": 30.0, "duration": 2.0, "background": "#101418", "shutterSamples": 8.0 }));
    comp["layers"] = Value::from(layers);
    json!({ "format": FORMAT, "version": VERSION, "comp": comp })
}

fn held(v: &Value) -> Held {
    Held { scene: Some(read(&Held::default(), &json!({ "scene": v })).unwrap().0), ..Default::default() }
}

fn first() -> Value {
    let mut a = shape("a", 10.0, "#ff0000");
    a["effects"] = json!([item("a-glow", "glow", json!({}))]);
    scene(vec![a, text("t", ""), group("g", 0.0, vec![shape("g1", 0.0, "#00ff00"), shape("g2", 50.0, "#0000ff"), shape("g3", 90.0, "#ffffff")]), shape("b", 200.0, "#888888"), shape("c", 240.0, "#444444")])
}

/// c moved to the front, a and t kept, the group moved (its g2 kept, g1 replaced, g3 removed, g4 added), b removed, d added.
fn second(by_id: bool) -> Value {
    let keep = |v: Value| if by_id { Value::from(v["id"].as_str().unwrap()) } else { v };
    let mut a = shape("a", 10.0, "#ff0000");
    a["effects"] = json!([item("a-glow", "glow", json!({}))]);
    scene(vec![
        keep(shape("c", 240.0, "#444444")),
        keep(a),
        keep(text("t", "")),
        group("g", 30.0, vec![keep(shape("g2", 50.0, "#0000ff")), shape("g1", 0.0, "#ffff00"), shape("g4", 120.0, "#00ffff")]),
        shape("d", 160.0, "#ff00ff"),
    ])
}

#[test]
fn a_change_holds_the_scene_a_full_load_holds() {
    let mut h = held(&first());
    let (changed, kept, _, _) = read(&h, &json!({ "change": second(true) })).unwrap();
    let (full, none, _, _) = read(&Held::default(), &json!({ "scene": second(false) })).unwrap();
    assert_eq!((kept, none), (Some(5), None), "c, a with its glow, t and g2 are kept");
    assert_eq!(format!("{:?}", changed.comp), format!("{:?}", full.comp));
    for t in [0.0, 0.5, 1.0, 1.5] {
        assert_eq!(stage::parts(&eval::at(&changed.comp, t).unwrap()), stage::parts(&eval::at(&full.comp, t).unwrap()), "t={t}");
    }
    // A second change against the scene the first left: only the text given anew.
    h.scene = Some(changed);
    let mut next = second(true);
    next["comp"]["layers"] = json!(["c", "a", text("t", "tnum"), "g", "d"]);
    let (again, kept, _, _) = read(&h, &json!({ "change": next })).unwrap();
    assert_eq!(kept, Some(8), "c, a with its glow, the group with its three, d");
    assert_eq!(again.comp.layers[2].props["features"], "tnum");
}

#[test]
fn a_bad_change_is_refused_and_leaves_the_held_scene() {
    let mut h = held(&first());
    let before = format!("{:?}", h.scene.as_ref().unwrap().comp);
    let refuse = |h: &mut Held, layers: Value, want: &str| {
        let mut v = first();
        v["comp"]["layers"] = layers;
        let err = load(h, &mut None, &mut None, &json!({ "change": v })).unwrap_err();
        assert!(err.contains(want), "{err}");
        assert_eq!(format!("{:?}", h.scene.as_ref().unwrap().comp), before);
    };
    refuse(&mut h, json!(["a", "nope"]), "\"nope\" is not in the held scene");
    refuse(&mut h, json!(["a", "b", "a"]), "a: kept twice");
    refuse(&mut h, json!(["a", group("g", 0.0, vec![Value::from("a-glow")])]), "a glow can't be in g's layers");
    // A layer given anew is checked as a load checks it, its stage included (a feature its font lacks).
    refuse(&mut h, json!(["a", "b", text("t", "zz99")]), "t.features: the font \"Inter\" has no zz99 feature");
    let err = read(&Held::default(), &json!({ "change": first() })).unwrap_err();
    assert!(err.contains("no scene is held"), "{err}");
    let mut v = first();
    v["comp"]["layers"] = json!(["a"]);
    assert!(read(&h, &json!({ "scene": v })).unwrap_err().contains("an item must be an object"));
}
