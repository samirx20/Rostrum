//! Premultiplication invariants of the comp's CPU twins (hem-r13 e-premult; docs: skills/compositing/topics/premult.md).
//! A pixel with straight colour `s` and coverage `a` is stored `[s·a, a]`; every twin must keep alpha a coverage (0 … 1, finite) and,
//! unless it adds light on purpose, colour no brighter than alpha. Written without a build (R13 had no cargo slot): run
//! `cargo test -p rostrum-color premult` before relying on it.

use super::{matte, pre, unpre};
use super::{Defocus, Light, VBlur, Warp, FIRST_DISPLAY_OP, MERGE_OPS, defocus_pixel, eval, fog, merge, relight_pixel, vector_blur_pixel, warp_pixel};
use crate::pipeline::Working;

const EPS: f32 = 1e-5;

/// Straight colours × coverages: transparent, a soft edge (a = ¼, ½), and opaque; black, grey, white and a saturated colour.
fn pixels() -> Vec<[f32; 4]> {
    let mut v = vec![];
    for a in [0.0, 0.25, 0.5, 1.0] {
        for s in [[0.0; 3], [0.5; 3], [1.0; 3], [1.0, 0.2, 0.0]] {
            v.push(pre(s, a));
        }
    }
    v
}

fn coverage_ok(p: [f32; 4], what: &str) {
    assert!(p.iter().all(|v| v.is_finite()), "{what}: {p:?}");
    assert!(p[3] >= -EPS && p[3] <= 1.0 + EPS, "{what}: alpha {p:?}");
}

fn colour_within_alpha(p: [f32; 4], what: &str) {
    coverage_ok(p, what);
    assert!(p[..3].iter().all(|&c| c >= -EPS && c <= p[3] + EPS), "{what}: colour above alpha or negative {p:?}");
}

#[test]
fn every_merge_op_keeps_alpha_a_coverage_and_closed_ops_keep_colour_within_alpha() {
    for w in [Working::Display, Working::LinearDisplay, Working::AcesCg] {
        for o in 0..MERGE_OPS.len() {
            for &a in &pixels() {
                for &b in &pixels() {
                    for display in [false, true] {
                        // The display-only blend modes need the display flag; the others are defined either way.
                        if o >= FIRST_DISPLAY_OP && !display {
                            continue;
                        }
                        let r = merge(o, a, b, 1.0, display, w);
                        let what = format!("{} display={display} {w:?} a={a:?} b={b:?}", MERGE_OPS[o]);
                        // plus adds light on purpose (colour may exceed alpha); alpha is still ≤ 1 (R5: an opaque pass sum carried alpha n).
                        // Display ops in ACEScg convert gamut (a saturated ACEScg colour can leave Rec.709): only alpha is bounded there.
                        // minus / from / difference write negative colour by design (premult.md, e-premult F3).
                        if ["plus", "minus", "from", "difference"].contains(&MERGE_OPS[o]) || (display && w == Working::AcesCg) {
                            coverage_ok(r, &what);
                        } else {
                            colour_within_alpha(r, &what);
                        }
                    }
                }
            }
        }
    }
}

#[test]
fn an_edge_pixel_over_nothing_comes_back_with_its_straight_colour() {
    let layer = pre([1.0, 0.5, 0.25], 0.5);
    for (w, display) in [(Working::Display, false), (Working::LinearDisplay, false), (Working::LinearDisplay, true), (Working::AcesCg, true)] {
        let r = merge(0, layer, [0.0; 4], 1.0, display, w);
        let (u, v) = (unpre(r), unpre(layer));
        assert!((r[3] - 0.5).abs() < 1e-4, "{r:?}");
        assert!((0..3).all(|k| (u[k] - v[k]).abs() < 2e-3), "straight colour changed: {u:?} vs {v:?}");
    }
}

#[test]
fn plus_of_opaque_passes_stays_one_alpha() {
    let pass = pre([0.2, 0.3, 0.4], 1.0);
    let mut acc = [0.0; 4];
    for _ in 0..4 {
        acc = merge(6, pass, acc, 1.0, false, Working::AcesCg);
    }
    assert_eq!(acc[3], 1.0);
    assert!((acc[0] - 0.8).abs() < 1e-5, "{acc:?}");
}

#[test]
fn the_matte_scales_colour_and_alpha_together() {
    let c = pre([0.8, 0.4, 0.2], 0.5);
    let r = matte::apply([0.5, 0.5, 0.5, 1.0], c);
    colour_within_alpha(r, "matteApply");
    let (u, v) = (unpre(r), unpre(c));
    assert!((0..3).all(|k| (u[k] - v[k]).abs() < EPS), "{u:?} {v:?}");
}

#[test]
fn fog_keeps_colour_within_alpha_and_leaves_alpha() {
    for z in [0.0, 3.0, 50.0, f32::INFINITY] {
        for &c in &pixels() {
            let r = fog(c, z, 0.2, 1.0, [1.0, 0.9, 0.8]);
            colour_within_alpha(r, "fog");
            assert_eq!(r[3], c[3]);
        }
    }
}

#[test]
fn relight_leaves_alpha_and_replace_stays_within_albedo_times_alpha() {
    let l = [Light { point: false, v: [0.0, 0.0, 1.0], color: [1.0; 3], radius: 0.0 }];
    for &c in &pixels() {
        let r = relight_pixel(c, [0.0, 0.0, 1.0], [0.0; 3], Some([0.5; 3]), &l, true);
        coverage_ok(r, "relight");
        assert_eq!(r[3], c[3]);
        // Replace: the picture's own light goes; the albedo (premultiplied by alpha) times the irradiance comes in.
        assert!(r[..3].iter().all(|&v| v <= c[3] * 0.5 + EPS), "{r:?}");
    }
}

#[test]
fn defocus_and_vector_blur_of_a_half_covered_object_stay_premultiplied() {
    // A square of straight colour 1 at coverage ½ on transparent, 8 px wide in a 32 × 16 picture.
    let src = |i: i32, _j: i32| if (12..20).contains(&i) { pre([1.0, 0.5, 0.25], 0.5) } else { [0.0; 4] };
    let d = Defocus { lens: [0.05, 2.0, 4.0, 0.036], max_radius: 8.0, max_depth: 1e4, taps: 64.0 };
    let z = |_: i32, _: i32| 40.0;
    let b = VBlur { shutter: 1.0, samples: 16.0, max_radius: 12.0 };
    let vel = |_: i32, _: i32| [6.0, 0.0];
    for x in 0..32 {
        let q = [x as f32 + 0.5, 8.5];
        colour_within_alpha(defocus_pixel(&src, &z, q, [32.0, 16.0], &d), &format!("defocus x={x}"));
        colour_within_alpha(vector_blur_pixel(&src, &vel, &vel, None, q, [32.0, 16.0], &b), &format!("vectorBlur x={x}"));
    }
}

#[test]
fn warp_of_a_half_covered_square_keeps_alpha_a_coverage_and_straight_colour() {
    let sq = [[0.0, 0.0], [16.0, 0.0], [16.0, 16.0], [0.0, 16.0]];
    let shifted: [[f32; 2]; 4] = sq.map(|p| [p[0] + 0.5, p[1] + 0.25]);
    let src = |i: i32, j: i32| if (0..16).contains(&i) && (0..16).contains(&j) { pre([1.0, 1.0, 1.0], 0.5) } else { [0.0; 4] };
    for cubic in [false, true] {
        let w = Warp { from: sq, open: shifted, mid: shifted, close: shifted, samples: 1.0, cubic };
        for x in 0..20 {
            for y in 0..20 {
                let c = warp_pixel(&src, [x as f32 + 0.5, y as f32 + 0.5], &w);
                colour_within_alpha(c, &format!("warp cubic={cubic} {x},{y}"));
                // Where the square covers the pixel, the straight colour is the square's (white), not darkened by the transparent edge.
                if c[3] > 0.05 {
                    assert!((unpre(c)[0] - 1.0).abs() < 0.05, "straight colour moved at {x},{y}: {c:?}");
                }
            }
        }
    }
}

/// e-premult F1 (fixed R13): `warp` clamped premultiplied colour to alpha, so a CG highlight of 4.0 at alpha 1 left a corner pin as 1.0.
#[test]
fn warp_does_not_clip_light_above_alpha() {
    let sq = [[0.0, 0.0], [16.0, 0.0], [16.0, 16.0], [0.0, 16.0]];
    let w = Warp { from: sq, open: sq, mid: sq, close: sq, samples: 1.0, cubic: true };
    let c = warp_pixel(&|_, _| [4.0, 4.0, 4.0, 1.0], [8.5, 8.5], &w);
    assert!((c[0] - 4.0).abs() < 1e-4, "clipped: {c:?}");
}

#[test]
fn despill_keeps_the_edge_pixel_premultiplied() {
    let u: Vec<(&str, Vec<f32>)> = vec![
        ("screen", vec![0.02, 0.16, 0.03]), ("local", vec![0.0]), ("channel", vec![1.0]), ("balance", vec![0.5]), ("method", vec![2.0]),
        ("amount", vec![1.0]), ("replace", vec![0.0; 3]), ("keepLuma", vec![0.0]),
    ];
    for &c in &pixels() {
        let r = eval("despill", &u, Working::AcesCg, [0.0; 4], c).unwrap();
        colour_within_alpha(r, "despill");
        assert_eq!(r[3], c[3]);
    }
}
