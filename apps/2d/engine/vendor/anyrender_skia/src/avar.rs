//! Rostrum patch (H5): undo a variable font's `avar` mapping, so Skia draws the instance Parley shaped.
//!
//! Parley (skrifa / harfrust) hands each glyph run its *normalized* coordinates, which already went through the
//! font's `avar` segment maps. Skia only takes design-space values and applies `avar` itself, so turning a
//! normalized coordinate straight back into a design value (a plain lerp over min / default / max) applies `avar`
//! twice: the drawn outlines then belong to another instance than the advances (Roboto Flex remaps `opsz`, so a
//! title at opsz 40 was drawn as opsz 83). The inverse of each axis's piecewise-linear map is applied first.
//! `avar` version 2's cross-axis variations are not inverted (only its version 1 segment maps).

/// Each axis's `avar` segment map, in `fvar` axis order: `(from, to)` normalized pairs, ascending.
pub(crate) fn segment_maps(avar: &[u8]) -> Vec<Vec<(f32, f32)>> {
    let u16_at = |at: usize| avar.get(at..at + 2).map(|b| u16::from_be_bytes([b[0], b[1]]));
    let f2dot14_at = |at: usize| u16_at(at).map(|v| v as i16 as f32 / 16384.0);
    let Some(axis_count) = u16_at(6) else {
        return Vec::new();
    };
    let mut maps = Vec::with_capacity(axis_count as usize);
    let mut at = 8;
    for _ in 0..axis_count {
        let Some(count) = u16_at(at) else { break };
        let map = (0..count as usize)
            .map_while(|k| Some((f2dot14_at(at + 2 + 4 * k)?, f2dot14_at(at + 4 + 4 * k)?)))
            .collect();
        maps.push(map);
        at += 2 + 4 * count as usize;
    }
    maps
}

/// The coordinate before `map`: the segment whose mapped ends hold `value`, interpolated back.
pub(crate) fn unmap(map: &[(f32, f32)], value: f32) -> f32 {
    map.windows(2)
        .find(|pair| pair[0].1 <= value && value <= pair[1].1)
        .map(|pair| {
            let ((from0, to0), (from1, to1)) = (pair[0], pair[1]);
            if to1 == to0 { from0 } else { from0 + (value - to0) * (from1 - from0) / (to1 - to0) }
        })
        .unwrap_or(value)
}
