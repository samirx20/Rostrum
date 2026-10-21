//! Synthetic mattes measured to the exact. Every expected number is worked out by hand in the comment next to it, or
//! counted by a plain loop here that shares no code with the module (the oracle).

use super::*;

fn close(got: f64, want: f64, tol: f64, what: &str) {
    assert!((got - want).abs() <= tol, "{what}: got {got}, want {want}");
}
fn num(v: &Value, path: &[&str]) -> f64 {
    path.iter().try_fold(v, |v, k| v.get(*k)).and_then(Value::as_f64).unwrap_or_else(|| panic!("{path:?} is not a number in {v}"))
}
fn run(w: usize, h: usize, alpha: &[&[f32]]) -> Value {
    measure(&StatsInput::new(w, h, alpha.to_vec())).unwrap()
}

/// 100 × 64: alpha = clamp((x − 20.5) / 40, 0, 1) in every row. The 0.05 / 0.95 crossings are at x = 22.5 and 58.5.
fn ramp(shift: usize) -> Vec<f32> {
    (0..64 * 100).map(|i| (((i % 100) as f32 - shift as f32 - 20.5) / 40.0).clamp(0.0, 1.0)).collect()
}

#[test]
fn ramp_band_width_and_coverage() {
    let a = ramp(0);
    let m = run(100, 64, &[&a]);
    // Band 0.05 … 0.95 is 0.9 · 40 = 36 px wide along the gradient, in every row.
    for p in ["p50", "p90", "max"] {
        close(num(&m, &["edge", "bandWidthPx", p]), 36.0, 1e-3, p);
    }
    assert_eq!(m["edge"]["samples"], 64);
    // Boundary pixels of alpha > 0.5 are the column x = 41 (a = 0.5125; x = 40 is 0.4875): 64 pixel edges.
    assert_eq!(m["edge"]["contourPx"], 64.0);
    // Columns: ≤ 0.005: x 0..=20 (21); ≥ 0.995: x 61..=99 (39); partial: 40. Each column is 1 % of the 100.
    close(num(&m, &["coverage", "pure0"]), 21.0, 1e-9, "pure0");
    close(num(&m, &["coverage", "pure1"]), 39.0, 1e-9, "pure1");
    close(num(&m, &["coverage", "partial"]), 40.0, 1e-9, "partial");
    // Alpha > 0.5: x 41..=99 (59 columns) of 64 rows.
    assert_eq!(m["coverage"]["areaPx"], 59 * 64);
    assert_eq!(m["coverage"]["bbox"], json!([41, 0, 100, 64]));
    // 16 bins of width 1/16: alpha(x) = (x − 20.5)/40 falls in bin floor(16 · alpha); x ≤ 20 → bin 0 (21 columns), x ≥ 58 → bin 15.
    let hist: Vec<u64> = m["coverage"]["hist"].as_array().unwrap().iter().map(|v| v.as_u64().unwrap()).collect();
    assert_eq!(hist.iter().sum::<u64>(), 6400);
    assert_eq!(hist[0], 64 * (21 + 2)); // x = 21, 22 (alpha 0.0125, 0.0375) are in bin 0 too
    assert_eq!(hist[15], 64 * 42); // alpha ≥ 15/16: x − 20.5 ≥ 37.5, x 58..=99
    // Soft share: alpha > 0.05: x ≥ 23 (77 columns); of them ≤ 0.95: x 23..=58 (36).
    close(num(&m, &["edge", "softFraction"]), 36.0 / 77.0, 1e-5, "softFraction");
    // The subject touches the border, nothing is enclosed.
    assert_eq!(m["holes"]["count"], 0);
    assert_eq!(m["holes"]["looseSpecks"]["count"], 0);
    assert_eq!(m["holes"]["subjectAreaPx"], 59.0 * 64.0);
    assert!(m["chatter"].is_null() && m["spill"].is_null() && m["compare"].is_null());
}

#[test]
fn half_size_work_reports_full_frame_pixels() {
    let a = ramp(0);
    let mut input = StatsInput::new(100, 64, vec![&a]);
    input.thresholds.half_above = 50;
    let m = measure(&input).unwrap();
    // The 2 × 2 average of a linear ramp is the same ramp sampled every 2 px: 18 half px = 36 px.
    close(num(&m, &["edge", "bandWidthPx", "p50"]), 36.0, 0.5, "half-size band width");
    close(num(&m, &["edge", "contourPx"]), 64.0, 1e-9, "half-size contour");
    close(num(&m, &["holes", "subjectAreaPx"]), 3776.0, 128.0, "half-size outline area");
}

/// A hard disc (centre 32, 32, radius 24) in 64 × 64 with a 5 × 5 hole holding a one-pixel island, a 2 × 2 hole, a
/// one-pixel speck and a 2 × 2 speck outside.
#[test]
fn disc_holes_and_specks() {
    let (w, h) = (64usize, 64usize);
    let mut a = vec![0f32; w * h];
    let mut disc = 0usize;
    for y in 0..h {
        for x in 0..w {
            let (dx, dy) = (x as i32 - 32, y as i32 - 32);
            if dx * dx + dy * dy <= 24 * 24 {
                a[y * w + x] = 1.0;
                disc += 1;
            }
        }
    }
    for y in 30..35 {
        for x in 26..31 {
            a[y * w + x] = 0.0;
        }
    }
    a[32 * w + 28] = 1.0;
    for y in 38..40 {
        for x in 38..40 {
            a[y * w + x] = 0.0;
        }
    }
    a[3 * w + 3] = 1.0;
    for y in 58..60 {
        for x in 58..60 {
            a[y * w + x] = 1.0;
        }
    }
    let m = run(w, h, &[&a]);
    // Holes: the 5 × 5 ring around the island is 24 px, the 2 × 2 is 4: two holes, 28 px, largest 24.
    assert_eq!(m["holes"]["count"], 2);
    assert_eq!(m["holes"]["areaPx"], 28.0);
    assert_eq!(m["holes"]["largest"], 24.0);
    // Specks: 1 + 4 px outside; the island inside the hole is not one.
    assert_eq!(m["holes"]["looseSpecks"]["count"], 2);
    assert_eq!(m["holes"]["looseSpecks"]["areaPx"], 5.0);
    assert_eq!(m["holes"]["looseSpecks"]["largest"], 4.0);
    // The filled outline is the disc as drawn (holes and island included).
    assert_eq!(m["holes"]["subjectAreaPx"], disc as f64);
    // Hard edge: all of alpha 1 or 0, so the band is under 2 px wide at every sample.
    assert!(num(&m, &["edge", "bandWidthPx", "max"]) < 2.0);
    assert_eq!(m["coverage"]["areaPx"].as_u64().unwrap() as usize, disc - 25 - 4 + 1 + 1 + 4);
    // A region that excludes the specks (the left half only, x < 32): specks are not counted.
    let region: Vec<f32> = (0..w * h).map(|i| if i % w < 32 { 1.0 } else { 0.0 }).collect();
    let mut input = StatsInput::new(w, h, vec![&a]);
    input.region = Some(&region);
    let r = measure(&input).unwrap();
    assert_eq!(r["holes"]["looseSpecks"]["count"], 1);
    assert_eq!(r["holes"]["looseSpecks"]["areaPx"], 1.0);
    assert_eq!(r["holes"]["count"], 1);
    // The hole at x 26..30 is wholly left (24 px); the 2 × 2 at x 38..39 is wholly right (0 px in the region, not counted).
    assert_eq!(r["holes"]["areaPx"], 24.0);
}

/// 48 × 48: alpha 1 for r < 10, 0.5 for 10 ≤ r < 12, else 0. Plate in the ring: excess 0.2 / 0.4 by parity of x + y.
#[test]
fn spill_ring() {
    let (w, h) = (48usize, 48usize);
    let (mut a, mut plate, mut fg) = (vec![0f32; w * h], vec![[0.1f32; 3]; w * h], vec![[0f32; 3]; w * h]);
    let (mut n_ring, mut n_odd, mut n_fg) = (0usize, 0usize, 0usize);
    for y in 0..h {
        for x in 0..w {
            let r2 = (x as i32 - 24).pow(2) + (y as i32 - 24).pow(2);
            let i = y * w + x;
            if r2 < 100 {
                a[i] = 1.0;
                plate[i] = [0.3, 0.4, 0.3]; // excess 0.1 before
                fg[i] = [0.3, 0.3, 0.3]; // 0 after
                n_fg += 1;
            } else if r2 < 144 {
                a[i] = 0.5;
                n_ring += 1;
                let odd = (x + y) % 2 == 1;
                n_odd += odd as usize;
                plate[i] = if odd { [0.2, 0.6, 0.2] } else { [0.2, 0.4, 0.2] }; // excess 0.4 / 0.2
                fg[i] = [0.15, 0.16, 0.14]; // straight [0.3, 0.32, 0.28]: excess 0.02
            }
        }
    }
    let mut input = StatsInput::new(w, h, vec![&a]);
    input.plate = vec![&plate];
    input.fg = vec![&fg];
    input.screen = Some([0.0, 0.8, 0.2]);
    let m = measure(&input).unwrap();
    let s = &m["spill"];
    assert_eq!(s["edgeBand"]["px"], n_ring);
    assert_eq!(s["foreground"]["px"], n_fg);
    close(num(s, &["edgeBand", "before", "mean"]), (0.2 * (n_ring - n_odd) as f64 + 0.4 * n_odd as f64) / n_ring as f64, 1e-5, "before mean");
    close(num(s, &["edgeBand", "before", "p95"]), 0.4, 1e-6, "before p95");
    close(num(s, &["edgeBand", "after", "mean"]), 0.02, 1e-5, "after mean");
    close(num(s, &["edgeBand", "after", "p95"]), 0.02, 1e-5, "after p95");
    close(num(s, &["foreground", "before", "mean"]), 0.1, 1e-6, "fg before");
    close(num(s, &["foreground", "after", "p95"]), 0.0, 1e-6, "fg after");
    // Edge colour [0.3, 0.32, 0.28]: g is the max, hue = 60 · ((b − r)/(max − min) + 2) = 60 · (−0.5 + 2) = 90°; screen [0, 0.8, 0.2]: 60 · (0.25 + 2) = 135°.
    close(num(s, &["edgeHue", "meanDeg"]), 90.0, 1e-3, "edge hue");
    close(num(s, &["edgeHue", "screenDeg"]), 135.0, 1e-3, "screen hue");
    close(num(s, &["edgeHue", "deltaDeg"]), -45.0, 1e-3, "hue delta");
    assert_eq!(s["channel"], "g");
    // A blue screen measures the blue channel: swapped colours, same excess.
    let blue: Vec<[f32; 3]> = plate.iter().map(|c| [c[0], c[2], c[1]]).collect();
    let mut input = StatsInput::new(w, h, vec![&a]);
    input.plate = vec![&blue];
    input.screen = Some([0.0, 0.2, 0.8]);
    let b = measure(&input).unwrap();
    assert_eq!(b["spill"]["channel"], "b");
    close(num(&b, &["spill", "edgeBand", "before", "p95"]), 0.4, 1e-6, "blue before p95");
}

/// 32 × 32, two frames. Static region: rows 0..24 (the plate's luma moves by 0.5 in rows 24..32, where alpha also changes).
#[test]
fn chatter_in_static_regions() {
    let (w, h) = (32usize, 32usize);
    let mut a0 = vec![0f32; w * h];
    for y in 0..h {
        for x in 17..w {
            a0[y * w + x] = 1.0;
        }
        a0[y * w + 16] = 0.5;
    }
    let mut a1 = a0.clone();
    for y in 0..8 {
        for x in 17..w {
            a1[y * w + x] = 0.98; // core flicker 0.02: 8 rows × 15 columns = 120 px
        }
    }
    for y in 0..12 {
        a1[y * w + 16] = 0.55; // edge flicker 0.05: 12 px
    }
    for y in 0..4 {
        for x in 0..3 {
            a1[y * w + x] = 0.004; // screen noise 0.004: 12 px
        }
    }
    for y in 24..32 {
        for x in 17..w {
            a1[y * w + x] = 0.7; // moves, but with the plate: not static
        }
    }
    let p0 = vec![[0.2f32; 3]; w * h];
    let mut p1 = p0.clone();
    for y in 24..32 {
        for x in 0..w {
            p1[y * w + x] = [0.7; 3];
        }
    }
    let mut input = StatsInput::new(w, h, vec![&a0, &a1]);
    input.plate = vec![&p0, &p1];
    let m = measure(&input).unwrap();
    let c = &m["chatter"];
    assert_eq!(c["frames"], 2);
    // Static: 24 rows of 32 = 768 of 1024 px = 75 %.
    close(num(c, &["staticPct"]), 75.0, 1e-9, "staticPct");
    // Core zone (mean alpha > 0.95): columns 17..31 × rows 0..24 = 360 px; 120 differ by 0.02.
    assert_eq!(c["core"]["px"], 360);
    close(num(c, &["core", "mad"]), 120.0 * 0.02 / 360.0, 1e-6, "core mad");
    close(num(c, &["core", "p99"]), 0.02, 1e-6, "core p99");
    // Edge zone: column 16 × 24 rows; 12 differ by 0.05.
    assert_eq!(c["edge"]["px"], 24);
    close(num(c, &["edge", "mad"]), 12.0 * 0.05 / 24.0, 1e-6, "edge mad");
    close(num(c, &["edge", "p99"]), 0.05, 1e-6, "edge p99");
    // Screen zone: columns 0..15 × 24 rows = 384 px; 12 differ by 0.004 (3 % of them, so p99 is 0.004).
    assert_eq!(c["screen"]["px"], 384);
    close(num(c, &["screen", "mad"]), 12.0 * 0.004 / 384.0, 1e-6, "screen mad");
    close(num(c, &["screen", "p99"]), 0.004, 1e-6, "screen p99");
    // Without a plate every pixel counts as static: the moving rows join the zones.
    let n = measure(&StatsInput::new(w, h, vec![&a0, &a1])).unwrap();
    close(num(&n, &["chatter", "staticPct"]), 100.0, 1e-9, "no plate");
    assert!(n["chatter"]["static"].as_str().unwrap().contains("no plate"));
}

#[test]
fn temporal_series() {
    let (w, h) = (40usize, 20usize);
    let frame = |x0: usize| -> Vec<f32> { (0..w * h).map(|i| if (i / w) >= 5 && (i / w) < 10 && (i % w) >= x0 && (i % w) < x0 + 10 { 1.0 } else { 0.0 }).collect() };
    let (f0, f1, f2) = (frame(4), frame(6), frame(9));
    let m = run(w, h, &[&f0, &f1, &f2]);
    let t = &m["temporal"];
    assert_eq!(t["areaPx"], json!([50, 50, 50]));
    assert_eq!(t["areaDelta"], json!([0, 0]));
    // Centroid x moves 2 then 3 px, y stays.
    close(num(t, &["centroidJump", "mean"]), 2.5, 1e-9, "mean jump");
    close(num(t, &["centroidJump", "max"]), 3.0, 1e-9, "max jump");
}

fn rect(w: usize, h: usize, x0: usize) -> Vec<f32> {
    (0..w * h).map(|i| if (10..20).contains(&(i / w)) && (x0..x0 + 20).contains(&(i % w)) { 1.0 } else { 0.0 }).collect()
}

#[test]
fn reference_equal_and_shifted() {
    let (w, h) = (40usize, 30usize);
    let a = rect(w, h, 10);
    let mut input = StatsInput::new(w, h, vec![&a]);
    input.reference = Some(&a);
    let same = measure(&input).unwrap();
    let c = &same["compare"];
    assert_eq!(num(c, &["iou"]), 1.0);
    assert_eq!(num(c, &["mad"]), 0.0);
    assert_eq!(num(c, &["sad"]), 0.0);
    assert_eq!(num(c, &["gradientError"]), 0.0);
    assert!(c["edgeMad"].is_null(), "a hard matte has no band pixels");
    // One pixel to the right: 20 × 10 each, 190 shared, union 210; 20 pixels differ by 1.
    let r = rect(w, h, 11);
    input.reference = Some(&r);
    let sh = measure(&input).unwrap();
    let c = &sh["compare"];
    close(num(c, &["iou"]), 190.0 / 210.0, 1e-6, "iou");
    close(num(c, &["mad"]), 20.0 / 1200.0, 1e-6, "mad");
    close(num(c, &["sad"]), 100.0 * 20.0 / 1200.0, 1e-5, "sad");
    close(num(c, &["sadPx"]), 20.0, 1e-9, "sadPx");
    // Gradient oracle: central differences, clamped at the border, summed here without the module's helper.
    let at = |m: &[f32], x: i64, y: i64| m[(y.clamp(0, h as i64 - 1) as usize) * w + x.clamp(0, w as i64 - 1) as usize] as f64;
    let mut g = 0.0;
    for y in 0..h as i64 {
        for x in 0..w as i64 {
            let dx = (at(&a, x + 1, y) - at(&a, x - 1, y)) - (at(&r, x + 1, y) - at(&r, x - 1, y));
            let dy = (at(&a, x, y + 1) - at(&a, x, y - 1)) - (at(&r, x, y + 1) - at(&r, x, y - 1));
            g += (dx * dx + dy * dy).sqrt();
        }
    }
    close(num(c, &["gradientError"]), g / 1200.0, 1e-6, "gradientError");
}

#[test]
fn reference_ramp_shifted_by_one() {
    let (a, r) = (ramp(0), ramp(1));
    let mut input = StatsInput::new(100, 64, vec![&a]);
    input.reference = Some(&r);
    let m = measure(&input).unwrap();
    let c = &m["compare"];
    // Total variation of the ramp is 1 per row: sum |a − r| = 64; mad 64 / 6400 = 0.01; sad 1 %.
    close(num(c, &["sadPx"]), 64.0, 1e-4, "sadPx");
    close(num(c, &["mad"]), 0.01, 1e-6, "mad");
    close(num(c, &["sad"]), 1.0, 1e-4, "sad");
    // iou: alpha > 0.5 from x = 41 against from x = 42: 58 shared of 59.
    close(num(c, &["iou"]), 58.0 / 59.0, 1e-6, "iou");
    // Band pixels (0.05 … 0.95) of either: x 23..=58 and 24..=59 → 23..=59 (37 columns), each differing by 0.025.
    close(num(c, &["edgeMad"]), 0.025, 1e-6, "edgeMad");
    assert_eq!(c["edgePx"], 37 * 64);
}

#[test]
fn screen_residual_and_uniformity() {
    let (w, h) = (16usize, 16usize);
    let mut a = vec![0f32; w * h];
    a[5] = 0.004;
    a[6] = 0.008;
    a[200] = 1.0; // not screen
    let mut local = vec![[0.1f32, 0.8, 0.1]; w * h];
    for i in (0..w * h).step_by(2) {
        local[i][1] = 0.6; // half the pixels 0.6, half 0.8: std 0.1 (the subject pixel is excluded below)
    }
    let mut input = StatsInput::new(w, h, vec![&a]);
    input.local = vec![&local];
    let m = measure(&input).unwrap();
    // Alpha < 0.01 is 255 pixels; their sum is 0.012.
    assert_eq!(m["screen"]["px"], 255);
    close(num(&m, &["screen", "residual", "mean"]), 0.012 / 255.0, 1e-6, "residual mean");
    close(num(&m, &["screen", "residual", "max"]), 0.008, 1e-6, "residual max");
    close(num(&m, &["screen", "residual", "nonzeroPct"]), 100.0 * 2.0 / 255.0, 1e-4, "nonzeroPct");
    // Pixel 200 is even (0.6) and excluded: 127 even pixels of 0.6 minus none... 128 evens − 1 = 127 at 0.6, 128 at 0.8.
    let (n6, n8) = (127.0f64, 128.0f64);
    let mean = (0.6 * n6 + 0.8 * n8) / 255.0;
    let var = (0.36 * n6 + 0.64 * n8) / 255.0 - mean * mean;
    close(m["screen"]["uniformity"]["std"][1].as_f64().unwrap(), var.sqrt(), 1e-5, "std g");
    assert_eq!(m["screen"]["uniformity"]["std"][0], 0.0);
}

#[test]
fn notes_state_numbers_only() {
    let a = ramp(0);
    let m = run(100, 64, &[&a]);
    let notes = m["notes"].as_array().unwrap();
    assert!(notes.iter().any(|n| n.as_str().unwrap().contains("edge band") && n.as_str().unwrap().contains("36")));
    for n in notes {
        let s = n.as_str().unwrap().to_lowercase();
        for word in ["too ", "should", "good", "bad", "fix", "try ", "increase", "reduce"] {
            assert!(!s.contains(word), "note has advice or judgement: {s}");
        }
    }
}

#[test]
fn bad_inputs_are_named() {
    let a = vec![0f32; 10 * 10];
    let short = vec![0f32; 99];
    assert!(measure(&StatsInput::new(10, 10, vec![&short])).unwrap_err().contains("99 pixels"));
    let mut input = StatsInput::new(10, 10, vec![&a, &a]);
    input.plate = vec![&[[0f32; 3]; 100]];
    assert!(measure(&input).unwrap_err().contains("plate has 1 frames"));
    let mut input = StatsInput::new(10, 10, vec![&a]);
    input.focus = 3;
    assert!(measure(&input).unwrap_err().contains("focus"));
    assert!(measure(&StatsInput::new(10, 10, vec![])).is_err());
}

/// 1080p with a soft-edged subject, plate, fg, reference and two frames: under 4 KB, and (release) under 150 ms a frame.
/// Run: `cargo test -p rostrum-color --release matte_stats::tests::timing -- --ignored --nocapture`.
#[test]
#[ignore = "timing, release only"]
fn timing_1080p() {
    let (w, h) = (1920usize, 1080usize);
    let frame = |dx: f32| -> Vec<f32> {
        (0..w * h)
            .map(|i| {
                let (x, y) = ((i % w) as f32 - 960.0 - dx, (i / w) as f32 - 540.0);
                let r = (x * x + y * y).sqrt();
                let hole = ((x - 100.0).powi(2) + y * y).sqrt() < 60.0;
                if hole { 0.0 } else { ((380.0 - r) / 30.0).clamp(0.0, 1.0) }
            })
            .collect()
    };
    let (a0, a1) = (frame(0.0), frame(1.5));
    let plate: Vec<[f32; 3]> = (0..w * h).map(|i| if a0[i] > 0.5 { [0.3, 0.4, 0.3] } else { [0.05, 0.6, 0.1] }).collect();
    let fg: Vec<[f32; 3]> = a0.iter().map(|a| [0.3 * a, 0.3 * a, 0.3 * a]).collect();
    let local = vec![[0.05f32, 0.6, 0.1]; w * h];
    let mut input = StatsInput::new(w, h, vec![&a0, &a1]);
    input.plate = vec![&plate, &plate];
    input.fg = vec![&fg, &fg];
    input.local = vec![&local, &local];
    input.reference = Some(&a1);
    let t = std::time::Instant::now();
    let m = measure(&input).unwrap();
    let ms = t.elapsed().as_secs_f64() * 1e3;
    let bytes = m.to_string().len();
    println!("1080p, 2 frames, every block: {ms:.1} ms, {bytes} bytes\n{}", serde_json::to_string_pretty(&m).unwrap());
    assert!(bytes < 4096);
    if !cfg!(debug_assertions) {
        assert!(ms < 300.0, "{ms} ms for two frames (one single-frame set, one chatter pair)");
    }
}
