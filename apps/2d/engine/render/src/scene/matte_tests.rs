//! A track matte that names no layer beside it is refused loudly when the scene loads or is edited (else the layer
//! would silently draw unmatted, or vanish).

use serde_json::{json, Map};

use super::super::fields::Role;
use super::super::Node;
use super::check;

fn layer(id: &str, matte: &str) -> Node {
    let mut props = Map::new();
    props.insert("matte".into(), json!(matte));
    props.insert("matteMode".into(), json!("alpha"));
    Node { id: id.into(), kind: "shape", role: Role::Layer, props, anim: vec![], effects: vec![], masks: vec![], layers: vec![], frames: vec![], rig: vec![] }
}

fn comp(layers: Vec<Node>) -> Node {
    Node { id: "main".into(), kind: "comp", role: Role::Comp, props: Map::new(), anim: vec![], effects: vec![], masks: vec![], layers, frames: vec![], rig: vec![] }
}

#[test]
fn a_matte_must_be_a_layer_beside_it() {
    assert!(check(&comp(vec![layer("pic", "title"), layer("title", "")])).is_ok());
    let missing = check(&comp(vec![layer("pic", "nope")])).unwrap_err();
    assert!(missing.contains("pic.matte") && missing.contains("nope"), "{missing}");
    assert!(check(&comp(vec![layer("pic", "pic")])).is_err(), "its own matte");
    assert!(check(&comp(vec![layer("a", "b"), layer("b", "a")])).is_err(), "a loop");
    let mut group = layer("g", "");
    group.layers.push(layer("inner", "title"));
    assert!(check(&comp(vec![group, layer("title", "")])).is_err(), "a matte in another group is not beside it");
}
