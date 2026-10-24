//! Reading font files into the registry's faces (fonts.rs): a folder, one file, or the computer's installed fonts
//! (Windows: C:\Windows\Fonts and the person's own fonts folders; Mac: /Library/Fonts, /System/Library/Fonts and
//! ~/Library/Fonts), through fontdb (MIT; the font database usvg already uses). Each face's family, weight (a
//! variable font's whole `wght` range), italic or not, and its file. The files are mapped only while they are read.

use std::path::{Path, PathBuf};
use std::sync::OnceLock;

use fontdb::{Database, Source as DbSource, Style};
use skrifa::{FontRef, MetadataProvider, Tag};

use super::fonts::{Font, Source};

/// Every face in `db`, under its English family name; a shipped one also without a trailing " Variable" (fonts.rs:
/// "Inter Variable" is "Inter"). An installed one keeps its name: "Segoe UI Variable" is a family of its own beside
/// "Segoe UI".
fn faces(db: &Database, source: Source, family: Option<&str>) -> Vec<Font> {
    let mut out = vec![];
    for f in db.faces() {
        let path = match &f.source {
            DbSource::File(p) | DbSource::SharedFile(p, _) => p.clone(),
            DbSource::Binary(_) => continue,
        };
        let Some(own) = f.families.first().map(|(n, _)| n.clone()) else { continue };
        let w = f.weight.0 as f32;
        let range = db.with_face_data(f.id, |data, index| {
            let font = FontRef::from_index(data, index).ok()?;
            let axis = font.axes().get_by_tag(Tag::new(b"wght"))?;
            Some((axis.min_value(), axis.max_value()))
        });
        let (weight, variable) = match range.flatten() {
            Some(r) => (r, true),
            None => ((w, w), false),
        };
        let face = Font { family: String::new(), path, index: f.index, weight, variable, italic: f.style != Style::Normal, source, alias: false };
        match family {
            Some(given) => out.push(Font { family: given.to_string(), ..face }),
            None => {
                let short = own.strip_suffix(" Variable").filter(|_| source == Source::Shipped).map(str::to_string);
                out.push(Font { family: short.clone().unwrap_or_else(|| own.clone()), ..face.clone() });
                if short.is_some() {
                    out.push(Font { family: own, alias: true, ..face });
                }
            }
        }
    }
    out
}

/// The fonts of one folder (the app's shipped fonts), sorted by file.
pub fn folder(dir: &Path, source: Source) -> Vec<Font> {
    let mut db = Database::new();
    db.load_fonts_dir(dir);
    sorted(faces(&db, source, None))
}

/// The faces of one file, all under the family the project names it by. A file that isn't a font is refused.
pub fn file(path: &Path, family: &str) -> Result<Vec<Font>, String> {
    let mut db = Database::new();
    db.load_font_file(path).map_err(|e| format!("font {}: {e}", path.display()))?;
    let out = faces(&db, Source::Project, Some(family));
    if out.is_empty() {
        return Err(format!("font {}: not a font file", path.display()));
    }
    Ok(out)
}

/// The computer's installed fonts, read once per run (a font installed while the app runs shows after a restart).
/// `ROSTRUM2D_NO_SYSTEM_FONTS=1` leaves them out (to check that a project needs nothing outside the app).
pub fn installed() -> &'static [Font] {
    static ONCE: OnceLock<Vec<Font>> = OnceLock::new();
    ONCE.get_or_init(|| {
        if std::env::var("ROSTRUM2D_NO_SYSTEM_FONTS").is_ok_and(|v| v == "1") {
            return vec![];
        }
        let mut db = Database::new();
        db.load_system_fonts();
        sorted(faces(&db, Source::Installed, None))
    })
}

fn sorted(mut v: Vec<Font>) -> Vec<Font> {
    v.sort_by(|a, b| (a.family.to_lowercase(), &a.path, a.index).cmp(&(b.family.to_lowercase(), &b.path, b.index)));
    v
}

/// The bytes of one face, as a font file of its own: a face inside a collection (.ttc) is copied out with the tables
/// it uses, so the page and the measurer each get exactly that face (a collection would register all of its faces
/// under one family name).
pub fn face_bytes(path: &PathBuf, index: u32) -> Result<Vec<u8>, String> {
    let all = std::fs::read(path).map_err(|e| format!("font {}: {e}", path.display()))?;
    if all.get(..4) != Some(b"ttcf") {
        return Ok(all);
    }
    let bad = || format!("font {}: face {index} of the collection can't be read", path.display());
    let u32_at = |o: usize| all.get(o..o + 4).map(|b| u32::from_be_bytes([b[0], b[1], b[2], b[3]]) as usize).ok_or_else(bad);
    let u16_at = |o: usize| all.get(o..o + 2).map(|b| u16::from_be_bytes([b[0], b[1]]) as usize).ok_or_else(bad);
    let start = u32_at(12 + 4 * index as usize)?;
    let tables = u16_at(start + 4)?;
    let head = 12 + 16 * tables;
    let mut out = all.get(start..start + head).ok_or_else(bad)?.to_vec();
    for t in 0..tables {
        let rec = start + 12 + 16 * t;
        let (offset, len) = (u32_at(rec + 8)?, u32_at(rec + 12)?);
        let at = out.len() as u32;
        out[12 + 16 * t + 8..12 + 16 * t + 12].copy_from_slice(&at.to_be_bytes());
        out.extend_from_slice(all.get(offset..offset + len).ok_or_else(bad)?);
        while out.len() % 4 != 0 {
            out.push(0);
        }
    }
    Ok(out)
}
