//! serve's `measure` (ENGINE_CONTRACT.md § 1): the box each text is laid out in, from its evaluated fields, by the
//! same path that draws it. Each text becomes one layer of a scratch comp, checked as a load checks it (mod.rs
//! `node`), written by stage.rs and laid out on the measuring page (the page shell's fonts, glyphs.rs's way; kept
//! between requests: measure_page.rs); its layer box is read as boxes.rs reads one (the border box, `final_layout`).
//! The whole list is one stage, one layout pass. No time: the caller evaluates animated fields first.

use serde_json::{json, Map, Value};

use super::fields::{self, Kind};
use super::{eval, fonts, stage, type_font, Node};

type R<T> = Result<T, String>;

/// The fields every text must give: what decides its box.
const NEEDED: &[&str] = &["body", "font", "size", "weight", "stretch", "tracking", "lineHeight", "align", "boxWidth"];

/// The type fields a text may leave out, as fields.py's defaults (the font as it is, one line, no letters played).
pub(super) fn plain() -> Map<String, Value> {
    let mut m = Map::new();
    for (f, v) in [
        ("ligatures", json!(true)), ("figures", json!("default")), ("smallCaps", json!(false)), ("features", json!("")),
        ("slant", json!(0.0)), ("grade", json!(0.0)), ("axes", json!("")), ("path", json!("")), ("pathOffset", json!(0.0)),
        ("pathAlign", json!("start")), ("pathOverflow", json!("hide")), ("letterDelay", json!(0.0)),
        ("letterSplit", json!("letters")), ("letterOrder", json!("forward")), ("letterSeed", json!(0.0)),
        ("counter", json!(false)), ("count", json!(0.0)), ("countDecimals", json!(0.0)), ("countDigits", json!(1.0)), ("countSeparator", json!("comma")),
        ("countPrefix", json!("")), ("countSuffix", json!("")),
    ] {
        m.insert(f.into(), v);
    }
    m
}

/// Every field of `kind`, set to what changes nothing: no move, no turn, full size and opacity, showing always.
pub(crate) fn neutral(kind: &str) -> Map<String, Value> {
    let mut m = Map::new();
    for (name, k) in fields::of(kind).expect("a known type").1 {
        let v = match (name, k) {
            ("scale" | "scaleX" | "scaleY" | "opacity", _) => json!(1.0),
            (f, _) if f.starts_with("run") && (f.ends_with("Scale") || f.ends_with("Opacity")) => json!(1.0),
            ("end", _) => json!(1e9),
            ("fillUnder", _) => json!("#00000000"),
            (_, Kind::Number) => json!(0.0),
            (_, Kind::Color) => json!("#000000"),
            (_, Kind::Toggle) => json!(false),
            (_, Kind::Text) => json!(""),
            (_, Kind::Choice(o)) => json!(o[0]),
        };
        m.insert(name.into(), v);
    }
    m
}

/// The scratch comp's size: wide and tall enough that no text is pressed by its edges.
const ROOM: u32 = 16384;

fn page_id(i: usize) -> String {
    format!("rostrum-measure-{i}")
}

/// One text's layer: the neutral layer, its type set plain, then the request's fields (an unknown one is refused).
fn layer(i: usize, item: &Value) -> R<(String, Value)> {
    let id = item["id"].as_str().ok_or("measure: every item needs an id")?.to_string();
    let own = item.as_object().unwrap();
    if let Some(missing) = NEEDED.iter().find(|f| !own.contains_key(**f)) {
        return Err(format!("{id}: measure needs {missing} (every text gives {})", NEEDED.join(", ")));
    }
    let mut props = neutral("text");
    props.extend(plain());
    props.extend(own.iter().filter(|(k, _)| *k != "id").map(|(k, v)| (k.clone(), v.clone())));
    // Its id in the page is its place in the list: a caller's id can be anything.
    Ok((id, json!({ "id": page_id(i), "type": "text", "props": props })))
}

/// `{"items": [{id, body, font, size, …}, …]}` → `{"ok": true, "sizes": {id: [w, h]}}`. `held`: the loaded scene's
/// fonts (its own `fonts`, then the app's), else the app's.
pub fn measure(req: &Value, held: Option<&[fonts::Font]>) -> R<Value> {
    let items = req["items"].as_array().ok_or("measure needs items: [{id, body, font, size, …}, …]")?;
    let listed;
    let all: &[fonts::Font] = match held {
        Some(f) => f,
        None => {
            listed = std::sync::Arc::new(fonts::list(&Value::Null)?);
            type_font::register(&listed);
            listed.as_slice()
        }
    };
    let mut ids = vec![];
    let mut layers = vec![];
    let mut used: Vec<String> = vec![];
    for (i, item) in items.iter().enumerate() {
        let (id, l) = layer(i, item)?;
        let node = super::node(&l, "measure").map_err(|e| e.replace(&page_id(i), &id))?;
        // The load's check (scene_serve.rs `check`), word for word.
        let font = fonts::pick(all, node.props["font"].as_str().unwrap_or(""), 400.0, node.props["italic"].as_bool() == Some(true))
            .map_err(|e| format!("{id}: {e}"))?;
        if !used.contains(&font.family) {
            used.push(font.family.clone());
        }
        ids.push(id);
        layers.push(node);
    }
    let mut comp_props = neutral("comp");
    comp_props.insert("width".into(), json!(ROOM));
    comp_props.insert("height".into(), json!(ROOM));
    comp_props.insert("fps".into(), json!(30.0));
    comp_props.insert("background".into(), json!("#000000"));
    let comp = Node { id: "measure".into(), kind: "comp", role: fields::Role::Comp, props: comp_props, anim: vec![], effects: vec![], masks: vec![], layers, frames: vec![], paint: vec![], paint_inside: true, fill_frames: vec![], rig: vec![], stops: vec![] };
    let named = |e: String| ids.iter().enumerate().rev().fold(e, |e, (i, id)| e.replace(&page_id(i), id));
    let markup = stage::stage(&eval::whole(&comp, 0.0)).map_err(named)?;
    let sizes = super::measure_page::lay_out(&fonts::faces_of(all, &used), ROOM, &markup, |doc| {
        let mut sizes = Map::new();
        for (i, id) in ids.iter().enumerate() {
            let n = doc.query_selector(&format!("#{}", page_id(i))).ok().flatten().ok_or_else(|| format!("{id}: its layer is missing from the measured page"))?;
            let s = doc.get_node(n).unwrap().final_layout().size;
            sizes.insert(id.clone(), json!([s.width as f64, s.height as f64]));
        }
        Ok(sizes)
    })?;
    Ok(json!({ "ok": true, "sizes": sizes }))
}
