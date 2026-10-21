//! The blend modes: the one list in `apps/2d/python/rostrum2d/blends.txt` (the Python layer reads the same file),
//! compiled in. Each row: the document's name, the CSS `mix-blend-mode` the painter draws (vendor/blitz-paint
//! blend.rs → Skia), Lottie's number, the inspector's label. Every place that writes a layer's blend into the
//! stage markup asks `css` / `style` here.

use std::sync::LazyLock;

const FILE: &str = include_str!("../../../../python/rostrum2d/blends.txt");

/// (name, css) per row, in the file's order. A malformed row is a build-time mistake: it panics on first use, naming the line.
static ROWS: LazyLock<Vec<(&'static str, &'static str)>> = LazyLock::new(|| {
    FILE.lines()
        .enumerate()
        .filter(|(_, l)| !l.trim().is_empty() && !l.trim_start().starts_with('#'))
        .map(|(i, l)| {
            let cols: Vec<&str> = l.split(" | ").map(str::trim).collect();
            assert!(cols.len() == 4, "blends.txt line {}: expected 'name | css | lottie number | label', got {l:?}", i + 1);
            (cols[0], cols[1])
        })
        .collect()
});

static NAMES: LazyLock<Vec<&'static str>> = LazyLock::new(|| ROWS.iter().map(|r| r.0).collect());

/// The `blend` field's options.
pub fn names() -> &'static [&'static str] {
    &NAMES
}

/// The CSS `mix-blend-mode` of a blend (the field is checked at load, so the name is one of `names`).
pub fn css(name: &str) -> &'static str {
    ROWS.iter().find(|r| r.0 == name).map(|r| r.1).unwrap_or_else(|| panic!("blend {name:?} is not in blends.txt (checked at load)"))
}

/// The declaration a wrapper needs to carry a layer's blend: empty for normal.
pub fn style(name: &str) -> String {
    match css(name) {
        "normal" => String::new(),
        c => format!("mix-blend-mode:{c};"),
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn every_blend_is_a_css_mode_the_painter_draws() {
        // The painter (vendor/blitz-paint/src/blend.rs) maps exactly these to Skia; anything else would draw as normal.
        const DRAWN: &[&str] = &["normal", "multiply", "screen", "overlay", "darken", "lighten", "color-dodge", "color-burn", "hard-light",
            "soft-light", "difference", "exclusion", "hue", "saturation", "color", "luminosity", "plus-lighter"];
        for n in super::names() {
            assert!(DRAWN.contains(&super::css(n)), "{n} → {} is not drawn by the painter", super::css(n));
        }
        assert_eq!(super::css("add"), "plus-lighter");
    }
}
