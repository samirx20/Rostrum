//! `.cube` export (the "show LUT" for Resolve): a grade, or grade + view, sampled on a 3D grid over the codes of
//! an input space, with the spaces written in the header comments.
use super::Grade;
use crate::convert::convert;
use crate::lut::{Cube, Lut, Lut1d, Lut3d};
use crate::spaces::Space;
use crate::tf::Curve;
use crate::view::{Target, View};

impl Grade {
    /// Sample `input` code 0 … 1 → ACEScg → the grade → (the view's display light, when `view` is given) →
    /// `output` code on a `size³` grid (33 or 65 for Resolve; 2 … 256 accepted). With a view, `output` is a
    /// display encoding (e.g. `rec1886_rec709`, `srgb_display`, `rec2100_pq` for `hdr1000`). Pick an `input`
    /// whose 0 … 1 codes cover the light (a log space such as `acescct`), not a linear one.
    ///
    /// A scene-linear `input` (a gamut id such as `acescg` or `sgamut3cine`) has no usable 0 … 1 codes (the shadows
    /// would be a few cells and everything over 1 is lost): use [`Grade::bake_shaped`], which gives the 1D shaper too.
    pub fn bake(&self, size: usize, input: &str, output: &str, view: Option<(&str, Target)>) -> Result<Cube, String> {
        if linear_input(input)? {
            return Err(format!("`{input}` is linear light: a 3D table over its codes would crush the shadows and clip highlights. Bake over a log space (acescct, or the camera's), or use bake_shaped, which adds a 1D shaper"));
        }
        self.bake_table(size, input, output, view, None)
    }

    /// [`Grade::bake`] that also takes a scene-linear `input`: the 3D table is over ACEScct-encoded codes (rescaled to 0 .. 1 over 0 .. 16) of that
    /// linear space (the shaper's codes) and the second table is the 1D shaper (linear → those codes) to apply first
    /// (a `.cube` holds one table, so the two are two files). A log or display `input` gives `(table, None)`.
    pub fn bake_shaped(&self, size: usize, input: &str, output: &str, view: Option<(&str, Target)>) -> Result<(Cube, Option<Cube>), String> {
        if !linear_input(input)? {
            return Ok((self.bake_table(size, input, output, view, None)?, None));
        }
        let shaper = Lut1d::bake(SHAPER_POINTS, [0.0; 3], [SHAPER_MAX; 3], |p| p.map(|c| (Curve::AcesCct.encode(c) - shaper_lo()) / (Curve::AcesCct.encode(SHAPER_MAX) - shaper_lo())));
        let cube = self.bake_table(size, input, output, view, Some(Curve::AcesCct))?;
        let comments = vec![
            " Rostrum 1D shaper (rostrum-color Grade::bake_shaped)".into(),
            format!(" in: {input} (linear light), out: ACEScct codes of {input}, rescaled so 0 .. {SHAPER_MAX} is 0 .. 1"),
            format!(" apply first, then the 3D table; domain 0..{SHAPER_MAX}, {SHAPER_POINTS} points, linear interpolation"),
        ];
        Ok((cube, Some(Cube { title: Some("Rostrum shaper".into()), comments, lut: Lut::D1(shaper) })))
    }

    fn bake_table(&self, size: usize, input: &str, output: &str, view: Option<(&str, Target)>, shaper: Option<Curve>) -> Result<Cube, String> {
        self.check()?;
        if !(2..=256).contains(&size) {
            return Err(format!("a baked .cube has 2 … 256 points per axis (33 or 65 for Resolve); got {size}"));
        }
        let dec = convert(input, "acescg")?;
        let view = view.map(|(id, t)| View::resolve(id, t).map(|v| (v, t))).transpose()?;
        let enc = convert(view.map_or("acescg", |(_, t)| t.gamut()), output)?;
        let lut = Lut3d::bake(size, [0.0; 3], [1.0; 3], |p| {
            let p = shaper.map_or(p, |c| p.map(|v| c.decode(shaper_lo() + v * (c.encode(SHAPER_MAX) - shaper_lo()))));
            let cg = self.apply(dec.apply(p));
            enc.apply(view.map_or(cg, |(v, t)| v.forward(cg, t)))
        });
        let shown = view.map_or(" view: none (the grade alone, no view transform)".into(), |(v, t)| {
            format!(" view: {} {} (display light in the target's primaries)", v.id, t.id())
        });
        let comments = vec![
            " Rostrum grade (rostrum-color Grade::bake)".into(),
            match shaper {
                Some(_) => format!(" in: {input} (linear light) through the 1D shaper file: ACEScct codes rescaled so 0 .. 16 is 0 .. 1"),
                None => format!(" in: {input}"),
            },
            format!(" out: {output}"),
            shown,
            format!(" grid: {size}^3 over {} codes 0..1; apply tetrahedral", if shaper.is_some() { "shaper" } else { input }),
        ];
        Ok(Cube { title: Some("Rostrum grade".into()), comments, lut: Lut::D3(lut) })
    }
}

/// The shaper's domain (scene-linear 0 … 16: 6.4 stops over mid grey) and size: 1D tables are linear between entries.
pub const SHAPER_MAX: f32 = 16.0;
pub const SHAPER_POINTS: usize = 4096;

/// Whether `input` is a scene-linear space (a gamut id): bake over a shaper.
fn linear_input(input: &str) -> Result<bool, String> {
    Ok(Space::get(input).ok_or_else(|| format!("unknown colour space `{input}`"))?.curve == Curve::Linear)
}


fn shaper_lo() -> f32 {
    Curve::AcesCct.encode(0.0)
}
