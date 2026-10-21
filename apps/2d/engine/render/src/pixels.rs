//! Pixel helpers for frame readback and image conversion: the half-float decode table (every F16 bit pattern →
//! f32) and band-parallel conversion on all cores (a 1080p F16 frame is 16 MB). What a frame's pixels become on
//! the way out is color.rs `output`.

use std::ops::Range;
use std::sync::OnceLock;

/// IEEE half → f32 for every bit pattern.
pub fn halves() -> &'static [f32] {
    static TABLE: OnceLock<Vec<f32>> = OnceLock::new();
    TABLE.get_or_init(|| (0..=u16::MAX).map(half_to_f32).collect())
}

fn half_to_f32(h: u16) -> f32 {
    let sign = if h & 0x8000 != 0 { -1.0 } else { 1.0 };
    let exp = ((h >> 10) & 0x1f) as i32;
    let man = (h & 0x3ff) as f32;
    sign * match exp {
        0 => man * 2f32.powi(-24),
        31 => if man == 0.0 { f32::INFINITY } else { f32::NAN },
        e => (1.0 + man / 1024.0) * 2f32.powi(e - 15),
    }
}

/// Runs `f(pixel range, its output bytes)` over `px` pixels in bands on up to 8 threads; `out` holds `bpp` bytes
/// a pixel.
pub fn bands<F>(px: usize, f: F, out: &mut [u8], bpp: usize)
where
    F: Fn(Range<usize>, &mut [u8]) + Sync,
{
    let threads = std::thread::available_parallelism().map(|n| n.get()).unwrap_or(4).min(8);
    let band = px.div_ceil(threads).max(1);
    std::thread::scope(|s| {
        for (k, dst) in out.chunks_mut(band * bpp).enumerate() {
            let f = &f;
            let start = k * band;
            s.spawn(move || f(start..start + dst.len() / bpp, dst));
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn halves_decode() {
        assert_eq!(half_to_f32(0x3c00), 1.0);
        assert_eq!(half_to_f32(0x3800), 0.5);
        assert_eq!(half_to_f32(0x0000), 0.0);
        assert!((half_to_f32(0x0001) - 5.96e-8).abs() < 1e-9);
    }

    #[test]
    fn bands_cover_every_pixel_once() {
        let mut out = vec![0u8; 1001 * 2];
        bands(1001, |r, dst| r.zip(dst.chunks_exact_mut(2)).for_each(|(i, o)| o.copy_from_slice(&(i as u16).to_le_bytes())), &mut out, 2);
        assert!(out.chunks(2).enumerate().all(|(i, b)| u16::from_le_bytes([b[0], b[1]]) as usize == i));
    }
}
