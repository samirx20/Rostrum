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

/// A cut (a hold key, then the next key) never smears two shots: a sub-frame on the far side of the jump reads the
/// value on the frame's side (FRAME.md › Cuts; spec test 6). The frame here jumps from x 0 to x 900 at 1 s.
#[test]
fn shutter_samples_never_cross_a_jump() {
    let mut f = item("frame", "camera", json!({ "zoom": 1.0, "x": 200.0, "y": 200.0, "homeX": 200.0, "homeY": 200.0 }));
    f["anim"] = json!({ "x": [{ "t": 0.0, "v": 0.0, "ease": "hold" }, { "t": 1.0, "v": 900.0, "ease": "linear" }, { "t": 2.0, "v": 1000.0, "ease": "linear" }] });
    let mut comp = item("c", "comp", json!({}));
    comp["layers"] = json!([f]);
    let scene = Scene::load(&json!({ "format": FORMAT, "version": VERSION, "comp": comp })).unwrap();
    let x = |centre: f64, t: f64| eval::shutter_at(centre, t, || eval::props_at(&scene.comp.layers[0], t))["x"].as_f64().unwrap();
    for ts in super::sample_times(1.0 - 1.0 / 30.0, 30.0, 360.0, 8) {
        assert_eq!(x(1.0 - 1.0 / 30.0, ts), 0.0, "the frame before the cut sees the next shot at {ts}");
    }
    for ts in super::sample_times(1.0, 30.0, 360.0, 8) {
        let v = x(1.0, ts);
        assert!((900.0..902.0).contains(&v), "the frame of the cut sees the shot before at {ts}: x {v}");
    }
    assert!(x(1.5, 1.5 + 1.0 / 120.0) > 950.0, "away from the cut the move still blurs");
    assert_eq!(eval::props_at(&scene.comp.layers[0], 0.99)["x"].as_f64(), Some(0.0), "no shutter: the plain value");
}

/// Steps follow the motion (steps.rs): a fast move gets copies at most GAP_PX apart, a still or slow one keeps the
/// fewest (no extra cost), and the count never passes MOST.
/// Motion blur blurs where a thing is, never what it is (as After Effects): a counter counting while it moves shows
/// the frame's one number in every sub-frame (critic 2d-r9: "2,058" printed over "2,068"), while its place still blurs.
#[test]
fn shutter_samples_keep_what_is_drawn() {
    let mut s = item("n", "text", json!({ "counter": true, "countSeparator": "comma", "countDigits": 1.0 }));
    s["anim"] = json!({
        "count": [{ "t": 0.0, "v": 0.0, "ease": "linear" }, { "t": 1.0, "v": 3000.0, "ease": "linear" }],
        "x": [{ "t": 0.0, "v": 0.0, "ease": "linear" }, { "t": 1.0, "v": 900.0, "ease": "linear" }],
    });
    let mut comp = item("c", "comp", json!({}));
    comp["layers"] = json!([s]);
    let scene = Scene::load(&json!({ "format": FORMAT, "version": VERSION, "comp": comp })).unwrap();
    let layer = &scene.comp.layers[0];
    let still = eval::props_at(layer, 0.5);
    let mut xs = vec![];
    for ts in super::sample_times(0.5, 30.0, 180.0, 8) {
        let p = eval::shutter_at(0.5, ts, || eval::props_at(layer, ts));
        assert_eq!(p["body"], still["body"], "sub-frame at {ts} shows another number");
        xs.push(p["x"].as_f64().unwrap());
    }
    assert_eq!(still["body"], json!("1,500"));
    assert!(xs.windows(2).all(|w| w[1] > w[0]), "its place still blurs: {xs:?}");
}

/// A layer showing in a frame shows in all its sub-frames, also those before 0 s or before its start (critic 2d-r11:
/// with motion blur on, frame 0 drew every layer at half strength); one that doesn't show in the frame shows in none.
#[test]
fn shutter_samples_keep_who_shows() {
    let mut late = item("late", "shape", json!({ "w": 100.0, "h": 50.0, "start": 0.5 }));
    late["anim"] = json!({ "x": [{ "t": 0.0, "v": 0.0, "ease": "linear" }, { "t": 1.0, "v": 900.0, "ease": "linear" }] });
    let mut comp = item("c", "comp", json!({}));
    comp["layers"] = json!([item("first", "shape", json!({ "w": 100.0, "h": 50.0 })), late]);
    let scene = Scene::load(&json!({ "format": FORMAT, "version": VERSION, "comp": comp })).unwrap();
    let ids = |centre: f64, ts: f64| -> Vec<String> {
        eval::shutter_at(centre, ts, || eval::at(&scene.comp, ts)).unwrap().layers.iter().map(|l| l.id.to_string()).collect()
    };
    for ts in super::sample_times(0.0, 30.0, 180.0, 8) {
        assert_eq!(ids(0.0, ts), ["first"], "frame 0, sub-frame at {ts}");
    }
    for ts in super::sample_times(0.5, 30.0, 180.0, 8) {
        assert_eq!(ids(0.5, ts), ["first", "late"], "the late layer's first frame, sub-frame at {ts}");
    }
    let before = 0.5 - 1.0 / 30.0;
    for ts in super::sample_times(before, 30.0, 360.0, 8) {
        assert_eq!(ids(before, ts), ["first"], "the frame before its start, sub-frame at {ts}");
    }
}

#[test]
fn blur_steps_follow_the_move_on_screen() {
    let blur = item("tr", "trail", json!({ "copies": 1.0, "spacing": 1.0, "fade": 0.5 }));
    let steps = |speed: f64| super::steps::steps(&moving(speed, blur.clone()).comp, 0.5, 30.0, 180.0, 8);
    assert_eq!(steps(0.0), 8, "nothing moves: the fewest");
    assert_eq!(steps(4.0), 8, "2 px per shutter: the fewest");
    // 60 px a frame, half a frame open: 30 px per shutter → 30 steps, 1 px apart.
    assert_eq!(steps(60.0), 30);
    assert_eq!(steps(10_000.0), super::steps::MOST);
}

/// motion/hold.rs: in a motion-blurred frame, a layer that drifts under a quarter pixel while the shutter is open is
/// staged as at the frame's time in every sub-frame (painted once), and one that moves further is staged per sub-frame.
#[test]
fn a_layer_drifting_under_a_quarter_pixel_is_held_and_a_moving_one_is_not() {
    let mut slow = item("slow", "shape", json!({ "x": 50.0, "y": 50.0, "w": 40.0, "h": 40.0 }));
    slow["anim"] = json!({ "x": [{ "t": 0.0, "v": 50.0, "ease": "linear" }, { "t": 1.0, "v": 60.0, "ease": "linear" }] }); // 10 px/s: 1/6 px while a 180° shutter is open at 30 fps
    let mut fast = item("fast", "shape", json!({ "x": 50.0, "y": 150.0, "w": 40.0, "h": 40.0 }));
    fast["anim"] = json!({ "x": [{ "t": 0.0, "v": 50.0, "ease": "linear" }, { "t": 1.0, "v": 250.0, "ease": "linear" }] });
    let mut comp = item("c", "comp", json!({ "shutter": 180.0, "shutterSamples": 8.0 }));
    comp["layers"] = json!([slow, fast]);
    let scene = Scene::load(&json!({ "format": FORMAT, "version": VERSION, "comp": comp })).unwrap();
    let staged = crate::scene_serve::stage_at(&scene, 0.5, &json!({})).unwrap();
    let samples = staged.sample_pieces();
    assert!(samples.len() >= 8);
    let (s, f) = (1, 2); // background, slow, fast
    assert!(samples.iter().all(|p| p[s] == samples[0][s]), "the slow layer is held");
    assert!(samples.windows(2).any(|w| w[0][f] != w[1][f]), "the fast layer moves");
}

/// B1: a rack focus doesn't change a still layer's depth-of-field blur between the sub-frames of one frame (the focus
/// is the frame's own time's in each), so the layer is one piece, painted and blurred once a frame.
#[test]
fn a_rack_focus_keeps_a_still_layer_one_piece_through_the_shutter() {
    let mut cam = item("f", "camera", json!({ "x": 200.0, "y": 200.0, "homeX": 200.0, "homeY": 200.0, "zoom": 1.0, "dof": true, "focusBlur": 20.0 }));
    cam["anim"] = json!({ "focus": [{ "t": 0.0, "v": 0.0, "ease": "linear" }, { "t": 0.2, "v": 3.0, "ease": "linear" }] }); // 15 depth a second
    let still = item("still", "shape", json!({ "w": 100.0, "h": 50.0, "x": 100.0, "y": 100.0, "depth": 1.0 }));
    let mut fast = item("fast", "shape", json!({ "w": 100.0, "h": 50.0 }));
    fast["anim"] = json!({ "x": [{ "t": 0.0, "v": 0.0, "ease": "linear" }, { "t": 1.0, "v": 1800.0, "ease": "linear" }] });
    let mut comp = item("c", "comp", json!({ "shutter": 180.0, "shutterSamples": 8.0 }));
    comp["layers"] = json!([cam, still, fast]);
    let scene = Scene::load(&json!({ "format": FORMAT, "version": VERSION, "comp": comp })).unwrap();
    let staged = crate::scene_serve::stage_at(&scene, 0.1, &json!({})).unwrap();
    let samples = staged.sample_pieces();
    assert!(samples.len() >= 8);
    let piece = |p: &Vec<String>| p.iter().find(|x| x.contains("cam~still")).cloned().unwrap();
    assert!(samples.iter().all(|p| piece(p) == piece(&samples[0])), "the still layer's blur is the same in every sub-frame");
    assert!(samples.windows(2).any(|w| w[0] != w[1]), "the fast layer moves");
}
