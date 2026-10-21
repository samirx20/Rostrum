//! The upper hull gamma per hue: the smallest gamma whose approximate boundary lies outside the limiting
//! gamut at five test points between the cusp and the limit J. Port of OCIO 2.5.2 ACES2
//! `generate_gamma_test_data`, `evaluate_gamma_fit` and the search in `make_upper_hull_gamma`.
use super::cam::{Jmh, lerp};
use super::gamut::{self, FOCUS_GAIN_BLEND};
use super::tables::Gamut;

/// (J, J intersect source, slope, J intersect cusp) per test position.
fn tests(cusp: [f32; 2], limit_j_max: f32, mid_j: f32, focus_dist: f32) -> [[f32; 4]; 5] {
    let threshold = lerp(cusp[0], limit_j_max, FOCUS_GAIN_BLEND);
    let focus_j = gamut::focus_j(cusp[0], mid_j, limit_j_max);
    [0.01f32, 0.1, 0.5, 0.8, 0.99].map(|pos| {
        let j = lerp(cusp[0], limit_j_max, pos);
        let gain = gamut::focus_gain(j, threshold, limit_j_max, focus_dist);
        let j_src = gamut::solve_j_intersect(j, cusp[1], focus_j, limit_j_max, gain);
        let slope = gamut::slope(j_src, focus_j, limit_j_max, gain);
        [j, j_src, slope, gamut::solve_j_intersect(cusp[0], cusp[1], focus_j, limit_j_max, gain)]
    })
}

/// The fitted gamma (not inverted) for cusp-table entry `i`.
pub(crate) fn fit(g: &Gamut, i: usize, peak: f32, limit_j_max: f32, limit: &Jmh) -> f32 {
    let (hue, cusp) = (g.hues[i], [g.cusp[i][0], g.cusp[i][1]]);
    let data = tests(cusp, limit_j_max, g.mid_j, g.focus_dist);
    let lum = peak / 100.0;
    let fits = |gamma: f32| {
        data.iter().all(|&[_, j_src, slope, j_cusp]| {
            let m = gamut::boundary(cusp, limit_j_max, 1.0 / gamma, g.lower_gamma_inv, j_src, slope, j_cusp);
            limit.jmh_to_rgb([j_src + slope * m, m, hue]).iter().any(|&c| c > lum)
        })
    };
    let (mut lo, mut hi, mut found) = (0.0f32, 0.4f32, false);
    while !found && hi < 5.0 {
        found = fits(hi);
        if !found {
            (lo, hi) = (hi, hi + 0.4);
        }
    }
    while hi - lo > 1e-5 {
        let t = (hi + lo) / 2.0;
        if fits(t) { hi = t } else { lo = t }
    }
    hi
}
