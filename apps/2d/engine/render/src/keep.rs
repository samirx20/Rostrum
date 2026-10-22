//! The kept document: the page is parsed once; every later frame becomes edits to it (changed attributes
//! and text; a subtree whose shape changed is rebuilt), then a restyle of what changed. The edits are
//! found by walking the next frame's stage markup beside the kept stage.

use blitz_dom::{Attribute, BaseDocument, DocumentMutator, Node, NodeData};
use blitz_traits::node_id::NodeId;

#[derive(Default, Debug)]
pub struct Edits {
    pub attrs: Vec<(NodeId, Attribute)>,
    pub removed_attrs: Vec<(NodeId, Attribute)>,
    pub texts: Vec<(NodeId, String)>,
    /// Old node whose children are replaced by copies of the new node's children.
    pub rebuilt: Vec<(NodeId, NodeId)>,
}

impl Edits {
    pub fn count(&self) -> usize {
        self.attrs.len() + self.removed_attrs.len() + self.texts.len() + self.rebuilt.len()
    }
}

fn same_shape(a: &Node, b: &Node) -> bool {
    match (&a.data, &b.data) {
        (NodeData::Element(x), NodeData::Element(y)) => x.name == y.name,
        (NodeData::Text(_), NodeData::Text(_)) | (NodeData::Comment { .. }, NodeData::Comment { .. }) => true,
        _ => false,
    }
}

/// The edits that turn the subtree at `o` (kept) into the one at `n` (this frame's parse).
pub fn diff_from(old: &BaseDocument, new: &BaseDocument, o: NodeId, n: NodeId) -> Edits {
    let mut edits = Edits::default();
    walk(old, new, o, n, &mut edits);
    edits
}

/// The edits that turn each kept node into its new one, pair by pair (restage.rs); None when a pair isn't the same kind
/// of node (the caller stages the whole page instead).
pub fn diff_pairs(old: &BaseDocument, new: &BaseDocument, pairs: impl IntoIterator<Item = (NodeId, NodeId)>) -> Option<Edits> {
    let mut edits = Edits::default();
    for (o, n) in pairs {
        if !same_shape(old.get_node(o)?, new.get_node(n)?) {
            return None;
        }
        walk(old, new, o, n, &mut edits);
    }
    Some(edits)
}

fn walk(old: &BaseDocument, new: &BaseDocument, o: NodeId, n: NodeId, edits: &mut Edits) {
    let (on, nn) = (old.get_node(o).unwrap(), new.get_node(n).unwrap());
    match (&on.data, &nn.data) {
        (NodeData::Element(oe), NodeData::Element(ne)) => {
            for a in ne.attrs() {
                if oe.attrs().iter().find(|b| b.name == a.name).is_none_or(|b| b.value != a.value) {
                    edits.attrs.push((o, a.clone()));
                }
            }
            for b in oe.attrs() {
                if !ne.attrs().iter().any(|a| a.name == b.name) {
                    edits.removed_attrs.push((o, b.clone()));
                }
            }
        }
        (NodeData::Text(ot), NodeData::Text(nt)) => {
            if ot.content != nt.content {
                edits.texts.push((o, nt.content.clone()));
            }
            return;
        }
        _ => {}
    }
    let (oc, nc) = (&on.children, &nn.children);
    let shape_kept = oc.len() == nc.len() && oc.iter().zip(nc).all(|(&a, &b)| same_shape(old.get_node(a).unwrap(), new.get_node(b).unwrap()));
    if !shape_kept {
        edits.rebuilt.push((o, n));
        return;
    }
    for (&a, &b) in oc.iter().zip(nc) {
        walk(old, new, a, b, edits);
    }
}

/// Copies `n` (from the new frame's parse) into the kept document; returns the copy's id.
fn copy(m: &mut DocumentMutator, new: &BaseDocument, n: NodeId) -> Option<NodeId> {
    let node = new.get_node(n)?;
    let id = match &node.data {
        NodeData::Element(e) => m.create_element(e.name.clone(), e.attrs().to_vec()),
        NodeData::Text(t) => m.create_text_node(&t.content),
        NodeData::Comment { .. } => m.create_comment_node(""),
        _ => return None,
    };
    let children: Vec<NodeId> = node.children.iter().filter_map(|&c| copy(m, new, c)).collect();
    m.append_children(id, &children);
    Some(id)
}

/// Applies the edits to the kept document (the restyle happens at its next resolve).
pub fn apply(kept: &mut BaseDocument, new: &BaseDocument, edits: &Edits) {
    let mut m = kept.mutate();
    for (id, a) in &edits.attrs {
        m.set_attribute(*id, a.name.clone(), &a.value);
    }
    for (id, a) in &edits.removed_attrs {
        m.clear_attribute(*id, a.name.clone());
    }
    for (id, text) in &edits.texts {
        m.set_node_text(*id, text);
    }
    for &(o, n) in &edits.rebuilt {
        let children: Vec<NodeId> = new.get_node(n).unwrap().children.iter().filter_map(|&c| copy(&mut m, new, c)).collect();
        m.remove_and_drop_all_children(o);
        m.append_children(o, &children);
    }
    m.flush();
}

/// The page a frame's stage markup is parsed into (serve.rs): one document kept for the render and parsed
/// afresh each frame with the parser a new document uses (making a document per frame, Stylo's set-up,
/// cost more than parsing the markup). Returns the stage node.
pub struct Scratch(pub blitz_html::HtmlDocument);

impl Scratch {
    fn page(markup: &str) -> String {
        format!("<!DOCTYPE html><html><head></head><body><div id=\"rostrum-stage\">{markup}</div></body></html>")
    }

    pub fn new(config: impl Fn() -> blitz_dom::DocumentConfig) -> Self {
        Scratch(blitz_html::HtmlDocument::from_html(&Self::page(""), config()))
    }

    pub fn parse(&mut self, markup: &str) -> Option<NodeId> {
        let root = self.0.root_node().id;
        {
            let mut m = self.0.mutate();
            m.remove_and_drop_all_children(root);
            blitz_html::DocumentHtmlParser::parse_into_mutator(&mut m, &Self::page(markup));
        }
        self.0.query_selector("#rostrum-stage").ok().flatten()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use blitz_dom::DocumentConfig;

    #[test]
    fn a_reused_scratch_page_parses_each_frame_as_a_new_page_does() {
        let mut scratch = Scratch::new(DocumentConfig::default);
        for m in ["<div class=\"a\" style=\"opacity:0.5\"><span>hi</span> there</div><p>x</p>", "<p>y<b>z</b></p><svg viewBox=\"0 0 4 4\"><path d=\"M0 0L4 4\"></path></svg>", ""] {
            let st = scratch.parse(m).unwrap();
            let fresh = blitz_html::HtmlDocument::from_html(&Scratch::page(m), DocumentConfig::default());
            let fs = fresh.query_selector("#rostrum-stage").unwrap().unwrap();
            assert_eq!(diff_from(&scratch.0, &fresh, st, fs).count(), 0, "{m}");
            assert_eq!(scratch.0.get_node(st).unwrap().children.len(), fresh.get_node(fs).unwrap().children.len());
        }
    }
}
