//! `{"outline": {"id", "t"}}` (scene_serve.rs): the one place the varied-stroke outline is asked for outside drawing.
//! Lottie has no variable-width stroke, so its export asks for the engine's own outline (stage_path.rs, stroke_width.rs)
//! as path data and carries it as a fill: one geometry, no copy in Python.

use serde_json::{json, Value};

use super::eval::{self, Item};
use super::Node;

fn find<'a, 'b>(it: &'b Item<'a>, id: &str) -> Option<&'b Item<'a>> {
    if it.id == id {
        return Some(it);
    }
    it.layers.iter().find_map(|c| find(c, id))
}

/// `d` is the outline at `t` ("" when none of the stroke shows), null when the layer's stroke is even.
pub fn outline(comp: &Node, req: &Value) -> Result<Value, String> {
    let id = req["id"].as_str().ok_or("outline needs id (a path layer)")?;
    let t = req["t"].as_f64().ok_or("outline needs t (seconds)")?;
    let whole = eval::whole(comp, t);
    let it = find(&whole, id).ok_or_else(|| format!("outline: no layer \"{id}\""))?;
    if it.kind != "path" {
        return Err(format!("outline: \"{id}\" is a {}, not a path", it.kind));
    }
    Ok(json!({ "ok": true, "d": super::stage::outline_d(it)? }))
}
