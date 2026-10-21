//! Rostrum patch: CSS `mix-blend-mode` and isolation. Blitz painted every element with `Mix::Normal`.
//! An element with a blend mode is drawn into its own layer that composites onto what is behind it with
//! that mode; "behind it" is its stacking context, as in browsers: a stacking context (transform, opacity,
//! filter, clip-path, `isolation: isolate`, a blend mode of its own) with a blending element inside is an
//! isolated group, so the blend never reaches past it.
use blitz_dom::{BaseDocument, Node};
use peniko::{BlendMode, Compose, Mix};
use style::computed_values::isolation::T as Isolation;
use style::computed_values::mix_blend_mode::T as MixBlendMode;
use style::properties::ComputedValues;

/// The element's `mix-blend-mode` as a layer blend.
pub(crate) fn css_blend(styles: &ComputedValues) -> BlendMode {
    let mix = match styles.get_effects().mix_blend_mode {
        MixBlendMode::Normal => Mix::Normal,
        MixBlendMode::Multiply => Mix::Multiply,
        MixBlendMode::Screen => Mix::Screen,
        MixBlendMode::Overlay => Mix::Overlay,
        MixBlendMode::Darken => Mix::Darken,
        MixBlendMode::Lighten => Mix::Lighten,
        MixBlendMode::ColorDodge => Mix::ColorDodge,
        MixBlendMode::ColorBurn => Mix::ColorBurn,
        MixBlendMode::HardLight => Mix::HardLight,
        MixBlendMode::SoftLight => Mix::SoftLight,
        MixBlendMode::Difference => Mix::Difference,
        MixBlendMode::Exclusion => Mix::Exclusion,
        MixBlendMode::Hue => Mix::Hue,
        MixBlendMode::Saturation => Mix::Saturation,
        MixBlendMode::Color => Mix::Color,
        MixBlendMode::Luminosity => Mix::Luminosity,
        MixBlendMode::PlusLighter => return BlendMode::new(Mix::Normal, Compose::Plus),
    };
    BlendMode::new(mix, Compose::SrcOver)
}

fn blends(styles: &ComputedValues) -> bool {
    styles.get_effects().mix_blend_mode != MixBlendMode::Normal
}

/// Whether the element starts a stacking context (the cases Rostrum's stages produce).
fn stacking_context(styles: &ComputedValues) -> bool {
    styles.guarantees_stacking_context() || styles.get_box().has_transform_or_perspective() || !styles.get_effects().filter.0.is_empty()
}

/// Whether the element is an isolated group for blending: `isolation: isolate`, or a stacking context with
/// an element inside that blends (not counting ones inside a nested stacking context, which isolates them).
pub(crate) fn isolates(doc: &BaseDocument, node: &Node, styles: &ComputedValues) -> bool {
    if styles.get_box().isolation == Isolation::Isolate {
        return true;
    }
    if !stacking_context(styles) {
        return false;
    }
    fn inside(doc: &BaseDocument, node: &Node) -> bool {
        node.children.iter().any(|&id| {
            let child = &doc.tree()[id];
            match child.primary_styles() {
                Some(s) if blends(&s) => true,
                Some(s) if stacking_context(&s) => false,
                _ => inside(doc, child),
            }
        })
    }
    inside(doc, node)
}
