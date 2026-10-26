//! The scene description (ENGINE_CONTRACT.md v2): loaded and checked whole (anything unknown is refused, naming
//! the item and field), then evaluated per frame (eval.rs) and written as the stage the renderer draws (stage.rs).
//! serve's `scene`, `frame {t}`, `export` and `edit` requests are in scene_serve.rs.

pub mod blends;
pub mod change;
pub mod ease;
pub mod eval;
pub mod fields;
pub mod follow;
pub mod font_list;
pub mod fonts;
pub mod fonts_scan;
pub mod grade;
pub mod grain;
pub mod grade_curve;
pub mod letters;
pub mod matte;
pub mod measure;
pub mod measure_page;
pub mod morph;
pub mod outline_cmd;
pub mod path_data;
pub mod shape_cmd;
pub mod shape_geom;
pub mod stage;
pub mod stage_type;
pub mod stage_fill;
pub mod stage_raster;
pub mod stage_fx;
pub mod stroke_width;
pub mod type_font;
pub mod width_profile;
#[cfg(test)]
mod tests;
#[cfg(test)]
mod raster_tests;

use std::collections::HashSet;
use std::sync::Arc;

use serde_json::{Map, Value};

use change::Refs;

use ease::Ease;
use fields::{Kind, Role};

pub const FORMAT: &str = "rostrum-2d-scene";
pub const VERSION: u64 = 3;      // 2: the scene's frame (FRAME.md) in place of cameras; 3: picture and painted fill per use (fillOffsetX … fillBlend, fillFrames)

/// One key: its time, its value (a number, a colour kept as written and in linear light, a path's shape or width profile) and the ease of
/// the stretch it starts; a number key's optional spatial handles `out` (leaving it) and `in` (arriving at it), offsets
/// from its value (eval.rs `between`).
#[derive(Clone, Debug)]
pub struct Key {
    pub t: f64,
    pub value: KeyValue,
    pub ease: Ease,
    pub out: Option<f64>,
    pub inn: Option<f64>,
}

#[derive(Clone, Debug)]
pub enum KeyValue {
    Number(f64),
    Color(String, [f64; 4]),
    /// A path's `d`, blended to the next key's by morph.rs.
    Path(String),
    /// A path's `widthProfile` as written and read, blended to the next key's by width_profile::blend.
    Profile(String, Vec<(f64, f64)>),
}

/// One item of the scene: still values (`props`, every field present), keys per animated field (sorted by time),
/// and its children.
#[derive(Clone, Debug)]
pub struct Node {
    pub id: String,
    pub kind: &'static str,
    pub role: Role,
    pub props: Map<String, Value>,
    pub anim: Vec<(String, Vec<Key>)>,
    pub effects: Vec<Node>,
    pub masks: Vec<Node>,
    pub layers: Vec<Node>,
    /// A drawing layer's drawings: (frame number it appears at, its picture, where the picture lies in the canvas),
    /// sorted by frame (contract § 2).
    pub frames: Vec<Pic>,
    /// Paint on an element (contract § 2 `paint`): its drawings as `frames` are, and whether it is kept inside the
    /// element's own pixels. Empty: no paint.
    pub paint: Vec<Pic>,
    pub paint_inside: bool,
    /// A painted fill's drawings (contract § 2 `fillFrames`; a shape or path), as `frames` are: the one showing is the
    /// fill's picture (stage_raster.rs). Empty: the fill is `fillPicture` as written.
    pub fill_frames: Vec<Pic>,
    /// A rig's bones, iks and binds (crate::rig; RIG.md).
    pub rig: Vec<Node>,
    /// A gradient's colour stops (stage_fill.rs).
    pub stops: Vec<Node>,
}

#[derive(Clone, Debug)]
pub struct Scene {
    pub comp: Node,
    /// The fonts its text can name (fonts.rs): the scene's own `fonts`, then the app's, then the computer's.
    pub fonts: Arc<Vec<fonts::Font>>,
    /// The `fonts` the scene gave (null: none): a later load giving the same takes `fonts` as they are.
    fonts_given: Value,
}

impl Scene {
    /// A `scene` load with nothing held (the tests' way in).
    #[cfg(test)]
    pub fn load(v: &Value) -> Result<Scene, String> {
        Scene::read(v, &mut Refs::none(), None)
    }

    /// A load (scene_serve.rs `scene` / `change`): `refs` resolves the ids a `change` keeps from the held scene
    /// (change.rs); `held`'s fonts are taken as they are when the same `fonts` are given.
    pub fn read(v: &Value, refs: &mut Refs, held: Option<&Scene>) -> Result<Scene, String> {
        if v["format"] != FORMAT {
            return Err(format!("not a scene description: format {} (expected \"{FORMAT}\")", v["format"]));
        }
        match v["version"].as_u64() {
            Some(VERSION) => {}
            other => return Err(format!("scene version {}; this engine reads {VERSION}", other.map_or(v["version"].to_string(), |n| n.to_string()))),
        }
        let comp = node_in(&v["comp"], "scene", refs)?;
        if comp.role != Role::Comp {
            return Err(format!("{}: the scene's top item is a {}, not a comp", comp.id, comp.kind));
        }
        let mut seen = HashSet::new();
        comp.walk(&mut |n| if seen.insert(n.id.clone()) { Ok(()) } else { Err(format!("{}: the id is used twice", n.id)) })?;
        crate::rig::check(&comp)?;
        crate::frame::check(&comp)?;
        follow::check(&comp)?;
        matte::check(&comp)?;
        grade::check(&comp)?;
        let given = v.get("fonts").cloned().unwrap_or(Value::Null);
        let fonts = match held {
            Some(h) if h.fonts_given == given => h.fonts.clone(),
            _ => Arc::new(fonts::list(&given)?),
        };
        type_font::register(&fonts);
        Ok(Scene { comp, fonts, fonts_given: given })
    }

    pub fn width(&self) -> u32 {
        self.comp.props["width"].as_f64().unwrap_or(0.0) as u32
    }

    pub fn height(&self) -> u32 {
        self.comp.props["height"].as_f64().unwrap_or(0.0) as u32
    }

    pub fn fps(&self) -> f64 {
        self.comp.props["fps"].as_f64().unwrap_or(30.0)
    }

    pub fn duration(&self) -> f64 {
        self.comp.props["duration"].as_f64().unwrap_or(0.0)
    }

    /// `edit` (a drag, a typed value): `[{"id", "props"?: {field: value}, "anim"?: {field: [keys] | null}}, …]`,
    /// checked whole before any of it is applied.
    pub fn edit(&mut self, edits: &Value) -> Result<usize, String> {
        let list = edits.as_array().ok_or("edit takes a list of {id, props?, anim?}")?;
        let mut next = self.comp.clone();
        for e in list {
            let id = e["id"].as_str().ok_or("an edit needs an id")?;
            let n = next.find_mut(id).ok_or_else(|| format!("{id}: no such item in the scene"))?;
            let fields = fields::of(n.kind).unwrap().1;
            for (name, value) in e["props"].as_object().into_iter().flatten() {
                let f = fields.iter().find(|f| f.0 == name).ok_or_else(|| unknown_field(id, n.kind, name, &fields))?;
                check_value(id, f, value)?;
                n.props.insert(name.clone(), value.clone());
            }
            for (name, keys) in e["anim"].as_object().into_iter().flatten() {
                n.anim.retain(|(p, _)| p != name);
                if !keys.is_null() {
                    let f = fields.iter().find(|f| f.0 == name).ok_or_else(|| unknown_field(id, n.kind, name, &fields))?;
                    n.anim.push((name.clone(), track(id, n.kind, f, keys)?));
                }
            }
            n.anim.sort_by(|a, b| a.0.cmp(&b.0));
        }
        crate::rig::check(&next)?;
        crate::frame::check(&next)?;
        follow::check(&next)?;
        matte::check(&next)?;
        grade::check(&next)?;
        self.comp = next;
        Ok(list.len())
    }
}

impl Node {
    pub fn walk(&self, f: &mut impl FnMut(&Node) -> Result<(), String>) -> Result<(), String> {
        f(self)?;
        self.effects.iter().chain(&self.masks).chain(&self.layers).chain(&self.rig).chain(&self.stops).try_for_each(|c| c.walk(f))
    }

    fn find_mut(&mut self, id: &str) -> Option<&mut Node> {
        if self.id == id {
            return Some(self);
        }
        self.effects.iter_mut().chain(&mut self.masks).chain(&mut self.layers).chain(&mut self.rig).chain(&mut self.stops).find_map(|c| c.find_mut(id))
    }
}

fn unknown_field(id: &str, kind: &str, name: &str, fields: &[fields::Field]) -> String {
    format!("{id}: a {kind} has no field \"{name}\"; it has: {}", fields.iter().map(|f| f.0).collect::<Vec<_>>().join(", "))
}

/// One item, checked: its type known, every field present with a value of the right kind, nothing unknown,
/// children only where its role allows them.
fn node(v: &Value, parent: &str) -> Result<Node, String> {
    node_in(v, parent, &mut Refs::none())
}

/// `node`, where a child given as an id is the held scene's item of that id, kept as it is (change.rs).
fn node_in(v: &Value, parent: &str, refs: &mut Refs) -> Result<Node, String> {
    let obj = v.as_object().ok_or_else(|| format!("{parent}: an item must be an object"))?;
    let id = v["id"].as_str().ok_or_else(|| format!("{parent}: an item without an id"))?.to_string();
    let ty = v["type"].as_str().ok_or_else(|| format!("{id}: no type"))?;
    let kind = fields::TYPES.iter().copied().find(|t| *t == ty).ok_or_else(|| format!("{id}: unknown item type \"{ty}\"; this engine draws: {}", fields::TYPES.join(", ")))?;
    let (role, fields) = fields::of(kind).unwrap();
    for k in obj.keys() {
        if !matches!(k.as_str(), "id" | "type" | "props" | "anim" | "effects" | "masks" | "layers") && !(k == "frames" && matches!(kind, "drawing" | "video")) && !(k == "rig" && kind == "rig") && !(k == "stops" && kind == "gradient") && !(k == "paint" && PAINTED.contains(&kind)) && !(k == "fillFrames" && RASTER_FILLED.contains(&kind)) {
            return Err(format!("{id}: unknown part \"{k}\" (an item has id, type, props, anim, effects, masks, layers; a drawing or video also frames; a rig also rig; a gradient also stops; a {} also paint; a {} also fillFrames)", PAINTED.join(", "), RASTER_FILLED.join(", ")));
        }
    }
    let props = v["props"].as_object().ok_or_else(|| format!("{id}: no props"))?.clone();
    for name in props.keys() {
        if !fields.iter().any(|f| f.0 == name) {
            return Err(unknown_field(&id, kind, name, &fields));
        }
    }
    for f in &fields {
        check_value(&id, f, props.get(f.0).ok_or_else(|| format!("{id}: field \"{}\" is missing (the scene carries every field)", f.0))?)?;
    }
    let mut anim = vec![];
    for (name, keys) in v["anim"].as_object().into_iter().flatten() {
        let f = fields.iter().find(|f| f.0 == name).ok_or_else(|| unknown_field(&id, kind, name, &fields))?;
        anim.push((name.clone(), track(&id, kind, f, keys)?));
    }
    let mut kids = |part: &str, allowed: bool, want: &[Role]| -> Result<Vec<Node>, String> {
        let Some(list) = v.get(part) else { return Ok(vec![]) };
        if !allowed {
            return Err(format!("{id}: a {kind} has no {part}"));
        }
        let list = list.as_array().ok_or_else(|| format!("{id}: {part} must be a list"))?;
        let out = list.iter().map(|c| match c.as_str() {
            Some(kept) => refs.take(kept, &id),
            None => node_in(c, &id, refs),
        }).collect::<Result<Vec<_>, _>>()?;
        match out.iter().find(|c| !want.contains(&c.role)) {
            Some(c) => Err(format!("{}: a {} can't be in {id}'s {part}", c.id, c.kind)),
            None => Ok(out),
        }
    };
    let layer = role == Role::Layer;
    Ok(Node {
        effects: kids("effects", layer, &[Role::Effect])?,
        masks: kids("masks", layer, &[Role::Mask])?,
        layers: kids("layers", role == Role::Comp || matches!(kind, "group" | "rig"), &[Role::Layer])?,
        rig: kids("rig", kind == "rig", &[Role::Rig])?,
        stops: kids("stops", kind == "gradient", &[Role::Stop])?,
        frames: if matches!(kind, "drawing" | "video") { drawings(&id, &v["frames"], kind == "drawing")? } else { vec![] },
        paint: if v.get("paint").is_some() { drawings(&format!("{id}.paint"), &v["paint"]["frames"], false)? } else { vec![] },
        paint_inside: v["paint"]["inside"].as_bool().unwrap_or(true),
        fill_frames: if v.get("fillFrames").is_some() { drawings(&format!("{id}.fillFrames"), &v["fillFrames"], false)? } else { vec![] },
        id, kind, role, props, anim,
    })
}

/// The item types that may carry paint (rostrum2d/paint_fields.py TYPES).
pub const PAINTED: &[&str] = &["shape", "text", "image", "video", "path"];

/// The item types a picture or painted fill fills (stage_raster.rs).
pub const RASTER_FILLED: &[&str] = &["shape", "path"];

/// One picture of a drawing, an element's paint or a painted fill: (the frame it appears at, its file, and for a
/// drawing the canvas rectangle [x, y, w, h] the picture covers: its ink only; None = the whole canvas).
pub type Pic = (i64, String, Option<[f64; 4]>);

/// A drawing's `frames: [{"at": n, "src": "…png", "crop": [x, y, w, h]?}, …]`, sorted by `at`; every picture must
/// exist. `crop` (canvas px, a drawing's only: `cropped`) is where the picture lies in the canvas.
fn drawings(id: &str, v: &Value, cropped: bool) -> Result<Vec<Pic>, String> {
    let list = v.as_array().ok_or_else(|| format!("{id}: a drawing needs frames: [{{at, src}}, …]"))?;
    let mut out = vec![];
    for f in list {
        let at = f["at"].as_i64().ok_or_else(|| format!("{id}.frames: a drawing without a whole frame number at"))?;
        let src = f["src"].as_str().ok_or_else(|| format!("{id}.frames: the drawing at frame {at} has no src"))?;
        if !std::path::Path::new(src).is_file() {
            return Err(format!("{id}.frames: the picture of the drawing at frame {at} is missing: {src}"));
        }
        out.push((at, src.to_string(), crop(id, at, &f["crop"], cropped)?));
    }
    out.sort_by_key(|f| f.0);
    Ok(out)
}

fn crop(id: &str, at: i64, v: &Value, allowed: bool) -> Result<Option<[f64; 4]>, String> {
    if v.is_null() {
        return Ok(None);
    }
    let bad = || format!("{id}.frames: the drawing at frame {at} has crop {v}: a drawing's crop is [x, y, w, h] in canvas px, w and h above 0");
    if !allowed {
        return Err(format!("{id}.frames: only a drawing's pictures have a crop (frame {at})"));
    }
    let n: Vec<f64> = v.as_array().ok_or_else(bad)?.iter().filter_map(Value::as_f64).filter(|x| x.is_finite()).collect();
    match n[..] {
        [x, y, w, h] if w > 0.0 && h > 0.0 => Ok(Some([x, y, w, h])),
        _ => Err(bad()),
    }
}

fn check_value(id: &str, f: &fields::Field, v: &Value) -> Result<(), String> {
    let ok = match f.1 {
        Kind::Number => v.is_number(),
        Kind::Toggle => v.is_boolean(),
        Kind::Text => v.is_string(),
        Kind::Color => v.as_str().is_some_and(|s| eval::parse_hex(s).is_some()),
        Kind::Choice(options) => v.as_str().is_some_and(|s| options.contains(&s)),
    };
    if ok {
        return Ok(());
    }
    let want = match f.1 {
        Kind::Number => "a number".to_string(),
        Kind::Toggle => "true or false".to_string(),
        Kind::Text => "text".to_string(),
        Kind::Color => "a colour #rrggbb or #rrggbbaa".to_string(),
        Kind::Choice(o) => format!("one of {}", o.join(", ")),
    };
    Err(format!("{id}.{}: {v} is not {want}", f.0))
}

/// A field's keys, checked and sorted by time (stable, as Python's `sorted`).
fn track(id: &str, kind: &str, f: &fields::Field, keys: &Value) -> Result<Vec<Key>, String> {
    let name = f.0;
    if !fields::animatable(kind, f) {
        return Err(format!("{id}.{name}: this field can't be animated"));
    }
    let list = keys.as_array().filter(|l| !l.is_empty()).ok_or_else(|| format!("{id}.{name}: anim must be a non-empty list of keys"))?;
    let mut out = vec![];
    for k in list {
        let obj = k.as_object().ok_or_else(|| format!("{id}.{name}: a key must be an object"))?;
        if let Some(bad) = obj.keys().find(|k| !matches!(k.as_str(), "t" | "v" | "c" | "d" | "ease" | "x1" | "y1" | "x2" | "y2" | "stiffness" | "damping" | "out" | "in")) {
            return Err(format!("{id}.{name}: a key has no field \"{bad}\""));
        }
        let t = k["t"].as_f64().ok_or_else(|| format!("{id}.{name}: a key without a time t"))?;
        let value = match f.1 {
            Kind::Color => {
                let c = k["c"].as_str().ok_or_else(|| format!("{id}.{name}: a colour key needs c (#rrggbb or #rrggbbaa) at t={t}"))?;
                KeyValue::Color(c.to_string(), eval::parse_hex(c).ok_or_else(|| format!("{id}.{name}: {c} is not a colour #rrggbb or #rrggbbaa"))?)
            }
            Kind::Text if name == "widthProfile" => {
                let text = k["d"].as_str().ok_or_else(|| format!("{id}.{name}: a widthProfile key needs d (the profile text, \"pos,mult …\") at t={t}"))?;
                KeyValue::Profile(text.to_string(), width_profile::read(id, text).map_err(|e| format!("{e} (the key at t={t})"))?)
            }
            Kind::Text => KeyValue::Path(k["d"].as_str().ok_or_else(|| format!("{id}.{name}: a shape key needs d (path data) at t={t}"))?.to_string()),
            _ => KeyValue::Number(k["v"].as_f64().ok_or_else(|| format!("{id}.{name}: a number key needs v at t={t}"))?),
        };
        let ease_name = match &k["ease"] {
            Value::Null => "smooth",
            e => e.as_str().ok_or_else(|| format!("{id}.{name}: ease must be a name"))?,
        };
        let ease = Ease::parse(ease_name, |p| k[p].as_f64()).map_err(|e| format!("{id}.{name}: {e}"))?;
        let handle = |side: &str| -> Result<Option<f64>, String> {
            match &k[side] {
                Value::Null => Ok(None),
                _ if !matches!(value, KeyValue::Number(_)) => Err(format!("{id}.{name}: the key at t={t} has a spatial handle \"{side}\"; only a number key may (not a colour, shape or width profile)")),
                h => h.as_f64().map(Some).ok_or_else(|| format!("{id}.{name}: the key at t={t} has \"{side}\" {h}, not a number")),
            }
        };
        let (out_h, in_h) = (handle("out")?, handle("in")?);
        out.push(Key { t, value, ease, out: out_h, inn: in_h });
    }
    out.sort_by(|a, b| a.t.total_cmp(&b.t));
    for w in out.windows(2) {
        if let (KeyValue::Path(a), KeyValue::Path(b)) = (&w[0].value, &w[1].value) {
            morph::blend(id, a, b, 0.5).map_err(|e| format!("{e} (morphing from the key at t={} to the key at t={})", w[0].t, w[1].t))?;
        }
    }
    if let [k] = &out[..] {
        if let KeyValue::Path(d) = &k.value {
            path_data::read(id, d).map_err(|e| format!("{e} (the key at t={})", k.t))?;
        }
    }
    Ok(out)
}
