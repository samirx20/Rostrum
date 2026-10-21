//! `rostrum2d-render sksl grade <spec.json> <lut dir>`: the one grade (rostrum-color `grade`, C7) as the colour
//! filter a layer gets, in any working space (display / linear-display / acescg: `program`), as `{"code", "uniforms": [[name, [values]]], "images": [[name, rhalf file]]}`. The grade runs on ACEScg light:
//! on display values the filter decodes them (sRGB curve, Rec.709 → ACEScg) and encodes them back, so an identity
//! grade is exact. LUT tables are written to `<lut dir>` as RHALF files (half floats: the GPU reads 8 bits of an
//! F32 image). The spec is the document's grade in operations (src/engine/video/gradeProgram.ts), one list
//! `{ "ops": [...], "mix" }` or a layer stack `{ "layers": [{ "id", "ops", "mix", "from", "combine", "matte" }], "mix" }`:
//! the forms, operations and fields are rostrum-color grade/spec.rs's (unknown ones are errors). Child images
//! (`lut0`, `lut1`, …) are the LUT nodes' tables and the hue / lum / sat curves' tables, depth first.
//!
//! The matte seam (rostrum-color grade/mod.rs "The matte seam"). A grade whose mattes need neighbours (denoise, shrink,
//! grow, blur) also gets `"blender": true` (its `code` is then a runtime blender `half4 main(half4 m, half4 c)`: `c` the
//! picture, `m` the packed matte image) and `"mattes": [{ "layer", "channel", "shader", "key": {code, uniforms}, "denoise":
//! {code, uniforms} | null, "shrink", "grow", "blur", "norm" }]`: the stages the host chains as SVG filter primitives
//! before the blender (`gradeProgram.ts`); a layer's windows are one such stage with `"shader": true` (its key is the windows'
//! image-filter shader, window_sksl.rs, and it has no further filters). `"matteView": "<layer id>"` in the spec makes the program return that layer's
//! coverage as a grey picture instead of the grade.

use rostrum_color::grade::{Grade, MatteStage};
use rostrum_color::view::Sksl;
use rostrum_color::Curve;
use serde_json::{json, Value};

/// The grade's colour filter (or blender) for a layer, in whichever working space the render paints (module doc):
/// the renderer sets `rostrumWorking` itself (anyrender_skia working_space: 0 display, 1 linear display, 2 ACEScg),
/// so one program serves preview and export of every document alike. `view`: the program shows a matte (no output encode).
pub fn program(g: &Grade) -> Result<Sksl, String> {
    program_of(g.sksl()?, false)
}

fn program_of(s: Sksl, view: bool) -> Result<Sksl, String> {
    let m = |a: &str, b: &str| rostrum_color::view::sksl::mat(&rostrum_color::convert::gamut_matrix(a, b).unwrap().map(|r| r.map(|v| v as f32)));
    let (d, e) = (Curve::Srgb.sksl_name(false), Curve::Srgb.sksl_name(true));
    let blender = s.code.contains("half4 main(half4 m, half4 c)");
    let (entry, call, inner) = if blender {
        ("half4 main(half4 m, half4 c)", "gradeMain(m, half4(half3(cg), 1.0))", s.code.replacen("half4 main(half4 m, half4 c)", "half4 gradeMain(half4 m, half4 c)", 1))
    } else {
        ("half4 main(half4 c)", "gradeMain(half4(half3(cg), 1.0))", s.code.replacen("half4 main(half4 c)", "half4 gradeMain(half4 c)", 1))
    };
    let encode = if view { "g".to_string() } else { format!("rostrumWorking < 0.5 ? float3({e}(y.r), {e}(y.g), {e}(y.b)) : y") };
    let code = format!(
        "{}{}{}
uniform float rostrumWorking;
{entry} {{
    float a = float(c.a);
    if (a <= 0.0) {{ return c; }}
    float3 x = float3(c.rgb) / a;
    float3 l = rostrumWorking < 0.5 ? float3({d}(x.r), {d}(x.g), {d}(x.b)) : x;
    float3 cg = rostrumWorking < 1.5 ? ({to}) * l : l;
    float3 g = float3({call}.rgb);
    float3 y = {y};
    float3 o = {encode};
    return half4(half3(o * a), c.a);
}}
",
        // The sRGB functions, unless the grade already has them (a LUT node in an sRGB space).
        if inner.contains(&format!("float {d}(")) { String::new() } else { Curve::Srgb.sksl(false) },
        if inner.contains(&format!("float {e}(")) { String::new() } else { Curve::Srgb.sksl(true) },
        inner,
        to = m("lin_rec709", "acescg"),
        y = if view { "g".to_string() } else { format!("rostrumWorking < 1.5 ? ({}) * g : g", m("acescg", "lin_rec709")) },
    );
    Ok(Sksl { code, uniforms: s.uniforms })
}

/// A matte stage's key as a colour program on the picture in any working space: it reads the ACEScg light and writes the
/// key (times the stage's channel mask, alpha 1) as the stage's value, not as a colour (no encode). Outside the picture: 0.
fn key_program(s: &Sksl) -> Sksl {
    let m = |a: &str, b: &str| rostrum_color::view::sksl::mat(&rostrum_color::convert::gamut_matrix(a, b).unwrap().map(|r| r.map(|v| v as f32)));
    let d = Curve::Srgb.sksl_name(false);
    let code = format!(
        "{}{}
uniform float rostrumWorking;
half4 main(half4 c) {{
    float a = float(c.a);
    if (a <= 0.0) {{ return half4(0.0, 0.0, 0.0, 1.0); }}
    float3 x = float3(c.rgb) / a;
    float3 l = rostrumWorking < 0.5 ? float3({d}(x.r), {d}(x.g), {d}(x.b)) : x;
    float3 cg = rostrumWorking < 1.5 ? ({to}) * l : l;
    return keyMain(half4(half3(cg), 1.0));
}}
",
        if s.code.contains(&format!("float {d}(")) { String::new() } else { Curve::Srgb.sksl(false) },
        s.code.replacen("half4 main(half4 c)", "half4 keyMain(half4 c)", 1),
        to = m("lin_rec709", "acescg"),
    );
    Sksl { code, uniforms: s.uniforms.clone() }
}

fn stage_json(s: &MatteStage) -> Value {
    // A window stage's key is an image-filter shader that makes the matte itself: no picture colour to convert.
    let k = if s.shader { Sksl { code: s.key.code.clone(), uniforms: s.key.uniforms.clone() } } else { key_program(&s.key) };
    json!({
        "layer": s.layer, "channel": s.channel, "shader": s.shader,
        "key": { "code": k.code, "uniforms": k.uniforms },
        "denoise": s.denoise.as_ref().map(|d| json!({ "code": d.code, "uniforms": d.uniforms })),
        "shrink": s.shrink, "grow": s.grow, "blur": s.blur, "norm": s.norm,
    })
}

pub fn run(spec: &str, lut_dir: &str) -> Result<Value, String> {
    let mut spec: Value = serde_json::from_str(&std::fs::read_to_string(spec).map_err(|e| format!("{spec}: {e}"))?).map_err(|e| e.to_string())?;
    let view = spec.as_object_mut().and_then(|o| o.remove("matteView")).map(|v| v.as_str().map(String::from).ok_or_else(|| format!("`matteView` is a layer id; got {v}"))).transpose()?;
    let g = Grade::from_spec(&spec)?;
    let s = match &view {
        Some(id) => program_of(g.sksl_matte_view(id)?, true)?,
        None => program(&g)?,
    };
    let mut images = vec![];
    for (i, t) in g.lut_images().iter().enumerate() {
        let path = std::path::Path::new(lut_dir).join(format!("lut{i}.rhalf"));
        write_rhalf(&path, t)?;
        images.push(json!([format!("lut{i}"), path.to_string_lossy()]));
    }
    let stages = g.matte_stages()?;
    let mut out = json!({ "code": s.code, "uniforms": s.uniforms, "images": images });
    if !stages.is_empty() {
        out["blender"] = json!(true);
        out["mattes"] = Value::Array(stages.iter().map(stage_json).collect());
    }
    Ok(out)
}

/// A grade's child image (a LUT table) as an RHALF file (half floats: the GPU reads 8 bits of an F32 image).
pub fn write_rhalf(path: &std::path::Path, t: &rostrum_color::grade::LutImage) -> Result<(), String> {
    let mut bytes = blitz_dom::net::RHALF_MAGIC.to_vec();
    bytes.extend_from_slice(&(t.width as u32).to_le_bytes());
    bytes.extend_from_slice(&(t.height as u32).to_le_bytes());
    bytes.extend(t.rgba.iter().flat_map(|v| half::f16::from_f32(*v).to_le_bytes()));
    std::fs::write(path, bytes).map_err(|e| format!("{}: {e}", path.display()))
}

/// `rostrum2d-render sksl lut <spec.json> <out.cube> [--size N] [--in space] [--out space] [--view id [--target sdr|hdr1000]] [--note text]…`:
/// the one grade (the same spec as `sksl grade`) baked into a `.cube` (rostrum-color `Grade::bake`), for Resolve and
/// other tools. Prints `{"file", "size", "in", "out", "view", "target"}`. The notes go into the header comments
/// (the host writes the Rostrum version and commit there).
pub fn bake(args: &[String]) -> Result<Value, String> {
    use rostrum_color::view::Target;
    let [spec, out, rest @ ..] = args else { return Err("usage: rostrum2d-render sksl lut <spec.json> <out.cube> [--size N] [--in space] [--out space] [--view id [--target sdr|hdr1000]] [--note text]".into()) };
    let (mut size, mut input, mut output, mut view, mut target, mut notes) = (33usize, "srgb_display".to_string(), "srgb_display".to_string(), None::<String>, "sdr".to_string(), vec![]);
    let mut it = rest.iter();
    while let Some(flag) = it.next() {
        let mut value = || it.next().cloned().ok_or(format!("{flag} takes a value"));
        match flag.as_str() {
            "--size" => size = value()?.parse().map_err(|_| "--size is a whole number (33 or 65 for Resolve)".to_string())?,
            "--in" => input = value()?,
            "--out" => output = value()?,
            "--view" => view = Some(value()?),
            "--target" => target = value()?,
            "--note" => notes.push(value()?),
            other => return Err(format!("unknown option {other} (--size, --in, --out, --view, --target, --note)")),
        }
    }
    let spec_json: Value = serde_json::from_str(&std::fs::read_to_string(spec).map_err(|e| format!("{spec}: {e}"))?).map_err(|e| e.to_string())?;
    let g = Grade::from_spec(&spec_json)?;
    let t = Target::from_id(&target).ok_or_else(|| format!("--target is sdr or hdr1000; got `{target}`"))?;
    let (mut cube, shaper) = g.bake_shaped(size, &input, &output, view.as_deref().map(|v| (v, t)))?;
    // The host's notes first (version, commit, what was baked), then the bake's own (spaces, grid).
    cube.comments.splice(0..0, notes.iter().map(|n| format!(" {n}")));
    // A scene-linear input also gets its 1D shaper, next to the table (`name.shaper.cube`: apply it first).
    let shaper_file = shaper.map(|mut s| -> Result<String, String> {
        let path = std::path::Path::new(out);
        let name = path.file_stem().map_or("lut".into(), |n| n.to_string_lossy().into_owned());
        let file = path.with_file_name(format!("{name}.shaper.cube"));
        s.comments.splice(0..0, notes.iter().map(|n| format!(" {n}")));
        s.comments.push(format!(" table: {}", path.file_name().map_or(out.to_string(), |n| n.to_string_lossy().into_owned())));
        std::fs::write(&file, s.write()).map_err(|e| format!("{}: {e}", file.display()))?;
        Ok(file.to_string_lossy().into_owned())
    }).transpose()?;
    std::fs::write(out, cube.write()).map_err(|e| format!("{out}: {e}"))?;
    Ok(json!({ "file": out, "size": size, "in": input, "out": output, "view": view, "target": t.id(), "shaper": shaper_file }))
}
