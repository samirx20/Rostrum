//! Colour effects on a layer (grade_fields.py; ENGINE_CONTRACT.md § 4 colour): adjust, levels, curves and a .cube
//! LUT become one rostrum-color grade, the same one `sksl grade` serves (grade_cmd.rs), compiled to one SkSL colour
//! filter. The painter runs it on the layer's look as an `<feshader effect="grade">` (vendor/blitz-paint
//! svg_filter.rs; the renderer sets its working space). Order: adjust (exposure, temperature / tint, contrast,
//! saturation, hue), then levels and curves (grade_curve.rs), then the LUT at its amount. A bad curve, levels or
//! LUT file is refused when the scene loads and after every edit (`check`), naming the layer, field and .cube line.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, OnceLock};

use rostrum_color::grade::{Grade, Layer, LutNode, Op};
use rostrum_color::{Cube, Interp, Lut};
use serde_json::{json, Map, Value};

use super::eval::Item;
use super::stage::{escape, percent};
use super::Node;

type R<T> = Result<T, String>;

/// A .cube file read once per version (path, length, modification time), its table written as an RHALF image.
struct Table {
    lut: Lut,
    image: PathBuf,
}

type Key = (String, u64, u128);

fn tables() -> &'static Mutex<HashMap<Key, Arc<Table>>> {
    static T: OnceLock<Mutex<HashMap<Key, Arc<Table>>>> = OnceLock::new();
    T.get_or_init(Default::default)
}

/// Where LUT images go: the machine's cache (`~/.rostrum/cache/2d-lut`), one small file per .cube version.
fn cache_dir() -> R<PathBuf> {
    let home = std::env::var_os("USERPROFILE").or_else(|| std::env::var_os("HOME")).ok_or("no home folder (USERPROFILE / HOME) for the LUT cache")?;
    let dir = Path::new(&home).join(".rostrum").join("cache").join("2d-lut");
    std::fs::create_dir_all(&dir).map_err(|e| format!("{}: {e}", dir.display()))?;
    Ok(dir)
}

fn lut_node(lut: Lut) -> R<Op> {
    // A creative .cube takes and gives screen colours (sRGB), as photo and video editors make them.
    Ok(Op::Lut(Box::new(LutNode::new(lut, Interp::Tetrahedral, "srgb_display", "srgb_display")?)))
}

fn table(path: &str) -> R<Arc<Table>> {
    if !Path::new(path).is_absolute() {
        return Err(format!("\"{path}\": a LUT file is given by its absolute path"));
    }
    let meta = std::fs::metadata(path).map_err(|e| format!("{path}: {e}"))?;
    let mtime = meta.modified().ok().and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok()).map_or(0, |d| d.as_nanos());
    let key = (path.to_string(), meta.len(), mtime);
    if let Some(t) = tables().lock().unwrap().get(&key) {
        return Ok(t.clone());
    }
    let text = std::fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?;
    let cube = Cube::parse(&text).map_err(|e| format!("{path}: {e}"))?;
    let img = Grade::new(vec![lut_node(cube.lut.clone())?]).lut_images().remove(0);
    let name = {
        use std::hash::{Hash, Hasher};
        let mut h = std::collections::hash_map::DefaultHasher::new();
        key.hash(&mut h);
        format!("{:016x}.rhalf", h.finish())
    };
    let image = cache_dir()?.join(name);
    if !image.is_file() {
        // Written under a name of its own, then renamed: another process never reads half a table.
        let tmp = image.with_extension(format!("tmp{}", std::process::id()));
        crate::grade_cmd::write_rhalf(&tmp, &img)?;
        std::fs::rename(&tmp, &image).map_err(|e| format!("{}: {e}", image.display()))?;
    }
    let t = Arc::new(Table { lut: cube.lut, image });
    tables().lock().unwrap().insert(key, t.clone());
    Ok(t)
}

/// The grade of a layer's colour fields and its LUT image; None when no effect is on. Errors start with the field.
fn grade(p: &Map<String, Value>) -> R<Option<(Grade, Option<PathBuf>)>> {
    let on = |f: &str| p.get(f).and_then(Value::as_bool).unwrap_or(false);
    let n = |f: &str| p.get(f).and_then(Value::as_f64).unwrap_or(0.0);
    let mut ops = vec![];
    if on("adjust") {
        // Only what moves away from neutral is in the program.
        let steps = [
            (n("exposure") != 0.0, json!({ "op": "exposure", "stops": n("exposure") })),
            (n("temperature") != 0.0 || n("tint") != 0.0, json!({ "op": "warmth", "temperature": n("temperature"), "tint": n("tint") })),
            (n("contrast") != 1.0, json!({ "op": "contrast", "contrast": n("contrast") })),
            (n("saturation") != 1.0, json!({ "op": "saturation", "saturation": n("saturation") })),
            (n("hue") != 0.0, json!({ "op": "hue", "degrees": n("hue") })),
        ];
        ops.extend(steps.into_iter().filter(|s| s.0).map(|s| s.1));
    }
    ops.extend(super::grade_curve::op(p)?);
    let lut = p.get("lut").and_then(Value::as_str).unwrap_or("");
    if ops.is_empty() && lut.is_empty() {
        return Ok(None);
    }
    let mut g = Grade::from_spec(&json!({ "ops": ops })).map_err(|e| format!("colour: {e}"))?;
    let mut image = None;
    if !lut.is_empty() {
        let t = table(lut).map_err(|e| format!("lut: {e}"))?;
        let node = lut_node(t.lut.clone())?;
        let mix = n("lutMix") as f32;
        g.ops.push(if mix >= 1.0 { node } else { Op::Layer(Box::new(Layer { mix, ..Layer::new(vec![node]) })) });
        image = Some(t.image.clone());
    }
    Ok(Some((g, image)))
}

/// Checked when the scene loads and after every edit: every layer's colour effects make a grade the GPU can run.
pub fn check(n: &Node) -> R<()> {
    n.walk(&mut |l| {
        if l.props.get("levels").and_then(Value::as_bool) == Some(true) {
            let (b, w) = (l.props["inBlack"].as_f64().unwrap_or(0.0), l.props["inWhite"].as_f64().unwrap_or(1.0));
            if w <= b {
                return Err(format!("{}.inWhite: White in ({w}) must be above Black in ({b})", l.id));
            }
        }
        match grade(&l.props).map_err(|e| format!("{}.{e}", l.id))? {
            Some((g, _)) => crate::grade_cmd::program(&g).map(|_| ()).map_err(|e| format!("{}: its colour effects: {e}", l.id)),
            None => Ok(()),
        }
    })
}

/// The layer's look under its colour effects (unchanged when none is on): the filter's SVG and a full-size box using it.
pub fn wrap(it: &Item, body: String) -> R<String> {
    let Some((g, image)) = grade(&it.props).map_err(|e| format!("{}.{e}", it.id))? else { return Ok(body) };
    let s = crate::grade_cmd::program(&g).map_err(|e| format!("{}: its colour effects: {e}", it.id))?;
    let uniforms: Vec<String> = s.uniforms.iter().map(|(k, v)| format!("{k} {}", v.iter().map(f32::to_string).collect::<Vec<_>>().join(" "))).collect();
    let images = image.map(|p| format!("lut0 /__local_asset?p={}", percent(&p.to_string_lossy()))).unwrap_or_default();
    let id: String = format!("rg-{}", it.id.chars().map(|c| if c.is_ascii_alphanumeric() || c == '_' { c.to_string() } else { format!("-{:x}-", c as u32) }).collect::<String>());
    Ok(format!(
        "<svg width=\"0\" height=\"0\" style=\"position:absolute;left:0;top:0;\"><defs><filter id=\"{id}\" color-interpolation-filters=\"sRGB\">\
         <feshader effect=\"grade\" in=\"SourceGraphic\" result=\"graded\" radius=\"0\" grow=\"0\" uniforms=\"{}\" images=\"{}\">{}</feshader></filter></defs></svg>\
         <div style=\"position:absolute;left:0;top:0;width:100%;height:100%;filter:url(#{id});\">{body}</div>",
        uniforms.join(";"), escape(&images), escape(&s.code)
    ))
}
