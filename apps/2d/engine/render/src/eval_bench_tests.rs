//! Measurement only: where a motion-blurred frame's layer evaluation goes (scene_serve.rs `stage_at`), for whole films.
//! `ROSTRUM2D_BENCH_SCENES=a.json,b.json cargo test --profile agent eval_bench -- --ignored --nocapture`; each file is a
//! scene description (`describe` in apps/2d/python), drawn every `ROSTRUM2D_BENCH_EVERY`-th frame (default 3).

use std::collections::BTreeMap;
use std::time::Instant;

use serde_json::{json, Value};

#[test]
#[ignore]
fn eval_bench() {
    let every: usize = std::env::var("ROSTRUM2D_BENCH_EVERY").ok().and_then(|s| s.parse().ok()).unwrap_or(3);
    for path in std::env::var("ROSTRUM2D_BENCH_SCENES").unwrap_or_default().split(',').filter(|p| !p.is_empty()) {
        let v: Value = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
        let scene = crate::scene::Scene::load(&v).unwrap();
        let p = &v["comp"]["props"];
        let (fps, dur) = (p["fps"].as_f64().unwrap_or(30.0), p["duration"].as_f64().unwrap());
        let frames = (dur * fps).round() as usize;
        let (mut total, mut n, mut split) = (0.0, 0, BTreeMap::<&str, f64>::new());
        for i in (0..frames).step_by(every) {
            let t0 = Instant::now();
            let st = crate::scene_serve::stage_at(&scene, i as f64 / fps, &json!({})).unwrap();
            total += t0.elapsed().as_secs_f64() * 1000.0;
            n += 1;
            for (k, ms) in st.split() {
                *split.entry(k).or_default() += ms;
            }
        }
        let parts: Vec<String> = split.iter().map(|(k, v)| format!("{k} {:.1}", v / n as f64)).collect();
        println!("{path}: {n} frames, {:.1} ms a frame ({})", total / n as f64, parts.join(", "));
    }
}
