//! The families there are, for people and agents (serve's `fonts`, `rostrum2d-render fonts`): each family once, from
//! the registry (fonts.rs), with where it comes from, its real weights and whether it has italics. Shipped families
//! first, then the project's, then the computer's, each group by name.

use serde_json::{json, Value};
use skrifa::{FontRef, MetadataProvider, Tag};

use super::fonts::{Font, Source};
use super::fonts_scan::face_bytes;

/// A variable face's named weights (its instances' `wght`), else every hundred inside its range.
fn named(f: &Font) -> Vec<f32> {
    let (lo, hi) = f.weight;
    let mut out: Vec<f32> = face_bytes(&f.path, f.index).ok().and_then(|bytes| {
        let font = FontRef::new(&bytes).ok()?;
        let at = font.axes().iter().position(|a| a.tag() == Tag::new(b"wght"))?;
        Some(font.named_instances().iter().filter_map(|i| i.user_coords().nth(at)).collect::<Vec<f32>>())
    }).unwrap_or_default();
    if out.is_empty() {
        out = (1..=9).map(|n| n as f32 * 100.0).filter(|w| (lo..=hi).contains(w)).collect();
    }
    out
}

fn family(name: &str, faces: &[&Font]) -> Value {
    let mut weights: Vec<f32> = faces.iter().flat_map(|f| if f.variable { named(f) } else { vec![f.weight.0] }).collect();
    weights.sort_by(|a, b| a.partial_cmp(b).unwrap());
    weights.dedup();
    let lo = faces.iter().map(|f| f.weight.0).fold(f32::MAX, f32::min);
    let hi = faces.iter().map(|f| f.weight.1).fold(f32::MIN, f32::max);
    json!({
        "family": name, "source": faces[0].source.word(), "weights": weights, "range": [lo, hi],
        "variable": faces.iter().any(|f| f.variable), "italic": faces.iter().any(|f| f.italic),
        "upright": faces.iter().any(|f| !f.italic), "files": files(faces),
    })
}

/// The family's files, each once, upright ones first (the first is the one to show the family's name in).
fn files(faces: &[&Font]) -> Vec<String> {
    let mut out: Vec<String> = vec![];
    for f in faces.iter().filter(|f| !f.italic).chain(faces.iter().filter(|f| f.italic)) {
        let p = f.path.display().to_string();
        if !out.contains(&p) {
            out.push(p);
        }
    }
    out
}

/// `{"ok": true, "families": [{family, source, weights, range, variable, italic, upright, files}, …], "aliases": [names]}`
/// (`aliases`: second names a text may also give, such as "Inter Variable").
pub fn list(fonts: &[Font]) -> Value {
    let mut names: Vec<(u8, String)> = vec![];
    for f in fonts.iter().filter(|f| !f.alias) {
        let rank = match f.source { Source::Shipped => 0, Source::Project => 1, Source::Installed => 2 };
        if !names.iter().any(|(_, n)| *n == f.family) {
            names.push((rank, f.family.clone()));
        }
    }
    names.sort_by(|a, b| (a.0, a.1.to_lowercase()).cmp(&(b.0, b.1.to_lowercase())));
    let families: Vec<Value> = names.iter().map(|(_, n)| {
        let faces: Vec<&Font> = fonts.iter().filter(|f| f.family == *n).collect();
        family(n, &faces)
    }).collect();
    let mut aliases: Vec<&str> = fonts.iter().filter(|f| f.alias).map(|f| f.family.as_str()).collect();
    aliases.dedup();
    json!({ "ok": true, "families": families, "aliases": aliases })
}
