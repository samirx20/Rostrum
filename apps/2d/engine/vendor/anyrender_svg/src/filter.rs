// Copyright 2026 HireMyLens Media
// SPDX-License-Identifier: Apache-2.0 OR MIT

//! Rostrum patch (2D SVG filters): a usvg `<filter>` as an anyrender filter graph. usvg has already resolved its units,
//! the filter region, each primitive's subregion and its inputs into the filtered element's user space, which is the
//! space of the layer the filter is drawn in, so lengths pass through as they are. Each primitive runs in its own
//! `color-interpolation-filters` space (linearRGB unless sRGB), as browsers do.

use crate::util;
use anyrender::filters::color_transformation::ColorMatrix;
use anyrender::filters::component_transfer::{ComponentTransferFilter, GammaTransferFunction, LinearTransferFunction, TransferFunction};
use anyrender::filters::composite::{ArithmeticCompositeOperator, CompositeOperator};
use anyrender::filters::displacement::{ColorChannel, DisplacementMapFilter};
use anyrender::filters::interpolation::{FilterColorSpace, SpacedFilter};
use anyrender::filters::morphology::{MorphologyFilter, MorphologyOperator};
use anyrender::filters::turbulence::{TurbulenceFilter, TurbulenceType};
use anyrender::filters::{Filter, FilterEffect, FilterId, FilterInput, FilterInputs, FilterSource};
use kurbo::{Rect, Vec2};
use peniko::color::{AlphaColor, Srgb};
use std::collections::HashMap;
use usvg::filter::{self as fe, Input, Kind};

/// Keeps alpha, clears colour (SourceAlpha of any input).
const ALPHA_ONLY: [f32; 20] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0];

pub(crate) fn rect(r: usvg::NonZeroRect) -> Rect {
    Rect::new(r.left() as f64, r.top() as f64, r.right() as f64, r.bottom() as f64)
}

fn color(c: usvg::Color, opacity: usvg::Opacity) -> AlphaColor<Srgb> {
    AlphaColor::from_rgba8(c.red, c.green, c.blue, 255).multiply_alpha(opacity.get())
}

fn color_matrix(kind: &fe::ColorMatrixKind) -> ColorMatrix {
    match kind {
        fe::ColorMatrixKind::Matrix(v) if v.len() == 20 => {
            let mut m = [0f32; 20];
            m.copy_from_slice(v);
            ColorMatrix(m)
        }
        fe::ColorMatrixKind::Saturate(s) => {
            let s = s.get();
            ColorMatrix([
                0.213 + 0.787 * s, 0.715 - 0.715 * s, 0.072 - 0.072 * s, 0.0, 0.0,
                0.213 - 0.213 * s, 0.715 + 0.285 * s, 0.072 - 0.072 * s, 0.0, 0.0,
                0.213 - 0.213 * s, 0.715 - 0.715 * s, 0.072 + 0.928 * s, 0.0, 0.0,
                0.0, 0.0, 0.0, 1.0, 0.0,
            ])
        }
        fe::ColorMatrixKind::HueRotate(deg) => ColorMatrix::hue_rotate(deg.to_radians()),
        fe::ColorMatrixKind::LuminanceToAlpha => ColorMatrix([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2125, 0.7154, 0.0721, 0.0, 0.0]),
        fe::ColorMatrixKind::Matrix(_) => ColorMatrix([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]),
    }
}

fn transfer(f: &fe::TransferFunction) -> TransferFunction {
    match f {
        fe::TransferFunction::Table(t) if !t.is_empty() => TransferFunction::Table(t.iter().copied().collect()),
        fe::TransferFunction::Discrete(t) if !t.is_empty() => TransferFunction::Discrete(t.clone()),
        fe::TransferFunction::Linear { slope, intercept } => TransferFunction::Linear(LinearTransferFunction { slope: *slope, intercept: *intercept }),
        fe::TransferFunction::Gamma { amplitude, exponent, offset } => {
            TransferFunction::Gamma(GammaTransferFunction { amplitude: *amplitude, exponent: *exponent, offset: *offset })
        }
        _ => TransferFunction::Identity,
    }
}

fn channel(c: fe::ColorChannel) -> ColorChannel {
    match c {
        fe::ColorChannel::R => ColorChannel::Red,
        fe::ColorChannel::G => ColorChannel::Green,
        fe::ColorChannel::B => ColorChannel::Blue,
        fe::ColorChannel::A => ColorChannel::Alpha,
    }
}

/// The filter graph of `filter`, or `None` when it has no primitive that draws (then the element draws as it is).
/// Primitives this does not draw yet (lighting, feImage, feTile, feConvolveMatrix) pass their input through.
pub(crate) fn convert(filter: &fe::Filter) -> Option<Filter> {
    let mut g = SpacedFilter::new();
    let mut named: HashMap<&str, FilterId> = HashMap::new();
    let mut last: Option<FilterId> = None;
    for p in filter.primitives() {
        let space = match p.color_interpolation() {
            fe::ColorInterpolation::SRGB => FilterColorSpace::Srgb,
            fe::ColorInterpolation::LinearRGB => FilterColorSpace::LinearRgb,
        };
        let source = FilterInput::Source(FilterSource::SourceGraphic);
        let input = |i: &Input| match i {
            Input::SourceGraphic => source.clone(),
            Input::SourceAlpha => FilterInput::Source(FilterSource::SourceAlpha),
            Input::Reference(r) => named.get(r.as_str()).map(|&id| FilterInput::Result(id)).or(last.map(FilterInput::Result)).unwrap_or(source.clone()),
        };
        let one = |i: &Input| FilterInputs::single(input(i));
        let two = |a: &Input, b: &Input| FilterInputs::dual(input(a), input(b));
        let id = match p.kind() {
            Kind::Blend(b) => g.add(FilterEffect::Blend(util::to_mix(b.mode())), two(b.input1(), b.input2()), Some(space)),
            Kind::ColorMatrix(m) => g.add(FilterEffect::ColorMatrix(color_matrix(m.kind())), one(m.input()), Some(space)),
            Kind::ComponentTransfer(c) => g.add(
                FilterEffect::ComponentTransfer(ComponentTransferFilter {
                    red_function: transfer(c.func_r()),
                    green_function: transfer(c.func_g()),
                    blue_function: transfer(c.func_b()),
                    alpha_function: transfer(c.func_a()),
                }),
                one(c.input()),
                Some(space),
            ),
            Kind::Composite(c) => {
                let op = match c.operator() {
                    fe::CompositeOperator::Over => CompositeOperator::Over,
                    fe::CompositeOperator::In => CompositeOperator::In,
                    fe::CompositeOperator::Out => CompositeOperator::Out,
                    fe::CompositeOperator::Atop => CompositeOperator::Atop,
                    fe::CompositeOperator::Xor => CompositeOperator::Xor,
                    fe::CompositeOperator::Arithmetic { k1, k2, k3, k4 } => CompositeOperator::Arithmetic(ArithmeticCompositeOperator { k1, k2, k3, k4 }),
                };
                g.add(FilterEffect::Composite(op), two(c.input1(), c.input2()), Some(space))
            }
            Kind::DisplacementMap(d) => g.add(
                FilterEffect::DisplacementMap(DisplacementMapFilter { scale: d.scale(), x_channel: channel(d.x_channel_selector()), y_channel: channel(d.y_channel_selector()) }),
                two(d.input1(), d.input2()),
                Some(space),
            ),
            Kind::DropShadow(d) => {
                // feGaussianBlur of the input's alpha, feOffset, feFlood, feComposite in, merged under the input.
                let i = input(d.input());
                let alpha = g.add(FilterEffect::ColorMatrix(ColorMatrix(ALPHA_ONLY)), FilterInputs::single(i.clone()), Some(space));
                let blur = g.add(FilterEffect::blur_xy(d.std_dev_x().get(), d.std_dev_y().get()), FilterInputs::single(FilterInput::Result(alpha)), Some(space));
                let moved = g.add(FilterEffect::Offset(Vec2::new(d.dx() as f64, d.dy() as f64)), FilterInputs::single(FilterInput::Result(blur)), Some(space));
                let flood = g.add_source(FilterEffect::Flood(color(d.color(), d.opacity())), FilterColorSpace::Working);
                let shadow = g.add(FilterEffect::Composite(CompositeOperator::In), FilterInputs::dual(FilterInput::Result(flood), FilterInput::Result(moved)), Some(space));
                g.add(FilterEffect::Composite(CompositeOperator::Over), FilterInputs::dual(i, FilterInput::Result(shadow)), Some(space))
            }
            Kind::Flood(f) => g.add_source(FilterEffect::Flood(color(f.color(), f.opacity())), FilterColorSpace::Working),
            Kind::GaussianBlur(b) => g.add(FilterEffect::blur_xy(b.std_dev_x().get(), b.std_dev_y().get()), one(b.input()), Some(space)),
            Kind::Merge(m) => {
                // Each feMergeNode over the ones before it; no node: transparent.
                let mut acc: Option<FilterId> = None;
                for i in m.inputs() {
                    let top = input(i);
                    acc = Some(match acc {
                        None => g.add(FilterEffect::Offset(Vec2::ZERO), FilterInputs::single(top), Some(space)),
                        Some(below) => g.add(FilterEffect::Composite(CompositeOperator::Over), FilterInputs::dual(top, FilterInput::Result(below)), Some(space)),
                    });
                }
                match acc {
                    Some(id) => id,
                    None => g.add_source(FilterEffect::Flood(AlphaColor::TRANSPARENT), FilterColorSpace::Working),
                }
            }
            Kind::Morphology(m) => {
                let (rx, ry) = (m.radius_x().get(), m.radius_y().get());
                let operator = match m.operator() {
                    fe::MorphologyOperator::Erode => MorphologyOperator::Erode,
                    fe::MorphologyOperator::Dilate => MorphologyOperator::Dilate,
                };
                g.add(FilterEffect::Morphology(MorphologyFilter { operator, radius: rx, radius_y: (rx != ry).then_some(ry) }), one(m.input()), Some(space))
            }
            Kind::Offset(o) => g.add(FilterEffect::Offset(Vec2::new(o.dx() as f64, o.dy() as f64)), one(o.input()), Some(space)),
            Kind::Turbulence(t) => {
                let (fx, fy) = (t.base_frequency_x().get(), t.base_frequency_y().get());
                g.add_source(
                    FilterEffect::Turbulence(TurbulenceFilter {
                        base_frequency: fx,
                        base_frequency_y: (fx != fy).then_some(fy),
                        num_octaves: t.num_octaves(),
                        seed: t.seed() as u32,
                        turbulence_type: match t.kind() {
                            fe::TurbulenceKind::FractalNoise => TurbulenceType::FractalNoise,
                            fe::TurbulenceKind::Turbulence => TurbulenceType::Turbulence,
                        },
                    }),
                    space,
                )
            }
            Kind::ConvolveMatrix(c) => g.add(FilterEffect::Offset(Vec2::ZERO), one(c.input()), Some(space)),
            Kind::DiffuseLighting(l) => g.add(FilterEffect::Offset(Vec2::ZERO), one(l.input()), Some(space)),
            Kind::SpecularLighting(l) => g.add(FilterEffect::Offset(Vec2::ZERO), one(l.input()), Some(space)),
            Kind::Tile(t) => g.add(FilterEffect::Offset(Vec2::ZERO), one(t.input()), Some(space)),
            Kind::Image(_) => g.add_source(FilterEffect::Flood(AlphaColor::TRANSPARENT), FilterColorSpace::Working),
        };
        // The primitive's subregion (usvg defaults it to the filter region).
        g.graph.crops.push((id, rect(p.rect())));
        named.insert(p.result(), id);
        last = Some(id);
    }
    let out = last?;
    let mut graph = g.finish(out);
    graph.region = Some(rect(filter.rect()));
    Some(graph)
}
