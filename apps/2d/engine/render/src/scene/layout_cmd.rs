//! serve's `layout` (ENGINE_CONTRACT.md § 1): boxes laid out as CSS flex / grid by the renderer's own layout
//! (Blitz: Stylo + Taffy + Parley), texts wrapped by the code that draws them. Each tree becomes nested divs on the
//! measuring page (measure_page.rs, as `measure`), its style written as inline CSS from a strict whitelist; a text is
//! the box and markup a text layer's letters get on the stage (stage.rs `text_content`) but in normal flow, so it wraps
//! at the room its container gives it. All trees are one page, one layout pass. Each node's border box is read from the
//! unrounded layout (a text placed at its slot width wraps there again when drawn) relative to its parent's.

use std::fmt::Write;

use blitz_dom::{BaseDocument, NodeId};
use serde_json::{json, Map, Value};

use super::{eval, fields, fonts, measure, stage, stage_type, type_font, Node};

type R<T> = Result<T, String>;

/// The page: wide and tall enough that no root is pressed by its edges.
const ROOM: u32 = 16384;

/// The type fields a text must give (as `measure`; its width is the layout's).
const NEEDED: &[&str] = &["body", "font", "size", "weight", "stretch", "tracking", "lineHeight", "align"];

#[derive(Clone, Copy, PartialEq)]
enum Display {
    Flex,
    Grid,
    Stack,
    None,
}

/// What a node's style is read against: its own kind and its parent's display (None for a root).
struct Ctx<'a> {
    id: &'a str,
    kind: &'a str,
    parent: Option<Display>,
}

/// One node, read: its page id, the caller's id, its CSS, and what it holds.
struct Laid {
    id: String,
    page: String,
    css: String,
    inner: Inner,
}

enum Inner {
    Box(Vec<Laid>),
    /// Index into the texts' scratch layers.
    Text(usize),
    Leaf,
}

struct Reading {
    tree: usize,
    n: usize,
    /// (page id, the caller's id, the text's layer) for every text, in order.
    texts: Vec<(String, String, Value)>,
}

fn page_id(tree: usize, n: usize) -> String {
    format!("rostrum-layout-{tree}-{n}")
}

fn bad(c: &Ctx, key: &str, v: &Value, want: &str) -> String {
    format!("{}: style.{key} must be {want}, not {v}", c.id)
}

fn px(n: f64) -> String {
    format!("{n}px")
}

fn number(c: &Ctx, key: &str, v: &Value, min: f64) -> R<f64> {
    match v.as_f64() {
        Some(n) if n.is_finite() && n >= min => Ok(n),
        _ => Err(bad(c, key, v, &if min == 0.0 { "a number ≥ 0".to_string() } else { "a number".to_string() })),
    }
}

fn whole(c: &Ctx, key: &str, v: &Value) -> R<u64> {
    v.as_u64().filter(|n| *n >= 1).ok_or_else(|| bad(c, key, v, "a whole number ≥ 1"))
}

/// A size: px number | "N%" | "fit" (fit-content, width / height only) | "auto".
fn size(c: &Ctx, key: &str, v: &Value, fit: bool) -> R<String> {
    let want = if fit { "px (a number), \"N%\", \"fit\" or \"auto\"" } else { "px (a number), \"N%\" or \"auto\"" };
    match v {
        Value::Number(_) => Ok(px(number(c, key, v, 0.0).map_err(|_| bad(c, key, v, want))?)),
        Value::String(s) if s == "auto" => Ok("auto".into()),
        Value::String(s) if s == "fit" && fit => Ok("fit-content".into()),
        Value::String(s) if s.ends_with('%') => {
            let n: f64 = s[..s.len() - 1].trim().parse().map_err(|_| bad(c, key, v, want))?;
            if !n.is_finite() || n < 0.0 {
                return Err(bad(c, key, v, want));
            }
            if c.parent.is_none() {
                return Err(format!("{}: style.{key} is a percentage, but a root has no parent to take it of", c.id));
            }
            Ok(format!("{n}%"))
        }
        _ => Err(bad(c, key, v, want)),
    }
}

/// Padding / margin: one px number, or [top, right, bottom, left]; a margin's entries may be "auto".
fn edges(c: &Ctx, key: &str, v: &Value, margin: bool) -> R<String> {
    let want = if margin { "px (a number) or [top, right, bottom, left] of numbers or \"auto\"" } else { "px ≥ 0 (a number) or [top, right, bottom, left]" };
    let one = |e: &Value| -> R<String> {
        match e {
            Value::String(s) if margin && s == "auto" => Ok("auto".into()),
            Value::Number(_) => number(c, key, e, if margin { f64::NEG_INFINITY } else { 0.0 }).map(px).map_err(|_| bad(c, key, v, want)),
            _ => Err(bad(c, key, v, want)),
        }
    };
    match v {
        Value::Array(a) if a.len() == 4 => Ok(a.iter().map(one).collect::<R<Vec<_>>>()?.join(" ")),
        Value::Array(_) => Err(bad(c, key, v, want)),
        e => one(e),
    }
}

fn choice<'a>(c: &Ctx, key: &str, v: &Value, map: &[(&str, &'a str)]) -> R<&'a str> {
    let s = v.as_str().unwrap_or("");
    map.iter().find(|(k, _)| *k == s).map(|(_, css)| *css).ok_or_else(|| {
        bad(c, key, v, &format!("one of {}", map.iter().map(|(k, _)| format!("\"{k}\"")).collect::<Vec<_>>().join(", ")))
    })
}

/// A grid track list: px, %, fr, auto, min-content, max-content, minmax(a, b), fit-content(px | %), repeat(n, …).
/// Checked here: a template Stylo can't read would be dropped without a word.
fn tracks(s: &str) -> bool {
    fn split(s: &str, sep: char) -> Option<Vec<&str>> {
        let (mut depth, mut start, mut out) = (0i32, 0, vec![]);
        for (i, ch) in s.char_indices() {
            match ch {
                '(' => depth += 1,
                ')' => depth -= 1,
                _ if ch == sep && depth == 0 => {
                    out.push(&s[start..i]);
                    start = i + 1;
                }
                _ => {}
            }
            if depth < 0 {
                return None;
            }
        }
        (depth == 0).then(|| {
            out.push(&s[start..]);
            out.into_iter().map(str::trim).filter(|t| !t.is_empty() || sep == ',').collect()
        })
    }
    fn unit(t: &str, units: &[&str]) -> bool {
        units.iter().any(|u| t.strip_suffix(u).and_then(|n| n.parse::<f64>().ok()).is_some_and(|n| n.is_finite() && n >= 0.0))
    }
    fn breadth(t: &str) -> bool {
        matches!(t, "auto" | "min-content" | "max-content") || unit(t, &["px", "%", "fr"])
    }
    fn args<'s>(t: &'s str, f: &str) -> Option<Vec<&'s str>> {
        t.strip_prefix(f)?.strip_prefix('(')?.strip_suffix(')').and_then(|a| split(a, ','))
    }
    fn track(t: &str) -> bool {
        if let Some(a) = args(t, "minmax") {
            return a.len() == 2 && breadth(a[0]) && !unit(a[0], &["fr"]) && breadth(a[1]);
        }
        if let Some(a) = args(t, "fit-content") {
            return a.len() == 1 && unit(a[0], &["px", "%"]);
        }
        if let Some(a) = args(t, "repeat") {
            return a.len() == 2 && a[0].parse::<u32>().is_ok_and(|n| n >= 1) && list(a[1]);
        }
        breadth(t)
    }
    fn list(s: &str) -> bool {
        split(s, ' ').is_some_and(|ts| !ts.is_empty() && ts.iter().all(|t| track(t)))
    }
    list(s)
}

/// Keys only a box (a container) takes.
const BOX_ONLY: &[&str] = &["direction", "gap", "rowGap", "columnGap", "padding", "justify", "align", "columns", "rows"];
/// Every key a style may have.
const KEYS: &[&str] = &[
    "display", "direction", "wrap", "gap", "rowGap", "columnGap", "padding", "margin", "justify", "align", "alignSelf", "justifySelf",
    "width", "height", "minWidth", "maxWidth", "minHeight", "maxHeight", "grow", "shrink", "basis", "aspect", "columns", "rows",
    "colSpan", "rowSpan", "position", "left", "top", "right", "bottom", "overflow",
];

/// The CSS of one node's style; also its own display (a box's), and a text's `wrap`.
fn style(c: &Ctx, s: &Map<String, Value>) -> R<(String, Display, bool)> {
    for k in s.keys() {
        if !KEYS.contains(&k.as_str()) {
            return Err(format!("{}: unknown style key \"{k}\"; a style has: {}", c.id, KEYS.join(", ")));
        }
        if c.kind != "box" && BOX_ONLY.contains(&k.as_str()) {
            return Err(format!("{}: style.{k} is a container's; a {} doesn't take it", c.id, c.kind));
        }
    }
    let mut css = String::from("box-sizing:border-box;");
    let display = match s.get("display") {
        None if c.kind == "box" => Display::Flex,
        None => Display::Flex, // not a container: only "none" changes anything
        Some(v) if c.kind == "box" => match choice(c, "display", v, &[("flex", "flex"), ("grid", "grid"), ("stack", "stack"), ("none", "none")])? {
            "flex" => Display::Flex,
            "grid" => Display::Grid,
            "stack" => Display::Stack,
            _ => Display::None,
        },
        Some(v) => {
            choice(c, "display", v, &[("none", "none")])?;
            Display::None
        }
    };
    if c.kind == "box" {
        css += match display {
            Display::Flex => "display:flex;",
            Display::Grid | Display::Stack => "display:grid;",
            Display::None => "display:none;",
        };
    } else if display == Display::None {
        css += "display:none;";
    }
    let flex = c.kind == "box" && display == Display::Flex;
    let grid = c.kind == "box" && display == Display::Grid;
    let for_flex = |k: &str| -> R<()> { if flex { Ok(()) } else { Err(format!("{}: style.{k} is for a flex box (a row or column); this box isn't one", c.id)) } };
    let for_grid = |k: &str| -> R<()> { if grid { Ok(()) } else { Err(format!("{}: style.{k} is for a grid box; this box isn't one", c.id)) } };
    let mut wrap = true;
    for (k, v) in s {
        let k = k.as_str();
        match k {
            "display" => {}
            "direction" => {
                for_flex(k)?;
                let d = choice(c, k, v, &[("row", "row"), ("column", "column"), ("row-reverse", "row-reverse"), ("column-reverse", "column-reverse")])?;
                let _ = write!(css, "flex-direction:{d};");
            }
            "wrap" => {
                let on = v.as_bool().ok_or_else(|| bad(c, k, v, "true or false"))?;
                match c.kind {
                    "box" => {
                        for_flex(k)?;
                        css += if on { "flex-wrap:wrap;" } else { "flex-wrap:nowrap;" };
                    }
                    "text" => wrap = on,
                    _ => return Err(format!("{}: style.wrap is a flex box's or a text's; a leaf doesn't take it", c.id)),
                }
            }
            "gap" => { let _ = write!(css, "gap:{};", px(number(c, k, v, 0.0)?)); }
            "rowGap" => { let _ = write!(css, "row-gap:{};", px(number(c, k, v, 0.0)?)); }
            "columnGap" => { let _ = write!(css, "column-gap:{};", px(number(c, k, v, 0.0)?)); }
            "padding" => { let _ = write!(css, "padding:{};", edges(c, k, v, false)?); }
            "margin" => { let _ = write!(css, "margin:{};", edges(c, k, v, true)?); }
            "justify" => {
                if display == Display::Stack {
                    // A stack's children share one cell: justify places each in it.
                    let j = choice(c, k, v, &[("start", "start"), ("center", "center"), ("end", "end"), ("stretch", "stretch")])?;
                    let _ = write!(css, "justify-items:{j};");
                } else {
                    let (s, e) = if flex { ("flex-start", "flex-end") } else { ("start", "end") };
                    let j = choice(c, k, v, &[("start", s), ("center", "center"), ("end", e), ("between", "space-between"), ("around", "space-around"), ("evenly", "space-evenly")])?;
                    let _ = write!(css, "justify-content:{j};");
                }
            }
            "align" => {
                let (s, e) = if flex { ("flex-start", "flex-end") } else { ("start", "end") };
                let a = choice(c, k, v, &[("start", s), ("center", "center"), ("end", e), ("stretch", "stretch"), ("baseline", "baseline")])?;
                let _ = write!(css, "align-items:{a};");
            }
            "alignSelf" | "justifySelf" => {
                let parent = c.parent.ok_or_else(|| format!("{}: style.{k} places a child in its container; a root has none", c.id))?;
                if k == "justifySelf" && !matches!(parent, Display::Grid | Display::Stack) {
                    return Err(format!("{}: style.justifySelf places a child in a grid or stack cell; its container is neither", c.id));
                }
                let (s, e) = if parent == Display::Flex { ("flex-start", "flex-end") } else { ("start", "end") };
                let a = choice(c, k, v, &[("auto", "auto"), ("start", s), ("center", "center"), ("end", e), ("stretch", "stretch"), ("baseline", "baseline")])?;
                let _ = write!(css, "{}:{a};", if k == "alignSelf" { "align-self" } else { "justify-self" });
            }
            "width" | "height" => { let _ = write!(css, "{k}:{};", size(c, k, v, true)?); }
            "minWidth" | "maxWidth" | "minHeight" | "maxHeight" => {
                let prop = match k { "minWidth" => "min-width", "maxWidth" => "max-width", "minHeight" => "min-height", _ => "max-height" };
                let val = size(c, k, v, false)?;
                // CSS has no max-width: auto; its "no limit" is none.
                let val = if val == "auto" && prop.starts_with("max") { "none".into() } else { val };
                let _ = write!(css, "{prop}:{val};");
            }
            "grow" => { let _ = write!(css, "flex-grow:{};", number(c, k, v, 0.0)?); }
            "shrink" => { let _ = write!(css, "flex-shrink:{};", number(c, k, v, 0.0)?); }
            "basis" => { let _ = write!(css, "flex-basis:{};", size(c, k, v, false)?); }
            "aspect" => match v.as_f64() {
                Some(n) if n.is_finite() && n > 0.0 => { let _ = write!(css, "aspect-ratio:{n};"); }
                _ => return Err(bad(c, k, v, "a number > 0 (width / height)")),
            },
            "columns" => {
                for_grid(k)?;
                let t = match v {
                    Value::String(t) if tracks(t) => t.clone(),
                    Value::String(_) => return Err(bad(c, k, v, "a whole number or a track list (\"1fr 2fr 200px\", \"repeat(3, 1fr)\", minmax(…), auto, fit-content(…))")),
                    _ => format!("repeat({}, minmax(0px, 1fr))", whole(c, k, v)?),
                };
                let _ = write!(css, "grid-template-columns:{t};");
            }
            "rows" => {
                for_grid(k)?;
                match v.as_str() {
                    Some(t) if tracks(t) => { let _ = write!(css, "grid-template-rows:{t};"); }
                    _ => return Err(bad(c, k, v, "a track list (\"auto 1fr\", \"repeat(2, 120px)\")")),
                }
            }
            "colSpan" | "rowSpan" => {
                if c.parent != Some(Display::Grid) {
                    return Err(format!("{}: style.{k} spans cells of a grid; its container isn't a grid", c.id));
                }
                let _ = write!(css, "{}:span {};", if k == "colSpan" { "grid-column" } else { "grid-row" }, whole(c, k, v)?);
            }
            "position" => {
                if c.parent.is_none() {
                    return Err(format!("{}: style.position sets a child apart in its container; a root has none (it is at 0, 0)", c.id));
                }
                choice(c, k, v, &[("absolute", "absolute")])?;
                css += "position:absolute;";
            }
            "left" | "top" | "right" | "bottom" => {
                if s.get("position").and_then(Value::as_str) != Some("absolute") {
                    return Err(format!("{}: style.{k} places a child set apart; give it position: \"absolute\"", c.id));
                }
                let _ = write!(css, "{k}:{};", px(number(c, k, v, f64::NEG_INFINITY)?));
            }
            "overflow" => {
                let o = choice(c, k, v, &[("visible", "visible"), ("hidden", "hidden")])?;
                let _ = write!(css, "overflow:{o};");
            }
            _ => unreachable!("checked against KEYS"),
        }
    }
    // A stack's children all take its one cell (a child set apart keeps the box as its frame).
    if c.parent == Some(Display::Stack) && s.get("position").is_none() {
        css += "grid-area:1 / 1;";
    }
    Ok((css, display, wrap))
}

/// One node read into `Laid` (its text layers gathered into `r.texts`), with no markup yet.
fn read(v: &Value, parent: Option<Display>, r: &mut Reading, seen: &mut Vec<String>) -> R<Laid> {
    let obj = v.as_object().ok_or("layout: every node must be an object {id, kind, style, …}")?;
    let id = obj.get("id").and_then(Value::as_str).ok_or("layout: every node needs an id (text)")?.to_string();
    if seen.contains(&id) {
        return Err(format!("{id}: two nodes in one tree have this id"));
    }
    seen.push(id.clone());
    let kind = obj.get("kind").and_then(Value::as_str).unwrap_or("");
    let own: &[&str] = match kind {
        "box" => &["children"],
        "text" => &["text"],
        "leaf" => &["w", "h"],
        _ => return Err(format!("{id}: kind must be \"box\", \"text\" or \"leaf\", not {}", obj.get("kind").unwrap_or(&Value::Null))),
    };
    if let Some(k) = obj.keys().find(|k| !matches!(k.as_str(), "id" | "kind" | "style") && !own.contains(&k.as_str())) {
        return Err(format!("{id}: a {kind} node has no \"{k}\"; it has id, kind, style, {}", own.join(", ")));
    }
    let empty = Map::new();
    let s = match obj.get("style") {
        None => &empty,
        Some(Value::Object(m)) => m,
        Some(other) => return Err(format!("{id}: style must be an object, not {other}")),
    };
    let c = Ctx { id: &id, kind, parent };
    let (mut css, display, wrap) = style(&c, s)?;
    let page = page_id(r.tree, r.n);
    r.n += 1;
    let inner = match kind {
        "box" => {
            let kids = match obj.get("children") {
                None => vec![],
                Some(Value::Array(a)) => a.clone(),
                Some(other) => return Err(format!("{id}: children must be a list of nodes, not {other}")),
            };
            Inner::Box(kids.iter().map(|k| read(k, Some(display), r, seen)).collect::<R<_>>()?)
        }
        "text" => {
            let own = obj.get("text").and_then(Value::as_object).ok_or_else(|| format!("{id}: a text node needs text: {{body, font, size, …}}"))?;
            if let Some(missing) = NEEDED.iter().find(|f| !own.contains_key(**f)) {
                return Err(format!("{id}: layout needs text.{missing} (every text gives {})", NEEDED.join(", ")));
            }
            if own.contains_key("boxWidth") {
                return Err(format!("{id}: a text's width is the layout's; leave text.boxWidth out (style.width fixes it)"));
            }
            let mut props = measure::neutral("text");
            props.extend(measure::plain());
            props.extend(own.iter().map(|(k, v)| (k.clone(), v.clone())));
            // White space as the stage writes a wrapped text, and wrapping at whatever room it is given.
            css.insert_str(0, if wrap { "white-space:pre-wrap;" } else { "white-space:pre;" });
            r.texts.push((page.clone(), id.clone(), json!({ "id": &page, "type": "text", "props": props })));
            Inner::Text(r.texts.len() - 1)
        }
        _ => {
            for (axis, key) in [("w", "width"), ("h", "height")] {
                if !s.contains_key(key) {
                    let n = obj.get(axis).and_then(Value::as_f64).filter(|n| n.is_finite() && *n >= 0.0);
                    let n = n.ok_or_else(|| format!("{id}: a leaf needs {axis} (px ≥ 0) unless style.{key} gives it"))?;
                    let _ = write!(css, "{key}:{};", px(n));
                }
            }
            Inner::Leaf
        }
    };
    if parent.is_none() {
        css += "position:absolute;left:0px;top:0px;";
    }
    Ok(Laid { id, page, css, inner })
}

fn markup(n: &Laid, texts: &[(String, String)], out: &mut String) {
    match &n.inner {
        Inner::Box(kids) => {
            let _ = write!(out, "<div id=\"{}\" style=\"{}\">", n.page, n.css);
            for k in kids {
                markup(k, texts, out);
            }
            out.push_str("</div>");
        }
        // The text layer's own style first, then the layout's (its width, white space) over it.
        Inner::Text(i) => { let _ = write!(out, "<div id=\"{}\" style=\"{}{}\">{}</div>", n.page, texts[*i].0, n.css, texts[*i].1); }
        Inner::Leaf => { let _ = write!(out, "<div id=\"{}\" style=\"{}\"></div>", n.page, n.css); }
    }
}

/// A node's border-box top-left in page px, from the unrounded layout up its containing blocks.
fn origin(doc: &BaseDocument, id: NodeId) -> (f64, f64) {
    let mut node = doc.get_node(id).unwrap();
    let (mut x, mut y) = (0.0, 0.0);
    loop {
        let l = node.unrounded_layout();
        x += l.location.x as f64;
        y += l.location.y as f64;
        match node.containing_block() {
            Some(p) => node = node.with(p),
            None => return (x, y),
        }
    }
}

fn r3(v: f64) -> f64 {
    (v * 1000.0).round() / 1000.0
}

/// Each node's box under `parent` (its page px origin) into `out`.
fn boxes(doc: &BaseDocument, n: &Laid, parent: Option<(f64, f64)>, out: &mut Map<String, Value>) -> R<()> {
    let id = doc.get_element_by_id(&n.page).or_else(|| doc.query_selector(&format!("#{}", n.page)).ok().flatten()).ok_or_else(|| format!("{}: its node is missing from the laid-out page", n.id))?;
    let (x, y) = origin(doc, id);
    let s = doc.get_node(id).unwrap().unrounded_layout().size;
    let (px, py) = parent.unwrap_or((x, y));
    out.insert(n.id.clone(), json!([r3(x - px), r3(y - py), r3(s.width as f64), r3(s.height as f64)]));
    if let Inner::Box(kids) = &n.inner {
        for k in kids {
            boxes(doc, k, Some((x, y)), out)?;
        }
    }
    Ok(())
}

/// `{"trees": [NODE, …]}` → `{"ok": true, "boxes": [{id: [x, y, w, h]}, …]}` (one map per tree; ENGINE_CONTRACT.md § 1).
/// `held`: the loaded scene's fonts (its own `fonts`, then the app's), else the app's.
pub fn layout(req: &Value, held: Option<&[fonts::Font]>) -> R<Value> {
    let trees = req["trees"].as_array().ok_or("layout needs trees: [{id, kind, style, children | text | w, h}, …]")?;
    let mut r = Reading { tree: 0, n: 0, texts: vec![] };
    let mut roots = vec![];
    for (i, t) in trees.iter().enumerate() {
        r.tree = i;
        r.n = 0;
        roots.push(read(t, None, &mut r, &mut vec![])?);
    }
    // A text's page id in an error is the caller's id (latest first: "…-0-1" is in "…-0-10").
    let texts_of = &r.texts;
    let named = |e: String| texts_of.iter().rev().fold(e, |e, (page, id, _)| e.replace(page.as_str(), id));
    let listed;
    let all: &[fonts::Font] = match held {
        Some(f) => f,
        None if r.texts.is_empty() => &[],
        None => {
            listed = std::sync::Arc::new(fonts::list(&Value::Null)?);
            type_font::register(&listed);
            listed.as_slice()
        }
    };
    // Every text checked as a load checks it (mod.rs `node`) and written as the stage writes a text layer.
    let mut layers = vec![];
    let mut used: Vec<String> = vec![];
    for (_, _, l) in texts_of {
        let node = super::node(l, "layout").map_err(named)?;
        let font = fonts::pick(all, node.props["font"].as_str().unwrap_or(""), 400.0, node.props["italic"].as_bool() == Some(true)).map_err(|e| named(format!("{}: {e}", node.id)))?;
        if !used.contains(&font.family) {
            used.push(font.family.clone());
        }
        layers.push(node);
    }
    let mut comp_props = measure::neutral("comp");
    comp_props.insert("width".into(), json!(ROOM));
    comp_props.insert("height".into(), json!(ROOM));
    comp_props.insert("fps".into(), json!(30.0));
    let comp = Node { id: "layout".into(), kind: "comp", role: fields::Role::Comp, props: comp_props, anim: vec![], effects: vec![], masks: vec![], layers, frames: vec![], paint: vec![], paint_inside: true, fill_frames: vec![], rig: vec![], stops: vec![] };
    let evaluated = eval::whole(&comp, 0.0);
    let mut texts = vec![];
    for it in &evaluated.layers {
        if stage_type::by_letter(it) {
            return Err(named(format!("{}: a text drawn letter by letter (on a path, keys played letter by letter, or figures set tabular by hand) has no wrap to lay out; send it as a leaf of its measured size", it.id)));
        }
        texts.push(stage::text_content(it).map_err(named)?);
    }
    let mut page = String::new();
    for n in &roots {
        markup(n, &texts, &mut page);
    }
    let out = super::measure_page::lay_out(&fonts::faces_of(all, &used), ROOM, &page, |doc| {
        roots.iter().map(|n| {
            let mut m = Map::new();
            boxes(doc, n, None, &mut m)?;
            Ok(Value::Object(m))
        }).collect::<R<Vec<_>>>()
    })?;
    Ok(json!({ "ok": true, "boxes": out }))
}

#[cfg(test)]
mod tests {
    use serde_json::{json, Value};

    fn lay(tree: Value) -> serde_json::Map<String, Value> {
        let out = super::layout(&json!({ "trees": [tree] }), None).unwrap();
        out["boxes"][0].as_object().unwrap().clone()
    }

    fn b(m: &serde_json::Map<String, Value>, id: &str) -> [f64; 4] {
        let a = m[id].as_array().unwrap();
        [0, 1, 2, 3].map(|i| a[i].as_f64().unwrap())
    }

    fn leaf(id: &str, w: u32, h: u32) -> Value {
        json!({ "id": id, "kind": "leaf", "w": w, "h": h, "style": { "shrink": 0 } })
    }

    fn text(id: &str, body: &str, style: Value) -> Value {
        json!({ "id": id, "kind": "text", "style": style, "text": { "body": body, "font": "Roboto Flex", "size": 24, "weight": 400,
                "stretch": 100, "tracking": 0, "lineHeight": 1.2, "align": "left" } })
    }

    #[test]
    fn a_row_with_gap_and_padding() {
        let m = lay(json!({ "id": "row", "kind": "box", "style": { "padding": [10, 20, 10, 20], "gap": 8, "align": "start" },
                            "children": [leaf("a", 40, 30), leaf("b", 50, 20)] }));
        assert_eq!(b(&m, "row"), [0.0, 0.0, 20.0 + 40.0 + 8.0 + 50.0 + 20.0, 50.0]);
        assert_eq!(b(&m, "a"), [20.0, 10.0, 40.0, 30.0]);
        assert_eq!(b(&m, "b"), [68.0, 10.0, 50.0, 20.0]);
    }

    #[test]
    fn a_text_wraps_in_a_fixed_width_column() {
        let long = "The quick brown fox jumps over the lazy dog, again and again, until it wraps.";
        let m = lay(json!({ "id": "col", "kind": "box", "style": { "direction": "column", "width": 200, "padding": 10, "gap": 4 },
                            "children": [text("t", long, json!({})), leaf("under", 20, 20)] }));
        let t = b(&m, "t");
        assert_eq!([t[0], t[1], t[2]], [10.0, 10.0, 180.0], "a column stretches its text to its room");
        assert!(t[3] > 24.0 * 1.2 * 2.5, "the text wrapped onto several lines: {t:?}");
        assert!((b(&m, "under")[1] - (10.0 + t[3] + 4.0)).abs() < 0.01, "what follows sits under the wrapped text");
        // The same text and width through `measure` (the code that draws it) gives the same box.
        let measured = super::super::measure::measure(&json!({ "items": [{ "id": "t", "body": long, "font": "Roboto Flex", "size": 24, "weight": 400,
            "stretch": 100, "tracking": 0, "lineHeight": 1.2, "align": "left", "boxWidth": 180 }] }), None).unwrap();
        assert_eq!(measured["sizes"]["t"][1].as_f64().unwrap().round(), t[3].round());
        let one = lay(json!({ "id": "col", "kind": "box", "style": { "direction": "column", "width": 200 },
                              "children": [text("t", long, json!({ "wrap": false }))] }));
        assert!(b(&one, "t")[3] < 24.0 * 1.2 * 1.5, "wrap: false keeps one line");
    }

    #[test]
    fn a_grid_of_three_columns() {
        // width "auto": a leaf fills its cell (its own w would fix it).
        let kids: Vec<Value> = (0..5).map(|i| json!({ "id": format!("c{i}"), "kind": "leaf", "h": 40, "style": { "width": "auto" } })).collect();
        let m = lay(json!({ "id": "g", "kind": "box", "style": { "display": "grid", "columns": 3, "gap": 10, "width": 320 }, "children": kids }));
        assert_eq!(b(&m, "c0"), [0.0, 0.0, 100.0, 40.0]);
        assert_eq!(b(&m, "c2")[0], 220.0);
        assert_eq!(b(&m, "c3")[..2], [0.0, 50.0]);
        assert_eq!(b(&m, "g")[3], 90.0);
    }

    #[test]
    fn a_percentage_width_and_an_absolute_child() {
        let m = lay(json!({ "id": "p", "kind": "box", "style": { "width": 400, "height": 100, "padding": 10 }, "children": [
            { "id": "half", "kind": "leaf", "h": 20, "style": { "width": "50%" } },
            { "id": "pin", "kind": "leaf", "w": 30, "h": 30, "style": { "position": "absolute", "right": 0, "bottom": 5 } },
            leaf("after", 10, 10),
        ] }));
        assert_eq!(b(&m, "half")[2], 190.0, "50 % of the content box (400 − 2 × 10)");
        assert_eq!(b(&m, "pin")[..2], [370.0, 65.0], "set apart, placed from the box's edges");
        assert_eq!(b(&m, "after")[0], 10.0 + 190.0, "a child set apart takes no room");
    }

    #[test]
    fn trees_are_laid_out_apart_and_bad_styles_named() {
        let out = super::layout(&json!({ "trees": [leaf("a", 10, 10), leaf("a", 20, 30)] }), None).unwrap();
        assert_eq!(out["boxes"][1]["a"], json!([0.0, 0.0, 20.0, 30.0]));
        let e = super::layout(&json!({ "trees": [{ "id": "r", "kind": "box", "children": [{ "id": "x", "kind": "leaf", "w": 1, "h": 1, "style": { "colour": 1 } }] }] }), None).unwrap_err();
        assert!(e.contains("x") && e.contains("colour"), "{e}");
        let e = super::layout(&json!({ "trees": [{ "id": "r", "kind": "box", "style": { "justify": "middle" } }] }), None).unwrap_err();
        assert!(e.starts_with("r: style.justify"), "{e}");
        assert!(super::tracks("1fr 2fr 200px") && super::tracks("repeat(3, minmax(0px, 1fr))") && !super::tracks("1fr; color: red"));
    }
}
