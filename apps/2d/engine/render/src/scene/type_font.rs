//! A text layer's font, read for its type (contract § 4 text): the OpenType features and variable axes the stage
//! writes as CSS (a feature or axis the font doesn't have is refused, naming the layer and field), and the real
//! advance widths of letters placed one by one (letters.rs), at the layer's size, tracking and axes. No kerning.
//!
//! The stage writer is handed only the evaluated comp, so the scene's fonts are registered here when a scene
//! loads (Scene::load): the registry's faces (fonts.rs), each face's file read once and kept. A text's face is the
//! one the page draws for its weight and slope (fonts.rs `pick`).

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{Arc, Mutex, OnceLock};

use skrifa::{instance::Size, raw::TableProvider, FontRef, MetadataProvider, Tag};

use super::eval::Item;
use super::fonts::Font;

type R<T> = Result<T, String>;

#[derive(Default)]
struct Registry {
    faces: Arc<Vec<Font>>,
    bytes: HashMap<(PathBuf, u32), Arc<Vec<u8>>>,
}

fn registry() -> &'static Mutex<Registry> {
    static TABLE: OnceLock<Mutex<Registry>> = OnceLock::new();
    TABLE.get_or_init(Default::default)
}

/// The scene's fonts (fonts.rs `list`), shared with the scene that holds them (no copy per load).
pub fn register(fonts: &Arc<Vec<Font>>) {
    registry().lock().unwrap_or_else(|e| e.into_inner()).faces = fonts.clone();
}

/// The file of the face a text layer is drawn in (its font, weight and slope).
fn bytes(it: &Item) -> R<Arc<Vec<u8>>> {
    let mut r = registry().lock().unwrap_or_else(|e| e.into_inner());
    let face = super::fonts::pick(&r.faces, it.str("font"), it.num("weight"), it.on("italic")).map_err(|e| format!("{}.font: {e}", it.id))?;
    let key = (face.path.clone(), face.index);
    if let Some(b) = r.bytes.get(&key) {
        return Ok(b.clone());
    }
    let b = Arc::new(super::fonts_scan::face_bytes(&key.0, key.1).map_err(|e| format!("{}.font: {e}", it.id))?);
    r.bytes.insert(key, b.clone());
    Ok(b)
}

fn open<'a>(it: &Item, bytes: &'a [u8]) -> R<FontRef<'a>> {
    FontRef::new(bytes).map_err(|e| format!("{}.font: \"{}\" is not a readable font ({e})", it.id, it.str("font")))
}

fn tag(it: &Item, field: &str, s: &str) -> R<Tag> {
    match s.as_bytes() {
        b @ [_, _, _, _] if b.iter().all(|c| c.is_ascii_alphanumeric()) => Ok(Tag::new(&[b[0], b[1], b[2], b[3]])),
        _ => Err(format!("{}.{field}: \"{s}\" is not a 4-letter tag (letters and digits)", it.id)),
    }
}

/// The axes the stage sets besides weight and width: opsz (the size, as the stage always wrote), slnt and GRAD
/// when not 0, then `axes` ("XTRA 468, CASL 1"), which wins over the named ones. Values outside an axis's range
/// are clamped by the font, as in CSS; an axis the font doesn't have is refused.
fn axes(it: &Item, font: Option<&FontRef>) -> R<Vec<(Tag, f32)>> {
    let mut out = vec![(Tag::new(b"opsz"), it.num("size").clamp(8.0, 144.0).round() as f32)];
    let mut set = |t: Tag, v: f32, field: &str| -> R<()> {
        if let Some(f) = font {
            if f.axes().get_by_tag(t).is_none() {
                let have: Vec<String> = f.axes().iter().map(|a| a.tag().to_string()).collect();
                return Err(format!("{}.{field}: the font \"{}\" has no {t} axis; it has: {}", it.id, it.str("font"), have.join(", ")));
            }
        }
        out.retain(|(o, _)| *o != t);
        out.push((t, v));
        Ok(())
    };
    for (name, field) in [("slnt", "slant"), ("GRAD", "grade")] {
        if it.num(field) != 0.0 {
            set(Tag::new(name.as_bytes().try_into().unwrap()), it.num(field) as f32, field)?;
        }
    }
    for part in it.str("axes").split(',').map(str::trim).filter(|p| !p.is_empty()) {
        let bad = || format!("{}.axes: \"{part}\" is not \"TAG value\" (e.g. \"XTRA 468, CASL 1\")", it.id);
        let (t, v) = part.split_once(char::is_whitespace).ok_or_else(bad)?;
        let v: f32 = v.trim().parse().map_err(|_| bad())?;
        set(tag(it, "axes", t)?, v, "axes")?;
    }
    Ok(out)
}

/// The OpenType features asked for, in order (a later one of the same tag wins): ligatures off, figures, small
/// caps, then `features` ("ss01 ss03 salt", "cv05=2", "-kern"). One turned on that the font lacks is refused
/// (except proportional / lining figures, usually the font's own, and tabular figures, drawn by hand where the font
/// has none: `tabular_by_hand`).
fn features(it: &Item, font: Option<&FontRef>) -> R<Vec<(Tag, u16)>> {
    let mut want: Vec<(Tag, u16, &str)> = vec![];
    if !it.on("ligatures") {
        want.extend([(Tag::new(b"liga"), 0, "ligatures"), (Tag::new(b"clig"), 0, "ligatures")]);
    }
    for word in it.str("figures").split(' ') {
        let t = match word { "proportional" => b"pnum", "tabular" => b"tnum", "lining" => b"lnum", "old-style" => b"onum", _ => continue };
        want.push((Tag::new(t), 1, "figures"));
    }
    if it.on("smallCaps") {
        want.push((Tag::new(b"smcp"), 1, "smallCaps"));
    }
    for word in it.str("features").split(|c: char| c == ',' || c.is_whitespace()).filter(|w| !w.is_empty()) {
        let (name, value): (&str, u16) = match (word.strip_prefix('-'), word.split_once('=')) {
            (Some(off), _) => (off, 0),
            (None, Some((n, v))) => (n, v.parse().map_err(|_| format!("{}.features: \"{word}\": the value after = must be a whole number", it.id))?),
            (None, None) => (word, 1),
        };
        want.push((tag(it, "features", name)?, value, "features"));
    }
    if let Some(f) = font {
        let have = font_features(f);
        // Tabular figures on a font without them are drawn by hand (`tabular_by_hand`), not asked of the font.
        let tnum = Tag::new(b"tnum");
        if !have.contains(&tnum) {
            want.retain(|(t, _, field)| !(*t == tnum && *field == "figures"));
        }
        // Proportional and lining figures are most fonts' own; asking for them where the font has no switch is fine.
        let usual = |t: &Tag| *t == Tag::new(b"pnum") || *t == Tag::new(b"lnum");
        if let Some((t, _, field)) = want.iter().find(|(t, v, _)| *v != 0 && !usual(t) && !have.contains(t)) {
            let mut names: Vec<String> = have.iter().map(Tag::to_string).collect();
            names.sort();
            names.dedup();
            return Err(format!("{}.{field}: the font \"{}\" has no {t} feature; it has: {}", it.id, it.str("font"), names.join(" ")));
        }
    }
    Ok(want.into_iter().map(|(t, v, _)| (t, v)).collect())
}

/// Tabular figures asked for (`figures`) on a font without a tnum feature (Roboto Flex, the default): drawn by hand.
/// Every digit 0-9 takes the widest digit's advance (`measure`), its glyph centred in it, and the text is drawn letter
/// by letter (stage_type.rs `by_letter`), so a counting number keeps still instead of shifting as its digits change.
pub fn tabular_by_hand(it: &Item) -> bool {
    if !it.str("figures").split(' ').any(|w| w == "tabular") {
        return false;
    }
    let Ok(held) = bytes(it) else { return false };      // a font that can't be read is refused by `css`
    FontRef::new(&held).is_ok_and(|f| !font_features(&f).contains(&Tag::new(b"tnum")))
}

fn font_features(f: &FontRef) -> Vec<Tag> {
    let mut out = vec![];
    if let Ok(list) = f.gsub().and_then(|t| t.feature_list()) {
        out.extend(list.feature_records().iter().map(|r| r.feature_tag()));
    }
    if let Ok(list) = f.gpos().and_then(|t| t.feature_list()) {
        out.extend(list.feature_records().iter().map(|r| r.feature_tag()));
    }
    out
}

/// Whether anything asks the font a question (else the font file isn't opened at all).
fn asks(it: &Item) -> bool {
    it.num("slant") != 0.0 || it.num("grade") != 0.0 || !it.str("axes").trim().is_empty() || it.str("figures") != "default"
        || it.on("smallCaps") || !it.str("features").trim().is_empty()
}

/// `font-variation-settings` (and `font-feature-settings` when any feature is asked for) of a text layer.
pub fn css(it: &Item) -> R<String> {
    let held = if asks(it) { Some(bytes(it)?) } else { None };
    let font = held.as_deref().map(|b| open(it, b)).transpose()?;
    let axes: Vec<String> = axes(it, font.as_ref())?.iter().map(|(t, v)| format!("'{t}' {v}")).collect();
    let mut s = format!("font-variation-settings:{};", axes.join(", "));
    let feats = features(it, font.as_ref())?;
    if !feats.is_empty() {
        let list: Vec<String> = feats.iter().map(|(t, v)| format!("'{t}' {v}")).collect();
        s += &format!("font-feature-settings:{};", list.join(", "));
    }
    Ok(s)
}

/// The font's measures for one line of a text layer, in px: each letter's advance (tracking included), and the
/// ascent and descent above and below the baseline.
pub struct Measure {
    pub advances: Vec<f64>,
    pub ascent: f64,
    pub descent: f64,
}

pub fn measure(it: &Item, line: &str) -> R<Measure> {
    let held = bytes(it)?;
    let font = open(it, &held)?;
    let mut settings = axes(it, Some(&font))?;
    for (t, field) in [(Tag::new(b"wght"), "weight"), (Tag::new(b"wdth"), "stretch")] {
        if !settings.iter().any(|(o, _)| *o == t) {
            settings.push((t, it.num(field) as f32));
        }
    }
    let location = font.axes().location(settings.iter().copied());
    let size = Size::new(it.num("size") as f32);
    let glyphs = font.glyph_metrics(size, &location);
    let charmap = font.charmap();
    let track = it.num("tracking") * it.num("size");
    let width = |ch: char| -> R<f64> {
        let id = charmap.map(ch).ok_or_else(|| format!("{}.body: the font \"{}\" has no letter {ch:?}", it.id, it.str("font")))?;
        let w = glyphs.advance_width(id).ok_or_else(|| format!("{}.body: the width of {ch:?} in \"{}\" can't be read", it.id, it.str("font")))?;
        Ok(w as f64)
    };
    // Tabular figures by hand: every digit as wide as the widest (letters.rs centres each glyph in its advance).
    let digit = if tabular_by_hand(it) { Some(('0'..='9').map(&width).collect::<R<Vec<_>>>()?.into_iter().fold(0.0, f64::max)) } else { None };
    let kerned = if digit.is_none() { shaped(&font, &settings, &features(it, Some(&font))?, it.num("size"), line) } else { None };
    let mut advances = vec![];
    for (i, ch) in line.chars().enumerate() {
        let w = match (digit, &kerned) {
            (Some(d), _) if ch.is_ascii_digit() => d,
            (_, Some(k)) => k[i],
            _ => width(ch)?,
        };
        advances.push(w + track);
    }
    let m = font.metrics(size, &location);
    Ok(Measure { advances, ascent: m.ascent as f64, descent: m.descent.abs() as f64 })
}

/// Each letter's advance in px as the shaper lays the line out (harfrust, the shaper the stage's text layout uses):
/// the font's kerning included, so letters placed one by one sit where the same line drawn whole puts them. One
/// glyph per letter is needed (ligatures off, as drawn letter by letter); None otherwise, and the plain advances serve.
fn shaped(font: &FontRef, settings: &[(Tag, f32)], asked: &[(Tag, u16)], size: f64, line: &str) -> Option<Vec<f64>> {
    use harfrust::{Feature, ShapeOptions, ShaperData, ShaperInstance, UnicodeBuffer, Variation};
    let data = ShaperData::new(font);
    let instance = ShaperInstance::from_variations(font, settings.iter().map(|(tag, value)| Variation { tag: *tag, value: *value }));
    let shaper = data.shaper(font).instance(Some(&instance)).build();
    let mut buffer = UnicodeBuffer::new();
    buffer.push_str(line);
    buffer.guess_segment_properties();
    let off = |t: &[u8; 4]| Feature::new(Tag::new(t), 0, ..);
    let mut features: Vec<Feature> = asked.iter().map(|(t, v)| Feature::new(*t, u32::from(*v), ..)).collect();
    features.extend([off(b"liga"), off(b"clig"), off(b"dlig"), off(b"rlig")]);
    let glyphs = shaper.shape(buffer, ShapeOptions::new().features(&features));
    let starts: Vec<usize> = line.char_indices().map(|(b, _)| b).collect();
    let (infos, pos) = (glyphs.glyph_infos(), glyphs.glyph_positions());
    if infos.len() != starts.len() || infos.iter().zip(&starts).any(|(g, b)| g.cluster as usize != *b) {
        return None;
    }
    let per_unit = size / shaper.units_per_em() as f64;
    Some(pos.iter().map(|p| p.x_advance as f64 * per_unit).collect())
}
