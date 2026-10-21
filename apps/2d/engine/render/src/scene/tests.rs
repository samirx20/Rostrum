//! The engine evaluates scenes exactly as the Python layer's reference does (the one thing that would break
//! silently): `render/tests/scene/reference.json` is written by `make_reference.py` from rostrum2d's own
//! evaluator. Checked: the field table, every ease, a keyed scene's values at ten times, and one drawn frame.

use serde_json::Value;

use super::{eval, fields, stage, Scene};

fn reference() -> Value {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/scene/reference.json");
    serde_json::from_str(&std::fs::read_to_string(path).expect("reference.json (run make_reference.py)")).unwrap()
}

#[test]
fn the_field_table_is_fields_py() {
    let r = reference();
    let py = r["fields"].as_object().unwrap();
    let mut types: Vec<&str> = py.keys().map(String::as_str).collect();
    types.sort();
    let mut ours = fields::TYPES.to_vec();
    ours.sort();
    assert_eq!(types, ours, "item types differ from fields.py");
    for (ty, list) in py {
        let ours = fields::of(ty).unwrap().1;
        let want: Vec<(String, String, Value)> = list.as_array().unwrap().iter().map(|f| (f[0].as_str().unwrap().into(), f[1].as_str().unwrap().into(), f[2].clone())).collect();
        let got: Vec<(String, String, Value)> = ours.iter().map(|(n, k)| {
            let (kind, opts) = match k {
                fields::Kind::Number => ("number", Value::Null),
                fields::Kind::Color => ("color", Value::Null),
                fields::Kind::Toggle => ("toggle", Value::Null),
                fields::Kind::Text => ("text", Value::Null),
                fields::Kind::Choice(o) => ("choice", Value::from(o.to_vec())),
            };
            (n.to_string(), kind.to_string(), opts)
        }).collect();
        assert_eq!(got, want, "{ty}'s fields differ from fields.py");
        let anim: Vec<&str> = ours.iter().filter(|f| fields::animatable(ty, f)).map(|f| f.0).collect();
        let py_anim: Vec<&str> = r["animatable"][ty].as_array().unwrap().iter().map(|v| v.as_str().unwrap()).collect();
        assert_eq!(anim, py_anim, "{ty}'s animatable fields differ from fields.py");
    }
}

#[test]
fn every_ease_gives_pythons_numbers() {
    for e in reference()["eases"].as_array().unwrap() {
        let key = &e["key"];
        let ease = super::ease::Ease::parse(key["ease"].as_str().unwrap(), |p| key[p].as_f64()).unwrap();
        let (x, want) = (e["x"].as_f64().unwrap(), e["p"].as_f64().unwrap());
        let got = ease.at(x);
        assert!((got - want).abs() < 1e-12, "{key} at {x}: engine {got}, Python {want}");
    }
}

/// Same items, same values (numbers to 1e-9), same layers showing.
fn same(ours: &eval::Item, py: &Value, t: f64) {
    assert_eq!(ours.id, py["id"], "t={t}");
    for (f, want) in py["props"].as_object().unwrap() {
        let got = &ours.props[f];
        let ok = match (got.as_f64(), want.as_f64()) {
            (Some(a), Some(b)) => (a - b).abs() < 1e-9,
            _ => got == want,
        };
        assert!(ok, "{}.{f} at t={t}: engine {got}, Python {want}", ours.id);
    }
    for (part, kids) in [("effects", &ours.effects), ("masks", &ours.masks), ("layers", &ours.layers)] {
        let empty = vec![];
        let py_kids = py[part].as_array().unwrap_or(&empty);
        assert_eq!(kids.len(), py_kids.len(), "{}'s {part} at t={t}", ours.id);
        kids.iter().zip(py_kids).for_each(|(a, b)| same(a, b, t));
    }
}

#[test]
fn a_keyed_scene_evaluates_as_python_does() {
    let r = reference();
    let scene = Scene::load(&r["scene"]).unwrap();
    for f in r["frames"].as_array().unwrap() {
        let t = f["t"].as_f64().unwrap();
        same(&eval::at(&scene.comp, t).unwrap(), &f["comp"], t);
    }
}

#[test]
fn unknown_names_are_refused() {
    let r = reference();
    let bad = |path: &str, v: Value| {
        let mut s = r["scene"].clone();
        *s.pointer_mut(path).unwrap() = v;
        Scene::load(&s).expect_err(path)
    };
    assert!(bad("/comp/layers/0/type", "blob".into()).contains("unknown item type"));
    assert!(bad("/comp/layers/0/anim/x/0/ease", "wobbly".into()).contains("unknown ease"));
    let mut s = r["scene"].clone();
    s["comp"]["layers"][0]["props"]["colour"] = "#ffffff".into();
    assert!(Scene::load(&s).unwrap_err().contains("card: a shape has no field \"colour\""));
    s = r["scene"].clone();
    s["version"] = 2.into();
    assert_eq!(Scene::load(&s).unwrap_err(), "scene version 2; this engine reads 1");
}

/// The frame's display RGBA, the stage markup drawn in the scene shell on the CPU.
fn draw(markup: &str, w: u32, h: u32, fonts: &[super::fonts::Font]) -> Vec<u8> {
    let html = stage::shell(w, h, fonts).unwrap().replace("<div id=\"rostrum-stage\"></div>", &format!("<div id=\"rostrum-stage\">{markup}</div>"));
    let assets = crate::assets::Assets::new(crate::color::Spec::default());
    let mut doc = blitz_html::HtmlDocument::from_html(&html, crate::serve::page_config(w, h, &assets));
    doc.handle_messages();
    doc.resolve(0.0);
    let mut painter = crate::painter::Painter::cpu(w, h, None).unwrap();
    painter.paint(false, |scene| blitz_paint::paint_scene(scene, &mut doc, 1.0, w, h, 0, 0)).unwrap();
    let mut px = vec![];
    crate::color::output(&crate::color::Spec::default(), &painter.read(), w, false, false, 0, &mut px);
    px
}

#[test]
fn a_frame_draws_as_the_python_stopgap_drew_it() {
    let r = reference();
    let scene = Scene::load(&r["scene"]).unwrap();
    let (w, h) = (scene.width(), scene.height());
    let t = r["stage_t"].as_f64().unwrap();
    let ours = draw(&stage::stage(&eval::at(&scene.comp, t).unwrap()).unwrap(), w, h, &scene.fonts);
    let py = draw(r["stage"].as_str().unwrap(), w, h, &scene.fonts);
    let differing = ours.chunks(4).zip(py.chunks(4)).filter(|(a, b)| a.iter().zip(b.iter()).any(|(x, y)| x.abs_diff(*y) > 2)).count();
    assert!(differing == 0, "{differing} pixels differ between the engine's frame and the Python stopgap's at t={t}");
    let lit = ours.chunks(4).filter(|p| p[0] > 60 || p[1] > 60 || p[2] > 60).count();
    assert!(lit > 2000, "the frame is nearly empty ({lit} lit pixels): the check would prove nothing");
}

/// A drawing layer shows the last drawing with at ≤ floor(t·fps), nothing before the first (drawing.py `frame_at`).
#[test]
fn a_drawing_shows_the_drawing_of_its_frame() {
    let mut s = reference()["scene"].clone();
    let pic = concat!(env!("CARGO_MANIFEST_DIR"), "/Cargo.toml");          // any file: the engine only checks it exists
    let props: serde_json::Map<String, Value> = s["comp"]["layers"][0]["props"].as_object().unwrap().iter()
        .filter(|(k, _)| fields::of("drawing").unwrap().1.iter().any(|f| f.0 == k.as_str())).map(|(k, v)| (k.clone(), v.clone())).collect();
    s["comp"]["layers"].as_array_mut().unwrap().push(serde_json::json!({"id": "doodle", "type": "drawing", "props": props,
        "frames": [{"at": 6, "src": format!("{pic}?b")}, {"at": 2, "src": pic}]}));
    assert!(Scene::load(&s).unwrap_err().contains("doodle.frames"), "a missing picture must be refused");
    s["comp"]["layers"][4]["frames"][0]["src"] = pic.into();
    let scene = Scene::load(&s).unwrap();
    let src = |t: f64| eval::at(&scene.comp, t).unwrap().layers.iter().find(|l| l.id == "doodle").map(|l| l.str("src").to_string());
    assert_eq!(src(0.0).as_deref(), Some(""));                              // fps 30: frame 0, before the first drawing
    assert_eq!(src(2.0 / 30.0).as_deref(), Some(pic));                      // frame 2 exactly
    assert_eq!(src(0.199).as_deref(), Some(pic));                           // frame 5, held
}

/// A text layer naming a font that is neither the project's nor the app's is refused when the scene loads (never
/// drawn in a fallback face), and the message says which fonts there are.
#[test]
fn an_unknown_font_is_refused() {
    let mut s = reference()["scene"].clone();
    let text = s["comp"]["layers"].as_array_mut().unwrap().iter_mut().find(|l| l["type"] == "text").expect("a text layer in the reference");
    let id = text["id"].as_str().unwrap().to_string();
    text["props"]["font"] = "No Such Sans".into();
    let scene = Scene::load(&s).unwrap();
    let err = crate::scene_serve::check(&scene).unwrap_err();
    assert!(err.starts_with(&format!("{id}: font \"No Such Sans\" not found")) && err.contains("Roboto Flex") && err.contains("Inter"), "{err}");
}

/// A text following a path layer (follow.rs) takes the path's transform and trim window at every time, and a
/// missing path is refused at load (never drawn as a straight line).
#[test]
fn a_text_follows_its_path_layer_on_every_frame() {
    let mut s = reference()["scene"].clone();
    let layers = s["comp"]["layers"].as_array_mut().unwrap();
    let mut text = layers.iter().find(|l| l["type"] == "text").expect("a text layer in the reference").clone();
    let mut path = serde_json::Map::new();
    for (name, kind) in fields::of("path").unwrap().1 {
        let v = match (name, kind) {
            ("d", _) => Value::from("M 0 200 L 900 200"),
            ("w", _) => Value::from(900.0),
            ("h", _) | ("x", _) | ("y", _) => Value::from(400.0),
            ("trimEnd" | "scale" | "scaleX" | "scaleY" | "opacity" | "miter" | "anchorX" | "anchorY", _) => Value::from(if name.starts_with("anchor") { 0.5 } else { 1.0 }),
            ("end", _) => Value::from(36000.0),
            (_, fields::Kind::Number) => Value::from(0.0),
            (_, fields::Kind::Color) => Value::from("#ffffff"),
            (_, fields::Kind::Toggle) => Value::from(false),
            (_, fields::Kind::Text) => Value::from(""),
            (_, fields::Kind::Choice(o)) => Value::from(o[0]),
        };
        path.insert(name.into(), v);
    }
    text["id"] = "rider".into();
    text["props"]["body"] = "ABCDEFGH".into();
    text["props"]["letterDelay"] = 0.0.into();
    text["props"]["size"] = 60.0.into();
    text["props"]["path"] = "".into();
    text["props"]["pathAlign"] = "start".into();
    text["props"]["pathLayer"] = "rail".into();
    for k in ["anim", "effects", "masks"] {
        text.as_object_mut().unwrap().remove(k);
    }
    let rail = serde_json::json!({"id": "rail", "type": "path", "props": path,
        "anim": {"x": [{"t": 0.0, "v": 400.0, "ease": "linear"}, {"t": 1.0, "v": 800.0, "ease": "linear"}],
                 "trimEnd": [{"t": 0.0, "v": 0.0, "ease": "linear"}, {"t": 1.0, "v": 1.0, "ease": "linear"}]}});
    layers.push(text);
    let gone = s.clone();
    s["comp"]["layers"].as_array_mut().unwrap().push(rail);
    let err = Scene::load(&gone).unwrap_err();
    assert!(err.contains("rider.pathLayer") && err.contains("rail"), "{err}");
    let scene = Scene::load(&s).unwrap();
    let rider = |t: f64| eval::at(&scene.comp, t).unwrap().layers.into_iter().find(|l| l.id == "rider").unwrap();
    assert_eq!(rider(0.5).num("x"), 600.0, "the text takes the path's keyed x at that time");
    let shown = |t: f64| super::letters::place(&rider(t)).unwrap().letters.len();
    assert_eq!(shown(0.0), 0, "nothing of the path is drawn yet, so no letter shows");
    assert!(shown(0.2) > 0 && shown(0.2) < 8 && shown(1.0) == 8, "letters show as the path is drawn on: {} {} {}", shown(0.0), shown(0.2), shown(1.0));
}
