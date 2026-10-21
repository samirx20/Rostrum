//! `matteMorph`: a matte's grow / erode over a **disc** (COMP_CORE §3), not feMorphology's square window.
//!
//! A square max / min stamps every grey pixel into a (2r+1)² block, which shows as blocks along the contour of a soft
//! matte with fine detail. Here a tap at distance `d` (px, between pixel centres) counts with weight [`rim`]`(r, d)`:
//! 1 inside the radius, falling linearly to 0 over the next pixel, so a fractional radius is antialiased at the rim.
//! Dilate: `max(w·v)` over the taps; erode: `min(1 − w·(1 − v))` (the dilate of the complement). Taps outside the picture
//! are skipped (clamp to edge: the frame's border is not eaten). Mattes are opaque grey: the colour channels are
//! processed, alpha is kept. One tap loop reaches [`MAX_R`] px; a larger radius runs as equal passes ([`passes`]),
//! since discs add (the Minkowski sum of two discs is a disc).
//!
//! The SkSL below and [`morph`] are the same maths; `rim` is the one definition of the rim weight.

use super::Program;

/// Reach of one pass, px (the SkSL loop's fixed bound).
pub const MAX_R: f32 = 16.0;

/// Weight of a tap at distance `d` for radius `r`: 1 for `d ≤ r`, 0 for `d ≥ r + 1`, linear between.
pub fn rim(r: f32, d: f32) -> f32 {
    (r + 1.0 - d).clamp(0.0, 1.0)
}

/// A radius as equal passes of at most [`MAX_R`] (r ≤ 0: none).
pub fn passes(r: f32) -> Vec<f32> {
    if !(r > 0.0) {
        return vec![];
    }
    let n = (r / MAX_R).ceil().max(1.0) as usize;
    vec![r / n as f32; n]
}

fn one_pass(src: &[[f32; 4]], w: usize, h: usize, r: f32, erode: bool) -> Vec<[f32; 4]> {
    let reach = r.ceil() as isize;
    let taps: Vec<(isize, isize, f32)> = (-reach..=reach)
        .flat_map(|j| (-reach..=reach).map(move |i| (i, j)))
        .filter_map(|(i, j)| {
            let wt = rim(r, ((i * i + j * j) as f32).sqrt());
            (wt > 0.0).then_some((i, j, wt))
        })
        .collect();
    let mut out = src.to_vec();
    for y in 0..h as isize {
        for x in 0..w as isize {
            let mut acc = [if erode { 1.0f32 } else { 0.0 }; 3];
            for &(i, j, wt) in &taps {
                let (sx, sy) = (x + i, y + j);
                if sx < 0 || sy < 0 || sx >= w as isize || sy >= h as isize {
                    continue;
                }
                let v = src[sy as usize * w + sx as usize];
                for c in 0..3 {
                    acc[c] = if erode { acc[c].min(1.0 - wt * (1.0 - v[c])) } else { acc[c].max(wt * v[c]) };
                }
            }
            let o = &mut out[y as usize * w + x as usize];
            o[..3].copy_from_slice(&acc);
        }
    }
    out
}

/// The CPU twin of `matteMorph`: dilate (`erode` false) or erode by `r` px over a disc, in [`passes`] (r ≤ 0: as is).
pub fn morph(src: &[[f32; 4]], w: usize, h: usize, r: f32, erode: bool) -> Vec<[f32; 4]> {
    passes(r).into_iter().fold(src.to_vec(), |img, p| one_pass(&img, w, h, p, erode))
}

pub(crate) fn program() -> Program {
    Program {
        name: "matteMorph",
        blender: false,
        code: format!(
            "{}uniform float r;
uniform float erode;
half4 main(float2 p) {{
    float2 q = floor(p - box.xy) + 0.5;
    bool er = erode > 0.5;
    float3 acc = er ? float3(1.0) : float3(0.0);
    for (int j = -{m}; j <= {m}; j++) {{
        for (int i = -{m}; i <= {m}; i++) {{
            float w = clamp(r + 1.0 - length(float2(float(i), float(j))), 0.0, 1.0);
            if (w <= 0.0) {{ continue; }}
            float2 t = q + float2(float(i), float(j));
            if (t.x < 0.0 || t.y < 0.0 || t.x > box.z || t.y > box.w) {{ continue; }}
            float3 v = S(t).rgb;
            acc = er ? min(acc, 1.0 - w * (1.0 - v)) : max(acc, w * v);
        }}
    }}
    return half4(half3(acc), half(S(q).a));
}}
",
            super::aov::PRELUDE,
            m = MAX_R as i32
        ),
        uniforms: &["r", "erode"],
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn px(w: usize, h: usize, at: &[(usize, usize)], bg: f32, fg: f32) -> Vec<[f32; 4]> {
        let mut img = vec![[bg, bg, bg, 1.0]; w * h];
        for &(x, y) in at {
            img[y * w + x] = [fg, fg, fg, 1.0];
        }
        img
    }

    #[test]
    fn a_single_pixel_grown_by_3_is_a_disc_not_a_square() {
        let (w, h) = (15, 15);
        let g = morph(&px(w, h, &[(7, 7)], 0.0, 1.0), w, h, 3.0, false);
        let at = |dx: isize, dy: isize| g[((7 + dy) as usize) * w + (7 + dx) as usize][0];
        assert_eq!((at(0, 0), at(3, 0), at(0, -3), at(2, 2)), (1.0, 1.0, 1.0, 1.0)); // 2.83 ≤ 3
        assert_eq!(at(3, 3), 0.0, "the square's corner (4.2 px away) is not reached");
        assert_eq!(at(4, 0), 0.0);
        assert!(at(3, 1) > 0.5 && at(3, 1) < 1.0, "rim antialiased: {}", at(3, 1));
        assert!(g.iter().all(|p| p[3] == 1.0));
    }

    #[test]
    fn erode_is_the_symmetric_hole_and_the_border_is_not_eaten() {
        let (w, h) = (15, 15);
        let e = morph(&px(w, h, &[(7, 7)], 1.0, 0.0), w, h, 3.0, true);
        let d = morph(&px(w, h, &[(7, 7)], 0.0, 1.0), w, h, 3.0, false);
        for (a, b) in e.iter().zip(&d) {
            assert!((a[0] - (1.0 - b[0])).abs() < 1e-6);
        }
        let flat = morph(&vec![[1.0, 1.0, 1.0, 1.0]; w * h], w, h, 4.0, true);
        assert!(flat.iter().all(|p| p[0] == 1.0), "an erode of white stays white at the frame's border");
    }

    #[test]
    fn a_fractional_radius_is_a_soft_rim_and_big_radii_run_in_passes() {
        let (w, h) = (9, 9);
        let g = morph(&px(w, h, &[(4, 4)], 0.0, 1.0), w, h, 0.5, false);
        assert!((g[4 * w + 5][0] - 0.5).abs() < 1e-6, "{}", g[4 * w + 5][0]);
        assert_eq!(passes(0.0), Vec::<f32>::new());
        assert_eq!(passes(16.0), vec![16.0]);
        assert_eq!(passes(40.0).len(), 3);
        assert!((passes(40.0).iter().sum::<f32>() - 40.0).abs() < 1e-4);
    }

    #[test]
    fn the_program_uses_the_shared_rim() {
        let p = program();
        assert!(p.code.contains("clamp(r + 1.0 - length("));
        assert_eq!(rim(3.0, 3.0), 1.0);
        assert_eq!(rim(3.0, 4.0), 0.0);
    }
}
