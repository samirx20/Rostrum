//! `convert(src, dst)`: one reusable transform, decode → linear matrix → encode.
use crate::Rgb;
use crate::matrix::{self, Mat3};
use crate::spaces::{Gamut, Space};
use crate::tf::Curve;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Transform {
    pub decode: Curve,
    pub matrix: Mat3,
    pub encode: Curve,
}

/// The transform from colour space `src` to `dst` (ids from `spaces`); a loud error on an unknown id.
pub fn convert(src: &str, dst: &str) -> Result<Transform, String> {
    let get = |id: &str| Space::get(id).ok_or_else(|| format!("unknown colour space `{id}`"));
    let (s, d) = (get(src)?, get(dst)?);
    Ok(Transform { decode: s.curve, matrix: s.gamut().matrix_to(d.gamut()), encode: d.curve })
}

/// The linear matrix between two gamut ids.
pub fn gamut_matrix(src: &str, dst: &str) -> Result<Mat3, String> {
    let get = |id: &str| Gamut::get(id).ok_or_else(|| format!("unknown gamut `{id}`"));
    Ok(get(src)?.matrix_to(get(dst)?))
}

impl Transform {
    pub fn apply(&self, rgb: Rgb) -> Rgb {
        let lin = rgb.map(|c| self.decode.decode64(c as f64));
        matrix::apply(&self.matrix, lin).map(|c| self.encode.encode64(c) as f32)
    }
    pub fn apply_all(&self, px: &mut [Rgb]) {
        px.iter_mut().for_each(|p| *p = self.apply(*p));
    }
    pub fn inverse(&self) -> Transform {
        Transform { decode: self.encode, matrix: matrix::inverse(&self.matrix), encode: self.decode }
    }
}
