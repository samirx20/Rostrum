//! ACES 2.0 output transform, analytic, forward and inverse, for `sdr` (Rec.709-limited, 100 nits) and
//! `hdr1000` (P3-D65-limited, 1000 nits, in a Rec.2020 container). A port of OpenColorIO 2.5.2's
//! implementation (BSD-3-Clause: `ops/fixedfunction/ACES2/*`, `Renderer_ACES_OutputTransform20`), which
//! is the C++ form of the Academy's reference CTL (`aces-aswf/aces-output`, Apache-2.0; NOTICE in
//! the crate's `NOTICE`). OCIO's is ported rather than the CTL because OCIO is the oracle: same f32 operations,
//! same table construction. The chain around the fixed function is OCIO's built-in view:
//! ACEScg → clamp [0, 8·r_hit] (AP1) → transform → limiting RGB → clamp [0, peak] → display primaries.
mod cam;
mod gamut;
mod hull_gamma;
pub(crate) mod sksl;
mod tables;
mod tonescale;

use super::{M3, Target, mul};
use crate::convert::gamut_matrix;
use crate::matrix::{self, Primaries};
use cam::{AP0, AP1, Jmh, smax, smin, to_f32};
use std::sync::OnceLock;
use tonescale::{Chroma, Shared, Tonescale};

pub(crate) struct Aces2 {
    p_in: Jmh,
    p_out: Jmh,
    /// ACEScg (AP1) → the AP0 model's CAM16 cone space, and back (AP1 ↔ AP0 folded in).
    in_m: M3,
    out_m: M3,
    ts: Tonescale,
    cc: Chroma,
    limit_j_max: f32,
    model_gamma_inv: f32,
    reach: [f32; tables::N],
    g: tables::Gamut,
    /// Display-linear peak (1.0 = 100 nits) and limiting RGB ↔ display RGB (None: the same primaries).
    peak: f32,
    lim_disp: Option<(M3, M3)>,
}

fn clamp(x: f32, lo: f32, hi: f32) -> f32 {
    smin(smax(lo, x), hi) // OCIO's Clamp: NaN → lo
}

impl Aces2 {
    fn new(peak: f32, lim: Primaries, display: Option<(&str, &str)>) -> Aces2 {
        let (p_in, p_out, reach_p) = (Jmh::new(&AP0), Jmh::new(&lim), Jmh::new(&AP1));
        let ts = Tonescale::new(peak);
        let limit_j_max = p_in.y_to_j(peak);
        let lp = ts.log_peak;
        let mid_j = p_in.y_to_j(ts.c_t * cam::REF_LUM);
        let (focus_dist, lower_inv) = (1.35 + 1.35 * 1.75 * lp, 1.0 / (1.14 + 0.07 * lp));
        let g = tables::gamut(peak, &reach_p, &p_out, limit_j_max, ts.forward_limit, mid_j, focus_dist, lower_inv);
        let f64m = |m: &M3| m.map(|r| r.map(|v| v as f64));
        let ap1_ap0 = matrix::inverse(&matrix::rgb_to_xyz(&AP0));
        let ap1_ap0 = matrix::mul(&ap1_ap0, &matrix::rgb_to_xyz(&AP1));
        let in_m = to_f32(&matrix::mul(&f64m(&p_in.rgb_cam), &ap1_ap0));
        let out_m = to_f32(&matrix::mul(&matrix::inverse(&ap1_ap0), &f64m(&p_in.cam_rgb)));
        let m = |s, d| to_f32(&gamut_matrix(s, d).expect("built-in gamut"));
        Aces2 {
            reach: tables::reach_table(&reach_p, limit_j_max),
            cc: Chroma::new(peak, &ts),
            model_gamma_inv: 1.0 / cam::model_gamma(),
            lim_disp: display.map(|(l, d)| (m(l, d), m(d, l))),
            peak: peak / 100.0,
            p_in, p_out, in_m, out_m, ts, limit_j_max, g,
        }
    }

    pub(crate) fn get(t: Target) -> &'static Aces2 {
        static SDR: OnceLock<Aces2> = OnceLock::new();
        static HDR: OnceLock<Aces2> = OnceLock::new();
        let d65 = [0.3127, 0.329];
        match t {
            Target::Sdr => SDR.get_or_init(|| {
                Aces2::new(100.0, Primaries { r: [0.64, 0.33], g: [0.3, 0.6], b: [0.15, 0.06], w: d65 }, None)
            }),
            Target::Hdr1000 => HDR.get_or_init(|| {
                let p3 = Primaries { r: [0.68, 0.32], g: [0.265, 0.69], b: [0.15, 0.06], w: d65 };
                Aces2::new(1000.0, p3, Some(("lin_p3d65", "lin_rec2020")))
            }),
        }
    }

    /// The per-hue parameters, and the hue's cos / sin. OCIO evaluates cos(radians(h)) of the h it got from
    /// atan2(b, a); a / M and b / M are the same up to f32 rounding and save two trig calls per pixel.
    fn shared(&self, aab: [f32; 3], jmh: [f32; 3]) -> (Shared, f32, f32, f32) {
        let s = Shared { limit_j_max: self.limit_j_max, model_gamma_inv: self.model_gamma_inv,
                         reach_max_m: tables::reach_at(&self.reach, jmh[2]) };
        let (cos, sin) = if aab[0] > 0.0 && jmh[1] > 0.0 { (aab[1] / jmh[1], aab[2] / jmh[1]) } else { (1.0, 0.0) };
        (s, cos, sin, tonescale::norm(cos, sin, self.cc.scale))
    }

    /// ACEScg → display linear (target primaries, 1.0 = 100 nits).
    pub(crate) fn forward(&self, c: [f32; 3]) -> [f32; 3] {
        let lim = self.ts.forward_limit;
        let c = if c.iter().any(|v| v.is_nan()) { [0.0; 3] } else { c.map(|v| clamp(v, 0.0, lim)) };
        let aab = self.p_in.rgb_to_aab_with(&self.in_m, c);
        let jmh = self.p_in.aab_to_jmh(aab);
        let (s, cos, sin, mnorm) = self.shared(aab, jmh);
        let j_ts = self.ts.a_to_j(aab[0], &self.p_in);
        let tm = tonescale::compress_fwd(jmh, j_ts, mnorm, &s, &self.cc);
        let cm = gamut::compress_fwd(tm, &s, &self.g);
        let rgb = self.p_out.aab_to_rgb(self.p_out.jmh_to_aab_cs(cm, cos, sin)).map(|v| clamp(v, 0.0, self.peak));
        self.lim_disp.as_ref().map_or(rgb, |(f, _)| mul(f, rgb))
    }

    /// Display linear (target primaries) → ACEScg.
    pub(crate) fn inverse(&self, d: [f32; 3]) -> [f32; 3] {
        let rgb = self.lim_disp.as_ref().map_or(d, |(_, i)| mul(i, d));
        let rgb = if rgb.iter().any(|v| v.is_nan()) { [0.0; 3] } else { rgb.map(|v| clamp(v, 0.0, self.peak)) };
        let caab = self.p_out.rgb_to_aab(rgb);
        let cjmh = self.p_out.aab_to_jmh(caab);
        let (s, cos, sin, mnorm) = self.shared(caab, cjmh);
        let tm = gamut::compress_inv(cjmh, &s, &self.g);
        let j = self.ts.inv_j(tm[0], &self.p_in);
        let jmh = tonescale::compress_inv(tm, j, mnorm, &s, &self.cc);
        let ap1 = self.p_in.aab_to_rgb_with(&self.out_m, self.p_in.jmh_to_aab_cs(jmh, cos, sin));
        ap1.map(|v| clamp(v, 0.0, self.ts.forward_limit))
    }
}
