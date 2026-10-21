//! Incremental layout must give the layout a fresh page gives (serve.rs lays every frame out afresh until it
//! does): a page edited frame by frame is compared with each frame's markup laid out on its own.

use blitz_dom::{BaseDocument, DocumentConfig, NodeId};
use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};

fn page(markup: &str) -> String {
    format!("<!DOCTYPE html><html><head></head><body style=\"margin:0\"><div id=\"rostrum-stage\">{markup}</div></body></html>")
}

fn doc(markup: &str, incremental: bool) -> HtmlDocument {
    let mut d = HtmlDocument::from_html(&page(markup), DocumentConfig { viewport: Some(Viewport::new(1200, 600, 1.0, ColorScheme::Light)), incremental: Some(incremental), ..Default::default() });
    d.resolve(0.0);
    d
}

/// Every element's laid-out box (page position, size) in tree order, and each inline root's line heights.
fn dump(d: &BaseDocument) -> Vec<String> {
    let mut out = vec![];
    fn walk(d: &BaseDocument, id: NodeId, x: f32, y: f32, out: &mut Vec<String>) {
        let n = d.get_node(id).unwrap();
        let (mut x, mut y) = (x, y);
        if let Some(el) = n.element_data() {
            let l = n.final_layout();
            (x, y) = (x + l.location.x, y + l.location.y);
            let mut s = format!("{} {x:.1},{y:.1} {:.1}x{:.1}", el.name.local, l.size.width, l.size.height);
            if let Some(t) = &el.inline_layout_data {
                for line in t.layout.lines() {
                    let m = line.metrics();
                    s += &format!(" line(b{:.1} h{:.1})", m.baseline, m.line_height);
                }
            }
            out.push(s);
        }
        for &c in &n.children {
            walk(d, c, x, y, out);
        }
    }
    walk(d, d.root_node().id, 0.0, 0.0, &mut out);
    out
}

/// Applies each markup to one kept page (incremental layout) and checks it against a fresh page.
fn check(frames: &[String]) {
    let mut kept = doc(&frames[0], true);
    let stage = kept.query_selector("#rostrum-stage").unwrap().unwrap();
    let mut scratch = crate::keep::Scratch::new(DocumentConfig::default);
    for (k, m) in frames.iter().enumerate().skip(1) {
        let next = scratch.parse(m).unwrap();
        let edits = crate::keep::diff_from(&kept, &scratch.0, stage, next);
        crate::keep::apply(&mut kept, &scratch.0, &edits);
        kept.resolve(0.0);
        let fresh = doc(m, false);
        let (a, b) = (dump(&kept), dump(&fresh));
        assert_eq!(a, b, "frame {k} differs after edits from a fresh layout");
    }
}

fn letters(opacity: &[f32]) -> String {
    let word: String = "Quiet".chars().zip(opacity).map(|(c, o)| format!("<span style=\"display:inline-block;white-space:pre;transform:translate(0px, {:.2}px);opacity:{o}\">{c}</span>", 10.0 * (1.0 - o))).collect();
    format!("<div style=\"position:absolute;left:100px;top:100px;width:900px;display:flex;align-items:center;justify-content:center\"><span style=\"font-size:72px;font-weight:800\">{word}<span style=\"white-space:pre\"> </span>{word}</span></div>")
}

#[test]
fn opacity_edits_on_inline_block_letters_lay_out_as_a_fresh_page() {
    check(&[letters(&[0.0, 0.0, 0.0, 0.0, 0.0]), letters(&[0.5, 0.2, 0.0, 0.0, 0.0]), letters(&[1.0, 0.7, 0.4, 0.1, 0.0]), letters(&[1.0, 1.0, 1.0, 0.8, 0.5])]);
}
