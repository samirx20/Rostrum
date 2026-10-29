//! `{"shapes": {"items": [{id, shape, w, h, …}]}}` (scene_serve.rs): each parametric shape (shape_geom.rs) as the path
//! layer the stage draws it as, for Convert to path and combining: one geometry, no copy in Python. Needs no scene.
//! Each item is checked as a load checks a shape (mod.rs `node`); fields a shape doesn't have are left out, so a
//! document's layer can be sent as it is.

use serde_json::{json, Map, Value};

use super::fields::{self, Role};
use super::{eval, measure::neutral, shape_geom, Node};

/// → `{"ok": true, "paths": {id: {path field: value}}}`: the path fields the shape's own don't already give: `d` (in its
/// own box px), the path's settings, and for an open line or spiral its stroke (`stroke`, `strokeColor`, `strokeWidth`,
/// `cap`, `filled`) from its fill and line.
pub fn shapes(req: &Value) -> Result<Value, String> {
    let items = req["items"].as_array().ok_or("shapes needs items: [{id, shape, w, h, …}, …]")?;
    let mut ids = vec![];
    let mut layers = vec![];
    for item in items {
        let own = item.as_object().ok_or("shapes: every item must be an object")?;
        let id = own.get("id").and_then(Value::as_str).ok_or("shapes: every item needs an id")?;
        let mut props = neutral("shape");
        props.extend(own.iter().filter(|(k, _)| props.contains_key(*k)).map(|(k, v)| (k.clone(), v.clone())).collect::<Vec<_>>());
        layers.push(super::node(&json!({ "id": id, "type": "shape", "props": props }), "shapes")?);
        ids.push(id.to_string());
    }
    let comp = Node { id: "shapes".into(), kind: "comp", role: Role::Comp, props: neutral("comp"), anim: vec![], effects: vec![], masks: vec![], layers, frames: vec![], paint: vec![], paint_inside: true, fill_frames: vec![], rig: vec![], stops: vec![] };
    let whole = eval::whole(&comp, 0.0);
    let path_fields: Vec<&str> = fields::of("path").unwrap().1.iter().map(|f| f.0).collect();
    let mut paths = Map::new();
    for (id, it) in ids.iter().zip(&whole.layers) {
        if !shape_geom::is_path(it) {
            return Err(format!("{id}: a {} is drawn as a box; its outline comes from its w, h and radius", it.str("shape")));
        }
        let p = shape_geom::as_path(it)?;
        // What the path sets that the shape doesn't have, or has otherwise; its place and the rest of its look stay the layer's.
        let look: Map<String, Value> = p.props.into_owned().into_iter().filter(|(k, v)| path_fields.contains(&k.as_str()) && it.props.get(k) != Some(v)).collect();
        paths.insert(id.clone(), Value::Object(look));
    }
    Ok(json!({ "ok": true, "paths": paths }))
}
