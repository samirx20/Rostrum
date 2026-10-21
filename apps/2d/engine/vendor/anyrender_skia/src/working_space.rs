//! Rostrum patch: the colour space the surface being painted is in (rostrum-motion painter.rs sets it per
//! render). Half-float images are tagged with it, because their pixels were converted into it when they were
//! decoded; `None` is an unmanaged (display, sRGB-valued) surface.
use skia_safe::ColorSpace;
use std::cell::RefCell;

thread_local! {
    static SPACE: RefCell<Option<ColorSpace>> = const { RefCell::new(None) };
}

pub fn set(space: Option<ColorSpace>) {
    SPACE.with(|s| *s.borrow_mut() = space);
}

pub fn get() -> Option<ColorSpace> {
    SPACE.with(|s| s.borrow().clone())
}

/// The working space as the number colour programs read from a `uniform float rostrumWorking` (the one grade's filter):
/// 0 display values (no space), 1 linear sRGB, 2 anything else (linear ACEScg).
pub fn kind() -> f32 {
    match get() {
        None => 0.0,
        Some(cs) if cs == ColorSpace::new_srgb_linear() => 1.0,
        Some(_) => 2.0,
    }
}

/// A solid colour (unpremultiplied sRGB) as a runtime shader with a float `layout(color)` uniform: Skia converts it
/// into the working space and the GPU keeps it in float. A plain paint colour, or a colour shader (which Skia folds
/// back into one), reaches the GPU as 8 bits, which a linear surface shows as crushed darks.
pub fn solid(c: skia_safe::Color4f) -> Option<skia_safe::Shader> {
    thread_local! {
        static EFFECT: Result<skia_safe::RuntimeEffect, String> = skia_safe::RuntimeEffect::make_for_shader(
            "layout(color) uniform half4 c; half4 main(float2 p) { return half4(c.rgb * c.a, c.a); }", None);
    }
    EFFECT.with(|e| {
        let effect = match e {
            Ok(effect) => effect,
            // Never a silent fall back to a plain colour: the frame fails naming the shader.
            Err(err) => {
                anyrender::filters::shader_errors::push(format!("the solid-colour shader failed to compile: {err}"));
                return None;
            }
        };
        let bytes: Vec<u8> = [c.r, c.g, c.b, c.a].iter().flat_map(|v| v.to_le_bytes()).collect();
        let shader = effect.make_shader(skia_safe::Data::new_copy(&bytes), &[], None);
        if shader.is_none() {
            anyrender::filters::shader_errors::push("the solid-colour shader compiled but Skia could not build it".into());
        }
        shader
    })
}
