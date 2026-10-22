//! The fonts a scene can name (contract § 4 text `font`), resolved by family name: the project's own fonts (the
//! scene's optional `"fonts": {"Family": "C:\\…\\file.ttf"}`, which win) and the app's fonts folder. A text layer
//! naming a font found in neither is refused when the scene loads or is edited, naming what there is.
//!
//! The app's folder: `ROSTRUM2D_FONTS` if set, else `fonts\` beside the program, else `engine/fonts` above
//! `target/<profile>/` (the installed app, which mirrors the repo), else the
//! source tree's `apps/2d/engine/fonts/` (a build in this checkout). Only permissive fonts go there (SIL OFL;
//! each with its licence text beside it).

use std::path::{Path, PathBuf};

use serde_json::Value;
use skrifa::{raw::TableProvider, string::StringId, FontRef, MetadataProvider};

#[derive(Clone, Debug)]
pub struct Font {
    /// The family name a scene uses.
    pub family: String,
    pub path: PathBuf,
}

/// The app's fonts folder (see the module header).
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

/// The project's fonts (`project`: the scene's `fonts` object, or null), then the app folder's.
pub fn list(project: &Value) -> Result<Vec<Font>, String> {
    let mut fonts = vec![];
    match project {
        Value::Null => {}
        Value::Object(map) => {
            for (family, path) in map {
                let path = PathBuf::from(path.as_str().ok_or_else(|| format!("fonts: \"{family}\" must name a file"))?);
                names(&path)?; // readable and a font, or refused now
                fonts.push(Font { family: family.clone(), path });
            }
        }
        _ => return Err("fonts: must be an object, family name → font file".into()),
    }
    let dir = app_folder()?;
    let mut files: Vec<PathBuf> = std::fs::read_dir(&dir).map_err(|e| format!("fonts folder {}: {e}", dir.display()))?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().is_some_and(|x| x.eq_ignore_ascii_case("ttf") || x.eq_ignore_ascii_case("otf")))
        .collect();
    files.sort();
    for path in files {
        for family in names(&path)? {
            fonts.push(Font { family, path: path.clone() });
        }
    }
    Ok(fonts)
}

/// The family names a font file answers to: its typographic family (else its family), and the same without a
/// trailing " Variable" (variable fonts often carry it to tell themselves from their static cuts: "Inter Variable").
fn names(path: &Path) -> Result<Vec<String>, String> {
    let bytes = std::fs::read(path).map_err(|e| format!("font {}: {e}", path.display()))?;
    let font = FontRef::new(&bytes).map_err(|e| format!("font {}: not a font file ({e})", path.display()))?;
    font.name().map_err(|e| format!("font {}: no name table ({e})", path.display()))?;
    let get = |id| font.localized_strings(id).english_or_first().map(|s| s.to_string());
    let family = get(StringId::TYPOGRAPHIC_FAMILY_NAME).or_else(|| get(StringId::FAMILY_NAME)).ok_or_else(|| format!("font {}: no family name", path.display()))?;
    let mut out = vec![family.clone()];
    if let Some(short) = family.strip_suffix(" Variable") {
        out.push(short.to_string());
    }
    Ok(out)
}

/// The font a scene names, or an error listing what there is.
pub fn resolve<'a>(fonts: &'a [Font], family: &str) -> Result<&'a Font, String> {
    fonts.iter().find(|f| f.family == family).ok_or_else(|| {
        let mut have: Vec<&str> = fonts.iter().map(|f| f.family.as_str()).collect();
        have.dedup();
        format!("font \"{family}\" not found; there is: {}", have.join(", "))
    })
}
