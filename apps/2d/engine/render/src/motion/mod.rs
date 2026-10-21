//! Motion blur, smears and trails (apps/2d/MOTION.md). STUB written by the lead for the hooks; Team Hem member B replaces it.

use crate::scene::eval::Item;
use crate::scene::fields::Field;
use crate::scene::fields::Kind::Number;

/// The comp's shutter fields (motion blur).
pub const COMP: &[Field] = &[("shutter", Number), ("shutterSamples", Number)];

pub const TRAIL: &[Field] = &[("copies", Number), ("spacing", Number), ("fade", Number)];
pub const SMEAR: &[Field] = &[("amount", Number), ("max", Number)];

/// A motion effect's fields; None for any other type.
pub fn fields(kind: &str) -> Option<&'static [Field]> {
    match kind {
        "trail" => Some(TRAIL),
        "smear" => Some(SMEAR),
        _ => None,
    }
}

/// Whether keys may drive the field (true for every other type).
pub fn animatable(_kind: &str, _name: &str) -> bool {
    true
}

/// The smear's CSS transform for a layer at its time, if it has a smear that stretches it now.
pub fn smear_css(_it: &Item) -> Option<String> {
    None
}
