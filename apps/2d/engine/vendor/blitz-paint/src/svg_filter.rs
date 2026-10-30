//! `filter: url(#id)`: the referenced SVG `<filter>` element read into an anyrender filter graph
//! (Rostrum proof patch — upstream blitz-paint drops url() filters). Covers the primitives
//! Rostrum's looks use: feColorMatrix, feComponentTransfer, feComposite, feGaussianBlur,
//! feDisplacementMap, feMorphology, feFlood, feOffset, feImage, feMerge, feTurbulence. Inputs by
//! name (`in`, `in2`, `result`); lengths in user space (scaled with the painter's scale); feImage
//! covers its x / y / width / height in the element's bounding box.

use std::collections::HashMap;

use anyrender::filters::color_transformation::ColorMatrix;
use anyrender::filters::component_transfer::{ComponentTransferFilter, GammaTransferFunction, LinearTransferFunction, TransferFunction};
use anyrender::filters::composite::{ArithmeticCompositeOperator, CompositeOperator};
use anyrender::filters::displacement::{ColorChannel, DisplacementMapFilter};
use anyrender::filters::morphology::{MorphologyFilter, MorphologyOperator};
use anyrender::filters::turbulence::{TurbulenceFilter, TurbulenceType};
use anyrender::filters::interpolation::{FilterColorSpace, SpacedFilter};
use anyrender::filters::{images, ExternalImageSource, Filter, FilterEffect, FilterId, FilterInput, FilterInputs, FilterSource, RuntimeShaderFilter};
use blitz_dom::{BaseDocument, Node};
use kurbo::{Rect, Vec2};
use peniko::color::{AlphaColor, Srgb};

fn attr<'a>(n: &'a Node, name: &str) -> Option<&'a str> {
    n.attrs()?.iter().find(|a| &*a.name.local == name).map(|a| &*a.value)
}

fn num(n: &Node, name: &str, default: f32) -> f32 {
    attr(n, name).and_then(|v| v.split(|c: char| c == ',' || c.is_whitespace()).find(|s| !s.is_empty())?.parse().ok()).unwrap_or(default)
}

/// The second of a number pair (`stdDeviation="x y"`), else the first.
fn num_y(n: &Node, name: &str, default: f32) -> f32 {
    attr(n, name).map(numbers).and_then(|v| v.get(1).or(v.first()).copied()).unwrap_or(default)
}

/// An feBlend `mode` (Compositing and Blending's names).
fn blend_mode(v: Option<&str>) -> peniko::Mix {
    use peniko::Mix;
    match v.unwrap_or("normal") {
        "multiply" => Mix::Multiply,
        "screen" => Mix::Screen,
        "overlay" => Mix::Overlay,
        "darken" => Mix::Darken,
        "lighten" => Mix::Lighten,
        "color-dodge" => Mix::ColorDodge,
        "color-burn" => Mix::ColorBurn,
        "hard-light" => Mix::HardLight,
        "soft-light" => Mix::SoftLight,
        "difference" => Mix::Difference,
        "exclusion" => Mix::Exclusion,
        "hue" => Mix::Hue,
        "saturation" => Mix::Saturation,
        "color" => Mix::Color,
        "luminosity" => Mix::Luminosity,
        _ => Mix::Normal,
    }
}

fn numbers(v: &str) -> Vec<f32> {
    v.split(|c: char| c == ',' || c.is_whitespace()).filter(|s| !s.is_empty()).filter_map(|s| s.parse().ok()).collect()
}

fn local(n: &Node) -> String {
    n.element_data().map(|e| e.name.local.to_string()).unwrap_or_default()
}

/// A length that may be a percentage of `of`.
fn length(v: Option<&str>, of: f64, default: f64) -> f64 {
    match v {
        Some(s) if s.trim_end().ends_with('%') => s.trim_end().trim_end_matches('%').parse::<f64>().map(|p| p / 100.0 * of).unwrap_or(default),
        Some(s) => s.trim().parse().unwrap_or(default),
        None => default,
    }
}

/// A filter colour (`flood-color`) times its opacity: any CSS colour, its own alpha kept (Rostrum patch,
/// round 6: only hex / rgb() were read and an rgba() alpha was dropped). Not a colour: black, as SVG.
fn color(v: Option<&str>, opacity: f32) -> AlphaColor<Srgb> {
    let c = v.and_then(|s| color::parse_color(s.trim()).ok()).map(|c| c.to_alpha_color::<Srgb>()).unwrap_or(AlphaColor::from_rgba8(0, 0, 0, 255));
    c.multiply_alpha(opacity.clamp(0.0, 1.0))
}

fn color_matrix(n: &Node) -> ColorMatrix {
    let values = attr(n, "values").map(numbers).unwrap_or_default();
    match attr(n, "type").unwrap_or("matrix") {
        "saturate" => {
            let s = values.first().copied().unwrap_or(1.0);
            ColorMatrix([
                0.213 + 0.787 * s, 0.715 - 0.715 * s, 0.072 - 0.072 * s, 0.0, 0.0,
                0.213 - 0.213 * s, 0.715 + 0.285 * s, 0.072 - 0.072 * s, 0.0, 0.0,
                0.213 - 0.213 * s, 0.715 - 0.715 * s, 0.072 + 0.928 * s, 0.0, 0.0,
                0.0, 0.0, 0.0, 1.0, 0.0,
            ])
        }
        "hueRotate" => ColorMatrix::hue_rotate(values.first().copied().unwrap_or(0.0).to_radians()),
        "luminanceToAlpha" => ColorMatrix([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2125, 0.7154, 0.0721, 0.0, 0.0]),
        _ if values.len() == 20 => {
            // SVG's offsets are in 0..1; the matrix applies to 0..1 colours as well.
            let mut m = [0f32; 20];
            m.copy_from_slice(&values);
            ColorMatrix(m)
        }
        _ => ColorMatrix([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]),
    }
}

fn transfer(n: &Node) -> TransferFunction {
    let table = || attr(n, "tableValues").map(numbers).unwrap_or_default();
    match attr(n, "type").unwrap_or("identity") {
        "table" if !table().is_empty() => TransferFunction::Table(table().into_iter().collect()),
        "discrete" if !table().is_empty() => TransferFunction::Discrete(table()),
        "linear" => TransferFunction::Linear(LinearTransferFunction { slope: num(n, "slope", 1.0), intercept: num(n, "intercept", 0.0) }),
        "gamma" => TransferFunction::Gamma(GammaTransferFunction { amplitude: num(n, "amplitude", 1.0), exponent: num(n, "exponent", 1.0), offset: num(n, "offset", 0.0) }),
        _ => TransferFunction::Identity,
    }
}

fn channel(v: Option<&str>) -> ColorChannel {
    match v.unwrap_or("A") {
        "R" => ColorChannel::Red,
        "G" => ColorChannel::Green,
        "B" => ColorChannel::Blue,
        _ => ColorChannel::Alpha,
    }
}

/// An feImage's image decoded and registered (by a hash of the URL, so each image decodes once): a data:
/// URL, or (Rostrum) a local file — `/__local_asset?p=<path>` or file: — resolved against the page.
fn image_id(dom: &BaseDocument, href: &str) -> Option<u32> {
    use std::hash::{Hash, Hasher};
    let mut h = std::collections::hash_map::DefaultHasher::new();
    href.hash(&mut h);
    let id = h.finish() as u32;
    if images::contains(id) {
        return Some(id);
    }
    let bytes = if let Some(rest) = href.strip_prefix("data:") {
        let (meta, data) = rest.split_once(',')?;
        if !meta.ends_with(";base64") {
            return None;
        }
        use base64::Engine as _;
        base64::engine::general_purpose::STANDARD.decode(data.trim()).ok()?
    } else {
        let url = dom.base_url().join(href).ok()?;
        // Rostrum patch (comp, Wave 2): a colour-tagged picture (`&color=<input>`) decodes like an `<img>` with the same
        // query, through the renderer's loader (its colour input into the working space, half float).
        if url.query_pairs().any(|(k, _)| k == "color") {
            images::loader()?(url.as_str()).ok()?
        } else {
            let path = match url.scheme() {
                "file" => url.to_file_path().ok()?,
                _ if url.path() == "/__local_asset" => url.query_pairs().find(|(k, _)| k == "p")?.1.into_owned().into(),
                _ => return None,
            };
            std::fs::read(path).ok()?
        }
    };
    // Rostrum patch: an RHALF file (blitz-dom net.rs: half-float RGBA) stays half float (the one grade's LUT tables).
    if bytes.starts_with(blitz_dom::net::RHALF_MAGIC) && bytes.len() >= 16 {
        let word = |i: usize| u32::from_le_bytes([bytes[i], bytes[i + 1], bytes[i + 2], bytes[i + 3]]);
        images::register(id, images::FilterImage { width: word(8), height: word(12), rgba: bytes[16..].to_vec(), half: true });
        return Some(id);
    }
    if bytes.starts_with(blitz_dom::net::RGBA8_MAGIC) && bytes.len() >= 16 {
        let word = |i: usize| u32::from_le_bytes([bytes[i], bytes[i + 1], bytes[i + 2], bytes[i + 3]]);
        images::register(id, images::FilterImage { width: word(8), height: word(12), rgba: bytes[16..].to_vec(), half: false });
        return Some(id);
    }
    let rgba = image::load_from_memory(&bytes).ok()?.to_rgba8();
    images::register(id, images::FilterImage { width: rgba.width(), height: rgba.height(), rgba: rgba.into_raw(), half: false });
    Some(id)
}

/// The filter graph of `<filter id>` for an element whose border box is `bbox` (painter units; `scale`: px → painter units).
/// Rostrum patch (X6 ROI): `data-roi="x0 y0 x1 y1"` (fractions of the box; src/engine/comp/compRoi.ts): the primitive's
/// region of interest, its result cropped to it.
fn roi(graph: &mut Filter, n: &Node, fid: FilterId, bbox: Rect) {
    let Some(v) = attr(n, "data-roi") else { return };
    let f = numbers(v);
    if f.len() == 4 {
        let (w, h) = (bbox.width(), bbox.height());
        graph.crops.push((fid, Rect::new(bbox.x0 + f[0] as f64 * w, bbox.y0 + f[1] as f64 * h, bbox.x0 + f[2] as f64 * w, bbox.y0 + f[3] as f64 * h)));
    }
}

/// `view`: the visible frame in the element's own px, the space of `bbox` (passed to shader primitives as `view`).
pub(crate) fn svg_filter(dom: &BaseDocument, id: &str, bbox: Rect, view: Rect, scale: f64) -> Option<Filter> {
    let filter = dom.get_node(dom.get_element_by_id(id)?)?;
    if local(filter) != "filter" {
        return None;
    }
    // Rostrum patch (2D SVG filters): each primitive in its `color-interpolation-filters` space (its own, else the
    // filter's; linearRGB unless sRGB, as browsers), its inputs re-encoded once and the output back to the working space.
    let mut g = SpacedFilter::new();
    let filter_space = attr(filter, "color-interpolation-filters");
    let mut graph = Filter::empty();
    // Rostrum patch: a declared filter region (objectBoundingBox units: fractions or percentages of the box) crops
    // every primitive; a filter without one stays unbounded.
    if attr(filter, "width").is_some() || attr(filter, "height").is_some() {
        let frac = |key: &str, of: f64, default: f64| match attr(filter, key) {
            Some(s) if s.trim_end().ends_with('%') => s.trim_end().trim_end_matches('%').trim().parse::<f64>().map(|p| p / 100.0).unwrap_or(default) * of,
            Some(s) => s.trim().parse::<f64>().unwrap_or(default) * of,
            None => default * of,
        };
        let (x, y) = (bbox.x0 + frac("x", bbox.width(), -0.1), bbox.y0 + frac("y", bbox.height(), -0.1));
        graph.region = Some(Rect::new(x, y, x + frac("width", bbox.width(), 1.2), y + frac("height", bbox.height(), 1.2)));
    }
    let mut named: HashMap<String, FilterId> = HashMap::new();
    let mut last: Option<FilterId> = None;
    let s = scale as f32;
    for &child in filter.children.iter() {
        let Some(n) = dom.get_node(child) else { continue };
        let name = local(n);
        if !name.starts_with("fe") {
            continue;
        }
        let input = |key: &str| -> Option<FilterInput> {
            match attr(n, key) {
                Some("SourceGraphic") => Some(FilterInput::Source(FilterSource::SourceGraphic)),
                Some("SourceAlpha") => Some(FilterInput::Source(FilterSource::SourceAlpha)),
                Some(r) => named.get(r).map(|&i| FilterInput::Result(i)),
                None => last.map(FilterInput::Result).or(Some(FilterInput::Source(FilterSource::SourceGraphic))),
            }
        };
        let one = FilterInputs { primary: input("in"), secondary: None };
        let two = FilterInputs { primary: input("in"), secondary: input("in2") };
        let space = match attr(n, "color-interpolation-filters").or(filter_space).map(str::trim) {
            Some("sRGB") | Some("auto") => FilterColorSpace::Srgb,
            _ => FilterColorSpace::LinearRgb,
        };
        // `None`: the primitive reads and writes the working space as it is; `Some(Working)`: it makes values there.
        let mut made_in = Some(space);
        let (effect, inputs) = match name.as_str() {
            "feColorMatrix" => (FilterEffect::ColorMatrix(color_matrix(n)), one),
            "feComponentTransfer" => {
                let mut ct = ComponentTransferFilter { red_function: TransferFunction::Identity, green_function: TransferFunction::Identity, blue_function: TransferFunction::Identity, alpha_function: TransferFunction::Identity };
                for &f in n.children.iter() {
                    let Some(fnode) = dom.get_node(f) else { continue };
                    match local(fnode).as_str() {
                        "feFuncR" => ct.red_function = transfer(fnode),
                        "feFuncG" => ct.green_function = transfer(fnode),
                        "feFuncB" => ct.blue_function = transfer(fnode),
                        "feFuncA" => ct.alpha_function = transfer(fnode),
                        _ => {}
                    }
                }
                (FilterEffect::ComponentTransfer(ct), one)
            }
            "feComposite" => {
                let op = match attr(n, "operator").unwrap_or("over") {
                    "in" => CompositeOperator::In,
                    "out" => CompositeOperator::Out,
                    "atop" => CompositeOperator::Atop,
                    "xor" => CompositeOperator::Xor,
                    "arithmetic" => CompositeOperator::Arithmetic(ArithmeticCompositeOperator { k1: num(n, "k1", 0.0), k2: num(n, "k2", 0.0), k3: num(n, "k3", 0.0), k4: num(n, "k4", 0.0) }),
                    _ => CompositeOperator::Over,
                };
                (FilterEffect::Composite(op), two)
            }
            "feGaussianBlur" => (FilterEffect::blur_xy(num(n, "stdDeviation", 0.0) * s, num_y(n, "stdDeviation", 0.0) * s), one),
            "feBlend" => (FilterEffect::Blend(blend_mode(attr(n, "mode"))), two),
            "feDropShadow" => {
                // feGaussianBlur of the input's alpha, feOffset, feFlood, feComposite in, merged under the input.
                let i = one.primary.unwrap_or(FilterInput::Source(FilterSource::SourceGraphic));
                let alpha_only = ColorMatrix([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]);
                let a = g.add(FilterEffect::ColorMatrix(alpha_only), FilterInputs::single(i.clone()), Some(space));
                let (sx, sy) = (num(n, "stdDeviation", 2.0) * s, num_y(n, "stdDeviation", 2.0) * s);
                let b = g.add(FilterEffect::blur_xy(sx, sy), FilterInputs::single(FilterInput::Result(a)), Some(space));
                let o = g.add(FilterEffect::Offset(Vec2::new((num(n, "dx", 2.0) * s) as f64, (num(n, "dy", 2.0) * s) as f64)), FilterInputs::single(FilterInput::Result(b)), Some(space));
                let f = g.add_source(FilterEffect::Flood(color(attr(n, "flood-color"), num(n, "flood-opacity", 1.0))), FilterColorSpace::Working);
                let sh = g.add(FilterEffect::Composite(CompositeOperator::In), FilterInputs::dual(FilterInput::Result(f), FilterInput::Result(o)), Some(space));
                (FilterEffect::Composite(CompositeOperator::Over), FilterInputs::dual(i, FilterInput::Result(sh)))
            }
            "feDisplacementMap" => (
                FilterEffect::DisplacementMap(DisplacementMapFilter { scale: num(n, "scale", 0.0) * s, x_channel: channel(attr(n, "xChannelSelector")), y_channel: channel(attr(n, "yChannelSelector")) }),
                two,
            ),
            "feMorphology" => (
                FilterEffect::Morphology(MorphologyFilter { operator: if attr(n, "operator") == Some("dilate") { MorphologyOperator::Dilate } else { MorphologyOperator::Erode }, radius: num(n, "radius", 0.0) * s, radius_y: None }),
                one,
            ),
            "feFlood" => {
                made_in = Some(FilterColorSpace::Working);
                (FilterEffect::Flood(color(attr(n, "flood-color"), num(n, "flood-opacity", 1.0))), FilterInputs::NONE)
            }
            "feOffset" => (FilterEffect::Offset(Vec2::new((num(n, "dx", 0.0) * s) as f64, (num(n, "dy", 0.0) * s) as f64)), one),
            "feTurbulence" => (
                FilterEffect::Turbulence(TurbulenceFilter {
                    base_frequency: num(n, "baseFrequency", 0.0) / s,
                    base_frequency_y: Some(num_y(n, "baseFrequency", 0.0) / s).filter(|&y| y != num(n, "baseFrequency", 0.0) / s),
                    num_octaves: num(n, "numOctaves", 1.0) as u32,
                    seed: num(n, "seed", 0.0) as u32,
                    turbulence_type: if attr(n, "type") == Some("fractalNoise") { TurbulenceType::FractalNoise } else { TurbulenceType::Turbulence },
                }),
                FilterInputs::NONE,
            ),
            "feImage" => {
                // Rostrum patch (round 6): an image that does not load fails the frame (it was skipped silently).
                let href = attr(n, "href").or(attr(n, "xlink:href")).unwrap_or("");
                let Some(image) = image_id(dom, href) else {
                    let shown: String = href.chars().take(120).collect();
                    anyrender::filters::shader_errors::push(format!("the filter image \"{shown}\" (feImage in #{id}) could not be read or decoded"));
                    continue;
                };
                let img = images::get(image)?;
                // x / y / width / height in the element's box (objectBoundingBox percentages, or user-space px).
                let (x, y) = (bbox.x0 + length(attr(n, "x"), bbox.width(), 0.0) * if attr(n, "x").is_some_and(|v| v.ends_with('%')) { 1.0 } else { scale }, bbox.y0 + length(attr(n, "y"), bbox.height(), 0.0) * if attr(n, "y").is_some_and(|v| v.ends_with('%')) { 1.0 } else { scale });
                let w = length(attr(n, "width"), bbox.width(), bbox.width());
                let h = length(attr(n, "height"), bbox.height(), bbox.height());
                let t = [(w / img.width as f64) as f32, 0.0, 0.0, (h / img.height as f64) as f32, x as f32, y as f32];
                made_in = None;
                (FilterEffect::Image(ExternalImageSource { image_id: image, transform: Some(t) }), FilterInputs::NONE)
            }
            // Rostrum patch (round 5): a GPU shader primitive (Motion's raster effects, src/engine/effects/sksl.ts).
            // Its SkSL is the element's text; `uniforms` = "name v v …;*name v" (`*`: px, scaled like lengths);
            // the layer's box is passed as `box` (x, y, w, h), the visible frame in the same space as `view`.
            "feshader" => {
                let mut uniforms: Vec<(String, Vec<f32>)> = vec![
                    ("box".into(), vec![bbox.x0 as f32, bbox.y0 as f32, bbox.width() as f32, bbox.height() as f32]),
                    ("view".into(), vec![view.x0 as f32, view.y0 as f32, view.width() as f32, view.height() as f32]),
                ];
                for entry in attr(n, "uniforms").unwrap_or("").split(';').filter(|e| !e.trim().is_empty()) {
                    let mut parts = entry.split_whitespace();
                    let Some(name) = parts.next() else { continue };
                    let (name, k) = match name.strip_prefix('*') { Some(n) => (n, s), None => (name, 1.0) };
                    uniforms.push((name.to_string(), parts.filter_map(|v| v.parse::<f32>().ok()).map(|v| v * k).collect()));
                }
                let program: std::sync::Arc<str> = format!("// rostrum effect: {}
{}", attr(n, "effect").unwrap_or("?"), n.text_content()).into();
                // Rostrum patch (round 7): `images="name href;…"` — child images (a LUT), each loaded like an
                // feImage; one that does not load fails the frame.
                let mut child_images = vec![];
                for entry in attr(n, "images").unwrap_or("").split(';').filter(|e| !e.trim().is_empty()) {
                    let (name, href) = entry.trim().split_once(' ').unwrap_or((entry.trim(), ""));
                    match image_id(dom, href.trim()) {
                        Some(img) => child_images.push((name.to_string(), img)),
                        None => anyrender::filters::shader_errors::push(format!("the {} effect's image \"{}\" could not be read or decoded", attr(n, "effect").unwrap_or("?"), href.chars().take(120).collect::<String>())),
                    }
                }
                made_in = None;
                (FilterEffect::RuntimeShader(RuntimeShaderFilter { program, uniforms, sample_radius: num(n, "radius", 0.0) * s, grow: num(n, "grow", 0.0) * s, images: child_images }), if attr(n, "in2").is_some() { two } else { one })
            }
            "feMerge" => {
                // Each feMergeNode over the ones before it: a chain of "over" composites.
                let mut acc: Option<FilterInput> = None;
                for &m in n.children.iter() {
                    let Some(mn) = dom.get_node(m) else { continue };
                    if local(mn) != "feMergeNode" {
                        continue;
                    }
                    let src = match attr(mn, "in") {
                        Some("SourceGraphic") | None => Some(FilterInput::Source(FilterSource::SourceGraphic)),
                        Some("SourceAlpha") => Some(FilterInput::Source(FilterSource::SourceAlpha)),
                        Some(r) => named.get(r).map(|&i| FilterInput::Result(i)),
                    };
                    acc = Some(match acc {
                        None => src.unwrap_or(FilterInput::Source(FilterSource::SourceGraphic)),
                        Some(below) => FilterInput::Result(g.add(FilterEffect::Composite(CompositeOperator::Over), FilterInputs { primary: src, secondary: Some(below) }, Some(space))),
                    });
                }
                // One node: the node itself, re-encoded into the merge's space.
                let id = match acc {
                    Some(FilterInput::Result(id)) => id,
                    Some(single) => g.add(FilterEffect::Offset(Vec2::ZERO), FilterInputs::single(single), Some(space)),
                    None => continue,
                };
                roi(&mut graph, n, id, bbox);
                if let Some(r) = attr(n, "result") {
                    named.insert(r.to_string(), id);
                }
                last = Some(id);
                continue;
            }
            _ => continue,
        };
        let fid = match (made_in, inputs == FilterInputs::NONE) {
            (Some(space), true) => g.add_source(effect, space),
            (made_in, _) => g.add(effect, inputs, made_in),
        };
        roi(&mut graph, n, fid, bbox);
        if let Some(r) = attr(n, "result") {
            named.insert(r.to_string(), fid);
        }
        last = Some(fid);
    }
    // The primitives' graph, with the region and crops gathered on `graph`.
    let out = last?;
    let region = graph.region;
    let crops = std::mem::take(&mut graph.crops);
    graph = g.finish(out);
    graph.region = region;
    graph.crops = crops;
    // Rostrum patch (X6): `data-tap="<result> <file>|…"`: buffers the renderer writes to the comp's node cache (scene.rs).
    for entry in attr(filter, "data-tap").unwrap_or("").split('|').filter(|e| !e.trim().is_empty()) {
        if let Some((name, file)) = entry.trim().split_once(' ') {
            if let Some(&fid) = named.get(name) {
                graph.taps.push((fid, file.trim().to_string()));
            }
        }
    }
    Some(graph)
}
