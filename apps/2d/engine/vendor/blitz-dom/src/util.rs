use crate::node::{Node, NodeData};
use color::{AlphaColor, Srgb};
use keyboard_types::Modifiers;
use std::borrow::Cow;
use style::color::AbsoluteColor;

#[cfg(target_os = "macos")]
pub(crate) const ACTION_MOD: Modifiers = Modifiers::SUPER;
#[cfg(not(target_os = "macos"))]
pub(crate) const ACTION_MOD: Modifiers = Modifiers::CONTROL;

pub type Color = AlphaColor<Srgb>;

/// Decode raw font bytes, decompressing WOFF/WOFF2 if the `woff` feature is enabled.
/// Returns the original slice unchanged for TTF/OTF input, and also on decompression
/// failure. With the `woff` feature disabled, all input passes through unchanged.
pub fn decode_font_bytes(bytes: &[u8]) -> Cow<'_, [u8]> {
    if bytes.len() < 4 {
        return Cow::Borrowed(bytes);
    }
    match &bytes[0..4] {
        #[cfg(feature = "woff")]
        b"wOFF" => wuff::decompress_woff1(bytes)
            .map(Cow::Owned)
            .unwrap_or_else(|_| {
                #[cfg(feature = "tracing")]
                tracing::warn!("Failed to decompress woff1 font");
                Cow::Borrowed(bytes)
            }),
        #[cfg(feature = "woff")]
        b"wOF2" => wuff::decompress_woff2(bytes)
            .map(Cow::Owned)
            .unwrap_or_else(|_| {
                #[cfg(feature = "tracing")]
                tracing::warn!("Failed to decompress woff2 font");
                Cow::Borrowed(bytes)
            }),
        _ => Cow::Borrowed(bytes),
    }
}

#[cfg(feature = "svg")]
use std::sync::{Arc, LazyLock};
#[cfg(feature = "svg")]
use usvg::fontdb;
#[cfg(feature = "svg")]
pub(crate) static FONT_DB: LazyLock<std::sync::RwLock<Arc<fontdb::Database>>> = LazyLock::new(|| {
    let mut db = fontdb::Database::new();
    db.load_system_fonts();
    std::sync::RwLock::new(Arc::new(db))
});

/// Rostrum proof patch: a web font (@font-face) is also given to SVG text, which usvg shapes with fontdb.
#[cfg(feature = "svg")]
pub(crate) fn add_svg_font(bytes: &[u8]) {
    let mut db = FONT_DB.write().unwrap();
    Arc::make_mut(&mut db).load_font_data(bytes.to_vec());
}

/// Rostrum proof patch: the content of an SVG `<mask>` element as a standalone SVG of the masked box's
/// size (userSpaceOnUse: the box's own coordinates), with the sibling `<filter>`s it may reference. A
/// luminance mask (the SVG default) is turned into alpha with luminanceToAlpha.
#[cfg(feature = "svg")]
pub fn svg_mask_tree(doc: &crate::BaseDocument, id: &str, width: f32, height: f32) -> Option<Arc<usvg::Tree>> {
    let mask = doc.get_node(doc.get_element_by_id(id)?)?;
    if &*mask.element_data()?.name.local != "mask" {
        return None;
    }
    let attr = |name: &str| mask.attrs()?.iter().find(|a| &*a.name.local == name).map(|a| a.value.to_string());
    let alpha = attr("mask-type").as_deref() == Some("alpha")
        || attr("style").is_some_and(|s| s.replace(' ', "").contains("mask-type:alpha"));
    let mut filters = String::new();
    if let Some(parent) = mask.parent.and_then(|p| doc.get_node(p)) {
        for &c in &parent.children {
            let n = doc.get_node(c)?;
            if n.element_data().is_some_and(|e| &*e.name.local == "filter") {
                filters.push_str(&n.svg_source());
            }
        }
    }
    let content: String = mask.children.iter().filter_map(|&c| doc.get_node(c)).map(|n| n.svg_source()).collect();
    let body = if alpha {
        content
    } else {
        format!(r#"<filter id="__rostrum_l2a" filterUnits="userSpaceOnUse" x="-10000" y="-10000" width="20000" height="20000"><feColorMatrix type="luminanceToAlpha"/></filter><g filter="url(#__rostrum_l2a)">{content}</g>"#)
    };
    let source = format!(r#"<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" overflow="visible"><defs>{filters}</defs>{body}</svg>"#);
    parse_svg_image(source.as_bytes()).ok().map(|svg| svg.tree)
}

/// Which kind of CSS image layer list (`background-image` or `mask-image`) to
/// flush from style to dedicated storage on the node.
#[derive(Clone, Copy, Debug)]
pub enum ImageLayerKind {
    Background,
    Mask,
}

impl ImageLayerKind {
    pub fn image_type(self, idx: usize) -> ImageType {
        match self {
            Self::Background => ImageType::Background(idx),
            Self::Mask => ImageType::Mask(idx),
        }
    }
}

#[derive(Clone, Copy, Debug)]
pub enum ImageType {
    Image,
    Background(usize),
    Mask(usize),
}

/// A point
#[derive(Clone, Debug, Copy, Eq, PartialEq)]
pub struct Point<T> {
    /// The x coordinate
    pub x: T,
    /// The y coordinate
    pub y: T,
}

impl Point<f64> {
    pub const ZERO: Self = Point { x: 0.0, y: 0.0 };
}

// Debug print an RcDom
pub fn walk_tree(indent: usize, node: &Node) {
    // Skip all-whitespace text nodes entirely
    if let NodeData::Text(data) = &node.data {
        if data.content.chars().all(|c| c.is_ascii_whitespace()) {
            return;
        }
    }

    print!("{}", " ".repeat(indent));
    let id = node.id;
    match &node.data {
        NodeData::Document(_) => println!("#Document {id}"),

        NodeData::Text(data) => {
            if data.content.chars().all(|c| c.is_ascii_whitespace()) {
                println!("{id} #text: <whitespace>");
            } else {
                let content = data.content.trim();
                if content.len() > 10 {
                    println!(
                        "#text {id}: {}...",
                        content
                            .split_at(content.char_indices().take(10).last().unwrap().0)
                            .0
                            .escape_default()
                    )
                } else {
                    println!("#text {id}: {}", data.content.trim().escape_default())
                }
            }
        }

        NodeData::Comment { .. } => println!("<!-- COMMENT {id} -->"),

        NodeData::AnonymousBlock(_) => println!("{id} AnonymousBlock"),

        NodeData::Element(data) => {
            print!("<{} {id}", data.name.local);
            for attr in data.attrs.iter() {
                print!(" {}=\"{}\"", attr.name.local, attr.value);
            }
            if !node.children.is_empty() {
                println!(">");
            } else {
                println!("/>");
            }
        } // NodeData::Doctype {
          //     ref name,
          //     ref public_id,
          //     ref system_id,
          // } => println!("<!DOCTYPE {} \"{}\" \"{}\">", name, public_id, system_id),
          // NodeData::ProcessingInstruction { .. } => unreachable!(),
    }

    if !node.children.is_empty() {
        for child_id in node.children.iter() {
            walk_tree(indent + 2, node.with(*child_id));
        }

        if let NodeData::Element(data) = &node.data {
            println!("{}</{}>", " ".repeat(indent), data.name.local);
        }
    }
}

/// Parse an SVG image.
#[cfg(feature = "svg")]
pub(crate) fn parse_svg_image(source: &[u8]) -> Result<crate::node::SvgImageData, usvg::Error> {
    let options = usvg::Options {
        fontdb: Arc::clone(&*FONT_DB.read().unwrap()),
        ..Default::default()
    };
    crate::node::SvgImageData::from_data(source, &options)
}

pub trait ToColorColor {
    /// Converts a color into the `AlphaColor<Srgb>` type from the `color` crate
    fn as_color_color(&self) -> Color;
}
impl ToColorColor for AbsoluteColor {
    fn as_color_color(&self) -> Color {
        Color::new(
            *self
                .to_color_space(style::color::ColorSpace::Srgb)
                .raw_components(),
        )
    }
}

#[cfg(all(test, feature = "svg"))]
mod svg_tests {
    use super::parse_svg_image;

    #[test]
    fn svg_without_xmlns_parses() {
        let src = br#"<svg viewBox="0 0 24 24"><path d="M0 0h24v24H0z"/></svg>"#;
        let svg = parse_svg_image(src).unwrap();
        assert!(!svg.tree.root().children().is_empty());
    }

    #[test]
    fn missing_height_is_computed_from_width_and_viewbox_ratio() {
        let src = br#"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="200"><rect width="100%" height="100%" fill="green"/></svg>"#;
        let svg = parse_svg_image(src).unwrap();
        assert_eq!(svg.intrinsic_width(), Some(200.0));
        assert_eq!(svg.intrinsic_height(), None);
        assert_eq!(svg.viewbox_aspect_ratio(), Some(1.0));
        assert_eq!(svg.tree.size().width(), 200.0);
        assert_eq!(svg.intrinsic_size(), (200.0, 200.0));
    }

    #[test]
    fn viewbox_only_has_no_intrinsic_dimensions() {
        let src = br#"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 485 58"></svg>"#;
        let svg = parse_svg_image(src).unwrap();
        assert_eq!(svg.intrinsic_width(), None);
        assert_eq!(svg.intrinsic_height(), None);
        // The aspect ratio is still available from the viewBox.
        assert!((svg.aspect_ratio() - (485.0 / 58.0)).abs() < 1e-3);
    }

    #[test]
    fn absolute_dimensions_are_intrinsic() {
        let src = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="16" viewBox="0 0 48 32"></svg>"#;
        let svg = parse_svg_image(src).unwrap();
        assert_eq!(svg.intrinsic_width(), Some(24.0));
        assert_eq!(svg.intrinsic_height(), Some(16.0));
    }

    #[test]
    fn percentage_dimensions_are_not_intrinsic() {
        let src = br#"<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="50%" viewBox="0 0 200 100"></svg>"#;
        let svg = parse_svg_image(src).unwrap();
        assert_eq!(svg.intrinsic_width(), None);
        assert_eq!(svg.intrinsic_height(), None);
    }

    #[test]
    fn unit_lengths_are_intrinsic() {
        let src = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24px" height="1.5em" viewBox="0 0 48 32"></svg>"#;
        let svg = parse_svg_image(src).unwrap();
        assert!(svg.intrinsic_width().is_some());
        assert!(svg.intrinsic_height().is_some());
    }

    #[test]
    fn non_numeric_dimensions_are_not_intrinsic() {
        let src = br#"<svg xmlns="http://www.w3.org/2000/svg" width="auto" height="foo" viewBox="0 0 200 100"></svg>"#;
        let svg = parse_svg_image(src).unwrap();
        assert_eq!(svg.intrinsic_width(), None);
        assert_eq!(svg.intrinsic_height(), None);
    }
}

/// Creates an markup5ever::QualName.
/// Given a local name and an optional namespace
#[macro_export]
macro_rules! qual_name {
    ($local:tt $(, $ns:ident)?) => {
        $crate::QualName {
            prefix: None,
            ns: $crate::ns!($($ns)?),
            local: $crate::local_name!($local),
        }
    };
}

/// Rostrum proof patch: a node's own `position: relative` offset (CSS px; percentages count as 0).
pub fn relative_offset(node: &crate::Node) -> (f64, f64) {
    use style::values::generics::position::GenericInset;
    let Some(s) = node.primary_styles() else {
        return (0.0, 0.0);
    };
    if s.clone_position() != style::computed_values::position::T::Relative {
        return (0.0, 0.0);
    }
    let p = s.get_position();
    let px = |v: &style::values::computed::position::Inset| match v {
        GenericInset::LengthPercentage(lp) => lp.to_length().map(|l| l.px() as f64),
        _ => None,
    };
    let x = px(&p.left).or(px(&p.right).map(|v| -v)).unwrap_or(0.0);
    let y = px(&p.top).or(px(&p.bottom).map(|v| -v)).unwrap_or(0.0);
    (x, y)
}

/// Rostrum proof patch: the summed relative offsets of `from` and its ancestors up to (not including)
/// the inline root `root` — how far an inline span's content is moved (CSS px).
pub fn inline_relative_offset(doc: &crate::BaseDocument, from: Option<blitz_traits::node_id::NodeId>, root: blitz_traits::node_id::NodeId) -> (f64, f64) {
    let (mut x, mut y) = (0.0, 0.0);
    let mut cur = from;
    while let Some(id) = cur {
        if id == root {
            break;
        }
        let Some(node) = doc.get_node(id) else { break };
        let (dx, dy) = relative_offset(node);
        x += dx;
        y += dy;
        cur = node.parent;
    }
    (x, y)
}

/// Rostrum measurement patch (E17): ns spent in each `resolve` phase on this process, summed (style, damage, construct,
/// pconstruct, layout, transform, paint_tree, c_damage); the engine's staging profile reads and clears them.
pub static PHASE_NANOS: [std::sync::atomic::AtomicU64; 8] = [const { std::sync::atomic::AtomicU64::new(0) }; 8];

pub(crate) fn phase(i: usize, lap: &mut std::time::Instant) {
    let now = std::time::Instant::now();
    PHASE_NANOS[i].fetch_add((now - *lap).as_nanos() as u64, std::sync::atomic::Ordering::Relaxed);
    *lap = now;
}
