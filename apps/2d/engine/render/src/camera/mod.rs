//! The 2D camera (apps/2d/CAMERA.md). STUB written by the lead for the hooks; Team Hem member A replaces it.

use crate::scene::eval::Item;
use crate::scene::fields::Field;
use crate::scene::fields::Kind::Number;

pub const FIELDS: &[Field] = &[("x", Number), ("y", Number), ("zoom", Number), ("rotation", Number), ("start", Number), ("end", Number)];

/// The camera showing in a comp at its time (or none: every layer drawn as placed).
pub struct View;

impl View {
    pub fn of(_comp: &Item) -> View {
        View
    }

    /// One top-level layer's markup, seen through the camera by its depth (or locked to the screen).
    pub fn place(&self, _layer: &Item, markup: String) -> String {
        markup
    }
}
