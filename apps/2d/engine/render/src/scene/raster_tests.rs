//! A tiled picture or painted fill (stage_raster.rs) shows no seam where tiles meet, at a scale off the pixel grid,
//! turned, drifting, inside a turned and scaled layer (what a seamless painting relies on), and a painted fill's
//! picture is the painting's drawing of the frame (`fillFrames`).

use serde_json::{json, Value};

use super::{eval, stage, tests::draw, Scene};

/// A flat grey tile (any seam would show as a darker or lighter line across the flat colour).
fn tile(dir: &std::path::Path, name: &str, grey: u8) -> String {
    let path = dir.join(name);
    image::RgbaImage::from_pixel(8, 8, image::Rgba([grey, grey, grey, 255])).save(&path).unwrap();
    path.to_string_lossy().into_owned()
}

fn scene(card: Value) -> Value {
    let mut s = json!({"format": "rostrum-2d-scene", "version": super::VERSION, "comp": {"id": "c", "type": "comp", "layers": [card]}});
    s["comp"]["props"] = Value::Object(super::measure::neutral("comp"));
    s["comp"]["props"]["width"] = 400.into();
    s["comp"]["props"]["height"] = 300.into();
    s["comp"]["props"]["fps"] = 30.into();
    s["comp"]["props"]["duration"] = 2.into();
    s
}

fn card(src: &str) -> Value {
    let mut p = super::measure::neutral("shape");
    for (k, v) in [("x", json!(200)), ("y", json!(150)), ("anchorX", json!(0.5)), ("anchorY", json!(0.5)), ("w", json!(300)), ("h", json!(200)),
                   ("filled", json!(true)), ("fillOpacity", json!(1.0)), ("rotation", json!(7)), ("scale", json!(1.13)), ("fillPicture", json!(src)), ("fillFit", json!("tile")),
                   ("fillScale", json!(2.37)), ("fillRotation", json!(15)), ("fillDriftX", json!(41.3)), ("fillDriftY", json!(-9.7)), ("fillOffsetX", json!(3.3))] {
        p.insert(k.into(), v);
    }
    json!({"id": "card", "type": "shape", "props": p})
}

#[test]
fn tiles_meet_with_no_seam() {
    let dir = std::env::temp_dir().join(format!("rostrum-raster-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let scene = Scene::load(&scene(card(&tile(&dir, "grey.png", 128)))).unwrap();
    let px = draw(&stage::stage(&eval::at(&scene.comp, 0.53).unwrap()).unwrap(), 400, 300, &[]);
    // The middle of the card (well inside its turned outline): every pixel the one grey.
    let mut off = vec![];
    for y in 110..190 {
        for x in 120..280 {
            let g = px[(y * 400 + x) * 4 + 1];
            if g.abs_diff(128) > 2 {
                off.push((x, y, g));
            }
        }
    }
    assert!(off.is_empty(), "{} pixels inside the tiled fill differ from its flat grey (a seam), e.g. {:?}", off.len(), &off[..off.len().min(5)]);
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn a_painted_fill_shows_the_drawing_of_its_frame() {
    let dir = std::env::temp_dir().join(format!("rostrum-painted-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let (a, b) = (tile(&dir, "a.png", 40), tile(&dir, "b.png", 200));
    let mut c = card("");
    c["fillFrames"] = json!([{"at": 4, "src": b}, {"at": 0, "src": a}]);
    let scene = Scene::load(&scene(c)).unwrap();
    let pic = |t: f64| eval::at(&scene.comp, t).unwrap().layers[0].str("fillPicture").to_string();
    assert_eq!((pic(0.0), pic(3.0 / 30.0), pic(4.0 / 30.0)), (a.clone(), a, b));
    let _ = std::fs::remove_dir_all(&dir);
}

/// A red card under one mask (`mask` props over the neutral ones), drawn at 0.5 s over the frame's black: the red in the card's middle.
fn masked_red(mask: &[(&str, Value)]) -> u8 {
    let mut p = super::measure::neutral("shape");
    for (k, v) in [("x", json!(200)), ("y", json!(150)), ("anchorX", json!(0.5)), ("anchorY", json!(0.5)), ("w", json!(300)), ("h", json!(200)),
                   ("filled", json!(true)), ("fill", json!("#ff0000")), ("fillOpacity", json!(1.0))] {
        p.insert(k.into(), v);
    }
    let mut mp = super::measure::neutral("mask");
    for (k, v) in mask {
        mp.insert((*k).into(), v.clone());
    }
    let card = json!({"id": "card", "type": "shape", "props": p, "masks": [{"id": "reveal", "type": "mask", "props": mp}]});
    let scene = Scene::load(&scene(card)).unwrap();
    let px = draw(&stage::stage(&eval::at(&scene.comp, 0.5).unwrap()).unwrap(), 400, 300, &[]);
    px[(150 * 400 + 200) * 4]
}

#[test]
fn a_mask_of_width_or_height_zero_shows_nothing() {
    // The guides' reveal starts at W 0 (start-here.md): before it moves, nothing of the layer shows (2D r12).
    let at = |w: f64, h: f64, more: &[(&str, Value)]| {
        let mut m = vec![("x", json!(0)), ("y", json!(0)), ("w", json!(w)), ("h", json!(h))];
        m.extend(more.iter().cloned());
        masked_red(&m)
    };
    assert_eq!(at(300.0, 200.0, &[]), 255, "a mask over the whole card shows it");
    assert_eq!(at(0.0, 200.0, &[]), 0, "W 0 hides the card");
    assert_eq!(at(300.0, 0.0, &[]), 0, "H 0 hides the card");
    assert_eq!(at(-20.0, 200.0, &[]), 0, "a negative W hides it too");
    assert_eq!(at(0.0, 200.0, &[("feather", json!(30))]), 0, "a soft W 0 hides it");
    assert_eq!(at(0.0, 200.0, &[("shape", json!("ellipse"))]), 0, "an ellipse of W 0 hides it");
    assert_eq!(at(0.0, 200.0, &[("invert", json!(true))]), 255, "inverted, an empty mask hides nothing");
}
