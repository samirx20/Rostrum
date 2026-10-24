//! The one font registry (contract § 4 text `font`): every face a text can name, by family name, from three places,
//! the first that has a family giving all of its faces: the project's own fonts (the scene's optional
//! `"fonts": {"Family": "C:\\…\\file.ttf"}`), the fonts shipped with the app, then the fonts installed on the computer
//! (fonts_scan.rs). The engine's page, its text measuring, the font picker and the agents' `inspect_fonts` all read it.
//! A text naming a family found nowhere is refused when the scene loads or is edited: never drawn in another font.
//!
//! The shipped folder: `ROSTRUM2D_FONTS` if set, else `fonts\` beside the program, else `engine/fonts` above
//! `target/<profile>/` (the installed app, which mirrors the repo), else the source tree's `apps/2d/engine/fonts/`.
//! Only open-licence fonts go there (SIL OFL; each with its licence text beside it; ATTRIBUTIONS.md).

use std::collections::HashSet;
use std::path::{Path, PathBuf};

use serde_json::Value;

use super::fonts_scan;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Source {
    Project,
    Shipped,
    Installed,
}

impl Source {
    pub fn word(self) -> &'static str {
        match self {
            Source::Project => "project",
            Source::Shipped => "shipped",
            Source::Installed => "installed",
        }
    }
}

/// One face of a family: its file (and its place in a collection), its weights (one, or a variable font's range),
/// italic or not. `alias`: the face listed again under a second name (a variable font's "Inter Variable").
#[derive(Clone, Debug)]
pub struct Font {
    pub family: String,
    pub path: PathBuf,
    pub index: u32,
    pub weight: (f32, f32),
    pub variable: bool,
    pub italic: bool,
    pub source: Source,
    pub alias: bool,
}

/// The shipped fonts folder (see the module header).
pub fn app_folder() -> Result<PathBuf, String> {
    if let Ok(dir) = std::env::var("ROSTRUM2D_FONTS") {
        return Ok(PathBuf::from(dir));
    }
    let exe = std::env::current_exe().ok();
    let beside = exe.as_ref().and_then(|e| e.parent().map(|d| d.join("fonts")));
    // The installed app mirrors the repo (tools/release/bundle.py): engine/target/<profile>/x.exe -> engine/fonts.
    let layout = exe.as_ref().and_then(|e| Some(e.parent()?.parent()?.parent()?.join("fonts")));
    let source = Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join("fonts");
    beside.into_iter().chain(layout).chain([source]).find(|d| d.is_dir()).ok_or_else(|| "no fonts folder: set ROSTRUM2D_FONTS or put fonts\\ beside the program".to_string())
}

/// Every face there is (`project`: the scene's `fonts` object, or null): the project's, the app's, the computer's.
pub fn list(project: &Value) -> Result<Vec<Font>, String> {
    let mut out: Vec<Font> = vec![];
    let mut add = |faces: Vec<Font>| {
        let before: HashSet<String> = out.iter().map(|f| f.family.clone()).collect();
        out.extend(faces.into_iter().filter(|f| !before.contains(&f.family)));
    };
    match project {
        Value::Null => {}
        Value::Object(map) => {
            for (family, path) in map {
                let path = PathBuf::from(path.as_str().ok_or_else(|| format!("fonts: \"{family}\" must name a file"))?);
                add(fonts_scan::file(&path, family)?); // readable and a font, or refused now
            }
        }
        _ => return Err("fonts: must be an object, family name → font file".into()),
    }
    add(fonts_scan::folder(&app_folder()?, Source::Shipped));
    add(fonts_scan::installed().to_vec());
    Ok(out)
}

/// The face of `family` the page draws for this weight and slope: CSS font matching (a face whose weights hold it,
/// else the nearest the CSS way: up to 500 first between 400 and 500, lighter first below 400, heavier first above
/// 500). A family that isn't there, or an italic it doesn't have, is refused, naming what there is.
pub fn pick<'a>(fonts: &'a [Font], family: &str, weight: f64, italic: bool) -> Result<&'a Font, String> {
    let all: Vec<&Font> = fonts.iter().filter(|f| f.family == family).collect();
    if all.is_empty() {
        return Err(missing(fonts, family));
    }
    let slope: Vec<&Font> = all.iter().copied().filter(|f| f.italic == italic).collect();
    if slope.is_empty() {
        return Err(format!("the font \"{family}\" has no {} faces; turn italic {}", if italic { "italic" } else { "upright" }, if italic { "off" } else { "on" }));
    }
    let w = weight as f32;
    let rank = |f: &&Font| -> (u8, f32) {
        let (lo, hi) = f.weight;
        if lo <= w && w <= hi {
            return (0, 0.0);
        }
        let (above, gap) = if lo > w { (true, lo - w) } else { (false, w - hi) };
        let order = match (w, above) {
            (w, true) if (400.0..=500.0).contains(&w) && lo <= 500.0 => 1,
            (w, false) if (400.0..=500.0).contains(&w) => 2,
            (w, true) if (400.0..=500.0).contains(&w) => 3,
            (w, false) if w < 400.0 => 1,
            (w, true) if w < 400.0 => 2,
            (_, true) => 1,
            (_, false) => 2,
        };
        (order, gap)
    };
    Ok(slope.into_iter().min_by(|a, b| rank(a).partial_cmp(&rank(b)).unwrap()).unwrap())
}

/// "font "Helvetica" is not on this computer…", with the families named most like it.
fn missing(fonts: &[Font], family: &str) -> String {
    let want = family.to_lowercase();
    let word = want.split_whitespace().next().unwrap_or("").to_string();
    let mut like: Vec<&str> = fonts.iter().filter(|f| !f.alias).map(|f| f.family.as_str())
        .filter(|n| { let n = n.to_lowercase(); n == want || (!word.is_empty() && n.contains(&word)) }).collect();
    like.dedup();
    let near = if like.is_empty() { String::new() } else { format!("; close: {}", like.iter().take(8).cloned().collect::<Vec<_>>().join(", ")) };
    format!("font \"{family}\" not found: it is not in the project, the app or on this computer{near}")
}

/// The faces of the families `names` (the page embeds only these: the scene's own text fonts).
pub fn faces_of<'a>(fonts: &'a [Font], names: &[String]) -> Vec<Font> {
    fonts.iter().filter(|f| names.contains(&f.family)).cloned().collect()
}

/// The families the comp's texts name, each once, sorted.
pub fn used(comp: &super::Node) -> Vec<String> {
    let mut out = vec![];
    let _ = comp.walk(&mut |n| {
        if n.kind == "text" {
            out.push(n.props["font"].as_str().unwrap_or("").to_string());
        }
        Ok(())
    });
    out.sort();
    out.dedup();
    out
}
