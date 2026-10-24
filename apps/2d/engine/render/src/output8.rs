//! The 8-bit output step of an opaque pixel from integer codes (color.rs `gpu_codes`: one entry per half, the code at
//! dither offset 0 and the hash value from which it is one more), the same table the GPU's output step reads, so the
//! bytes are exactly those of the per-channel float step (`quantise8`) it was made from. No float maths and no
//! per-pixel division: this is what lets an export's colour step keep up with a fast painter.

use crate::color::dither_hash;

/// Pixels that are fully covered (alpha 1.0) with every channel finite are done here; any other pixel is left to the
/// general step. `p` is the pixel's four halves, `(x, y)` its place in the frame.
#[inline]
pub fn opaque(codes: &[u32], p: &[u8], (x, y): (u32, u32), o: &mut [u8]) -> bool {
    let bits = |k: usize| u16::from_le_bytes([p[k * 2], p[k * 2 + 1]]) as usize;
    if bits(3) != 0x3c00 || (0..3).any(|k| bits(k) & 0x7c00 == 0x7c00) {
        return false;
    }
    for k in 0..3 {
        let e = codes[bits(k)];
        let t = e >> 8;
        o[k] = ((e & 255) + (t != 0 && dither_hash(x, y, k as u32) >= t) as u32) as u8;
    }
    o[3] = 255;
    true
}
