//! The canvas's hand-off (gpu_output.rs, handoff.rs): a slot written again holds exactly the new frame's bytes (the
//! CPU's output step, in the screen's form too), though only the rows that changed were read back.

use super::*;

/// A frame of halves: opaque display colours, every 10th row partly transparent at every 5th pixel, row 7 clear.
fn frame(w: u32, h: u32, seed: u32, rows: std::ops::Range<u32>, base: &[u8]) -> Vec<u8> {
    let mut s = seed;
    let mut rnd = || {
        s ^= s << 13;
        s ^= s >> 17;
        s ^= s << 5;
        s
    };
    let mut px = base.to_vec();
    px.resize((w * h * 8) as usize, 0);
    for y in rows {
        for x in 0..w {
            let mut c = [0u16; 4].map(|_| half::f16::from_f32((rnd() % 1000) as f32 / 1000.0).to_bits());
            c[3] = match y % 10 {
                3 if x % 5 == 0 && seed != 9 => half::f16::from_f32(0.5).to_bits(),
                7 => 0,
                _ => half::f16::ONE.to_bits(),
            };
            for (k, v) in c.into_iter().enumerate() {
                let o = ((y * w + x) * 8) as usize + k * 2;
                px[o..o + 2].copy_from_slice(&v.to_le_bytes());
            }
        }
    }
    px
}

fn draw(p: &mut Painter, px: &[u8], spec: &crate::color::Spec) {
    let (w, h) = (p.width, p.height);
    let info = ImageInfo::new((w as i32, h as i32), ColorType::RGBAF16, AlphaType::Premul, spec.surface_space());
    let img = skia_safe::images::raster_from_data(&info, skia_safe::Data::new_copy(px), w as usize * 8).unwrap();
    let mut paint = Paint::default();
    paint.set_blend_mode(BlendMode::Src);
    p.surface.canvas().draw_image(&img, (0, 0), Some(&paint));
}

#[test]
fn a_slot_written_again_holds_the_new_frame_exactly() {
    let (w, h) = (97u32, 61u32);
    let spec = crate::color::Spec::parse(&serde_json::json!({})).unwrap();
    let a = frame(w, h, 0x2545_F491, 0..h, &[]);
    // Rows 20..34 new; with seed 9, rows 23 and 33 lose their partly see-through pixels (the CPU's rows become the GPU's).
    let b = frame(w, h, 9, 20..34, &a);
    let mut p = Painter::gpu(w, h, spec.surface_space()).expect("GPU");
    for screen in [false, true] {
        let mut slot = vec![0xABu8; (w * h * 4) as usize];
        let holds = (1, 0, w, h, false, screen);
        p.output_forget(0);
        for (k, px) in [&a, &b].into_iter().enumerate() {
            draw(&mut p, px, &spec);
            let raw = p.read().unwrap();
            let mut want = vec![];
            crate::color::output(&spec, &raw, w, false, false, 0, &mut want);
            if screen {
                crate::pixels::to_screen(&mut want);
            }
            p.output_start(&spec, false, screen, Some(holds)).expect("the GPU step").expect("started");
            let read = p.output_finish(&spec, &mut slot).expect("finished");
            let off = slot.iter().zip(&want).position(|(x, y)| x != y);
            assert!(off.is_none(), "screen {screen}, frame {k}: first different byte {off:?}");
            if k == 1 {
                assert!(read <= 14, "screen {screen}: {read} rows read back for 14 changed");
            }
        }
    }
}

/// A picture whose edge falls between pixels (any canvas size: the comp drawn at 0.583 × is 1120.0 × 630.0 wide, at a
/// hair more 1121 × 631 with a half-covered last column and row) keeps the GPU's output step: the CPU redoes only the
/// edge's blocks, never whole rows (once every row of such a frame went to the CPU: 25-40 ms a frame), and every size
/// gives the CPU's bytes exactly.
#[test]
fn an_edge_between_pixels_costs_the_cpu_only_its_blocks() {
    let spec = crate::color::Spec::parse(&serde_json::json!({})).unwrap();
    for (w, h) in [(1120u32, 630u32), (1121, 631), (1, 1), (33, 2), (1920, 1080)] {
        let mut px = frame(w, h, 0x2545_F491 ^ w, 0..h, &[]);
        for y in 0..h {
            for x in 0..w {
                // Opaque inside; the last column and row half covered (no row 7 gap, no scattered see-through pixels).
                let a = if x + 1 == w && w > 1120 || y + 1 == h && h > 630 { 0.5 } else { 1.0 };
                let o = ((y * w + x) * 8 + 6) as usize;
                px[o..o + 2].copy_from_slice(&half::f16::from_f32(a).to_le_bytes());
            }
        }
        let mut p = Painter::gpu(w, h, spec.surface_space()).expect("GPU");
        draw(&mut p, &px, &spec);
        let raw = p.read().unwrap();
        let mut want = vec![];
        crate::color::output(&spec, &raw, w, false, false, 0, &mut want);
        let mut got = vec![0u8; want.len()];
        p.output_into(&spec, false, false, &mut got).expect("the GPU step").expect("output");
        let off = got.iter().zip(&want).position(|(x, y)| x != y);
        assert!(off.is_none(), "{w}×{h}: first different byte {off:?}");
    }
    // The blocks a 1121 × 631 frame's edge marks: the last block of every row, and the whole last row.
    let fw = 1121usize.div_ceil(crate::gpu_output::BLOCK as usize);
    let mut flags = vec![0u8; fw * 631];
    for y in 0..631 {
        flags[y * fw + fw - 1] = 1;
    }
    flags[630 * fw..].fill(1);
    let rects = crate::gpu_output::cpu_rects(&flags, fw, 1121);
    let px: u32 = rects.iter().map(|[x0, y0, x1, y1]| (x1 - x0) * (y1 - y0)).sum();
    assert!(rects.len() <= 3 && px <= 32 * 631 + 8 * 1121, "{rects:?}: {px} px for the CPU");
    // A slanting edge (a turned frame's): a few blocks per band, never the row between its two sides.
    let mut flags = vec![0u8; fw * 631];
    for y in 0..631 {
        flags[y * fw + y / 40] = 1;
        flags[y * fw + fw - 1 - y / 40] = 1;
    }
    let px: u32 = crate::gpu_output::cpu_rects(&flags, fw, 1121).iter().map(|[x0, y0, x1, y1]| (x1 - x0) * (y1 - y0)).sum();
    assert!(px <= 2 * 2 * 32 * 631, "{px} px for the CPU");
}
