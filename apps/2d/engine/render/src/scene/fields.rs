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

const SHAPES: &[&str] = &["rect", "ellipse"];
/// A shape layer's kinds (super::shape_geom draws all but rect and ellipse as a path).
pub const SHAPE_KINDS: &[&str] = &["rect", "ellipse", "arc", "triangle", "polygon", "star", "line", "arrow", "spiral"];
pub const HEADS: &[&str] = &["none", "triangle", "open", "circle", "square", "bar"];
/// How a picture fills a shape (super::stage_fill).
pub const PICTURE_FITS: &[&str] = &["fill", "fit", "tile", "stretch"];
/// How a picture or painted fill meets its colour under it (stage_raster.rs; rostrum2d/fill_fields.py BLENDS).
pub const FILL_BLENDS: &[&str] = &["normal", "multiply", "screen", "overlay"];
/// How a video layer repeats its clip (stage_fx.rs `fold`; the Python layer's looping.py MODES).
pub const LOOP_MODES: &[&str] = &["off", "loop", "pingpong"];
/// Where a rider sits on its path (super::follow `ride`): the drawn-on tip, the trim's start, or `rideAlong`.
const RIDE_AT: &[&str] = &["end", "start", "along"];

/// Riding a path layer beside it (super::follow): its id ("" = none), where on it, and turning with it. Every layer
/// and the frame (its centre rides the path).
pub const RIDE: &[Field] = &[("ridePath", Text), ("rideAt", Choice(RIDE_AT)), ("rideAlong", Number), ("rideTurn", Toggle)];

const TRANSFORM: &[Field] = &[
    ("x", Number), ("y", Number), ("scale", Number), ("rotation", Number), ("opacity", Number),
    ("scaleX", Number), ("scaleY", Number), ("anchorX", Number), ("anchorY", Number),
    ("tiltX", Number), ("tiltY", Number), ("start", Number), ("end", Number),
];
/// After the blend (its options are the one list, super::blends) and before the layout's own fields.
const TRANSFORM_AFTER_BLEND: &[Field] = &[
    // The frame (crate::frame; FRAME.md): how far behind the frame's plane a top-level layer sits, or pinned to the frame.
    ("depth", Number), ("screenLock", Toggle),
    // A track matte (super::matte): a sibling layer's id ("" = none) and how its drawing is read.
    ("matte", Text), ("matteMode", Choice(super::matte::MODES)),
];
/// After the ride (RIDE).
const COLOUR: &[Field] = &[
    // Colour effects (super::grade): adjust, levels, curves (points as text, "x,y x,y …"), a .cube LUT ("" = none).
    ("adjust", Toggle), ("exposure", Number), ("contrast", Number), ("saturation", Number), ("temperature", Number),
    ("tint", Number), ("hue", Number),
    ("levels", Toggle), ("inBlack", Number), ("inWhite", Number), ("gamma", Number), ("outBlack", Number), ("outWhite", Number),
    ("curves", Toggle), ("curve", Text), ("curveR", Text), ("curveG", Text), ("curveB", Text),
    ("lut", Text), ("lutMix", Number),
];

/// Every layer's transform, look and colour fields, in the table's order.
fn transform() -> impl Iterator<Item = Field> {
    TRANSFORM.iter().copied().chain([("blend", Choice(super::blends::names()))]).chain(TRANSFORM_AFTER_BLEND.iter().chain(RIDE).chain(COLOUR).copied())
}

const COMP: &[Field] = &[("width", Number), ("height", Number), ("fps", Number), ("duration", Number), ("background", Color)];
const SHAPE: &[Field] = &[
    ("shape", Choice(SHAPE_KINDS)), ("w", Number), ("h", Number), ("radius", Number),
    // Each corner its own radius (rect): top-left, top-right, bottom-right, bottom-left.
    ("eachCorner", Toggle), ("radiusTL", Number), ("radiusTR", Number), ("radiusBR", Number), ("radiusBL", Number),
    // The parametric kinds (super::shape_geom).
    ("sides", Number), ("points", Number), ("innerRadius", Number), ("innerCorner", Number), ("tip", Number), ("hole", Number),
    ("startAngle", Number), ("sweep", Number), ("turns", Number), ("lineWidth", Number), ("lineCap", Choice(&["butt", "round", "square"])),
    ("headStart", Choice(HEADS)), ("headEnd", Choice(HEADS)), ("headSize", Number),
    ("filled", Toggle), ("fill", Color), ("fillOpacity", Number),
    ("stroke", Toggle), ("strokeColor", Color), ("strokeWidth", Number),
    ("fillPicture", Text), ("fillFit", Choice(PICTURE_FITS)), ("fillScale", Number),
    ("fillOffsetX", Number), ("fillOffsetY", Number), ("fillRotation", Number), ("fillDriftX", Number), ("fillDriftY", Number),
    ("fillUnder", Color), ("fillBlend", Choice(FILL_BLENDS)),
];
const TEXT: &[Field] = &[
    ("body", Text), ("font", Text), ("size", Number), ("weight", Number), ("italic", Toggle), ("color", Color), ("fillOpacity", Number), ("align", Choice(&["left", "center", "right"])),
    ("tracking", Number), ("lineHeight", Number), ("stretch", Number), ("boxWidth", Number),
    ("stroke", Toggle), ("strokeColor", Color), ("strokeWidth", Number),
    // Type (stage_type.rs): OpenType features, variable axes, text on a path, letter by letter.
    ("ligatures", Toggle), ("figures", Choice(FIGURES)), ("smallCaps", Toggle), ("features", Text),
    ("slant", Number), ("grade", Number), ("axes", Text),
    ("pathLayer", Text), ("path", Text), ("pathOffset", Number), ("pathAlign", Choice(&["start", "center", "end"])),
    ("pathOverflow", Choice(&["hide", "straight"])),
    ("letterDelay", Number), ("letterOrder", Choice(&["forward", "backward", "center", "random"])), ("letterSeed", Number),
    ("letterSplit", Choice(&["letters", "words"])),
    // A text that counts (super::counter): the number, its decimals, least digits and thousands mark, the words around it.
    ("counter", Toggle), ("count", Number), ("countDecimals", Number), ("countDigits", Number), ("countSeparator", Choice(super::counter::SEPARATORS)),
    ("countPrefix", Text), ("countSuffix", Text),
];
pub const FIGURES: &[&str] = &["default", "proportional lining", "tabular lining", "proportional old-style", "tabular old-style"];
const IMAGE: &[Field] = &[("src", Text), ("w", Number), ("h", Number), ("fit", Choice(&["cover", "contain", "stretch"])), ("radius", Number)];
const VIDEO: &[Field] = &[
    ("src", Text), ("w", Number), ("h", Number), ("fit", Choice(&["cover", "contain", "stretch"])), ("radius", Number),
    ("offset", Number), ("speed", Number), ("loop", Choice(LOOP_MODES)),
];
const GROUP: &[Field] = &[("w", Number), ("h", Number), ("clip", Toggle)];
const DRAWING: &[Field] = &[("w", Number), ("h", Number)];
const PATH: &[Field] = &[
    ("d", Text), ("w", Number), ("h", Number), ("filled", Toggle), ("fill", Color), ("fillOpacity", Number), ("fillRule", Choice(&["nonzero", "evenodd"])),
    ("stroke", Toggle), ("strokeColor", Color), ("strokeWidth", Number), ("cap", Choice(&["butt", "round", "square"])),
    ("join", Choice(&["miter", "round", "bevel"])), ("miter", Number), ("dash", Number), ("gap", Number), ("dashOffset", Number),
    ("trimStart", Number), ("trimEnd", Number),
    ("fillPicture", Text), ("fillFit", Choice(PICTURE_FITS)), ("fillScale", Number),
    ("fillOffsetX", Number), ("fillOffsetY", Number), ("fillRotation", Number), ("fillDriftX", Number), ("fillDriftY", Number),
    ("fillUnder", Color), ("fillBlend", Choice(FILL_BLENDS)),
    // A varied width (super::width_profile, drawn by super::stroke_width); widthProfile keys blend by width_profile::blend.
    ("taperStart", Number), ("taperEnd", Number), ("widthProfile", Text), ("taperAlong", Choice(&["line", "drawn"])),
];
const BLUR: &[Field] = &[("radius", Number)];
const GLOW: &[Field] = &[("radius", Number), ("strength", Number), ("ownColor", Toggle), ("color", Color)];
const GRADIENT: &[Field] = &[
    ("style", Choice(&["linear", "radial", "conic"])), ("angle", Number), ("cx", Number), ("cy", Number), ("color1", Color), ("color2", Color),
    ("middle", Toggle), ("color3", Color), ("mid", Number),
    // Free geometry (span "points"): linear from (x1, y1) to (x2, y2), radial radii rx, ry; fractions of the box.
    ("span", Choice(&["box", "points"])), ("x1", Number), ("y1", Number), ("x2", Number), ("y2", Number), ("rx", Number), ("ry", Number),
];
/// A gradient's colour stop (its `stops`; replace color1 / color2 / middle when there are any).
const STOP: &[Field] = &[("at", Number), ("color", Color), ("opacity", Number)];
const BACKDROP: &[Field] = &[("radius", Number), ("fillAmount", Number), ("saturate", Number), ("brightness", Number)];
/// Film grain (super::grain); `frame` is not a field: eval.rs writes the frame number now.
const GRAIN: &[Field] = &[("amount", Number), ("size", Number), ("colour", Toggle), ("still", Toggle), ("seed", Number), ("smooth", Toggle)];
/// Rough edges (super::rough); `frame` is not a field: eval.rs writes the frame number now.
const ROUGH: &[Field] = &[("amount", Number), ("size", Number), ("detail", Number), ("boil", Number), ("seed", Number)];
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
    /// A rig's part: bone, ik or bind (crate::rig::fields).
    Rig,
    /// A gradient's colour stop.
    Stop,
}

/// An item type's role and fields (a layer's are its own, then the transform's); None for an unknown type.
pub fn of(kind: &str) -> Option<(Role, Vec<Field>)> {
    let layer = |own: &[Field]| Some((Role::Layer, own.iter().copied().chain(transform()).collect()));
    match kind {
        "comp" => Some((Role::Comp, COMP.iter().chain(crate::motion::COMP).copied().collect())),
        "camera" => Some((Role::Layer, crate::frame::FIELDS.iter().chain(RIDE).copied().collect())),
        "shape" => layer(SHAPE),
        "text" => layer(TEXT),
        "image" => layer(IMAGE),
        "video" => layer(VIDEO),
        "group" | "rig" => layer(GROUP),
        "drawing" => layer(DRAWING),
        "path" => layer(PATH),
        "blur" => Some((Role::Effect, BLUR.to_vec())),
        "glow" => Some((Role::Effect, GLOW.to_vec())),
        "gradient" => Some((Role::Effect, GRADIENT.to_vec())),
        "backdrop" => Some((Role::Effect, BACKDROP.to_vec())),
        "shadow" => Some((Role::Effect, SHADOW.to_vec())),
        "grain" => Some((Role::Effect, GRAIN.to_vec())),
        "rough" => Some((Role::Effect, ROUGH.to_vec())),
        "mask" => Some((Role::Mask, MASK.to_vec())),
        "stop" => Some((Role::Stop, STOP.to_vec())),
        "trail" | "smear" => crate::motion::fields(kind).map(|f| (Role::Effect, f.to_vec())),
        "bone" | "ik" | "bind" => crate::rig::fields::of(kind).map(|f| (Role::Rig, f.to_vec())),
        _ => None,
    }
}

/// Every type the engine reads (for error messages and the fields.py check).
pub const TYPES: &[&str] = &["comp", "shape", "text", "image", "video", "group", "drawing", "path", "blur", "glow", "gradient", "backdrop", "shadow", "grain", "rough", "mask", "stop", "rig", "bone", "ik", "bind", "camera", "trail", "smear"];

/// Fields keys may drive: numbers, colours, a path's shape `d` and its `widthProfile`, except those that describe the item rather than a moment
/// (fields.py `STILL`).
pub fn animatable(kind: &str, field: &Field) -> bool {
    (matches!(field.1, Number | Color) || (kind == "path" && matches!(field.0, "d" | "widthProfile"))) && kind != "comp" && !matches!(field.0, "start" | "end" | "boxWidth" | "fillDriftX" | "fillDriftY")
        && !(matches!(kind, "drawing" | "path") && matches!(field.0, "w" | "h"))
        && !(kind == "text" && matches!(field.0, "letterDelay" | "letterSeed" | "countDecimals" | "countDigits"))
        && !(kind == "video" && matches!(field.0, "w" | "h" | "offset" | "speed"))
        && crate::rig::fields::animatable(kind, field.0)
        && crate::motion::animatable(kind, field.0)
        && !(kind == "camera" && crate::frame::STILL.contains(&field.0))
}

/// Fields that decide WHAT is drawn rather than where or how it is placed, by (item type, field): a counter's number.
/// In a motion-blurred frame every sub-frame reads them at the frame's own time (eval.rs `props_at`), so the content
/// stays sharp and only movement blurs, as in After Effects. Which picture shows (a drawing's frame, paint, grain, a
/// video's frame) follows the same rule in eval.rs. A new keyable field of that sort is listed here.
pub const CONTENT: &[(&str, &str)] = &[("text", "count")];

/// Whether `field` of an item of type `kind` decides what is drawn (CONTENT).
pub fn content(kind: &str, field: &str) -> bool {
    CONTENT.contains(&(kind, field))
}
