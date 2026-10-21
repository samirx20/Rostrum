//! Every scene item type's fields, as the engine checks them (ENGINE_CONTRACT.md § 2, § 5). The meaning, ranges,
//! labels and defaults live in the Python layer's one table (`apps/2d/python/rostrum2d/fields.py`); this is only
//! the names and kinds the engine needs to refuse what it doesn't know. `scene/tests.rs` checks it against
//! fields.py, so the two can't drift silently.

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Kind {
    Number,
    Color,
    Toggle,
    Text,
    Choice(&'static [&'static str]),
}

use Kind::*;

pub type Field = (&'static str, Kind);

pub const BLENDS: &[&str] = &["normal", "screen", "add", "multiply", "overlay", "soft-light"];
const SHAPES: &[&str] = &["rect", "ellipse"];

const TRANSFORM: &[Field] = &[
    ("x", Number), ("y", Number), ("scale", Number), ("rotation", Number), ("opacity", Number),
    ("anchorX", Number), ("anchorY", Number), ("scaleX", Number), ("scaleY", Number),
    ("tiltX", Number), ("tiltY", Number), ("start", Number), ("end", Number), ("blend", Choice(BLENDS)),
];

const COMP: &[Field] = &[("width", Number), ("height", Number), ("fps", Number), ("duration", Number), ("background", Color)];
const SHAPE: &[Field] = &[
    ("shape", Choice(SHAPES)), ("w", Number), ("h", Number), ("radius", Number), ("fill", Color),
    ("stroke", Toggle), ("strokeColor", Color), ("strokeWidth", Number),
];
const TEXT: &[Field] = &[
    ("body", Text), ("size", Number), ("weight", Number), ("color", Color), ("align", Choice(&["left", "center", "right"])),
    ("tracking", Number), ("lineHeight", Number), ("font", Text), ("stretch", Number), ("boxWidth", Number),
    ("stroke", Toggle), ("strokeColor", Color), ("strokeWidth", Number),
];
const IMAGE: &[Field] = &[("src", Text), ("w", Number), ("h", Number), ("fit", Choice(&["cover", "contain", "stretch"])), ("radius", Number)];
const GROUP: &[Field] = &[("w", Number), ("h", Number), ("clip", Toggle)];
const BLUR: &[Field] = &[("radius", Number)];
const GLOW: &[Field] = &[("radius", Number), ("strength", Number), ("ownColor", Toggle), ("color", Color)];
const GRADIENT: &[Field] = &[
    ("style", Choice(&["linear", "radial"])), ("angle", Number), ("color1", Color), ("color2", Color),
    ("middle", Toggle), ("color3", Color), ("mid", Number),
];
const SHADOW: &[Field] = &[("dx", Number), ("dy", Number), ("radius", Number), ("color", Color), ("strength", Number)];
const MASK: &[Field] = &[
    ("shape", Choice(SHAPES)), ("x", Number), ("y", Number), ("w", Number), ("h", Number),
    ("radius", Number), ("feather", Number), ("invert", Toggle),
];

/// Where an item may sit in the scene.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Role {
    Comp,
    Layer,
    Effect,
    Mask,
}

/// An item type's role and fields (a layer's are its own, then the transform's); None for an unknown type.
/// Drawing layers (painting-kit strokes, brief S6) are a layer type to add here, with their fields, and their
/// content in stage.rs `content`.
pub fn of(kind: &str) -> Option<(Role, Vec<Field>)> {
    let layer = |own: &[Field]| Some((Role::Layer, own.iter().chain(TRANSFORM).copied().collect()));
    match kind {
        "comp" => Some((Role::Comp, COMP.to_vec())),
        "shape" => layer(SHAPE),
        "text" => layer(TEXT),
        "image" => layer(IMAGE),
        "group" => layer(GROUP),
        "blur" => Some((Role::Effect, BLUR.to_vec())),
        "glow" => Some((Role::Effect, GLOW.to_vec())),
        "gradient" => Some((Role::Effect, GRADIENT.to_vec())),
        "shadow" => Some((Role::Effect, SHADOW.to_vec())),
        "mask" => Some((Role::Mask, MASK.to_vec())),
        _ => None,
    }
}

/// Every type the engine reads (for error messages and the fields.py check).
pub const TYPES: &[&str] = &["comp", "shape", "text", "image", "group", "blur", "glow", "gradient", "shadow", "mask"];

/// Fields keys may drive: numbers and colours, except those that describe the item rather than a moment
/// (fields.py `STILL`).
pub fn animatable(kind: &str, field: &Field) -> bool {
    matches!(field.1, Number | Color) && kind != "comp" && !matches!(field.0, "start" | "end" | "boxWidth")
}
