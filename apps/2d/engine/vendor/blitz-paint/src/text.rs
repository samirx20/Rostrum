use anyrender::PaintScene;
use blitz_dom::{BaseDocument, NodeId, node::TextBrush, util::ToColorColor};
use kurbo::{Affine, BezPath, Cap, Circle, Rect, Stroke};
use blitz_dom::css_shim::{self, Shim};
use parley::layout::GlyphRun;
use parley::{Affinity, Cursor, Layout, Line, PositionedLayoutItem, Selection};
use peniko::Fill;
use std::collections::HashMap;
use style::properties::generated::longhands::text_decoration_style::computed_value::T as TextDecorationStyle;
use style::values::computed::{
    Length, LengthPercentage, TextDecorationLength, TextDecorationLine, TextUnderlinePosition,
};
use style::values::generics::text::{GenericTextDecorationInset, GenericTextDecorationLength};

use crate::color::{Color, ToColorColor as _};
use crate::{FONT_EMBOLDEN_ENABLED, SELECTION_COLOR};

/// Draw the backgrounds of inline elements (e.g. `<span style="background: ...">`).
///
/// Each glyph run carries the node id of the innermost inline element it belongs to
/// (via its brush). We look up that node's `background-color` and, if non-transparent,
/// fill a rectangle covering the run's advance and its font's ascent/descent so that the
/// background sits behind the text.
///
/// The inline root's own background is painted separately (as a normal block box), so
/// runs belonging to the root are skipped to avoid drawing it twice.
pub(crate) fn draw_inline_backgrounds<'a>(
    scene: &mut impl PaintScene,
    lines: impl Iterator<Item = Line<'a, TextBrush>>,
    doc: &BaseDocument,
    transform: Affine,
    inline_root_id: NodeId,
    span_edges: &HashMap<u64, blitz_dom::node::SpanEdges>,
    scale: f64,
) {
    // Rostrum proof patch: a span's background covers its padding (and its descendants' runs), and
    // its borders are drawn, as browsers do; before, only each run's own text area was filled.
    struct Area {
        id: NodeId,
        depth: usize,
        x: (f64, f64),
        own_y: Option<(f64, f64)>,
        any_y: Option<(f64, f64)>,
        start: bool,
        end: bool,
    }
    let ancestors = |id: NodeId| {
        let mut out = vec![];
        let mut cur = Some(id);
        while let Some(n) = cur {
            if n == inline_root_id {
                break;
            }
            out.push(n);
            cur = doc.get_node(n).and_then(|node| node.parent);
        }
        out
    };
    let join = |a: Option<(f64, f64)>, b: (f64, f64)| Some(a.map_or(b, |a| (a.0.min(b.0), a.1.max(b.1))));
    for line in lines {
        let mut areas: Vec<Area> = vec![];
        let mut add = |id: NodeId, depth: usize, x: (f64, f64), y: Option<(f64, f64)>, own: bool, start: bool, end: bool| {
            let i = match areas.iter().position(|a| a.id == id) {
                Some(i) => i,
                None => {
                    areas.push(Area { id, depth, x, own_y: None, any_y: None, start: false, end: false });
                    areas.len() - 1
                }
            };
            let a = &mut areas[i];
            a.x = (a.x.0.min(x.0), a.x.1.max(x.1));
            if let Some(y) = y {
                a.any_y = join(a.any_y, y);
                if own {
                    a.own_y = join(a.own_y, y);
                }
            }
            a.start |= start;
            a.end |= end;
        };
        for item in line.items() {
            match item {
                PositionedLayoutItem::GlyphRun(glyph_run) => {
                    let metrics = glyph_run.run().font_metrics();
                    let x = glyph_run.offset() as f64;
                    let baseline = glyph_run.baseline() as f64;
                    let y = (baseline - metrics.ascent as f64, baseline + metrics.descent as f64);
                    let chain = ancestors(glyph_run.style().brush.id);
                    let depth = chain.len();
                    for (i, id) in chain.into_iter().enumerate() {
                        add(id, depth - i, (x, x + glyph_run.advance() as f64), Some(y), i == 0, false, false);
                    }
                }
                PositionedLayoutItem::InlineBox(ibox) => {
                    let Some((span, start)) = blitz_dom::node::spacer_span(ibox.id) else {
                        continue;
                    };
                    let e = span_edges.get(&span).copied().unwrap_or_default();
                    let (x0, x1) = (ibox.x as f64, (ibox.x + ibox.width) as f64);
                    let x = if start { (x0 + e.margin[0] as f64, x1) } else { (x0, x1 - e.margin[1] as f64) };
                    let chain = ancestors(NodeId::from_u64(span));
                    let depth = chain.len();
                    for (i, id) in chain.into_iter().enumerate() {
                        let own = i == 0;
                        add(id, depth - i, if own { x } else { (x0, x1) }, None, own, own && start, own && !start);
                    }
                }
            }
        }
        areas.sort_by_key(|a| a.depth);
        for a in &areas {
            let Some((y0, y1)) = a.own_y.or(a.any_y) else {
                continue;
            };
            let (rx, ry) = blitz_dom::util::inline_relative_offset(doc, Some(a.id), inline_root_id);
            let transform = transform * Affine::translate((rx * scale, ry * scale));
            let Some(styles) = doc.get_node(a.id).and_then(|node| node.primary_styles()) else {
                continue;
            };
            let e = span_edges.get(&(a.id.as_u64())).copied().unwrap_or_default();
            // Rostrum patch (round 6): an inline span's own `opacity` / `visibility` (inline_paint).
            let Some(span_alpha) = inline_paint(doc, a.id, inline_root_id) else {
                continue;
            };
            let current_color = styles.clone_color();
            let outer = Rect::new(a.x.0, y0 - (e.padding[0] + e.border[0]) as f64, a.x.1, y1 + (e.padding[2] + e.border[2]) as f64);
            let bg_color = styles.get_background().background_color.resolve_to_absolute(&current_color).as_srgb_color().multiply_alpha(span_alpha);
            if bg_color != Color::TRANSPARENT {
                scene.fill(Fill::NonZero, transform, bg_color, None, &outer);
            }
            let b = styles.get_border();
            let side = |c: &style::values::computed::Color| c.resolve_to_absolute(&current_color).as_srgb_color().multiply_alpha(span_alpha);
            let mut strip = |w: f32, color: Color, r: Rect| {
                if w > 0.0 && color != Color::TRANSPARENT {
                    scene.fill(Fill::NonZero, transform, color, None, &r);
                }
            };
            strip(e.border[0], side(&b.border_top_color), Rect::new(outer.x0, outer.y0, outer.x1, outer.y0 + e.border[0] as f64));
            strip(e.border[2], side(&b.border_bottom_color), Rect::new(outer.x0, outer.y1 - e.border[2] as f64, outer.x1, outer.y1));
            if a.start {
                strip(e.border[3], side(&b.border_left_color), Rect::new(outer.x0, outer.y0, outer.x0 + e.border[3] as f64, outer.y1));
            }
            if a.end {
                strip(e.border[1], side(&b.border_right_color), Rect::new(outer.x1 - e.border[1] as f64, outer.y0, outer.x1, outer.y1));
            }
        }
    }
}

/// Per-font-face cache of the OS/2 `usWinAscent / unitsPerEm` ratio, keyed by the font
/// blob's unique id and face index. `None` is cached for fonts without a usable OS/2 or
/// head table so they aren't re-parsed either.
type WinAscentCache = HashMap<(u64, u32), Option<f32>>;

/// The font's OS/2 `usWinAscent`, in the same (device) pixels as `font_size`.
///
/// This is the ascent browsers use as the top of the "em box" when positioning overlines. It
/// is typically taller than the hhea ascent Parley exposes via [`parley::layout::run::RunMetrics`].
/// Returns `None` when the font has no OS/2 table.
fn win_ascent(cache: &mut WinAscentCache, font: &parley::FontData, font_size: f32) -> Option<f32> {
    let ratio = *cache
        .entry((font.data.id(), font.index))
        .or_insert_with(|| win_ascent_ratio(font));
    Some(ratio? * font_size)
}

/// The unitless `usWinAscent / unitsPerEm` ratio for a font face, or `None` when the font
/// has no usable head/OS/2 table.
fn win_ascent_ratio(font: &parley::FontData) -> Option<f32> {
    use skrifa::raw::{FontRef, TableProvider as _};
    let font_ref = FontRef::from_index(font.data.as_ref(), font.index).ok()?;
    let units_per_em = font_ref.head().ok()?.units_per_em();
    let win_ascent = font_ref.os2().ok()?.us_win_ascent();
    Some(win_ascent as f32 / units_per_em as f32)
}

/// Mirrors Blink's `SelectBestDashGap`: choose the gap length (as close as possible to
/// `gap_length`) that fits a whole number of `dash_length` dashes across `stroke_length`,
/// so dashes are evenly distributed and a dash lands at each end of the line.
fn select_best_dash_gap(stroke_length: f64, dash_length: f64, gap_length: f64) -> f64 {
    let available_length = stroke_length + gap_length;
    let min_num_dashes = (available_length / (dash_length + gap_length)).floor();
    let max_num_dashes = min_num_dashes + 1.0;
    let min_num_gaps = min_num_dashes - 1.0;
    let max_num_gaps = max_num_dashes - 1.0;
    if min_num_gaps < 1.0 {
        return gap_length;
    }
    let min_gap = (stroke_length - min_num_dashes * dash_length) / min_num_gaps;
    let max_gap = (stroke_length - max_num_dashes * dash_length) / max_num_gaps;
    if max_gap <= 0.0 || (min_gap - gap_length).abs() < (max_gap - gap_length).abs() {
        min_gap
    } else {
        max_gap
    }
}

/// A text decoration resolved from a single "decorating box" (an element that
/// sets `text-decoration-line`), ready to be drawn over a glyph run. Because the
/// `text-decoration-*` properties do not inherit, decorations are propagated from
/// ancestors rather than inherited, so a run may be covered by several of these.
///
/// Only the run-independent (style-derived) values are stored here so an instance
/// can be cached on the ancestor stack and reused across every run within the same
/// decorating box. The `text-decoration-inset` and `text-underline-offset` values
/// depend on the run's advance/font-size and are resolved lazily when drawing.
#[derive(Clone)]
struct ResolvedDecoration {
    line: TextDecorationLine,
    style: TextDecorationStyle,
    color: Color,
    thickness: TextDecorationLength,
    /// `text-underline-offset`; `None` for `auto`. Resolved per run.
    underline_offset: Option<LengthPercentage>,
    /// Whether `text-underline-position: under` is in effect.
    underline_under: bool,
    /// Whether `text-underline-position: from-font` is in effect.
    underline_from_font: bool,
    /// `text-decoration-inset`. Resolved per run.
    inset: GenericTextDecorationInset<LengthPercentage>,
}

/// An element on the current ancestor path (inline root -> run node), caching the
/// values resolved from its computed style so descending into the same node across
/// consecutive runs doesn't re-resolve them.
struct DecorationStackEntry {
    node_id: NodeId,
    /// This node's (inherited) text colour, used for the glyphs of runs whose
    /// innermost node is this one.
    text_color: Color,
    /// The decoration this node introduces as a decorating box, if any.
    decoration: Option<ResolvedDecoration>,
}

/// Resolve the cached style values for a single node into a [`DecorationStackEntry`].
fn resolve_decoration_entry(doc: &BaseDocument, node_id: NodeId) -> DecorationStackEntry {
    let Some(styles) = doc.get_node(node_id).and_then(|node| node.primary_styles()) else {
        return DecorationStackEntry {
            node_id,
            text_color: Color::BLACK,
            decoration: None,
        };
    };

    let itext = styles.get_inherited_text();
    let text = styles.get_text();
    let text_color = itext.color.as_color_color();

    let drawn_lines = TextDecorationLine::UNDERLINE
        | TextDecorationLine::OVERLINE
        | TextDecorationLine::LINE_THROUGH;
    let line = text.text_decoration_line;
    // Decorations propagate through the box tree, and a `display: contents` element
    // generates no box, so its decorations have no effect on descendants.
    let is_contents = styles.clone_display().is_contents();
    let decoration = (!is_contents && line.intersects(drawn_lines)).then(|| {
        // `text-decoration-color: currentColor` (the initial value) resolves against
        // the decorating box's own colour, not the descendant run's.
        let color = text
            .text_decoration_color
            .as_absolute()
            .map(ToColorColor::as_color_color)
            .unwrap_or(text_color);

        ResolvedDecoration {
            line,
            style: text.text_decoration_style,
            color,
            thickness: text.text_decoration_thickness.clone(),
            underline_offset: itext.text_underline_offset.non_auto(),
            underline_under: itext
                .text_underline_position
                .contains(TextUnderlinePosition::UNDER),
            underline_from_font: itext
                .text_underline_position
                .contains(TextUnderlinePosition::FROM_FONT),
            inset: text.text_decoration_inset.clone(),
        }
    });

    DecorationStackEntry {
        node_id,
        text_color,
        decoration,
    }
}

/// The run-dependent geometry used to position and size a decoration, captured from a
/// single glyph run. Firefox draws a decoration once for the whole decorating box using
/// the box's own font, so we prefer the values from a run whose innermost node *is* the
/// decorating box (its own text), falling back to the first run it covers.
#[derive(Clone)]
struct DecorationRunGeometry {
    /// The baseline the decoration is positioned from (the run's own, `vertical-align`
    /// shifted, baseline).
    baseline: f32,
    ascent: f32,
    descent: f32,
    underline_offset: f32,
    underline_size: f32,
    strikethrough_size: f32,
    font: parley::FontData,
    font_size: f32,
    css_font_size: f64,
}

/// A decoration accumulated across the runs of a single line for one decorating box.
///
/// The `text-decoration-*` properties describe the whole box, so we gather the horizontal
/// extent it covers on the line (`min_x`/`max_x`) and the font geometry to draw with, then
/// paint a single line spanning the box rather than one segment per run.
struct LineDecoration {
    node_id: NodeId,
    deco: ResolvedDecoration,
    min_x: f64,
    max_x: f64,
    /// Geometry from a run whose innermost node is the decorating box itself.
    own: Option<DecorationRunGeometry>,
    /// Geometry from the first run the box covers (fallback when it has no own text on
    /// this line, e.g. it only wraps differently-sized descendants).
    first: Option<DecorationRunGeometry>,
}

/// Reusable scratch storage for drawing text across all inline formatting contexts in a
/// document. The vectors are cleared between uses without releasing their allocations.
#[derive(Default)]
pub(crate) struct DrawTextContext {
    stack: Vec<DecorationStackEntry>,
    path_scratch: Vec<NodeId>,
    deco_boxes: Vec<LineDecoration>,
    win_ascent_ratios: WinAscentCache,
}

/// Resolve the CSS `text-decoration-thickness` to a device-pixel size.
///
/// - Percentages are resolved against the font size,
/// - `from-font` uses the metrics from Parley,
/// - `auto` uses a thickness of `font-size / 10` (minimum: 1px).
///
/// The result is floored to a whole number of device pixels (minimum 1), matching
/// browsers, which snap decoration thickness to whole pixels.
fn decoration_size(
    thickness: &TextDecorationLength,
    metric_size: f32,
    css_font_size: f64,
    scale: f64,
) -> f32 {
    (match thickness {
        GenericTextDecorationLength::LengthPercentage(lp) => {
            lp.resolve(Length::new(css_font_size as f32)).px() as f64 * scale
        }
        GenericTextDecorationLength::FromFont => metric_size as f64,
        GenericTextDecorationLength::Auto => (css_font_size / 10.0).max(1.0) * scale,
    })
    .floor()
    .max(1.0) as f32
}

/// Draws a single decoration line of the given `text-decoration-style` spanning
/// `[x0, x0 + width]`. `baseline` is the line's baseline and `offset` positions the line
/// relative to it (`y = baseline - offset + size / 2`, growing downward). Geometry is built
/// explicitly (rather than relying on backend dash support) so it renders consistently
/// across renderers.
///
/// `double_dir` points away from the text (`+1` = down, `-1` = up) and is used to place the
/// second line of a `double` decoration.
#[allow(clippy::too_many_arguments)]
fn draw_decoration_line(
    scene: &mut impl PaintScene,
    transform: Affine,
    scale: f64,
    x0: f64,
    width: f64,
    baseline: f32,
    offset: f32,
    size: f32,
    brush: &anyrender::Paint,
    double_dir: f64,
    deco_style: TextDecorationStyle,
    inset_start: f64,
    inset_end: f64,
) {
    // Inset the line from the box's start/end edges (assumes LTR: start is the left edge).
    // Negative insets extend the line past the text.
    let x = x0 + inset_start;
    let w = width - inset_start - inset_end;
    if w <= 0.0 {
        return;
    }
    let y = (baseline - offset + size / 2.0) as f64;
    let size = size as f64;
    let butt_stroke = Stroke::new(size).with_caps(Cap::Butt);

    match deco_style {
        TextDecorationStyle::MozNone => {
            // no line. Equivalent to `text-decoration-line: none`
        }
        // `solid`
        TextDecorationStyle::Solid => {
            let line = kurbo::Line::new((x, y), (x + w, y));
            scene.stroke(&butt_stroke, transform, brush, None, &line);
        }
        // Two lines, each `size` thick, separated by a 1px (CSS) gap. This
        // matches Chrome, where the second line is offset by `thickness + 1px`
        // and sits further from the text (below for underline, above for
        // overline).
        TextDecorationStyle::Double => {
            let one_css_px = scale;
            for cy in [y, y + double_dir * (size + one_css_px)] {
                let line = kurbo::Line::new((x, cy), (x + w, cy));
                scene.stroke(&butt_stroke, transform, brush, None, &line);
            }
        }
        // Round dots (diameter = line thickness) spaced one dot apart.
        TextDecorationStyle::Dotted => {
            let radius = size / 2.0;
            let step = 2.0 * size;
            let mut cx = x + radius;
            while cx <= x + w - radius {
                let dot = Circle::new((cx, y), radius);
                scene.fill(Fill::NonZero, transform, brush, None, &dot);
                cx += step;
            }
        }
        // Dashes as filled rectangles. Dash/gap lengths are relative to the
        // thickness (matching Blink): thinner lines use proportionally longer
        // dashes and gaps so they don't read as dotted or solid.
        TextDecorationStyle::Dashed => {
            let (dash_ratio, gap_ratio) = if size >= 3.0 { (2.0, 1.0) } else { (3.0, 2.0) };
            let dash = size * dash_ratio;
            let nominal_gap = size * gap_ratio;
            // Nudge the gap so a whole number of dashes fits the run evenly.
            let gap = if w > 2.0 * dash {
                select_best_dash_gap(w, dash, nominal_gap)
            } else {
                nominal_gap
            };
            let mut dx = x;
            while dx < x + w {
                let end = (dx + dash).min(x + w);
                let rect = Rect::new(dx, y - size / 2.0, end, y + size / 2.0);
                scene.fill(Fill::NonZero, transform, brush, None, &rect);
                dx += dash + gap;
            }
        }
        // A squiggle built from alternating quadratic Béziers.
        TextDecorationStyle::Wavy => {
            let amplitude = size;
            let half_wave = (2.0 * size).max(1.0);
            let mut path = BezPath::new();
            path.move_to((x, y));
            let mut px = x;
            let mut up = true;
            while px < x + w {
                let nx = (px + half_wave).min(x + w);
                // A quad Bézier reaches half the control-point offset at its
                // midpoint, so use `2 * amplitude` to hit the target peak.
                let ctrl_y = if up {
                    y - 2.0 * amplitude
                } else {
                    y + 2.0 * amplitude
                };
                path.quad_to(((px + nx) / 2.0, ctrl_y), (nx, y));
                px = nx;
                up = !up;
            }
            let stroke = Stroke::new(size).with_caps(Cap::Round);
            scene.stroke(&stroke, transform, brush, None, &path);
        }
    }
}

/// Paint the decorations accumulated for one line, one line per decorating box.
fn flush_line_decorations(
    scene: &mut impl PaintScene,
    transform: Affine,
    scale: f64,
    deco_boxes: &[LineDecoration],
    win_ascent_ratios: &mut WinAscentCache,
    inline_root_id: NodeId,
    line_baseline: f32,
) {
    // Draw innermost boxes first so ancestors' decorations paint on top, matching the
    // per-run drawing order this replaced (`stack.iter().rev()`).
    for acc in deco_boxes.iter().rev() {
        let deco = &acc.deco;
        // Prefer the decorating box's own font; fall back to the first run it covers.
        let geom = match (&acc.own, &acc.first) {
            (Some(own), _) => own.clone(),
            (None, Some(first)) => {
                let mut geom = first.clone();
                // A descendant run's baseline may be shifted by `vertical-align`, but the
                // decoration is positioned from the decorating box's own baseline. For the
                // inline root that is the line's baseline.
                if acc.node_id == inline_root_id {
                    geom.baseline = line_baseline;
                }
                geom
            }
            (None, None) => continue,
        };
        let geom = &geom;
        let width = acc.max_x - acc.min_x;
        if width <= 0.0 {
            continue;
        }
        let brush = anyrender::Paint::from(deco.color);

        // `text-decoration-inset` shortens (or, when negative, extends) the line from the
        // inline-start/end edges. Percentages resolve against the decoration line length
        // (the box's total advance on this line); `auto` is no inset.
        let (inset_start, inset_end) = match &deco.inset {
            GenericTextDecorationInset::LengthPercentage { start, end } => {
                // The extent is in device pixels; convert to CSS pixels so the resolved
                // result can be scaled back.
                let line_length = Length::new((width / scale) as f32);
                (
                    start.resolve(line_length).px() as f64 * scale,
                    end.resolve(line_length).px() as f64 * scale,
                )
            }
            GenericTextDecorationInset::Auto => (0.0, 0.0),
        };

        if deco.line.contains(TextDecorationLine::UNDERLINE) {
            let size = decoration_size(
                &deco.thickness,
                geom.underline_size,
                geom.css_font_size,
                scale,
            );

            // `text-underline-offset` moves the underline away from the text. `auto` keeps
            // the font's suggested position; otherwise it resolves against the font size
            // (percentages relative to 1em).
            let extra_underline_offset = deco
                .underline_offset
                .as_ref()
                .map(|lp| lp.resolve(Length::new(geom.css_font_size as f32)).px() as f64 * scale)
                .unwrap_or(0.0);

            // `text-underline-position: under` places the underline below the glyph box
            // (below descenders) rather than at the font's suggested position near the
            // alphabetic baseline. We anchor the top of the line at the descent so it clears
            // descending glyphs like "gqy".
            // An explicit offset under `auto` is taken from the alphabetic
            // baseline, as CSS and Chrome have it, not from the auto gap.
            let base_offset = if deco.underline_under {
                -geom.descent
            } else if deco.underline_offset.is_some() && !deco.underline_from_font {
                0.0
            } else {
                geom.underline_offset
            };
            let offset = base_offset - extra_underline_offset as f32;

            // A `double` underline extends downward, away from the text.
            draw_decoration_line(
                scene,
                transform,
                scale,
                acc.min_x,
                width,
                geom.baseline,
                offset,
                size,
                &brush,
                1.0,
                deco.style,
                inset_start,
                inset_end,
            );
        }
        if deco.line.contains(TextDecorationLine::OVERLINE) {
            // Fonts don't provide a dedicated overline metric, so reuse the underline
            // thickness. The line sits at the top of the "em box": its lower edge rests on
            // the ascent so it clears the glyphs, and it extends upward from there.
            //
            // Browsers use the OS/2 `usWinAscent` for this edge, which is taller than the
            // hhea-based ascent Parley reports; using the smaller value would draw the
            // overline too low. Fall back to Parley's ascent for fonts without a usable
            // OS/2 table.
            let size = decoration_size(
                &deco.thickness,
                geom.underline_size,
                geom.css_font_size,
                scale,
            );
            let ascent =
                win_ascent(win_ascent_ratios, &geom.font, geom.font_size).unwrap_or(geom.ascent);
            let offset = ascent + size;

            // A `double` overline extends upward, away from the text.
            draw_decoration_line(
                scene,
                transform,
                scale,
                acc.min_x,
                width,
                geom.baseline,
                offset,
                size,
                &brush,
                -1.0,
                deco.style,
                inset_start,
                inset_end,
            );
        }
        if deco.line.contains(TextDecorationLine::LINE_THROUGH) {
            let size = decoration_size(
                &deco.thickness,
                geom.strikethrough_size,
                geom.css_font_size,
                scale,
            );

            // Centre the line-through a third of the ascent above the baseline, matching
            // Chrome (which places it `2/3 * ascent` below the text-top). Parley's
            // `strikethrough_offset` (the font's `yStrikeoutPosition`) sits lower and would
            // draw the line too close to the baseline.
            let ascent =
                win_ascent(win_ascent_ratios, &geom.font, geom.font_size).unwrap_or(geom.ascent);
            let offset = ascent / 3.0 + size / 2.0;

            draw_decoration_line(
                scene,
                transform,
                scale,
                acc.min_x,
                width,
                geom.baseline,
                offset,
                size,
                &brush,
                1.0,
                deco.style,
                inset_start,
                inset_end,
            );
        }
    }
}

pub(crate) fn stroke_text<'a>(
    scene: &mut impl PaintScene,
    lines: impl Iterator<Item = Line<'a, TextBrush>>,
    doc: &BaseDocument,
    transform: Affine,
    scale: f64,
    inline_root_id: NodeId,
    context: &mut DrawTextContext,
) {
    let DrawTextContext {
        stack,
        path_scratch,
        deco_boxes,
        win_ascent_ratios,
    } = context;
    stack.clear();
    path_scratch.clear();
    deco_boxes.clear();

    // Rostrum patch (round 6): every run's text-shadows first, under all of the element's text.
    let lines: Vec<Line<'a, TextBrush>> = lines.collect();
    draw_text_shadows(scene, lines.iter().cloned(), doc, transform, scale, inline_root_id);

    // Persistent stack mirroring the ancestor path (inline root -> current run's
    // node) as we walk the runs. The `text-decoration-*` properties are *not*
    // inherited; instead a decoration set on an ancestor is propagated to the
    // descendant text it wraps. Rather than re-resolving styles for the whole
    // ancestor chain on every run, we cache each node's resolved values here and,
    // for each run, only resolve styles for the nodes newly descended into (popping
    // as we ascend). `path_scratch` is a reusable buffer for the run's node path.
    for line in lines {
        // Decorations accumulated for this line, keyed by decorating box, so each box is
        // painted once (spanning all its runs) using its own font — matching Firefox, which
        // draws one decoration per box rather than one stepped segment per differently-sized
        // run. Clearing preserves the allocation for the next line and inline context.
        deco_boxes.clear();

        for item in line.items() {
            if let PositionedLayoutItem::GlyphRun(glyph_run) = item {
                let run = glyph_run.run();
                let font = run.font();
                let font_size = run.font_size();
                let metrics = run.font_metrics();
                let style = glyph_run.style();

                let css_font_size = font_size as f64 / scale;

                // Reconcile the stack with this run's ancestor path. Build the path
                // (inline root -> run node), keep the shared prefix already on the stack,
                // pop the rest, and resolve styles only for the newly-descended nodes.
                path_scratch.clear();
                let mut walk_id = Some(style.brush.id);
                while let Some(node_id) = walk_id {
                    path_scratch.push(node_id);
                    if node_id == inline_root_id {
                        break;
                    }
                    walk_id = doc.get_node(node_id).and_then(|node| node.parent);
                }
                path_scratch.reverse();

                let shared = stack
                    .iter()
                    .zip(path_scratch.iter())
                    .take_while(|(entry, node_id)| entry.node_id == **node_id)
                    .count();
                stack.truncate(shared);
                for &node_id in &path_scratch[shared..] {
                    stack.push(resolve_decoration_entry(doc, node_id));
                }

                // The glyph colour comes from the run's own node (the stack top): `color`
                // inherits, so the innermost inline element already carries the right value.
                let text_color = stack.last().map(|e| e.text_color).unwrap_or(Color::BLACK);

                let normalized_coords: &[i16] = bytemuck::cast_slice(run.normalized_coords());
                let (transform, glyph_xform, embolden) = run_placement(doc, &glyph_run, transform, scale, inline_root_id);
                // Rostrum patch (round 6): the run's spans' `opacity` / `visibility`, and its
                // `-webkit-text-stroke` in `paint-order` (round 14: cascaded, through the property shim).
                let Some(alpha) = inline_paint(doc, style.brush.id, inline_root_id) else {
                    continue;
                };
                let outline = text_stroke(doc, style.brush.id);
                let glyphs = || {
                    glyph_run.positioned_glyphs().map(|glyph| anyrender::Glyph {
                        id: glyph.id as _,
                        x: glyph.x,
                        y: glyph.y,
                    })
                };
                let stroke_first = outline.as_ref().is_some_and(|o| o.stroke_first);
                for stroke_pass in [stroke_first, !stroke_first] {
                    if stroke_pass {
                        let Some(o) = outline.as_ref() else { continue };
                        let pen = Stroke::new(o.width as f64 * scale);
                        scene.draw_glyphs(font, font_size, false, normalized_coords, embolden, &pen, &anyrender::Paint::from(o.color), alpha, transform, glyph_xform, glyphs());
                    } else {
                        scene.draw_glyphs(
                            font,
                            font_size,
                            !FONT_EMBOLDEN_ENABLED, // hint
                            normalized_coords,
                            embolden,
                            Fill::NonZero,
                            &anyrender::Paint::from(text_color),
                            alpha,
                            transform,
                            glyph_xform,
                            glyphs(),
                        );
                    }
                }

                // Accumulate this run's contribution to each decorating box on its ancestor
                // path. The decoration is drawn once per box after the whole line has been
                // walked (see `flush_line_decorations`), so mixed font sizes within a box
                // produce a single straight line rather than one stepped segment per run.
                let geometry = DecorationRunGeometry {
                    baseline: glyph_run.baseline(),
                    ascent: metrics.ascent,
                    descent: metrics.descent,
                    underline_offset: metrics.underline_offset,
                    underline_size: metrics.underline_size,
                    strikethrough_size: metrics.strikethrough_size,
                    font: font.clone(),
                    font_size,
                    css_font_size,
                };
                let run_node_id = style.brush.id;
                let run_x0 = glyph_run.offset() as f64;
                let run_x1 = run_x0 + glyph_run.advance() as f64;

                for entry in stack.iter() {
                    if entry.decoration.is_none() {
                        continue;
                    }
                    let idx = match deco_boxes.iter().position(|d| d.node_id == entry.node_id) {
                        Some(idx) => idx,
                        None => {
                            deco_boxes.push(LineDecoration {
                                node_id: entry.node_id,
                                deco: entry.decoration.clone().unwrap(),
                                min_x: f64::INFINITY,
                                max_x: f64::NEG_INFINITY,
                                own: None,
                                first: None,
                            });
                            deco_boxes.len() - 1
                        }
                    };
                    let acc = &mut deco_boxes[idx];
                    acc.min_x = acc.min_x.min(run_x0);
                    acc.max_x = acc.max_x.max(run_x1);
                    if acc.first.is_none() {
                        acc.first = Some(geometry.clone());
                    }
                    // A run whose innermost node is the box itself is the box's own text, so
                    // its font is the one Firefox positions and sizes the decoration with.
                    if entry.node_id == run_node_id {
                        acc.own = Some(geometry.clone());
                    }
                }
            }
        }

        flush_line_decorations(
            scene,
            transform,
            scale,
            deco_boxes,
            win_ascent_ratios,
            inline_root_id,
            line.metrics().baseline,
        );
    }
}

/// Draw selection highlight rectangles for the given byte range in a layout.
/// Uses Parley's Selection type for accurate geometry calculation.
pub(crate) fn draw_text_selection(
    scene: &mut impl PaintScene,
    layout: &Layout<TextBrush>,
    transform: Affine,
    selection_start: usize,
    selection_end: usize,
) {
    let anchor = Cursor::from_byte_index(layout, selection_start, Affinity::Downstream);
    let focus = Cursor::from_byte_index(layout, selection_end, Affinity::Downstream);
    let selection = Selection::new(anchor, focus);

    selection.geometry_with(layout, |rect, _line_idx| {
        let rect = kurbo::Rect::new(rect.x0, rect.y0, rect.x1, rect.y1);
        scene.fill(Fill::NonZero, transform, SELECTION_COLOR, None, &rect);
    });
}

/// Rostrum patch (round 6): how an inline run paints. `None` when its node is not `visibility: visible`
/// (inherited, so the run's own node decides); else the product of the `opacity` of the inline elements
/// from the run's node up to (not including) the inline root, whose own opacity is its layer.
pub(crate) fn inline_paint(doc: &BaseDocument, node_id: NodeId, inline_root_id: NodeId) -> Option<f32> {
    let styles = doc.get_node(node_id)?.primary_styles()?;
    if styles.get_inherited_box().visibility != style::computed_values::visibility::T::Visible {
        return None;
    }
    let mut alpha = 1.0;
    let mut cur = Some(node_id);
    while let Some(id) = cur {
        if id == inline_root_id {
            break;
        }
        let node = doc.get_node(id)?;
        if let Some(s) = node.primary_styles() {
            alpha *= s.get_effects().opacity;
        }
        cur = node.parent;
    }
    (alpha > 0.0).then_some(alpha)
}

/// `-webkit-text-stroke: <width> <color>` and `paint-order` of a run.
struct TextOutline {
    width: f32,
    color: Color,
    stroke_first: bool,
}

/// The run's outline. Rostrum patch (round 14): the run's node's cascaded `-webkit-text-stroke` and
/// `paint-order`, inherited by Stylo through the property shim (blitz_dom::css_shim), so stylesheet rules
/// count; round 6 walked the inline styles of the node's ancestors.
fn text_stroke(doc: &BaseDocument, node_id: NodeId) -> Option<TextOutline> {
    let styles = doc.get_node(node_id)?.primary_styles()?;
    let value = css_shim::value(&styles, Shim::TextStroke)?;
    // `<width> <color>` in either order; the colour may hold spaces (`rgb(0 0 0)`).
    let px = |s: &str| s.trim().strip_suffix("px").unwrap_or(s.trim()).parse::<f32>().ok();
    let (width, c) = match value.split_once(char::is_whitespace) {
        None => (px(value)?, ""),
        Some((first, rest)) => match px(first) {
            Some(w) => (w, rest.trim()),
            None => {
                let (rest, last) = value.rsplit_once(char::is_whitespace)?;
                (px(last)?, rest.trim())
            }
        },
    };
    if width <= 0.0 {
        return None;
    }
    let color = if c.is_empty() || c.eq_ignore_ascii_case("currentcolor") {
        styles.get_inherited_text().color.as_color_color()
    } else {
        color::parse_color(c).ok()?.to_alpha_color::<color::Srgb>()
    };
    let stroke_first = css_shim::value(&styles, Shim::PaintOrder).is_some_and(|o| o.starts_with("stroke"));
    Some(TextOutline { width, color, stroke_first })
}

/// Where a run's glyphs are drawn: the inline layout's transform moved by the run's spans' relative
/// offset, the synthetic-italic skew, and the synthetic-bold embolden (as stroke_text draws them).
fn run_placement(doc: &BaseDocument, glyph_run: &GlyphRun<'_, TextBrush>, transform: Affine, scale: f64, inline_root_id: NodeId) -> (Affine, Option<Affine>, kurbo::Vec2) {
    let run = glyph_run.run();
    let glyph_xform = run.synthesis().skew().map(|angle| Affine::skew(angle.to_radians().tan() as f64, 0.0));
    let embolden = if FONT_EMBOLDEN_ENABLED {
        let fs = run.font_size() as f64 / scale;
        kurbo::Vec2::new((0.015125 * fs).min(0.3), (0.0121 * fs).min(0.3))
    } else {
        kurbo::Vec2::default()
    };
    let (rx, ry) = blitz_dom::util::inline_relative_offset(doc, Some(glyph_run.style().brush.id), inline_root_id);
    (transform * Affine::translate((rx * scale, ry * scale)), glyph_xform, embolden)
}

/// Rostrum patch (round 14): an inline layout's text as an alpha mask, for `background-clip: text`
/// (render/background.rs). Every visible run's glyphs and their `-webkit-text-stroke`, in opaque black
/// times the spans' opacity, exactly where stroke_text draws them (Chrome's text-clip paint: all colours
/// black, no shadows). Decorations are not part of it.
pub(crate) fn draw_text_clip_mask<'a>(
    scene: &mut impl PaintScene,
    lines: impl Iterator<Item = Line<'a, TextBrush>>,
    doc: &BaseDocument,
    transform: Affine,
    scale: f64,
    inline_root_id: NodeId,
) {
    let black = anyrender::Paint::from(Color::BLACK);
    for line in lines {
        for item in line.items() {
            let PositionedLayoutItem::GlyphRun(glyph_run) = item else { continue };
            let node_id = glyph_run.style().brush.id;
            let Some(alpha) = inline_paint(doc, node_id, inline_root_id) else { continue };
            let run = glyph_run.run();
            let normalized_coords: &[i16] = bytemuck::cast_slice(run.normalized_coords());
            let (t, glyph_xform, embolden) = run_placement(doc, &glyph_run, transform, scale, inline_root_id);
            let glyphs = || glyph_run.positioned_glyphs().map(|g| anyrender::Glyph { id: g.id as _, x: g.x, y: g.y });
            scene.draw_glyphs(run.font(), run.font_size(), !FONT_EMBOLDEN_ENABLED, normalized_coords, embolden, Fill::NonZero, &black, alpha, t, glyph_xform, glyphs());
            if let Some(o) = text_stroke(doc, node_id) {
                let pen = Stroke::new(o.width as f64 * scale);
                scene.draw_glyphs(run.font(), run.font_size(), false, normalized_coords, embolden, &pen, &black, alpha, t, glyph_xform, glyphs());
            }
        }
    }
}

/// CSS `text-shadow` (inherited, so each run's own node carries it): the run's glyphs (and outline) in
/// the shadow's colour, offset, blurred by a layer (filters::shadow_sigma), the first shadow on top.
fn draw_text_shadows<'a>(
    scene: &mut impl PaintScene,
    lines: impl Iterator<Item = Line<'a, TextBrush>>,
    doc: &BaseDocument,
    transform: Affine,
    scale: f64,
    inline_root_id: NodeId,
) {
    for line in lines {
        for item in line.items() {
            let PositionedLayoutItem::GlyphRun(glyph_run) = item else { continue };
            let node_id = glyph_run.style().brush.id;
            let Some(styles) = doc.get_node(node_id).and_then(|n| n.primary_styles()) else { continue };
            let shadows = &styles.get_inherited_text().text_shadow.0;
            if shadows.is_empty() {
                continue;
            }
            let Some(alpha) = inline_paint(doc, node_id, inline_root_id) else { continue };
            let current_color = styles.clone_color();
            let run = glyph_run.run();
            let normalized_coords: &[i16] = bytemuck::cast_slice(run.normalized_coords());
            let glyph_xform = run.synthesis().skew().map(|angle| Affine::skew(angle.to_radians().tan() as f64, 0.0));
            let outline = text_stroke(doc, node_id);
            let (rx, ry) = blitz_dom::util::inline_relative_offset(doc, Some(node_id), inline_root_id);
            for shadow in shadows.iter().rev() {
                let color = shadow.color.resolve_to_absolute(&current_color).as_srgb_color();
                if color.components[3] == 0.0 {
                    continue;
                }
                let dx = (rx + shadow.horizontal.px() as f64) * scale;
                let dy = (ry + shadow.vertical.px() as f64) * scale;
                let t = transform * Affine::translate((dx, dy));
                let sigma = crate::filters::shadow_sigma(shadow.blur.px() as f64 * scale);
                if sigma > 0.0 {
                    let filter = anyrender::Filter::linear_list([anyrender::filters::FilterEffect::blur(sigma as f32)].into_iter());
                    scene.push_layer(Fill::NonZero, peniko::Mix::Normal, 1.0, Affine::IDENTITY, &Rect::new(-1e7, -1e7, 1e7, 1e7), Some(std::sync::Arc::new(filter)), None);
                }
                let glyphs = || glyph_run.positioned_glyphs().map(|g| anyrender::Glyph { id: g.id as _, x: g.x, y: g.y });
                let paint = anyrender::Paint::from(color);
                scene.draw_glyphs(run.font(), run.font_size(), false, normalized_coords, kurbo::Vec2::default(), Fill::NonZero, &paint, alpha, t, glyph_xform, glyphs());
                if let Some(o) = outline.as_ref() {
                    let pen = Stroke::new(o.width as f64 * scale);
                    scene.draw_glyphs(run.font(), run.font_size(), false, normalized_coords, kurbo::Vec2::default(), &pen, &paint, alpha, t, glyph_xform, glyphs());
                }
                if sigma > 0.0 {
                    scene.pop_layer();
                }
            }
        }
    }
}
