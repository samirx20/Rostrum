//! Path data (ENGINE_CONTRACT.md § 4 path): the one reader of a path's `d`, used to draw it (stage_path.rs) and to
//! blend two shapes (morph.rs).

use kurbo::{BezPath, Point};

/// `d` checked (absolute M, L, C, Z only; numbers by spaces or commas; a command's numbers may repeat, extra
/// pairs after M are lines), split into subpaths. Errors name `id.d`.
pub fn read(id: &str, d: &str) -> Result<Vec<BezPath>, String> {
    let bad = |why: String| format!("{id}.d: {why} (path data takes absolute M x y, L x y, C x1 y1 x2 y2 x y, Z)");
    let mut toks = vec![];
    let mut rest = d.trim_start_matches([' ', ',', '\n', '\t', '\r']);
    while !rest.is_empty() {
        let c = rest.as_bytes()[0] as char;
        let n = if c.is_ascii_alphabetic() && !matches!(c, 'e' | 'E') {
            toks.push(Err(c));
            1
        } else {
            let end = rest.char_indices().skip(1).find(|&(i, ch)| {
                let prev = rest.as_bytes()[i - 1] as char;
                !(ch.is_ascii_digit() || ch == '.' || matches!(ch, 'e' | 'E') || (matches!(ch, '-' | '+') && matches!(prev, 'e' | 'E')))
            }).map_or(rest.len(), |(i, _)| i);
            let num: f64 = rest[..end].parse().map_err(|_| bad(format!("\"{}\" is not a number", &rest[..end])))?;
            if !num.is_finite() {
                return Err(bad(format!("{num} is not a finite number")));
            }
            toks.push(Ok(num));
            end
        };
        rest = rest[n..].trim_start_matches([' ', ',', '\n', '\t', '\r']);
    }
    let mut subs: Vec<BezPath> = vec![];
    let mut i = 0;
    let mut cmd = ' ';
    while i < toks.len() {
        if let Err(c) = toks[i] {
            cmd = c;
            i += 1;
        } else if cmd == ' ' || cmd == 'Z' {
            return Err(bad("numbers before a command".into()));
        }
        let want = match cmd {
            'M' | 'L' => 2,
            'C' => 6,
            'Z' => 0,
            c => return Err(bad(format!("unknown command \"{c}\""))),
        };
        let nums: Vec<f64> = toks[i..].iter().take(want).map_while(|t| t.ok()).collect();
        if nums.len() < want {
            return Err(bad(format!("{cmd} needs {want} numbers")));
        }
        i += want;
        let p = |k: usize| Point::new(nums[k], nums[k + 1]);
        match cmd {
            'M' => {
                subs.push(BezPath::new());
                subs.last_mut().unwrap().move_to(p(0));
                cmd = 'L';
            }
            'Z' => match subs.last_mut() {
                Some(s) => s.close_path(),
                None => return Err(bad("Z before any M".into())),
            },
            _ => {
                let s = subs.last_mut().filter(|s| !matches!(s.elements().last(), Some(kurbo::PathEl::ClosePath))).ok_or_else(|| bad(format!("{cmd} needs an M first")))?;
                if cmd == 'L' { s.line_to(p(0)) } else { s.curve_to(p(0), p(2), p(4)) }
            }
        }
    }
    Ok(subs)
}
