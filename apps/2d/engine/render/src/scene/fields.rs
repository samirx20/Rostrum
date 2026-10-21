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
    // Type (stage_type.rs): OpenType features, variable axes, text on a path, letter by letter.
    ("ligatures", Toggle), ("figures", Choice(FIGURES)), ("smallCaps", Toggle), ("features", Text),
    ("slant", Number), ("grade", Number), ("axes", Text),
    ("path", Text), ("pathOffset", Number), ("pathAlign", Choice(&["start", "center", "end"])),
    ("pathOverflow", Choice(&["hide", "straight"])),
    ("letterDelay", Number), ("letterOrder", Choice(&["forward", "backward", "center", "random"])), ("letterSeed", Number),
    ("letterSplit", Choice(&["letters", "words"])),
];
pub const FIGURES: &[&str] = &["default", "proportional lining", "tabular lining", "proportional old-style", "tabular old-style"];
const IMAGE: &[Field] = &[("src", Text), ("w", Number), ("h", Number), ("fit", Choice(&["cover", "contain", "stretch"])), ("radius", Number)];
const VIDEO: &[Field] = &[
    ("src", Text), ("w", Number), ("h", Number), ("fit", Choice(&["cover", "contain", "stretch"])), ("radius", Number),
    ("offset", Number), ("speed", Number), ("loop", Toggle),
];
const GROUP: &[Field] = &[("w", Number), ("h", Number), ("clip", Toggle)];
const DRAWING: &[Field] = &[("w", Number), ("h", Number)];
const PATH: &[Field] = &[
    ("d", Text), ("w", Number), ("h", Number), ("filled", Toggle), ("fill", Color), ("fillRule", Choice(&["nonzero", "evenodd"])),
    ("stroke", Toggle), ("strokeColor", Color), ("strokeWidth", Number), ("cap", Choice(&["butt", "round", "square"])),
    ("join", Choice(&["miter", "round", "bevel"])), ("miter", Number), ("dash", Number), ("gap", Number), ("dashOffset", Number),
    ("trimStart", Number), ("trimEnd", Number),
];
const BLUR: &[Field] = &[("radius", Number)];
const GLOW: &[Field] = &[("radius", Number), ("strength", Number), ("ownColor", Toggle), ("color", Color)];
const GRADIENT: &[Field] = &[
    ("style", Choice(&["linear", "radial", "conic"])), ("angle", Number), ("cx", Number), ("cy", Number), ("color1", Color), ("color2", Color),
    ("middle", Toggle), ("color3", Color), ("mid", Number),
];
const BACKDROP: &[Field] = &[("radius", Number), ("fillAmount", Number), ("saturate", Number), ("brightness", Number)];
const SHADOW: &[Field] = &[("dx", Number), ("dy", Number), ("radius", Number), ("color", Color), ("strength", Number)];
const MASK: &[Field] = &[
    ("shape", Choice(SHAPES)), ("x", Number), ("y", Number), ("w", Number), ("h", Number),
    ("radius", Number), ("feather", Number), ("invert", Toggle), ("angle", Number),
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
pub fn of(kind: &str) -> Option<(Role, Vec<Field>)> {
    let layer = |own: &[Field]| Some((Role::Layer, own.iter().chain(TRANSFORM).copied().collect()));
    match kind {
        "comp" => Some((Role::Comp, COMP.to_vec())),
        "shape" => layer(SHAPE),
        "text" => layer(TEXT),
        "image" => layer(IMAGE),
        "video" => layer(VIDEO),
        "group" => layer(GROUP),
        "drawing" => layer(DRAWING),
        "path" => layer(PATH),
        "blur" => Some((Role::Effect, BLUR.to_vec())),
        "glow" => Some((Role::Effect, GLOW.to_vec())),
        "gradient" => Some((Role::Effect, GRADIENT.to_vec())),
        "backdrop" => Some((Role::Effect, BACKDROP.to_vec())),
        "shadow" => Some((Role::Effect, SHADOW.to_vec())),
        "mask" => Some((Role::Mask, MASK.to_vec())),
        _ => None,
    }
}

/// Every type the engine reads (for error messages and the fields.py check).
pub const TYPES: &[&str] = &["comp", "shape", "text", "image", "video", "group", "drawing", "path", "blur", "glow", "gradient", "backdrop", "shadow", "mask"];

/// Fields keys may drive: numbers and colours, except those that describe the item rather than a moment
/// (fields.py `STILL`).
pub fn animatable(kind: &str, field: &Field) -> bool {
    matches!(field.1, Number | Color) && kind != "comp" && !matches!(field.0, "start" | "end" | "boxWidth")
        && !(matches!(kind, "drawing" | "path") && matches!(field.0, "w" | "h"))
        && !(kind == "text" && matches!(field.0, "letterDelay" | "letterSeed"))
        && !(kind == "video" && matches!(field.0, "w" | "h" | "offset" | "speed"))
}
