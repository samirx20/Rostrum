//! A changed piece staged without parsing it (E17). Between motion-blur samples nearly every piece changes, but
//! mostly only its numbers (a transform, an opacity, a path's `d`): the same tags, the same attributes, other values.
//! Parsing each one again cost ~30 ms a sample on Night Bloom (650 KB of markup). Here the old and new piece are read
//! side by side as plain tag text; when they have the same tags and attribute names in the same order, the new values
//! become edits on the kept element they belong to, found by walking the kept piece in document order (the order the
//! parser made it in). The edits are the ones keep.rs's walk would make, so the page is the same. Anything this
//! reader doesn't handle exactly as the HTML parser does (other entities, unquoted values, raw-text elements, a
//! carriage return) or a kept piece that doesn't line up answers None, and restage.rs parses that piece as before.

use blitz_dom::{Attribute, BaseDocument, NodeData};
use blitz_traits::node_id::NodeId;

use crate::keep::Edits;

#[derive(PartialEq)]
enum Tok<'a> {
    Open(&'a str, Vec<(&'a str, &'a str)>, bool),
    Close(&'a str),
    Text(&'a str),
    Comment,
}

/// Elements whose content the parser reads differently (raw text, a dropped first newline).
const SPECIAL: [&str; 12] = ["style", "script", "textarea", "title", "xmp", "iframe", "noembed", "noframes", "noscript", "plaintext", "pre", "listing"];

fn tokens(s: &str) -> Option<Vec<Tok<'_>>> {
    let mut out = vec![];
    let mut rest = s;
    while !rest.is_empty() {
        if let Some(r) = rest.strip_prefix("<!--") {
            rest = &r[r.find("-->")? + 3..];
            out.push(Tok::Comment);
        } else if let Some(r) = rest.strip_prefix("</") {
            let end = r.find('>')?;
            out.push(Tok::Close(&r[..end]));
            rest = &r[end + 1..];
        } else if let Some(r) = rest.strip_prefix('<') {
            let end = r.find(|c: char| c.is_ascii_whitespace() || c == '>' || c == '/').unwrap_or(r.len());
            let name = &r[..end];
            if name.is_empty() || !name.starts_with(|c: char| c.is_ascii_alphabetic()) || SPECIAL.iter().any(|n| n.eq_ignore_ascii_case(name)) {
                return None;
            }
            let (mut r, mut attrs) = (&r[end..], vec![]);
            let closed = loop {
                r = r.trim_start_matches(|c: char| c.is_ascii_whitespace());
                if let Some(x) = r.strip_prefix("/>") {
                    r = x;
                    break true;
                }
                if let Some(x) = r.strip_prefix('>') {
                    r = x;
                    break false;
                }
                let n = r.find(|c: char| c.is_ascii_whitespace() || c == '=' || c == '>' || c == '/').filter(|&n| n > 0)?;
                let key = &r[..n];
                r = &r[n..];
                let value = match r.strip_prefix("=\"") {
                    Some(x) => {
                        let q = x.find('"')?;
                        r = &x[q + 1..];
                        &x[..q]
                    }
                    None if r.starts_with('=') => return None, // unquoted or single-quoted: parsed as before
                    None => "",
                };
                attrs.push((key, value));
            };
            out.push(Tok::Open(name, attrs, closed));
            rest = r;
        } else {
            let end = rest.find('<').unwrap_or(rest.len());
            out.push(Tok::Text(&rest[..end]));
            rest = &rest[end..];
        }
    }
    Some(out)
}

/// The text as the parser stores it: the entities stage.rs `escape` writes, and numeric ones.
fn decode(s: &str) -> Option<String> {
    if s.contains(['\r', '\0']) {
        return None;
    }
    let mut out = String::with_capacity(s.len());
    let mut rest = s;
    while let Some(at) = rest.find('&') {
        out += &rest[..at];
        let r = &rest[at + 1..];
        let end = r.find(';')?;
        let c = match &r[..end] {
            "amp" => '&',
            "lt" => '<',
            "gt" => '>',
            "quot" => '"',
            "apos" => '\'',
            e => match e.strip_prefix("#x").or(e.strip_prefix("#X")) {
                Some(h) => char::from_u32(u32::from_str_radix(h, 16).ok()?).filter(|&c| plain(c))?,
                None => char::from_u32(e.strip_prefix('#')?.parse().ok()?).filter(|&c| plain(c))?,
            },
        };
        out.push(c);
        rest = &r[end + 1..];
    }
    out += rest;
    Some(out)
}

/// A numeric entity the parser keeps as written (it remaps control codes and 0x80 to 0x9F).
fn plain(c: char) -> bool {
    c >= ' ' && !('\u{7f}'..='\u{9f}').contains(&c)
}

/// Same tags, attribute names and comment places; values and texts may differ.
fn same_skeleton(a: &[Tok], b: &[Tok]) -> bool {
    a.len() == b.len()
        && a.iter().zip(b).all(|(x, y)| match (x, y) {
            (Tok::Open(n, xa, xc), Tok::Open(m, ya, yc)) => n == m && xc == yc && xa.len() == ya.len() && xa.iter().zip(ya).all(|(p, q)| p.0 == q.0),
            (Tok::Text(_), Tok::Text(_)) => true,
            _ => x == y,
        })
}

/// The kept piece's nodes in document order.
fn preorder(doc: &BaseDocument, id: NodeId, out: &mut Vec<NodeId>) {
    out.push(id);
    for &c in doc.get_node(id).map_or(&[][..], |n| &n.children[..]) {
        preorder(doc, c, out);
    }
}

/// The edits that turn the kept piece at `kept_id` (staged from `old`) into `new`, without parsing; None when it
/// can't be done exactly (restage.rs then parses `new`).
pub fn edits(kept: &BaseDocument, kept_id: NodeId, old: &str, new: &str, out: &mut Edits) -> Option<()> {
    let (a, b) = (tokens(old)?, tokens(new)?);
    if !same_skeleton(&a, &b) {
        return None;
    }
    let mut nodes = vec![];
    preorder(kept, kept_id, &mut nodes);
    let mut nodes = nodes.into_iter();
    let mut found = Edits::default();
    for (x, y) in a.iter().zip(&b) {
        match (x, y) {
            (Tok::Close(_), _) => continue,
            (Tok::Comment, _) => {
                let n = kept.get_node(nodes.next()?)?;
                matches!(n.data, NodeData::Comment { .. }).then_some(())?;
            }
            (Tok::Text(xt), Tok::Text(yt)) => {
                let id = nodes.next()?;
                let NodeData::Text(t) = &kept.get_node(id)?.data else { return None };
                let (xd, yd) = (decode(xt)?, decode(yt)?);
                if t.content != xd || yd.is_empty() {
                    return None;
                }
                if xd != yd {
                    found.texts.push((id, yd));
                }
            }
            (Tok::Open(name, xa, _), Tok::Open(_, ya, _)) => {
                let id = nodes.next()?;
                let NodeData::Element(e) = &kept.get_node(id)?.data else { return None };
                if !(*e.name.local).eq_ignore_ascii_case(name) || e.attrs().len() != xa.len() {
                    return None;
                }
                for (i, (p, q)) in xa.iter().zip(ya).enumerate() {
                    let held: &Attribute = &e.attrs()[i];
                    if !(*held.name.local).eq_ignore_ascii_case(p.0) {
                        return None;
                    }
                    if p.1 != q.1 {
                        found.attrs.push((id, Attribute { name: held.name.clone(), value: decode(q.1)? }));
                    }
                }
            }
            _ => return None,
        }
    }
    nodes.next().is_none().then_some(())?;
    out.attrs.extend(found.attrs);
    out.texts.extend(found.texts);
    Some(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::keep::{diff_from, Scratch};
    use blitz_dom::DocumentConfig;

    fn sorted(e: &Edits) -> Vec<String> {
        let mut v: Vec<String> = e.attrs.iter().map(|(id, a)| format!("{id:?} {} {}", a.name.local, a.value)).chain(e.texts.iter().map(|(id, t)| format!("{id:?} text {t}"))).collect();
        v.sort();
        v
    }

    #[test]
    fn edits_from_text_are_the_ones_parsing_finds() {
        let pairs = [
            (r#"<div style="transform:translate(1px,2px)" class="a"><span>A&amp;B</span> x<svg viewBox="0 0 4 4"><path d="M0 0L4 4"/></svg></div>"#,
             r#"<div style="transform:translate(3px,2px)" class="a"><span>A&lt;B&#233;</span> y<svg viewBox="0 0 8 4"><path d="M1 0L4 4"/></svg></div>"#),
            (r#"<div><!-- c --><p data-x="&quot;1&quot;">t</p></div>"#, r#"<div><!-- c --><p data-x="&quot;2&quot;">u</p></div>"#),
        ];
        for (old, new) in pairs {
            let mut kept = Scratch::new(DocumentConfig::default);
            let st = kept.parse(old).unwrap();
            let piece = kept.0.get_node(st).unwrap().children[0];
            let mut from_text = Edits::default();
            edits(&kept.0, piece, old, new, &mut from_text).expect(old);
            let mut fresh = Scratch::new(DocumentConfig::default);
            let ns = fresh.parse(new).unwrap();
            let parsed = diff_from(&kept.0, &fresh.0, st, ns);
            assert_eq!(parsed.rebuilt.len() + parsed.removed_attrs.len(), 0);
            assert_eq!(sorted(&from_text), sorted(&parsed), "{old}");
        }
        // Not handled exactly: left to the parser.
        let mut kept = Scratch::new(DocumentConfig::default);
        let st = kept.parse("<p a=1>x</p>").unwrap();
        let piece = kept.0.get_node(st).unwrap().children[0];
        assert!(edits(&kept.0, piece, "<p a=1>x</p>", "<p a=2>x</p>", &mut Edits::default()).is_none());
        assert!(edits(&kept.0, piece, "<p a=1>x</p>", "<p a=1><b>x</b></p>", &mut Edits::default()).is_none());
    }
}
