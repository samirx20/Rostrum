//! The SFZ preprocessor (sfz.rs runs it before parsing): `#define $NAME value` and `$NAME`
//! substitution, `#include "file"` (resolved against the instrument's own folder, as sfizz does),
//! and comments. Libraries split into modules (Karoryfer, the Greg Sullivan e-pianos) need it.

use std::path::Path;

/// Strips `//` line comments and `/* … */` blocks, whichever starts first (`//****` is a line comment).
pub fn strip_comments(text: &str) -> String {
    let mut out = String::new();
    let mut rest = text;
    while let Some(i) = rest.find('/') {
        out.push_str(&rest[..i]);
        let after = &rest[i..];
        if after.starts_with("//") { rest = after.find('\n').map_or("", |j| &after[j..]); }
        else if after.starts_with("/*") { rest = after.find("*/").map_or("", |j| &after[j + 2..]); }
        else { out.push('/'); rest = &after[1..]; }
    }
    out.push_str(rest);
    out
}

/// The text with its includes inlined and its defines substituted; `root` is the folder of the file the instrument was opened from.
pub fn preprocess(text: &str, root: &Path) -> Result<String, String> {
    let mut defines: Vec<(String, String)> = vec![];
    let mut out = String::new();
    expand(text, root, &mut defines, &mut out, 0)?;
    Ok(out)
}

fn expand(text: &str, root: &Path, defines: &mut Vec<(String, String)>, out: &mut String, depth: usize) -> Result<(), String> {
    if depth > 16 { return Err("SFZ #include nests deeper than 16 files (a file includes itself?)".into()); }
    for line in strip_comments(text).lines() {
        // A #define's name is never substituted (it may be redefined); its value and every other line are.
        let raw = line.trim_start();
        let line = if raw.starts_with("#define") { line.to_string() } else { substitute(line, defines) };
        let t = line.trim_start();
        if let Some(d) = t.strip_prefix("#define") {
            let mut it = d.split_whitespace();
            let (Some(name), value) = (it.next(), substitute(&it.collect::<Vec<_>>().join(" "), defines)) else { return Err(format!("SFZ \"{t}\": #define needs a $name and a value")) };
            if !name.starts_with('$') { return Err(format!("SFZ \"{t}\": a #define name starts with $")); }
            defines.retain(|(n, _)| n != name);
            defines.push((name.to_string(), value));
            // Longest names first, so $EXT never replaces the start of $EXTRA.
            defines.sort_by_key(|(n, _)| std::cmp::Reverse(n.len()));
        } else if let Some(inc) = t.strip_prefix("#include") {
            let name = inc.trim().trim_matches('"').replace('\\', "/");
            let path = root.join(&name);
            let body = std::fs::read_to_string(&path).map_err(|e| format!("SFZ #include \"{name}\": {}: {e}", path.display()))?;
            expand(&body, root, defines, out, depth + 1)?;
        } else if t.starts_with('#') {
            return Err(format!("SFZ directive \"{}\" is not supported (only #define and #include)", t.split_whitespace().next().unwrap_or(t)));
        } else {
            out.push_str(&line);
            out.push('\n');
        }
    }
    Ok(())
}

/// `$NAME` → its value, for every define so far.
fn substitute(line: &str, defines: &[(String, String)]) -> String {
    if !line.contains('$') { return line.to_string(); }
    let mut s = line.to_string();
    for (n, v) in defines { s = s.replace(n.as_str(), v); }
    s
}
