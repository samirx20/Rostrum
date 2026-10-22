//! Rostrum patch (H15): track mattes drawn by the painter itself, so any layer the renderer can draw can be a matte.
//!
//! An element with `data-track-matte="alpha | alphaInverted | luma | lumaInverted"` does not draw its children as
//! usual: its first element child is the matte, the rest the content. The content is drawn into an isolated layer;
//! the matte is then drawn as every element is (the same painting, no second drawing path) into a layer composited
//! `DestIn` (kept where the matte covers) or `DestOut` (inverted). A luma matte is drawn over opaque black and its
//! layer turned into coverage by luminance (`luminanceToAlpha`), so where the matte is transparent it reads as black.
//!
//! Rostrum patch (H29): `data-track-matte="atop"` is paint on an element: the first child (the paint) is drawn
//! `SrcAtop` over the rest (the element), so it shows only where the element itself is drawn, by the same structure.

use std::sync::Arc;

use anyrender::filters::color_transformation::ColorMatrix;
use anyrender::filters::{Filter, FilterEffect};
use anyrender::PaintScene;
use kurbo::{Affine, Rect};
use peniko::{BlendMode, Color, Compose, Fill, Mix};

use crate::particles::data_attr;
use crate::render::ElementCx;

const EVERYWHERE: Rect = Rect::new(-1e7, -1e7, 1e7, 1e7);
/// Just below 1, so a backend can't fold the isolation layer into a plain clip (render/mask.rs › ALMOST_OPAQUE).
const ALMOST_OPAQUE: f32 = 1.0 - f32::EPSILON;
const LUMINANCE_TO_ALPHA: [f32; 20] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2125, 0.7154, 0.0721, 0.0, 0.0];

impl ElementCx<'_, '_> {
    /// Draws the element's children through its track matte (true) when it has `data-track-matte`; false leaves
    /// it to draw its children.
    pub(crate) fn draw_track_matte(&self, scene: &mut impl PaintScene) -> bool {
        let Some(mode) = data_attr(self.node, "data-track-matte") else { return false };
        let tree = self.context.dom.as_ref().tree();
        let kids: Vec<_> = self.node.children.iter().copied().filter(|&id| tree[id].is_element()).collect();
        let Some((&matte, content)) = kids.split_first() else { return true };
        let (luma, inverted, atop) = (mode.starts_with("luma"), mode.ends_with("Inverted"), mode == "atop");

        scene.push_layer(Fill::NonZero, Mix::Normal, ALMOST_OPAQUE, Affine::IDENTITY, &EVERYWHERE, None, None);
        for &id in content {
            self.context.render_node_for(scene, id, self.transform, EVERYWHERE);
        }
        let compose = if atop { Compose::SrcAtop } else if inverted { Compose::DestOut } else { Compose::DestIn };
        let filter = luma.then(|| Arc::new(Filter::single(FilterEffect::ColorMatrix(ColorMatrix(LUMINANCE_TO_ALPHA)))));
        scene.push_layer(Fill::NonZero, BlendMode::new(Mix::Normal, compose), 1.0, Affine::IDENTITY, &EVERYWHERE, filter, None);
        if luma {
            scene.fill(Fill::NonZero, Affine::IDENTITY, Color::BLACK, None, &EVERYWHERE);
        }
        self.context.render_node_for(scene, matte, self.transform, EVERYWHERE);
        scene.pop_layer();
        scene.pop_layer();
        true
    }
}
