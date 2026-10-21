//! `sksl grade …` and `sksl lut …` (grade_cmd.rs) and `rostrum2d-render sksl display-in <view> <target>`: the colour filter a display-referred clip gets in a linear
//! edit (rostrum-color `View::sksl_display_in`), as `{"code", "uniforms": [[name, [values]]]}` for the host to put
//! in the clip's `<feshader>` (the compositor's linear blend, C5). `filter` builds the same filter here (tests).

use rostrum_color::view::{Target, View};
use serde_json::json;
#[cfg(test)]
use skia_safe::{ColorFilter, Data, RuntimeEffect};

pub fn program(view: &str, target: &str) -> Result<rostrum_color::view::Sksl, String> {
    let t = Target::from_id(target).ok_or_else(|| format!("target is sdr or hdr1000; got `{target}`"))?;
    View::resolve(view, t)?.sksl_display_in(t)
}

/// Its inverse (`View::sksl_display_out`): the light as the view shows it, for a program that works on display code values.
pub fn program_out(view: &str, target: &str) -> Result<rostrum_color::view::Sksl, String> {
    let t = Target::from_id(target).ok_or_else(|| format!("target is sdr or hdr1000; got `{target}`"))?;
    View::resolve(view, t)?.sksl_display_out(t)
}

pub fn run(args: &[String]) {
    if args.first().map(String::as_str) == Some("lut") {
        match crate::grade_cmd::bake(&args[1..]) {
            Ok(v) => println!("{v}"),
            Err(e) => {
                eprintln!("{e}");
                std::process::exit(1);
            }
        }
        return;
    }
    if let [kind, spec, dir] = args {
        if kind == "grade" {
            match crate::grade_cmd::run(spec, dir) {
                Ok(v) => println!("{v}"),
                Err(e) => {
                    eprintln!("{e}");
                    std::process::exit(1);
                }
            }
            return;
        }
    }
    let [kind, view, target] = args else {
        eprintln!("usage: rostrum2d-render sksl display-in|display-out <view> <target> | sksl grade <spec.json> <lut dir> | sksl lut <spec.json> <out.cube> [--size N] [--in space] [--out space] [--view id] [--target t] [--note text]");
        std::process::exit(2);
    };
    let made = if kind == "display-out" { program_out(view, target) } else { program(view, target) };
    match (kind.as_str(), made) {
        ("display-in" | "display-out", Ok(s)) => println!("{}", json!({ "code": s.code, "uniforms": s.uniforms })),
        (_, Err(e)) => {
            eprintln!("{e}");
            std::process::exit(1);
        }
        (k, _) => {
            eprintln!("unknown sksl program `{k}` (display-in, display-out)");
            std::process::exit(2);
        }
    }
}

/// The program as a Skia colour filter, its uniform arrays packed at their offsets.
#[cfg(test)]
pub fn filter(s: &rostrum_color::view::Sksl) -> Result<ColorFilter, String> {
    let effect = RuntimeEffect::make_for_color_filter(&s.code, None)?;
    let size = effect.uniforms().iter().map(|u| u.offset() + u.size_in_bytes()).max().unwrap_or(0);
    let mut bytes = vec![0u8; size];
    for (name, values) in &s.uniforms {
        let u = effect.uniforms().iter().find(|u| u.name() == *name).ok_or_else(|| format!("no uniform {name}"))?;
        for (i, v) in values.iter().enumerate() {
            bytes[u.offset() + 4 * i..u.offset() + 4 * i + 4].copy_from_slice(&v.to_le_bytes());
        }
    }
    effect.make_color_filter(Data::new_copy(&bytes), None).ok_or_else(|| "color filter".into())
}
