use blitz_dom::util::ToColorColor as _;
use style::color::AbsoluteColor;
pub(crate) use style::computed_values::filter::single_value::T as StyloFilter;

use anyrender::filters::{Filter, FilterEffect};

pub(crate) fn convert_filters(filters: &[StyloFilter]) -> Option<Filter> {
    if filters.is_empty() {
        return None;
    }

    Some(Filter::linear_list(
        filters.iter().filter_map(convert_single_filter),
    ))
}

/// The id in an element's `filter: url(#id)` (Rostrum proof patch). Stylo built for Servo cannot hold
/// a url() filter (its Url variant is uninhabited), so it is read from the element's inline style.
pub(crate) fn url_filter_id(node: &blitz_dom::Node) -> Option<String> {
    url_ref_id(node, "filter")
}

/// The id in an inline-style `<property>: url(#id)` (Rostrum proof patch; see url_filter_id).
pub(crate) fn url_ref_id(node: &blitz_dom::Node, property: &str) -> Option<String> {
    let style = node.attrs()?.iter().find(|a| &*a.name.local == "style")?.value.to_string();
    let at = style.match_indices(property).find(|(i, _)| *i == 0 || matches!(style.as_bytes()[i - 1], b';' | b' '))?.0;
    let rest = &style[at..];
    let rest = &rest[..rest.find(';').unwrap_or(rest.len())];
    let url = &rest[rest.find("url(")? + 4..];
    let id = url.trim_start_matches(|c| c == '"' || c == '\'' || c == ' ').strip_prefix('#')?;
    Some(id.chars().take_while(|c| c.is_alphanumeric() || *c == '_' || *c == '-').collect())
}

/// The value of `<property>` in an element's inline style (Rostrum patch, round 6): for properties
/// Stylo built for Servo does not parse (`-webkit-text-stroke`, `paint-order`). The name must stand
/// alone (`-webkit-text-stroke` does not match `-webkit-text-stroke-width`).
pub(crate) fn inline_style_value(node: &blitz_dom::Node, property: &str) -> Option<String> {
    let style: &str = &node.attrs()?.iter().find(|a| &*a.name.local == "style")?.value;
    if !style.contains(property) {
        return None;
    }
    style.split(';').rev().find_map(|decl| {
        let (name, value) = decl.split_once(':')?;
        name.trim().eq_ignore_ascii_case(property).then(|| value.trim().trim_end_matches("!important").trim().to_string())
    })
}

/// The Gaussian sigma of a CSS shadow blur radius (box-shadow, text-shadow), in device px, as Chromium
/// computes it (`BlurRadiusToStdDev`: 0.288675 r + 0.5), which the app's GUI preview is (Rostrum patch,
/// round 6; the radius itself was passed as sigma: shadows about twice as soft).
pub(crate) fn shadow_sigma(radius: f64) -> f64 {
    if radius > 0.0 { 0.288675 * radius + 0.5 } else { 0.0 }
}

pub(crate) fn convert_single_filter(filter: &StyloFilter) -> Option<FilterEffect> {
    Some(match filter {
        StyloFilter::Blur(radius) => FilterEffect::blur(radius.px()),
        StyloFilter::Brightness(amount) => FilterEffect::brightness(amount.0),
        StyloFilter::Contrast(amount) => FilterEffect::contrast(amount.0),
        StyloFilter::Grayscale(amount) => FilterEffect::grayscale(amount.0),
        StyloFilter::HueRotate(angle) => FilterEffect::hue_rotate(angle.radians()),
        StyloFilter::Invert(amount) => FilterEffect::invert(amount.0),
        StyloFilter::Opacity(amount) => FilterEffect::opacity(amount.0),
        StyloFilter::Saturate(amount) => FilterEffect::saturate(amount.0),
        StyloFilter::Sepia(amount) => FilterEffect::sepia(amount.0),
        StyloFilter::DropShadow(shadow) => FilterEffect::drop_shadow(
            shadow.horizontal.px(),
            shadow.vertical.px(),
            shadow.blur.px(),
            // TODO: pass in correct currentColor
            shadow
                .color
                .resolve_to_absolute(&AbsoluteColor::BLACK)
                .as_color_color(),
        ),
        StyloFilter::Url(_) => return None,
    })
}
