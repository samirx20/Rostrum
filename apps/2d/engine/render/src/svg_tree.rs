//! `rostrum2d-render svg-tree <in.svg> <images folder>`: an SVG read by usvg (Apache-2.0 / MIT, our vendored copy)
//! and written as plain JSON on stdout for the Python importer (rostrum2d/io/svg.py). usvg resolves CSS, `use`,
//! units and shapes, so every path comes out as absolute M L C Z in the document's px (its transforms applied) and
//! every group keeps its opacity and blend. Embedded pictures are written into the images folder. What the tree
//! can't say plainly (gradients, patterns, clips, masks, filters, turned text) is named in a node's `notes`.
//!
//! `{"width", "height", "layers": [node, …]}`, bottom first; node:
//!   group `{"type", "id", "opacity", "blend", "layers", "notes"}`
//!   path  `{"type", "id", "d", "bbox": [x, y, w, h], "fill": {"color", "opacity", "rule"} | null,
//!           "stroke": {"color", "opacity", "width", "cap", "join", "miter", "dash"} | null, "notes"}`
//!   text  `{"type", "id", "text", "font", "size", "weight", "color", "opacity", "bbox", "outline": d, "notes"}`
//!   image `{"type", "id", "file", "bbox", "notes"}`

use std::fmt::Write as _;
use std::path::{Path, PathBuf};

use serde_json::{json, Value};
use usvg::tiny_skia_path::{PathSegment, Transform};

pub fn run(args: &[String]) {
    let (Some(src), Some(dir)) = (args.first(), args.get(1)) else {
        eprintln!("usage: rostrum2d-render svg-tree <in.svg> <images folder>");
        std::process::exit(2);
    };
    match tree(Path::new(src), Path::new(dir)) {
        Ok(v) => println!("{v}"),
        Err(e) => {
            eprintln!("svg-tree: {e}");
            std::process::exit(1);
        }
    }
}

fn tree(src: &Path, dir: &Path) -> Result<Value, String> {
    let data = std::fs::read(src).map_err(|e| format!("{}: {e}", src.display()))?;
    let mut opt = usvg::Options { resources_dir: src.parent().map(Path::to_path_buf), ..Default::default() };
    // The app's fonts first (what the 2D layers can name), then the system's, so text lays out as the SVG asks.
    if let Ok(d) = crate::scene::fonts::app_folder() {
        opt.fontdb_mut().load_fonts_dir(d);
    }
    opt.fontdb_mut().load_system_fonts();
    let t = usvg::Tree::from_data(&data, &opt).map_err(|e| format!("{}: {e}", src.display()))?;
    std::fs::create_dir_all(dir).map_err(|e| format!("{}: {e}", dir.display()))?;
    let mut w = Walk { dir: dir.to_path_buf(), images: 0 };
    let layers = w.children(t.root())?;
    Ok(json!({ "width": t.size().width(), "height": t.size().height(), "layers": layers }))
}

struct Walk {
    dir: PathBuf,
    images: usize,
}

impl Walk {
    fn children(&mut self, g: &usvg::Group) -> Result<Vec<Value>, String> {
        g.children().iter().map(|n| self.node(n)).collect::<Result<Vec<_>, _>>().map(|v| v.into_iter().flatten().collect())
    }

    fn node(&mut self, n: &usvg::Node) -> Result<Option<Value>, String> {
        Ok(Some(match n {
            usvg::Node::Group(g) => {
                let mut notes = vec![];
                if g.clip_path().is_some() {
                    notes.push("a clip path");
                }
                if g.mask().is_some() {
                    notes.push("a mask");
                }
                if !g.filters().is_empty() {
                    notes.push("a filter");
                }
                json!({ "type": "group", "id": g.id(), "opacity": g.opacity().get(), "blend": format!("{:?}", g.blend_mode()).to_lowercase(),
                        "layers": self.children(g)?, "notes": notes })
            }
            usvg::Node::Path(p) if !p.is_visible() => return Ok(None),
            usvg::Node::Path(p) => {
                let ts = p.abs_transform();
                let mut notes = vec![];
                let fill = p.fill().map(|f| json!({ "color": paint(f.paint(), &mut notes), "opacity": f.opacity().get(),
                                                  "rule": if f.rule() == usvg::FillRule::EvenOdd { "evenodd" } else { "nonzero" } }));
                let stroke = p.stroke().map(|s| json!({ "color": paint(s.paint(), &mut notes), "opacity": s.opacity().get(),
                    "width": s.width().get() * scale(ts), "cap": format!("{:?}", s.linecap()).to_lowercase(),
                    "join": match s.linejoin() { usvg::LineJoin::Round => "round", usvg::LineJoin::Bevel => "bevel", _ => "miter" },
                    "miter": s.miterlimit().get(), "dash": s.dasharray().map(|d| d.iter().map(|x| x * scale(ts)).collect::<Vec<_>>()) }));
                json!({ "type": "path", "id": p.id(), "d": d(p.data(), ts), "bbox": rect(p.abs_bounding_box()), "fill": fill, "stroke": stroke, "notes": notes })
            }
            usvg::Node::Text(t) => {
                let ts = t.abs_transform();
                let mut notes = vec![];
                if ts.kx.abs() > 1e-4 || ts.ky.abs() > 1e-4 {
                    notes.push("turned or slanted text (placed upright)".to_string());
                }
                let chunks = t.chunks();
                let span = chunks.iter().flat_map(|c| c.spans()).next();
                let text: String = chunks.iter().map(|c| c.text()).collect::<Vec<_>>().join("\n");
                let fill = span.and_then(|s| s.fill());
                let mut outline = String::new();
                flat(t.flattened(), &mut outline);
                json!({ "type": "text", "id": t.id(), "text": text,
                        "font": span.and_then(|s| s.font().families().first()).map(family),
                        "size": span.map(|s| s.font_size().get() * scale(ts)), "weight": span.map(|s| s.font().weight()),
                        "color": fill.map(|f| paint(f.paint(), &mut notes)), "opacity": fill.map(|f| f.opacity().get()),
                        "bbox": rect(t.abs_bounding_box()), "outline": outline, "notes": notes })
            }
            usvg::Node::Image(i) if !i.is_visible() => return Ok(None),
            usvg::Node::Image(i) => {
                let (ext, bytes) = match i.kind() {
                    usvg::ImageKind::PNG(b) => ("png", b),
                    usvg::ImageKind::JPEG(b) => ("jpg", b),
                    usvg::ImageKind::GIF(b) => ("gif", b),
                    usvg::ImageKind::WEBP(b) => ("webp", b),
                    usvg::ImageKind::SVG(_) => return Ok(Some(json!({ "type": "image", "id": i.id(), "file": null, "bbox": rect(i.abs_bounding_box()), "notes": ["an SVG inside an SVG (not imported)"] }))),
                };
                self.images += 1;
                let file = self.dir.join(format!("image_{}.{ext}", self.images));
                std::fs::write(&file, bytes.as_slice()).map_err(|e| format!("{}: {e}", file.display()))?;
                json!({ "type": "image", "id": i.id(), "file": file, "bbox": rect(i.abs_bounding_box()), "notes": [] })
            }
        }))
    }
}

/// A family's plain name (`Display` quotes named families).
fn family(f: &usvg::FontFamily) -> String {
    match f {
        usvg::FontFamily::Named(n) => n.clone(),
        other => other.to_string(),
    }
}

/// A text's glyph outlines (its flattened group) as one path in document px.
fn flat(g: &usvg::Group, out: &mut String) {
    for n in g.children() {
        match n {
            usvg::Node::Group(g) => flat(g, out),
            usvg::Node::Path(p) => out.push_str(&d(p.data(), p.abs_transform())),
            _ => {}
        }
    }
}

/// How much a transform scales lengths (a stroke width, a font size): the square root of its area scale.
fn scale(ts: Transform) -> f32 {
    (ts.sx * ts.sy - ts.kx * ts.ky).abs().sqrt()
}

fn rect(r: usvg::Rect) -> [f32; 4] {
    [r.x(), r.y(), r.width(), r.height()]
}

/// A colour as #rrggbb; a gradient or pattern as its first colour, named in `notes`.
fn paint(p: &usvg::Paint, notes: &mut Vec<String>) -> String {
    let c = match p {
        usvg::Paint::Color(c) => *c,
        usvg::Paint::LinearGradient(g) => first(g.stops(), "a linear gradient", notes),
        usvg::Paint::RadialGradient(g) => first(g.stops(), "a radial gradient", notes),
        usvg::Paint::Pattern(_) => {
            notes.push("a pattern fill (drawn grey)".into());
            usvg::Color::new_rgb(128, 128, 128)
        }
    };
    format!("#{:02x}{:02x}{:02x}", c.red, c.green, c.blue)
}

fn first(stops: &[usvg::Stop], what: &str, notes: &mut Vec<String>) -> usvg::Color {
    notes.push(format!("{what} (drawn in its first colour)"));
    stops.first().map(|s| s.color()).unwrap_or_else(usvg::Color::black)
}

/// Path data through `ts`, absolute M L C Z only (a quadratic becomes its exact cubic).
fn d(path: &usvg::tiny_skia_path::Path, ts: Transform) -> String {
    let mut s = String::new();
    let Some(p) = path.clone().transform(ts) else { return s };
    let mut last = (0.0f32, 0.0f32);
    for seg in p.segments() {
        let _ = match seg {
            PathSegment::MoveTo(a) => { last = (a.x, a.y); write!(s, "M{:.3} {:.3} ", a.x, a.y) }
            PathSegment::LineTo(a) => { last = (a.x, a.y); write!(s, "L{:.3} {:.3} ", a.x, a.y) }
            PathSegment::QuadTo(q, a) => {
                let (c1, c2) = ((last.0 + 2.0 / 3.0 * (q.x - last.0), last.1 + 2.0 / 3.0 * (q.y - last.1)), (a.x + 2.0 / 3.0 * (q.x - a.x), a.y + 2.0 / 3.0 * (q.y - a.y)));
                last = (a.x, a.y);
                write!(s, "C{:.3} {:.3} {:.3} {:.3} {:.3} {:.3} ", c1.0, c1.1, c2.0, c2.1, a.x, a.y)
            }
            PathSegment::CubicTo(b, c, a) => { last = (a.x, a.y); write!(s, "C{:.3} {:.3} {:.3} {:.3} {:.3} {:.3} ", b.x, b.y, c.x, c.y, a.x, a.y) }
            PathSegment::Close => write!(s, "Z "),
        };
    }
    s.trim_end().to_string()
}
