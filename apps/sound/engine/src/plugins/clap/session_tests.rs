use super::*;

fn surge() -> Option<String> {
    crate::plugins::clap::folders().into_iter().map(|d| d.join("Surge XT.clap")).find(|p| p.exists()).map(|p| p.to_string_lossy().into_owned())
}

/// A preset's state round trip: a parameter set in one instance, its state saved and loaded into
/// another, which then holds the same value, and renders differently from the default.
#[test]
fn a_clap_state_saved_from_one_instance_sets_another_and_its_render() {
    let Some(path) = surge() else {
        eprintln!("Surge XT not installed: skipped");
        return;
    };
    let spec = |params: &str, state: Option<String>| -> SessionSpec {
        serde_json::from_value(serde_json::json!({ "plugin": { "path": path, "id": "org.surge-synth-team.surge-xt", "params": serde_json::from_str::<serde_json::Value>(params).unwrap(), "state": state } })).unwrap()
    };
    let vol = 3484083994u32; // Global & FX / Global Volume
    let mut a = ClapSession::new(&spec(&format!("[[{vol}, 0.2]]"), None)).unwrap();
    assert!((a.values()[0].1 - 0.2).abs() < 1e-6);
    let state = a.state().unwrap();
    a.close(None);
    let mut b = ClapSession::new(&spec(&format!("[[{vol}, [[0, 0.9]]]]"), Some(state.clone()))).unwrap();
    let v = b.values();
    b.close(None);
    assert!((v[0].1 - 0.2).abs() < 1e-6, "{v:?}");
    // Rendered with that state (and nothing else): quieter than the default patch.
    let render = |state: Option<String>| {
        let s = crate::plugins::clap::PluginSpec { format: "clap".into(), path: path.clone(), id: "org.surge-synth-team.surge-xt".into(), params: vec![], state, at: 0.0, cc: vec![] };
        let (mut l, mut r) = (vec![0f32; 24000], vec![0f32; 24000]);
        crate::plugins::clap::render::render(&s, &[crate::plugins::clap::Note { start: 0, end: 20000, key: 57, velocity: 0.8 }], &mut l, &mut r, 48000.0, false).unwrap();
        (l.iter().map(|x| (*x as f64).powi(2)).sum::<f64>() / 24000.0).sqrt()
    };
    let (quiet, default) = (render(Some(state)), render(None));
    assert!(quiet < default * 0.8 && quiet > 0.0, "{quiet} vs {default}");
}
