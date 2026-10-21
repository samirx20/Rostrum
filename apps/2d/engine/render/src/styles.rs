//! Each element's author-declared CSS, as the renderer computes it (`rostrum2d-render styles`): the host's one
//! source of what a `className` means (src/engine/stage/classStyles.ts). Reads `{ html, ids: [id, …] }` on
//! stdin (a page: the stage's CSS, the document's Tailwind CSS and one element per class set) and writes
//! `{ id: { property: computed value } }`: every longhand an author rule declares on `#id` (the cascade's own
//! rule nodes, so a class that sets a property to its initial value counts too), serialised by Stylo as
//! `getComputedStyle` does (lengths in px, colours as rgb()). Nothing is laid out or painted.

use std::collections::BTreeMap;
use std::io::Read as _;
use std::sync::Arc;

use blitz_html::HtmlDocument;
use blitz_traits::shell::{ColorScheme, Viewport};
use serde_json::{Map, Value};
use style::properties::PropertyDeclarationId;
use style::rule_tree::CascadeOrigin;

pub fn run() {
    let mut input = String::new();
    std::io::stdin().read_to_string(&mut input).expect("stdin");
    let req: Value = serde_json::from_str(&input).expect("styles: a JSON request on stdin");
    let config = blitz_dom::DocumentConfig { viewport: Some(Viewport::new(1920, 1080, 1.0, ColorScheme::Light)), base_url: Some(crate::assets::BASE_URL.into()), net_provider: Some(Arc::new(crate::assets::Assets::default())), ..Default::default() };
    let mut doc = HtmlDocument::from_html(req["html"].as_str().unwrap_or(""), config);
    doc.handle_messages();
    doc.resolve(0.0);
    let guard = doc.guard().read();
    let mut out = Map::new();
    for id in req["ids"].as_array().into_iter().flatten().filter_map(Value::as_str) {
        let Ok(Some(node_id)) = doc.query_selector(&format!("#{id}")) else { continue };
        let Some(styles) = doc.get_node(node_id).and_then(|n| n.primary_styles()) else { continue };
        let mut declared = BTreeMap::new();
        for rule in styles.rules().self_and_ancestors() {
            if rule.cascade_level().origin() != CascadeOrigin::Author {
                continue;
            }
            let Some(source) = rule.style_source() else { continue };
            for decl in source.read(&guard).declarations() {
                if let PropertyDeclarationId::Longhand(longhand) = decl.id() {
                    declared.entry(longhand.name()).or_insert_with(|| Value::String(styles.computed_value_to_string(PropertyDeclarationId::Longhand(longhand))));
                }
            }
        }
        out.insert(id.to_string(), Value::Object(declared.into_iter().map(|(k, v)| (k.to_string(), v)).collect()));
    }
    println!("{}", Value::Object(out));
}
