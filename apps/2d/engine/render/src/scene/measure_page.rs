//! The page `measure` lays its texts out in (measure.rs), kept between requests. Making a page per request read,
//! encoded and parsed every font file again and set up a new document: 60–90 ms for one short text, on every key
//! typed into a new text. The page is made once per set of faces and its stage restaged per request as a frame's is
//! (restage.rs and keep.rs, the frame server's way, whose edited pages are checked against fresh ones), so the sizes
//! are the ones a fresh page gives. Another set of faces makes a new page; one whose fonts failed is never kept.
//! Kept per thread (a document can't be shared between threads; the engine measures on its request thread).

use std::path::PathBuf;

use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::node_id::NodeId;

use super::{fonts::Font, stage};
use crate::assets::Assets;
use crate::{keep, restage};

type R<T> = Result<T, String>;

/// What the page shell embeds of each face (stage.rs `shell`): a page is kept for exactly these.
type Faces = Vec<(String, PathBuf, u32, (f32, f32), bool, bool)>;

fn faces(fonts: &[Font]) -> Faces {
    fonts.iter().map(|f| (f.family.clone(), f.path.clone(), f.index, f.weight, f.variable, f.italic)).collect()
}

struct Page {
    faces: Faces,
    size: u32,
    doc: HtmlDocument,
    stage: NodeId,
    assets: Assets,
    scratch: keep::Scratch,
    kept: restage::Kept,
}

thread_local! {
    static KEPT: std::cell::RefCell<Option<Page>> = const { std::cell::RefCell::new(None) };
}

fn failures(assets: &Assets) -> R<()> {
    let failed = std::mem::take(&mut *assets.failures.lock().unwrap());
    if failed.is_empty() {
        return Ok(());
    }
    Err(format!("measure: {} font(s) failed to load: {}", failed.len(), failed.join("; ")))
}

fn page(fonts: &[Font], size: u32) -> R<Page> {
    let assets = Assets::default();
    let mut doc = HtmlDocument::from_html(&stage::shell(size, size, fonts)?, crate::serve::page_config(size, size, &assets));
    doc.handle_messages();
    doc.resolve(0.0);
    failures(&assets)?;
    let stage = doc.query_selector("#rostrum-stage").ok().flatten().ok_or("measure: the page shell has no empty stage to fill")?;
    let scratch = keep::Scratch::new(|| DocumentConfig { base_url: Some(crate::assets::BASE_URL.into()), ..Default::default() });
    Ok(Page { faces: faces(fonts), size, doc, stage, assets, scratch, kept: Default::default() })
}

/// `read` of the page with the faces `fonts`, `size` px square, laid out with `markup` on its stage.
pub fn lay_out<T>(fonts: &[Font], size: u32, markup: &str, read: impl FnOnce(&HtmlDocument) -> R<T>) -> R<T> {
    KEPT.with_borrow_mut(|kept| {
        if !kept.as_ref().is_some_and(|p| p.size == size && p.faces == faces(fonts)) {
            *kept = None;
            *kept = Some(page(fonts, size)?);
        }
        let p = kept.as_mut().unwrap();
        let staged = (|| {
            let edits = restage::edits(&p.doc, p.stage, &mut p.scratch, &mut p.kept, None, markup)?;
            keep::apply(&mut p.doc, &p.scratch.0, &edits);
            p.doc.handle_messages();
            p.doc.resolve(0.0);
            failures(&p.assets)
        })();
        if let Err(e) = staged {
            *kept = None;
            return Err(e);
        }
        read(&p.doc)
    })
}

#[cfg(test)]
mod tests {
    use serde_json::{json, Value};

    fn text(body: &str, font: &str, size: f64, box_width: f64) -> Value {
        json!({ "id": "t", "body": body, "font": font, "size": size, "weight": 400, "stretch": 100, "tracking": 0.02,
                "lineHeight": 1.2, "align": "left", "boxWidth": box_width })
    }

    /// Sizes from the kept page (edited request after request) are the sizes a fresh page gives.
    #[test]
    fn a_kept_page_measures_as_a_fresh_one() {
        let long = "The quick brown fox jumps over the lazy dog, again and again, until it wraps.";
        let asks = [text("Hello", "Roboto Flex", 96.0, 0.0), text(long, "Roboto Flex", 40.0, 300.0), text("Hi", "Roboto Flex", 40.0, 300.0),
            text(long, "Fraunces", 24.0, 0.0), text("Hello", "Roboto Flex", 96.0, 0.0)];
        let kept: Vec<Value> = asks.iter().map(|a| super::super::measure::measure(&json!({ "items": [a] }), None).unwrap()).collect();
        for (a, k) in asks.iter().zip(&kept) {
            super::KEPT.with_borrow_mut(|p| *p = None);
            assert_eq!(&super::super::measure::measure(&json!({ "items": [a] }), None).unwrap(), k, "{a}");
        }
    }
}
