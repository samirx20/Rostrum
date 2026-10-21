use super::*;

/// A state saved from one instance (a parameter set through the controller, flushed to the
/// processor) sets the same value in another. Surge XT (VST3) when installed; skipped otherwise.
#[test]
fn a_vst3_state_saved_from_one_instance_sets_another() {
    let Some(bundle) = crate::plugins::vst3::folders().into_iter().map(|d| d.join("Surge XT.vst3")).find(|p| p.exists()) else {
        eprintln!("Surge XT (VST3) not installed: skipped");
        return;
    };
    let spec = |params: &str, state: Option<String>| -> SessionSpec {
        serde_json::from_value(serde_json::json!({ "plugin": { "format": "vst3", "path": bundle.to_string_lossy(), "id": "01EFCDAB8291EBFA566D624153675854", "params": serde_json::from_str::<serde_json::Value>(params).unwrap(), "state": state } })).unwrap()
    };
    let vol = 1336600346u32; // Global Volume
    let mut a = Vst3Session::new(&spec(&format!("[[{vol}, 0.3]]"), None)).unwrap();
    let state = a.state().unwrap();
    a.close(None);
    let mut b = Vst3Session::new(&spec(&format!("[[{vol}, [[0, 0.9]]]]"), Some(state))).unwrap();
    let v = b.values();
    b.close(None);
    assert!((v[0].1 - 0.3).abs() < 1e-3, "{v:?}");
}
