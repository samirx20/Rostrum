//! Staging only what changed. The scene's stage comes as one piece of markup per top-level element (the background,
//! then each top-level layer: scene/stage.rs `parts`). The pieces the kept stage was made from are remembered; the next
//! frame parses only the pieces that differ and walks each beside its kept element (keep.rs), so a frame where 26 of
//! 200 layers move parses and walks 26, not 200. The page drawn is the same as staging it whole (the same kept document
//! and edits), so preview and export stay one path. Whenever the pieces don't line up one-to-one with the kept stage's
//! children, the frame is staged whole. A changed piece whose tags stayed the same (only values moved, as between
//! motion-blur samples) is not parsed at all: retext.rs turns its text into the edits directly.

use blitz_dom::{BaseDocument, NodeData};
use blitz_traits::node_id::NodeId;

use crate::keep::{self, Edits, Scratch};
use crate::retext;
use crate::stage_profile as prof;

const LOST: &str = "stage markup lost its container";

/// The pieces the kept stage was staged from, when its children are exactly one element per piece.
#[derive(Default)]
pub struct Kept(Option<Vec<String>>);

/// The edits that turn the kept stage into `markup`'s. `pieces`: the same markup cut per top-level element, when the
/// caller has it (a scene's frame or motion-blur sample); without them (a raw stage) the frame is staged whole.
pub fn edits(kept: &BaseDocument, stage: NodeId, scratch: &mut Scratch, last: &mut Kept, pieces: Option<Vec<String>>, markup: &str) -> Result<Edits, String> {
    let pieces = pieces.filter(|p| spells(p, markup));
    if let (Some(p), Some(old)) = (&pieces, last.0.take()) {
        if p.len() == old.len() {
            let changed: Vec<usize> = (0..p.len()).filter(|&i| p[i] != old[i]).collect();
            let old_kids = kept.get_node(stage).ok_or(LOST)?.children.clone();
            prof::note(prof::PIECES, p.len() as f64);
            prof::note(prof::CHANGED, changed.len() as f64);
            // Pieces whose tags stayed the same become edits straight from their text (retext.rs); the rest are parsed.
            let t = std::time::Instant::now();
            let mut e = Edits::default();
            let parse: Vec<usize> = changed.into_iter().filter(|&i| old_kids.len() != p.len() || retext::edits(kept, old_kids[i], &old[i], &p[i], &mut e).is_none()).collect();
            prof::note(prof::RETEXT, t.elapsed().as_secs_f64() * 1000.0);
            let t = std::time::Instant::now();
            let text = parse.iter().map(|&i| p[i].as_str()).collect::<String>();
            prof::note(prof::BYTES, text.len() as f64);
            let parsed = if parse.is_empty() {
                Some(Edits::default())
            } else {
                let next = scratch.parse(&text).ok_or(LOST)?;
                let new_kids = elements(&scratch.0, next, parse.len());
                new_kids.and_then(|n| keep::diff_pairs(kept, &scratch.0, parse.iter().map(|&i| old_kids[i]).zip(n)))
            };
            prof::note(prof::PARSE, t.elapsed().as_secs_f64() * 1000.0);
            if let Some(more) = parsed {
                e.attrs.extend(more.attrs);
                e.removed_attrs.extend(more.removed_attrs);
                e.texts.extend(more.texts);
                e.rebuilt.extend(more.rebuilt);
                last.0 = pieces;
                return Ok(e);
            }
        }
    }
    let t = std::time::Instant::now();
    let next = scratch.parse(markup).ok_or(LOST)?;
    prof::note(prof::BYTES, markup.len() as f64);
    prof::note(prof::PARSE, t.elapsed().as_secs_f64() * 1000.0);
    let e = keep::diff_from(kept, &scratch.0, stage, next);
    last.0 = pieces.filter(|p| elements(&scratch.0, next, p.len()).is_some());
    Ok(e)
}

/// The pieces, in order, are exactly the markup.
fn spells(pieces: &[String], markup: &str) -> bool {
    let mut rest = markup;
    for p in pieces {
        match rest.strip_prefix(p.as_str()) {
            Some(r) => rest = r,
            None => return false,
        }
    }
    rest.is_empty()
}

/// The node's children, when they are exactly `n` elements (no text or other nodes between).
fn elements(doc: &BaseDocument, node: NodeId, n: usize) -> Option<Vec<NodeId>> {
    let kids = &doc.get_node(node)?.children;
    let all = kids.iter().all(|&k| matches!(doc.get_node(k).map(|k| &k.data), Some(NodeData::Element(_))));
    (kids.len() == n && all).then(|| kids.to_vec())
}
