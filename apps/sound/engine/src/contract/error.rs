//! The contract's one error: the shared parts (shared/mcp/CONVENTIONS.md § 6), so the Python side passes
//! it on unchanged. `where` is a path into the request (`schedule.tracks[2].notes[5].pitch`).

use serde_json::{json, Value};

#[derive(Debug, Clone)]
pub struct Error {
    pub code: &'static str,
    pub at: String,
    pub subject: String,
    pub problem: String,
    pub accepted: Vec<String>,
    pub hint: String,
}

fn shown(v: &Value) -> String {
    let s = v.to_string();
    if s.len() > 60 { format!("{}…", &s[..s.char_indices().nth(57).map_or(s.len(), |(i, _)| i)]) } else { s }
}

impl Error {
    pub fn new(code: &'static str, at: &str, subject: impl Into<String>, problem: impl Into<String>) -> Error {
        Error { code, at: at.to_string(), subject: subject.into(), problem: problem.into(), accepted: vec![], hint: String::new() }
    }

    pub fn bad(at: &str, v: &Value, problem: &str, accepted: &[&str]) -> Error {
        Error { accepted: accepted.iter().map(|s| s.to_string()).collect(), ..Error::new("BAD_ARGUMENT", at, shown(v), problem) }
    }

    pub fn missing(at: &str) -> Error {
        Error::new("BAD_ARGUMENT", at, at.rsplit('.').next().unwrap_or(at).to_string(), "is required")
    }

    /// An unknown name, with the closest accepted one as the hint.
    pub fn unknown(at: &str, name: &str, accepted: &[&str]) -> Error {
        let hint = closest(name, accepted).map(|c| format!("Did you mean {c}?")).unwrap_or_default();
        Error { accepted: accepted.iter().map(|s| s.to_string()).collect(), hint, ..Error::new("BAD_ARGUMENT", at, format!("\"{name}\""), "is not a known name") }
    }

    pub fn not_found(at: &str, subject: &str, problem: impl Into<String>) -> Error {
        Error::new("NOT_FOUND", at, subject, problem)
    }

    pub fn render(problem: impl Into<String>) -> Error {
        Error::new("RENDER_FAILED", "render", "the mix", problem)
    }

    pub fn hint(mut self, hint: impl Into<String>) -> Error {
        self.hint = hint.into();
        self
    }

    /// The one line people and agents read.
    pub fn line(&self) -> String {
        let mut s = format!("Error: {}: {} {}.", self.at, self.subject, self.problem);
        if !self.accepted.is_empty() {
            let shown: Vec<&str> = self.accepted.iter().take(24).map(String::as_str).collect();
            s += &format!(" Accepted: {}.", shown.join(", "));
        }
        if !self.hint.is_empty() {
            s += &format!(" {}", self.hint);
        }
        s
    }

    pub fn to_json(&self) -> Value {
        json!({ "code": self.code, "where": self.at, "subject": self.subject, "problem": self.problem,
                "accepted": self.accepted, "hint": self.hint, "line": self.line() })
    }
}

/// The accepted name nearest `name` (edit distance, case-insensitive), if close enough to be a typo.
fn closest<'a>(name: &str, accepted: &[&'a str]) -> Option<&'a str> {
    let lower = name.to_lowercase();
    accepted.iter().map(|a| (distance(&lower, &a.to_lowercase()), *a)).filter(|(d, a)| *d <= 2.max(a.len() / 3)).min_by_key(|(d, _)| *d).map(|(_, a)| a)
}

fn distance(a: &str, b: &str) -> usize {
    let b: Vec<char> = b.chars().collect();
    let mut row: Vec<usize> = (0..=b.len()).collect();
    for (i, ca) in a.chars().enumerate() {
        let mut prev = row[0];
        row[0] = i + 1;
        for j in 0..b.len() {
            let next = (row[j + 1] + 1).min(row[j] + 1).min(prev + usize::from(ca != b[j]));
            prev = row[j + 1];
            row[j + 1] = next;
        }
    }
    row[b.len()]
}
