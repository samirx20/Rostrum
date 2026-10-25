//! An export's pictures are the same byte for byte whatever the number of drawing workers, and a failure on any
//! worker fails the export (naming the frame) instead of hanging or reporting success. On the CPU: no GPU needed.

use serde_json::{json, Value};

use crate::scene::{FORMAT, VERSION};
use crate::scene_serve::{load, Held};

fn item(id: &str, ty: &str, props: Value) -> Value {
    let mut p = crate::scene::measure::neutral(ty);
    p.extend(props.as_object().unwrap().clone());
    json!({ "id": id, "type": ty, "props": p })
}

/// Moving shapes, one glowing, motion-blurred: every frame differs and is drawn through sub-frames.
fn scene() -> Value {
    let mut layers = vec![];
    for (k, fill) in ["#ff3300", "#33ccff", "#ffffff"].iter().enumerate() {
        let x = 10.0 + 70.0 * k as f64;
        let mut s = item(&format!("s{k}"), "shape", json!({ "x": x, "y": 40.0 + 50.0 * k as f64, "w": 60.0, "h": 40.0, "fill": fill }));
        s["anim"] = json!({ "x": [{ "t": 0.0, "v": x }, { "t": 1.0, "v": x + 120.0 }] });
        if k == 1 {
            s["effects"] = json!([item("glow", "glow", json!({}))]);
        }
        layers.push(s);
    }
    let mut comp = item("main", "comp", json!({ "width": 320.0, "height": 240.0, "fps": 30.0, "duration": 1.0, "background": "#101418", "shutter": 180.0, "shutterSamples": 4.0 }));
    comp["layers"] = Value::from(layers);
    json!({ "format": FORMAT, "version": VERSION, "comp": comp })
}

#[test]
fn the_pictures_are_the_same_whatever_the_number_of_workers() {
    let (mut held, mut session) = (Held::default(), None);
    load(&mut held, &mut session, &mut None, &json!({ "scene": scene(), "cpu": true })).unwrap();
    let s = session.as_mut().unwrap();
    let dir = std::env::temp_dir().join(format!("rostrum-crew-{}", std::process::id()));
    let mut frames = vec![];
    for workers in [1, 3] {
        let out = dir.join(format!("w{workers}"));
        std::fs::create_dir_all(&out).unwrap();
        let images = out.join("f-{frame}.png").to_string_lossy().into_owned();
        let reply = crate::scene_export::export(&held, s, &json!({ "images": images, "end": 0.4, "workers": workers }), &mut |_| {}).unwrap();
        assert_eq!((reply["frames"].as_u64(), reply["workers"].as_u64()), (Some(12), Some(workers)));
        frames.push((0..12).map(|i| std::fs::read(out.join(format!("f-{i:04}.png"))).unwrap()).collect::<Vec<_>>());
    }
    for (i, (a, b)) in frames[0].iter().zip(&frames[1]).enumerate() {
        assert!(a == b, "frame {i} differs between 1 and 3 workers");
    }
    // A picture that can't be written fails the export, whichever worker drew it.
    let bad = dir.join("missing").join("f-{frame}.png").to_string_lossy().into_owned();
    let err = crate::scene_export::export(&held, s, &json!({ "images": bad, "end": 0.4, "workers": 3 }), &mut |_| {}).unwrap_err();
    assert!(err.contains("export frame"), "{err}");
    let _ = std::fs::remove_dir_all(&dir);
}

/// p1 (2026-10-25): a radial gradient of no size (centred on its box's edge) inside a tilted, flipped group had no Skia
/// shader; the unwrap panicked on the export's own drawing thread and the export waited forever. It now draws as its
/// edge colour and the export finishes.
#[test]
fn a_gradient_of_no_size_in_a_tilted_flipped_group_exports() {
    let mut grad = item("g", "gradient", json!({ "style": "radial", "cx": 0.5, "cy": 1.0, "color1": "#ff6a24", "color2": "#0d0605" }));
    grad["props"]["span"] = json!("box");
    let mut screen = item("screen", "shape", json!({ "x": 60.0, "y": 80.0, "w": 100.0, "h": 150.0, "fill": "#1a0c08" }));
    screen["effects"] = json!([grad]);
    let mut flip = item("flip", "group", json!({ "x": 120.0, "y": 120.0, "w": 120.0, "h": 160.0, "scaleX": 0.02 }));
    flip["anim"] = json!({ "scaleX": [{ "t": 0.0, "v": 0.0 }, { "t": 0.2, "v": 1.0 }] });
    flip["layers"] = json!([screen]);
    let mut tilt = item("tilt", "group", json!({ "x": 160.0, "y": 120.0, "w": 240.0, "h": 200.0, "tiltY": -4.0 }));
    tilt["layers"] = json!([flip]);
    let mut comp = item("main", "comp", json!({ "width": 320.0, "height": 240.0, "fps": 30.0, "duration": 0.2, "background": "#101418" }));
    comp["layers"] = json!([tilt]);
    let (mut held, mut session) = (Held::default(), None);
    load(&mut held, &mut session, &mut None, &json!({ "scene": { "format": FORMAT, "version": VERSION, "comp": comp }, "cpu": true })).unwrap();
    let dir = std::env::temp_dir().join(format!("rostrum-flat-grad-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let images = dir.join("f-{frame}.png").to_string_lossy().into_owned();
    let reply = crate::scene_export::export(&held, session.as_mut().unwrap(), &json!({ "images": images, "workers": 2 }), &mut |_| {});
    let _ = std::fs::remove_dir_all(&dir);
    assert_eq!(reply.unwrap()["frames"].as_u64(), Some(6));
}
