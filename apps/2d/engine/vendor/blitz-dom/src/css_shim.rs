//! Rostrum patch (round 14, H5): CSS properties Stylo built for Servo does not parse, cascaded anyway.
//!
//! Stylo for Servo drops `background-clip: text` (a Gecko-only keyword), `-webkit-text-stroke` and
//! `filter: url(#id)` (its Url filter is uninhabited) as parse errors, so a stylesheet rule setting them
//! vanished. Every such declaration, in a stylesheet or a style attribute, is copied right after itself
//! into a custom property (`background-clip: text` → `…; --rostrum-background-clip: text`) before Stylo
//! parses the text. Stylo cascades custom properties with the same specificity, order, `!important`,
//! `var()` and inheritance as any property, so the custom property's computed value *is* the cascaded
//! value. Each one is registered (`CSS.registerProperty`, syntax `*`) with its real property's
//! inheritance, so `background-clip` does not leak into children while `-webkit-text-stroke` does.
//! The painter reads them back with [`value`].
//!
//! Where Stylo does parse a property (`background-clip: padding-box`, `filter: blur()`), the copy only
//! mirrors it. Aliases (`-webkit-background-clip`) share one custom property, so the later one wins.

use std::borrow::Cow;
use std::sync::LazyLock;

use cssparser::{Parser, Token};
use style::properties::ComputedValues;
use style::stylesheets::UrlExtraData;
use style::stylist::Stylist;
use style::Atom;

/// A property Stylo for Servo cannot hold, cascaded through its custom property.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Shim {
    /// `-webkit-text-stroke` (inherits)
    TextStroke,
    /// `paint-order` (inherits)
    PaintOrder,
    /// `background-clip` / `-webkit-background-clip`, and the clip boxes of the `background` shorthand
    BackgroundClip,
    /// `filter` (for `url(#id)`)
    Filter,
    /// `backdrop-filter` / `-webkit-backdrop-filter` (for `url(#id)`)
    BackdropFilter,
    /// `mask-image` / `-webkit-mask-image`, and the `mask` / `-webkit-mask` shorthands (for `url(#id)`)
    MaskImage,
    /// `clip-path` / `-webkit-clip-path` (for `url(#id)`; Rostrum patch, 2D SVG masks)
    ClipPath,
}

impl Shim {
    const ALL: [Shim; 7] = [Shim::TextStroke, Shim::PaintOrder, Shim::BackgroundClip, Shim::Filter, Shim::BackdropFilter, Shim::MaskImage, Shim::ClipPath];

    /// The shim a CSS property feeds as it is (`-webkit-background-clip` → BackgroundClip).
    pub fn of(property: &str) -> Option<Shim> {
        match feed(property)? {
            Feed::Copy(shim) => Some(shim),
            Feed::ShorthandClip => None,
        }
    }

    /// The custom property's name as an atom (interned once).
    fn atom(self) -> &'static Atom {
        static ATOMS: LazyLock<[Atom; 7]> = LazyLock::new(|| Shim::ALL.map(|s| Atom::from(s.name())));
        &ATOMS[self as usize]
    }

    /// The custom property's name, without the leading `--`.
    fn name(self) -> &'static str {
        match self {
            Shim::TextStroke => "rostrum-text-stroke",
            Shim::PaintOrder => "rostrum-paint-order",
            Shim::BackgroundClip => "rostrum-background-clip",
            Shim::Filter => "rostrum-filter",
            Shim::BackdropFilter => "rostrum-backdrop-filter",
            Shim::MaskImage => "rostrum-mask-image",
            Shim::ClipPath => "rostrum-clip-path",
        }
    }

    fn inherits(self) -> bool {
        matches!(self, Shim::TextStroke | Shim::PaintOrder)
    }
}

/// How a declaration feeds a shim: copied as it is, or (the `background` shorthand) its clip boxes.
#[derive(Clone, Copy)]
enum Feed {
    Copy(Shim),
    ShorthandClip,
}

/// The CSS properties the shim watches (lower case).
const PROPERTIES: [(&str, Feed); 14] = [
    ("-webkit-text-stroke", Feed::Copy(Shim::TextStroke)),
    ("paint-order", Feed::Copy(Shim::PaintOrder)),
    ("background-clip", Feed::Copy(Shim::BackgroundClip)),
    ("-webkit-background-clip", Feed::Copy(Shim::BackgroundClip)),
    ("background", Feed::ShorthandClip),
    ("filter", Feed::Copy(Shim::Filter)),
    ("backdrop-filter", Feed::Copy(Shim::BackdropFilter)),
    ("-webkit-backdrop-filter", Feed::Copy(Shim::BackdropFilter)),
    ("mask-image", Feed::Copy(Shim::MaskImage)),
    ("-webkit-mask-image", Feed::Copy(Shim::MaskImage)),
    ("mask", Feed::Copy(Shim::MaskImage)),
    ("-webkit-mask", Feed::Copy(Shim::MaskImage)),
    ("clip-path", Feed::Copy(Shim::ClipPath)),
    ("-webkit-clip-path", Feed::Copy(Shim::ClipPath)),
];

/// Text worth tokenizing: it names a watched property somewhere (ASCII case-insensitive).
const NEEDLES: [&str; 6] = ["stroke", "paint-order", "background", "filter", "mask", "clip-path"];

/// Register every shim's custom property with its real property's inheritance (call once per Stylist,
/// before styling).
pub(crate) fn register(stylist: &mut Stylist, url_data: &UrlExtraData) {
    for shim in Shim::ALL {
        let _ = stylist.register_custom_property(url_data, &format!("--{}", shim.name()), "*", shim.inherits(), None);
    }
}

/// The cascaded value of `shim` for an element (its CSS text), or `None` when nothing sets it.
pub fn value(styles: &ComputedValues, shim: Shim) -> Option<&str> {
    let v = styles.custom_properties().get_for_cssom(shim.atom())?.as_universal()?;
    let css = v.css.trim();
    (!css.is_empty()).then_some(css)
}

/// A stylesheet's text with the shim's copies added.
pub fn rewrite_stylesheet(css: &str) -> Cow<'_, str> {
    rewrite(css, false)
}

/// A declaration list's text (a `style` attribute) with the shim's copies added.
pub fn rewrite_declarations(css: &str) -> Cow<'_, str> {
    rewrite(css, true)
}

/// Whether `set_style_property(name, …)` must go through [`rewrite_declarations`].
pub fn watches(name: &str) -> bool {
    feed(name).is_some()
}

fn feed(name: &str) -> Option<Feed> {
    PROPERTIES.iter().find(|(p, _)| p.eq_ignore_ascii_case(name)).map(|(_, f)| *f)
}

fn rewrite(css: &str, declarations: bool) -> Cow<'_, str> {
    let bytes = css.as_bytes();
    let mentions = |needle: &str| bytes.windows(needle.len()).any(|w| w.eq_ignore_ascii_case(needle.as_bytes()));
    if !NEEDLES.iter().any(|n| mentions(n)) {
        return Cow::Borrowed(css);
    }
    let mut edits = vec![];
    walk(&mut Parser::new(css), declarations, &mut edits);
    if edits.is_empty() {
        return Cow::Borrowed(css);
    }
    edits.sort_by_key(|e| e.0);
    let mut out = String::with_capacity(css.len() + edits.len() * 48);
    let mut at = 0;
    for (start, end, text) in edits {
        out.push_str(&css[at..start]);
        out.push_str(&text);
        at = end;
    }
    out.push_str(&css[at..]);
    Cow::Owned(out)
}

/// An edit: replace `css[start..end]` with the text.
type Edit = (usize, usize, String);

/// Walk a block's tokens. `declarations`: an identifier at the start of a statement may be a
/// declaration's name (inside any `{}` block, or a style attribute); at a stylesheet's top level only
/// rules start.
fn walk(input: &mut Parser<'_>, declarations: bool, edits: &mut Vec<Edit>) {
    let mut at_start = declarations;
    loop {
        let token = match input.next_including_whitespace_and_comments() {
            Ok(token) => token.clone(),
            Err(_) => return,
        };
        match token {
            Token::WhiteSpace(_) | Token::Comment(_) => {}
            Token::Semicolon => at_start = declarations,
            Token::CurlyBracketBlock => {
                nested(input, edits);
                at_start = declarations;
            }
            Token::Ident(ref name) if at_start => match feed(name) {
                Some(f) => at_start = declaration(input, f, edits) && declarations,
                None => at_start = false,
            },
            _ => at_start = false,
        }
    }
}

fn nested(input: &mut Parser<'_>, edits: &mut Vec<Edit>) {
    let _ = input.parse_nested_block(|block| {
        walk(block, true, edits);
        Ok::<(), cssparser::ParseError<()>>(())
    });
}

/// After a watched property's name: its value, up to `;` or the block's end, copied into the shim.
/// Returns whether the statement ended (false: it was not a declaration, e.g. a nested rule's selector).
fn declaration(input: &mut Parser<'_>, feed: Feed, edits: &mut Vec<Edit>) -> bool {
    // `name :`
    loop {
        match input.next_including_whitespace_and_comments() {
            Ok(Token::WhiteSpace(_)) | Ok(Token::Comment(_)) => continue,
            Ok(Token::Colon) => break,
            _ => return false,
        }
    }
    let value_start = input.position();
    let mut value_end;
    // The `background` shorthand: each layer's last box keyword is its clip (one box sets origin and
    // clip, two set origin then clip); `text` ones are replaced by `border-box` in the original, since
    // Stylo for Servo rejects the whole shorthand otherwise.
    let mut layers: Vec<Option<String>> = vec![None];
    let mut texts = vec![];
    let (mut bang, mut important) = (false, false);
    loop {
        value_end = input.position();
        let token = match input.next_including_whitespace_and_comments() {
            Ok(token) => token.clone(),
            Err(_) => break,
        };
        match token {
            Token::Semicolon => break,
            Token::CurlyBracketBlock => {
                // A nested rule whose selector began like a declaration (`paint-order:hover { … }`).
                nested(input, edits);
                return true;
            }
            Token::WhiteSpace(_) | Token::Comment(_) => continue,
            // A block opened in the value (`blur(`, `linear-gradient(`): step over its content now, so the
            // position (where the copy goes) is past its closing bracket, not inside it.
            Token::Function(_) | Token::ParenthesisBlock | Token::SquareBracketBlock => {
                let _ = input.parse_nested_block(|_| Ok::<(), cssparser::ParseError<()>>(()));
            }
            Token::Comma => layers.push(None),
            Token::Delim('!') => {
                bang = true;
                continue;
            }
            Token::Ident(ref word) => {
                important |= bang && word.eq_ignore_ascii_case("important");
                let word = word.to_ascii_lowercase();
                if matches!(word.as_str(), "text" | "border-box" | "padding-box" | "content-box") {
                    if word == "text" {
                        texts.push((value_end.byte_index(), input.position().byte_index()));
                    }
                    *layers.last_mut().unwrap() = Some(word);
                }
            }
            _ => {}
        }
        bang = false;
    }
    let important = if important { " !important" } else { "" };
    let copy = match feed {
        Feed::Copy(shim) => format!(";--{}:{}", shim.name(), input.slice(value_start..value_end)),
        Feed::ShorthandClip if texts.is_empty() => format!(";--{}:initial{important}", Shim::BackgroundClip.name()),
        Feed::ShorthandClip => {
            for (start, end) in texts {
                edits.push((start, end, "border-box".into()));
            }
            let clips: Vec<&str> = layers.iter().map(|l| l.as_deref().unwrap_or("border-box")).collect();
            format!(";--{}:{}{important}", Shim::BackgroundClip.name(), clips.join(","))
        }
    };
    let at = value_end.byte_index();
    edits.push((at, at, copy));
    true
}
