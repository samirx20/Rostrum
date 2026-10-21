//! The fields of a rig's parts (RIG.md › The document), names and kinds as `rostrum2d/rig/fields.py` has them;
//! scene/fields.rs hands the `bone`, `ik` and `bind` types here, and scene/tests.rs checks them against Python.
//! A `rig` layer itself has a group's fields (w, h, clip) and the transform.

use crate::scene::fields::Field;
use crate::scene::fields::Kind::{Choice, Number, Text};

pub const BONE: &[Field] = &[
    ("parent", Text), ("rotation", Number), ("scale", Number), ("moveX", Number), ("moveY", Number),
    ("x", Number), ("y", Number), ("angle", Number), ("length", Number),
];
pub const IK: &[Field] = &[
    ("bone", Text), ("mode", Choice(&["ik", "fk"])), ("targetX", Number), ("targetY", Number), ("mix", Number),
    ("bend", Choice(&["clockwise", "counterclockwise"])), ("pin", Number),
];
pub const BIND: &[Field] = &[("layer", Text), ("bone", Text), ("bone2", Text), ("grid", Number), ("soft", Number)];

/// A rig part's fields; None for any other type.
pub fn of(kind: &str) -> Option<&'static [Field]> {
    match kind {
        "bone" => Some(BONE),
        "ik" => Some(IK),
        "bind" => Some(BIND),
        _ => None,
    }
}

/// Whether keys may drive the field: a bone's pose and an ik's mix, target and pin; the rest describe the rig at
/// rest. True for every other type (scene/fields.rs decides those).
pub fn animatable(kind: &str, name: &str) -> bool {
    match kind {
        "bone" => matches!(name, "rotation" | "scale" | "moveX" | "moveY"),
        "ik" => matches!(name, "mix" | "targetX" | "targetY" | "pin"),
        "bind" => false,
        _ => true,
    }
}
