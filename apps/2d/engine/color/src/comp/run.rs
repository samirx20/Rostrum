//! `Key::run`: the CPU reference of the whole key chain (COMP_CORE §4), built from the programs' own CPU twins (`eval`)
//! and the spatial steps (spatial.rs) in the order the compiler chains them as SVG filter primitives. It is what
//! `matte.read` measures, so the chain here IS the contract for the compiler (parity-tested against the render):
//!
//! ```text
//! P   = the plate (premultiplied, working space)
//! S   = screen picture: none → the uniform colour; blur → screenFill(blur(screenWeight(P), local.blur));
//!       plate → the clean plate (alpha 1)                                         [local = mode ≠ none]
//! a0  = keyAlpha(m S, c P)
//!       difference key: N = the clean plate (alpha 1); a0 = diffAlpha(m [norm(blur(diffDistance(m N, c P), blur))], c P); S = N
//! a1  = despot: open by despot.white (erode, dilate), then close by despot.black (dilate, erode)
//! a2  = matteCombine(add, m core, c a1); core = auto: threshold(a0) → erode(auto.erode) → [blur(auto.soft) → norm];
//!       then matteCombine(add, m core.matte, c a2)
//! a3  = matteCombine(subtract, m garbage, c a2)
//! a   = a3 → erode (+ erode, − dilate) → [blur(soft) → norm]
//! D   = despill(m S, c P) (difference key: D = P, spill 0); replace = background: D + matteApply(m spill(m S, c P), c bg)   (feComposite arithmetic k2 = k3 = 1)
//! fg  = matteApply(m a, c norm(D))
//! edge (width > 0):    fg = edgeExtend(m blur(edgeWeight(fg), width), c fg)   (not normalised: its alpha is how much solid is near)
//! wrap (amount > 0):   fg = lightWrap(m matteApply(m norm(blur(wrapBand(fg), width)), c norm(blur(bg, width))), c fg)
//! ```
//! Blurs of 0 px and morphology of 0 px are left out (and so are their `norm`s).

use super::spatial::{blur, shrink};
use super::{Key, LocalMode, Method, Replace, eval, from_cg, grey, pre, to_cg, unpre};
use crate::comp::key::Blend;
use crate::pipeline::Working;

/// The pictures a key reads besides its plate (all `w × h`, row-major).
pub struct KeyInputs<'a> {
    /// The working space the render composites in.
    pub working: Working,
    /// `core.matte`'s picture (grey values), when the key has one.
    pub core_matte: Option<&'a [f32]>,
    /// `garbage`'s picture (grey values), when the key has one.
    pub garbage: Option<&'a [f32]>,
    /// The clean plate (`local.mode: "plate"`): straight ACEScg.
    pub local_plate: Option<&'a [[f32; 4]]>,
    /// The difference key's clean plate (`difference.plate` / `.layer`): straight ACEScg.
    pub clean_plate: Option<&'a [[f32; 4]]>,
    /// The background (light wrap, replace = background): premultiplied ACEScg.
    pub background: Option<&'a [[f32; 4]]>,
}

/// What the chain makes (ACEScg; mattes as values).
pub struct KeyOut {
    pub alpha0: Vec<f32>,
    pub alpha: Vec<f32>,
    /// The keyed foreground, premultiplied.
    pub fg: Vec<[f32; 4]>,
    /// The screen colour each pixel was keyed against (straight).
    pub screen: Vec<[f32; 3]>,
    /// The despilled plate, premultiplied by the plate's alpha.
    pub despilled: Vec<[f32; 4]>,
    pub spill: Vec<f32>,
}

type Img = Vec<[f32; 4]>;
type U = Vec<(&'static str, Vec<f32>)>;

impl Key {
    /// The uniforms of the screen measurement (keyAlpha, despill, spill, screenWeight read the ones they declare).
    pub fn uniforms(&self) -> U {
        let s = &self.screen;
        let d = &self.despill;
        let replace = match d.replace {
            Replace::Color(c) => c.to_vec(),
            _ => vec![0.0; 3],
        };
        let method = match d.method {
            Method::Weighted => 0.0,
            Method::Average => 1.0,
            Method::Limit => 2.0,
        };
        vec![
            ("screen", s.color.to_vec()),
            ("local", vec![if s.local.mode == LocalMode::None { 0.0 } else { 1.0 }]),
            ("channel", vec![s.channel.index() as f32]),
            ("balance", vec![s.balance]),
            ("gain", vec![s.gain]),
            ("threshold", vec![s.local.threshold]),
            ("black", vec![self.matte.black]),
            ("white", vec![self.matte.white]),
            ("gamma", vec![self.matte.gamma]),
            ("method", vec![method]),
            ("amount", vec![d.amount]),
            ("replace", replace),
            ("keepLuma", vec![if d.keep_luma { 1.0 } else { 0.0 }]),
        ]
    }

    /// The chain (module doc) on `plate` (straight ACEScg, `w × h`).
    pub fn run(&self, plate: &[[f32; 4]], w: usize, h: usize, inputs: &KeyInputs) -> Result<KeyOut, String> {
        self.run_read(plate, w, h, inputs, None)
    }

    /// The chain with a layer's `edgeRead: "bounded"` (TRACKING_CLEANUP §24; engine/comp/edgeRead.ts): `bound` = scene white. The matte
    /// reads the whole plate; despill (and so edge extend and light wrap) reads it with every channel at most `bound` (premultiplied:
    /// `bound × alpha`), against the screen colour at most `bound`. The core's excess (added back by the compositor) is not in `fg`.
    pub fn run_read(&self, plate: &[[f32; 4]], w: usize, h: usize, inputs: &KeyInputs, bound: Option<f32>) -> Result<KeyOut, String> {
        let wk = inputs.working;
        let n = w * h;
        let need = |len: usize, what: &str| if len == n { Ok(()) } else { Err(format!("the key's {what} has {len} pixels, not {n} ({w} × {h})")) };
        need(plate.len(), "plate")?;
        let px = |name: &str, u: &[(&str, Vec<f32>)], m: Option<&Img>, c: &Img| -> Img {
            (0..n).map(|i| eval(name, u, wk, m.map_or([0.0; 4], |m| m[i]), c[i]).expect("a comp program")).collect()
        };
        let greys = |v: &[f32]| -> Img { v.iter().map(|&v| grey(v)).collect() };
        let soften = |img: Img, sigma: f32| if sigma > 0.0 { px("norm", &[], None, &blur(&img, w, h, sigma)) } else { img };
        let into_working = |c: [f32; 4]| pre(from_cg(wk, [c[0], c[1], c[2]]), c[3]);
        let u = self.uniforms();
        let p: Img = plate.iter().map(|&c| into_working(c)).collect();
        let s = &self.screen;
        let screen: Img = match s.local.mode {
            LocalMode::None => vec![into_working([s.color[0], s.color[1], s.color[2], 1.0]); n],
            LocalMode::Blur => px("screenFill", &u, None, &blur(&px("screenWeight", &u, None, &p), w, h, s.local.blur)),
            LocalMode::Plate => {
                let cp = inputs.local_plate.ok_or("key.screen.local.mode \"plate\": the clean plate picture was not given")?;
                need(cp.len(), "clean plate")?;
                cp.iter().map(|&c| into_working([c[0], c[1], c[2], 1.0])).collect()
            }
        };
        // A difference key: the screen picture is the clean plate, and alpha comes from the distance to it.
        let (screen, alpha0) = match &self.difference {
            None => {
                let a0 = px("keyAlpha", &u, Some(&screen), &p);
                (screen, a0)
            }
            Some(df) => {
                let cp = inputs.clean_plate.ok_or("key.difference: the clean plate picture was not given")?;
                need(cp.len(), "clean plate")?;
                let n: Img = cp.iter().map(|&c| into_working([c[0], c[1], c[2], 1.0])).collect();
                let dist = soften(px("diffDistance", &[("weights", df.weights.to_vec())], Some(&n), &p), df.blur);
                let du = [("threshold", vec![df.threshold]), ("softness", vec![df.softness]), ("black", vec![self.matte.black]), ("white", vec![self.matte.white]), ("gamma", vec![self.matte.gamma])];
                let a0 = px("diffAlpha", &du, Some(&dist), &p);
                (n, a0)
            }
        };
        let m = &self.matte;
        let mut a = alpha0.clone();
        if m.despot_white > 0.0 {
            a = shrink(&shrink(&a, w, h, m.despot_white), w, h, -m.despot_white);
        }
        if m.despot_black > 0.0 {
            a = shrink(&shrink(&a, w, h, -m.despot_black), w, h, m.despot_black);
        }
        let add = [("mode", vec![0.0])];
        if let Some(c) = &self.core_auto {
            let core = shrink(&px("threshold", &[("threshold", vec![c.threshold])], None, &alpha0), w, h, c.erode);
            a = px("matteCombine", &add, Some(&soften(core, c.soft)), &a);
        }
        if self.core_matte.is_some() {
            let cm = inputs.core_matte.ok_or("key.core.matte: its picture was not given")?;
            need(cm.len(), "core matte")?;
            a = px("matteCombine", &add, Some(&greys(cm)), &a);
        }
        if self.garbage.is_some() {
            let g = inputs.garbage.ok_or("key.garbage: its picture was not given")?;
            need(g.len(), "garbage matte")?;
            a = px("matteCombine", &[("mode", vec![1.0])], Some(&greys(g)), &a);
        }
        let a = soften(shrink(&a, w, h, m.erode), m.soft);
        let bg: Option<Img> = inputs.background.map(|b| b.iter().map(|&c| { let u = unpre(c); into_working([u[0], u[1], u[2], u[3]]) }).collect());
        let need_bg = || bg.as_ref().ok_or("the key needs its background picture (despill.replace \"background\" / lightWrap), which was not given");
        // The colour steps' reading (the matte's when not bounded).
        let clamp = |c: [f32; 4], b: f32| -> [f32; 4] { [c[0].min(b * c[3]), c[1].min(b * c[3]), c[2].min(b * c[3]), c[3]] };
        let (pc, screen_c, uc) = match bound {
            None => (p.clone(), screen.clone(), u.clone()),
            Some(b) => {
                let mut uc = u.clone();
                uc[0].1 = s.color.iter().map(|&v| v.min(b)).collect();
                (p.iter().map(|&c| clamp(c, b)).collect(), screen.iter().map(|&c| clamp(c, b)).collect(), uc)
            }
        };
        // A difference key has no screen to despill against: the colour is the plate's.
        let (spill, mut d) = if self.difference.is_some() {
            (vec![grey(0.0); n], pc.clone())
        } else {
            (px("spill", &uc, Some(&screen_c), &pc), px("despill", &uc, Some(&screen_c), &pc))
        };
        if self.despill.replace == Replace::Background {
            let add = px("matteApply", &[], Some(&spill), need_bg()?);
            d = d.iter().zip(&add).map(|(x, y)| std::array::from_fn(|k| x[k] + y[k])).collect();
        }
        let mut fg = px("matteApply", &[], Some(&a), &px("norm", &[], None, &d));
        let e = &self.edge;
        if e.width > 0.0 {
            let bg_luma = { let y = super::ap1_y(); y[0] * s.color[0] + y[1] * s.color[1] + y[2] * s.color[2] };
            let eu = [("solid", vec![e.solid]), ("amount", vec![e.amount]), ("core", vec![e.core()]), ("keepLuma", vec![e.keep_luma]), ("bgLuma", vec![bg_luma])];
            let weight = if e.inset > 0.0 {
                // The fill reads only foreground `inset` px deeper than the solid's rim (that rim carries the old background's colour).
                let deep = shrink(&px("threshold", &[("threshold", vec![e.solid])], None, &a), w, h, e.inset);
                px("matteApply", &[], Some(&deep), &px("norm", &[], None, &d))
            } else {
                px("edgeWeight", &eu, None, &fg)
            };
            let fill = blur(&weight, w, h, e.width);
            fg = px("edgeExtend", &eu, Some(&fill), &fg);
        }
        let lw = &self.light_wrap;
        if lw.amount > 0.0 {
            let b = need_bg()?;
            let band = soften(px("wrapBand", &[], None, &fg), lw.width);
            let light = px("matteApply", &[], Some(&band), &soften(b.clone(), lw.width));
            let lu = [("amount", vec![lw.amount]), ("blend", vec![if lw.blend == Blend::Screen { 1.0 } else { 0.0 }])];
            fg = px("lightWrap", &lu, Some(&light), &fg);
        }
        let to_aces = |c: &[f32; 4]| { let u = unpre(*c); pre(to_cg(wk, [u[0], u[1], u[2]]), u[3]) };
        Ok(KeyOut {
            alpha0: alpha0.iter().map(|v| v[0]).collect(),
            alpha: a.iter().map(|v| v[0]).collect(),
            fg: fg.iter().map(to_aces).collect(),
            screen: screen.iter().map(|c| to_cg(wk, [c[0], c[1], c[2]])).collect(),
            despilled: d.iter().map(to_aces).collect(),
            spill: spill.iter().map(|v| v[0]).collect(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn a_key_on_screen_and_foreground_pixels() {
        let key = Key::from_json(&json!({ "screen": { "color": [0.02, 0.16, 0.03] }, "despill": { "method": "limit" } })).unwrap();
        let plate = [[0.02, 0.16, 0.03, 1.0], [0.3, 0.2, 0.15, 1.0]];
        for working in [Working::Display, Working::LinearDisplay, Working::AcesCg] {
            let out = key.run(&plate, 2, 1, &KeyInputs { working, core_matte: None, garbage: None, local_plate: None, clean_plate: None, background: None }).unwrap();
            assert!(out.alpha[0].abs() < 1e-4 && (out.alpha[1] - 1.0).abs() < 1e-4, "{working:?}: {:?}", out.alpha);
            assert!(out.fg[0][3].abs() < 1e-4);
            assert!((0..3).all(|k| (out.fg[1][k] - plate[1][k]).abs() < 1e-4), "{working:?}: {:?}", out.fg[1]);
            // The screen pixel's green is taken to the limit, max(r, b).
            assert!((out.despilled[0][1] - 0.03).abs() < 1e-4, "{:?}", out.despilled[0]);
        }
    }

    #[test]
    fn a_bounded_read_keeps_the_matte_and_bounds_the_colour() {
        // A clipped sky through a gap, a bright subject highlight, a half-covered edge pixel: the matte is the plain key's.
        let key = Key::from_json(&json!({ "screen": { "color": [0.7, 0.76, 3.0] }, "despill": { "method": "average" } })).unwrap();
        let plate = [[1.75, 2.64, 16.1, 1.0], [2.5, 2.4, 2.2, 1.0], [0.9, 1.0, 6.0, 1.0], [0.3, 0.2, 0.15, 1.0]];
        let inputs = KeyInputs { working: Working::AcesCg, core_matte: None, garbage: None, local_plate: None, clean_plate: None, background: None };
        let full = key.run(&plate, 4, 1, &inputs).unwrap();
        let read = key.run_read(&plate, 4, 1, &inputs, Some(1.0)).unwrap();
        assert_eq!(full.alpha, read.alpha);
        // every colour the steps made is at most white × alpha, and a pixel already under white is the plain key's
        for (c, a) in read.fg.iter().zip(&read.alpha) {
            assert!((0..3).all(|k| c[k] <= a + 1e-5), "{c:?} at alpha {a}");
        }
        assert!((0..4).all(|k| (read.fg[3][k] - full.fg[3][k]).abs() < 1e-5), "{:?} vs {:?}", read.fg[3], full.fg[3]);
    }

    #[test]
    fn a_difference_key_keeps_what_differs_from_the_clean_plate() {
        let key = Key::from_json(&json!({ "difference": { "plate": "clean.png", "threshold": 0.02, "softness": 0.1, "blur": 0 } })).unwrap();
        let clean = [[0.2, 0.3, 0.1, 1.0], [0.2, 0.3, 0.1, 1.0], [0.2, 0.3, 0.1, 1.0]];
        // the empty background, a subject far from it, a pixel 0.07 RMS away (half-way up the ramp)
        let off = 0.07 * 3f32.sqrt();
        let plate = [[0.2, 0.3, 0.1, 1.0], [0.8, 0.1, 0.5, 1.0], [0.2 + off, 0.3, 0.1, 1.0]];
        for working in [Working::Display, Working::AcesCg] {
            let out = key.run(&plate, 3, 1, &KeyInputs { working, core_matte: None, garbage: None, local_plate: None, clean_plate: Some(&clean), background: None }).unwrap();
            assert!(out.alpha[0].abs() < 1e-4 && (out.alpha[1] - 1.0).abs() < 1e-4 && (out.alpha[2] - 0.5).abs() < 1e-3, "{working:?}: {:?}", out.alpha);
            // no despill: the subject keeps its colour
            assert!((0..3).all(|k| (out.fg[1][k] - plate[1][k]).abs() < 1e-4), "{working:?}: {:?}", out.fg[1]);
            assert!(out.spill.iter().all(|&s| s == 0.0));
        }
        let missing = key.run(&plate, 3, 1, &KeyInputs { working: Working::AcesCg, core_matte: None, garbage: None, local_plate: None, clean_plate: None, background: None });
        assert!(missing.err().unwrap().contains("clean plate"));
    }
}
