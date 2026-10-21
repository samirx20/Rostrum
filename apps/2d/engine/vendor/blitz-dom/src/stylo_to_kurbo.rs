use euclid::default::Rect;
use kurbo::{Affine, Vec2};
use style::{
    properties::generated::style_structs::Box as BoxStyleStruct,
    values::{
        computed::{CSSPixelLength, Rotate},
        generics::transform::{Scale, Translate},
    },
};

// 6. Current Transformation Matrix
//
// The transformation matrix is computed from the transform, transform-origin, translate, rotate, scale, and offset properties as follows:
//
//   - Start with the identity matrix.
//   - Translate by the computed X, Y, and Z values of transform-origin.
//   - Translate by the computed X, Y, and Z values of translate.
//   - Rotate by the computed <angle> about the specified axis of rotate.
//   - Scale by the computed X, Y, and Z values of scale.
//   - Translate and rotate by the transform specified by offset.
//   - Multiply by each of the transform functions in transform from left to right.
//   - Translate by the negated computed X, Y and Z values of transform-origin.
//
// <https://drafts.csswg.org/css-transforms-2/#ctm>
/// A 4x4 product (row-major, column vectors).
pub fn mul4(a: &[f64; 16], b: &[f64; 16]) -> [f64; 16] {
    let mut r = [0.0; 16];
    for i in 0..4 {
        for j in 0..4 {
            r[i * 4 + j] = (0..4).map(|k| a[i * 4 + k] * b[k * 4 + j]).sum();
        }
    }
    r
}

/// Rostrum proof patch: the element's `transform` as a 4x4 matrix (row-major, column vectors) with its
/// transform-origin applied, when it is not 2D (perspective, rotateX / rotateY …); None when it is 2D
/// (then resolve_2d_transform carries it). Outside a 3D rendering context it is a painting effect.
pub fn resolve_3d_transform(box_styles: &BoxStyleStruct, reference_box: Rect<CSSPixelLength>) -> Option<[f64; 16]> {
    if box_styles.transform.0.is_empty() {
        return None;
    }
    let (t, _) = box_styles.transform.to_transform_3d_matrix(Some(&reference_box)).ok()?;
    if t.is_2d() {
        return None;
    }
    // euclid applies matrices to row vectors (p * M): transpose for column vectors.
    let m = [t.m11, t.m21, t.m31, t.m41, t.m12, t.m22, t.m32, t.m42, t.m13, t.m23, t.m33, t.m43, t.m14, t.m24, t.m34, t.m44].map(|v| v as f64);
    let o = &box_styles.transform_origin;
    let (ox, oy) = (o.horizontal.resolve(reference_box.width()).px() as f64, o.vertical.resolve(reference_box.height()).px() as f64);
    let tr = |x: f64, y: f64| [1.0, 0.0, 0.0, x, 0.0, 1.0, 0.0, y, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0];
    Some(mul4(&mul4(&tr(ox, oy), &m), &tr(-ox, -oy)))
}

pub fn resolve_2d_transform(
    box_styles: &BoxStyleStruct,
    reference_box: Rect<CSSPixelLength>,
) -> Option<Affine> {
    let translate = match &box_styles.translate {
        Translate::None => None,
        Translate::Translate(x, y, _z) => Some(Vec2 {
            x: x.resolve(reference_box.width()).px() as f64,
            y: y.resolve(reference_box.height()).px() as f64,
        }),
    };

    let rotate = match &box_styles.rotate {
        Rotate::None => None,
        Rotate::Rotate(angle) => Some(angle.radians64()),
        // A rotation about the z axis stays in the plane; the sign of the
        // axis component decides the direction, its magnitude cancels out.
        Rotate::Rotate3D(x, y, z, angle) if *x == 0.0 && *y == 0.0 && *z != 0.0 => {
            Some(angle.radians64() * z.signum() as f64)
        }
        // TODO: support 3D transforms
        Rotate::Rotate3D(_, _, _, _) => None,
    };

    let scale_transform = match &box_styles.scale {
        Scale::None => None,
        Scale::Scale(x, y, _z) => Some(Vec2 {
            x: *x as f64,
            y: *y as f64,
        }),
    };

    let transform = if box_styles.transform.0.is_empty() {
        None
    } else {
        box_styles
            .transform
            .to_transform_3d_matrix(Some(&reference_box))
            .ok()
            // The `has_3d` flag means a 3d function appeared in the list, not that the
            // matrix needs 3d: `translate3d(x, y, 0)` sets it while resolving to a
            // plain 2d translation.
            //
            // TODO: support 3D transforms. Outside a 3d rendering context the spec
            // still applies the transform as a painting effect -- its own example
            // paints `rotateY(50deg)` narrower -- so dropping one is wrong. `is_2d()`
            // is closer than the flag, not the rule.
            // See: https://drafts.csswg.org/css-transforms-2/#3d-transform-rendering
            .filter(|(t, _has_3d)| t.is_2d())
            .map(|(t, _)| {
                // See: https://drafts.csswg.org/css-transforms-2/#two-dimensional-subset
                // And https://docs.rs/kurbo/latest/kurbo/struct.Affine.html#method.new
                Affine::new([t.m11, t.m12, t.m21, t.m22, t.m41, t.m42].map(|v| v as f64))
            })
    };

    // TODO: support the "offset" property
    // <https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/offset>

    if translate.is_none() && rotate.is_none() && scale_transform.is_none() && transform.is_none() {
        return None;
    }

    // Apply the transform origin by:
    //   - Translating by the origin offset
    //   - Applying our transform
    //   - Translating by the inverse of the origin offset
    let transform_origin = &box_styles.transform_origin;
    let origin_translation = Affine::translate(Vec2 {
        x: transform_origin
            .horizontal
            .resolve(reference_box.width())
            .px() as f64,
        y: transform_origin
            .vertical
            .resolve(reference_box.height())
            .px() as f64,
    });

    let mut resolved = Affine::IDENTITY;

    if let Some(translation) = translate {
        resolved *= Affine::translate(translation)
    }

    if let Some(rotation) = rotate {
        resolved *= Affine::rotate(rotation)
    }

    if let Some(scale_transform) = scale_transform {
        resolved *= Affine::scale_non_uniform(scale_transform.x, scale_transform.y)
    }

    if let Some(transform) = transform {
        resolved *= transform;
    }

    resolved = origin_translation * resolved * origin_translation.inverse();

    if resolved != Affine::IDENTITY {
        Some(resolved)
    } else {
        None
    }
}
