//! The ONE `.cube` reader and writer (Adobe / Resolve Cube LUT Specification 1.0): TITLE, comments,
//! LUT_1D_SIZE / LUT_3D_SIZE, DOMAIN_MIN / DOMAIN_MAX (and Resolve's LUT_*_INPUT_RANGE). Malformed
//! input fails loudly with its line number. `write` is canonical, so read → write → read is byte-stable.
use super::{Interp, Lut1d, Lut3d};
use crate::Rgb;
use std::fmt::{self, Write};

#[derive(Clone, Debug, PartialEq)]
pub enum Lut {
    D1(Lut1d),
    D3(Lut3d),
}

/// A parsed `.cube`: the table plus its title and comment lines (text after `#`, in order).
#[derive(Clone, Debug, PartialEq)]
pub struct Cube {
    pub title: Option<String>,
    pub comments: Vec<String>,
    pub lut: Lut,
}

#[derive(Clone, Debug, PartialEq)]
pub struct CubeError {
    pub line: usize,
    pub msg: String,
}

impl fmt::Display for CubeError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, ".cube line {}: {}", self.line, self.msg)
    }
}
impl std::error::Error for CubeError {}

fn floats<const N: usize>(words: &[&str], line: usize) -> Result<[f32; N], CubeError> {
    let err = |msg: String| CubeError { line, msg };
    if words.len() != N {
        return Err(err(format!("expected {N} numbers, got {}", words.len())));
    }
    let mut out = [0.0; N];
    for (o, w) in out.iter_mut().zip(words) {
        *o = w.parse().map_err(|_| err(format!("bad number `{w}`")))?;
    }
    Ok(out)
}

impl Cube {
    pub fn parse(text: &str) -> Result<Cube, CubeError> {
        let (mut title, mut comments, mut data) = (None, Vec::new(), Vec::<Rgb>::new());
        let (mut size1, mut size3, mut min, mut max) = (None, None, None, None);
        let mut last = 0;
        for (i, raw) in text.lines().enumerate() {
            let line = i + 1;
            last = line;
            let err = |msg: &str| Err(CubeError { line, msg: msg.to_string() });
            let s = raw.trim();
            if s.is_empty() {
                continue;
            }
            if let Some(c) = s.strip_prefix('#') {
                comments.push(c.to_string());
                continue;
            }
            let words: Vec<&str> = s.split_whitespace().collect();
            if !words[0].starts_with(|c: char| c.is_ascii_alphabetic()) || floats::<1>(&words[..1], line).is_ok() {
                data.push(floats::<3>(&words, line)?);
                continue;
            }
            if !data.is_empty() {
                return err(&format!("keyword `{}` after the table data", words[0]));
            }
            let size = |lo: usize, hi: usize| -> Result<usize, CubeError> {
                let n = words.get(1).and_then(|w| w.parse().ok()).filter(|n| (lo..=hi).contains(n));
                n.filter(|_| words.len() == 2)
                    .ok_or(CubeError { line, msg: format!("{} needs one size in {lo}..={hi}", words[0]) })
            };
            let once = |taken: bool| match taken {
                true => Err(CubeError { line, msg: format!("duplicate {}", words[0]) }),
                false => Ok(()),
            };
            match words[0] {
                "TITLE" => {
                    once(title.is_some())?;
                    let t = s["TITLE".len()..].trim();
                    title = Some(t.strip_prefix('"').and_then(|t| t.strip_suffix('"')).unwrap_or(t).to_string());
                }
                "LUT_1D_SIZE" => {
                    once(size1.is_some())?;
                    size1 = Some(size(2, 65536)?);
                }
                "LUT_3D_SIZE" => {
                    once(size3.is_some())?;
                    size3 = Some(size(2, 256)?);
                }
                "DOMAIN_MIN" => {
                    once(min.is_some())?;
                    min = Some(floats::<3>(&words[1..], line)?);
                }
                "DOMAIN_MAX" => {
                    once(max.is_some())?;
                    max = Some(floats::<3>(&words[1..], line)?);
                }
                "LUT_1D_INPUT_RANGE" | "LUT_3D_INPUT_RANGE" => {
                    once(min.is_some())?;
                    let [lo, hi] = floats::<2>(&words[1..], line)?;
                    (min, max) = (Some([lo; 3]), Some([hi; 3]));
                }
                k => return err(&format!("unknown keyword `{k}`")),
            }
        }
        let err = |msg: String| Err(CubeError { line: last, msg });
        let (min, max) = (min.unwrap_or([0.0; 3]), max.unwrap_or([1.0; 3]));
        if (0..3).any(|c| !(min[c] < max[c])) {
            return err(format!("DOMAIN_MIN {min:?} must be below DOMAIN_MAX {max:?}"));
        }
        let (n, lut) = match (size1, size3) {
            (Some(_), Some(_)) => return err("both LUT_1D_SIZE and LUT_3D_SIZE (shaper + 3D is not supported)".into()),
            (None, None) => return err("missing LUT_1D_SIZE or LUT_3D_SIZE".into()),
            (Some(n), None) => (n, Lut::D1(Lut1d { min, max, data: Vec::new() })),
            (None, Some(n)) => (n * n * n, Lut::D3(Lut3d { size: n, min, max, data: Vec::new() })),
        };
        if data.len() != n {
            return err(format!("expected {n} table entries, got {}", data.len()));
        }
        let lut = match lut {
            Lut::D1(l) => Lut::D1(Lut1d { data, ..l }),
            Lut::D3(l) => Lut::D3(Lut3d { data, ..l }),
        };
        Ok(Cube { title, comments, lut })
    }

    /// Canonical text: title, comments, size, non-default domain, then one `r g b` per line
    /// (shortest round-trip decimals).
    pub fn write(&self) -> String {
        let mut o = String::new();
        if let Some(t) = &self.title {
            let _ = writeln!(o, "TITLE \"{t}\"");
        }
        self.comments.iter().for_each(|c| _ = writeln!(o, "#{c}"));
        let (key, n, min, max, data) = match &self.lut {
            Lut::D1(l) => ("LUT_1D_SIZE", l.data.len(), l.min, l.max, &l.data),
            Lut::D3(l) => ("LUT_3D_SIZE", l.size, l.min, l.max, &l.data),
        };
        let _ = writeln!(o, "{key} {n}");
        if min != [0.0; 3] {
            let _ = writeln!(o, "DOMAIN_MIN {} {} {}", min[0], min[1], min[2]);
        }
        if max != [1.0; 3] {
            let _ = writeln!(o, "DOMAIN_MAX {} {} {}", max[0], max[1], max[2]);
        }
        data.iter().for_each(|v| _ = writeln!(o, "{} {} {}", v[0], v[1], v[2]));
        o
    }

    /// 1D: linear per channel; 3D: `interp`.
    pub fn apply(&self, rgb: Rgb, interp: Interp) -> Rgb {
        match &self.lut {
            Lut::D1(l) => l.apply(rgb),
            Lut::D3(l) => l.apply(rgb, interp),
        }
    }
}
