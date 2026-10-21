//! Rostrum patch (round 8): instanced particle sprites, and the raster mesh warp's element hook.
//!
//! Particles: an element with `data-particles` (Rostrum's <Emitter>, src/engine/particles/) does not draw its
//! children; each child is a sprite, painted once into a recorded scene, and stamped once per particle at its
//! place (x, y, rotation, scale x / y around the sprite's centre, in the element's px) with its opacity and
//! tint (a white sprite takes the tint exactly) — `PaintScene::draw_instances`: on Skia one textured mesh for
//! all stamps of a sprite, its image painted at the largest size a stamp needs. `data-trails` are fading
//! polylines drawn under them.

use anyrender::{Paint, PaintScene, Scene, SpriteInstance};
use kurbo::{Affine, BezPath, Cap, Join, Point, Rect, Stroke, Vec2};
use peniko::{Color, Gradient};

use crate::render::ElementCx;

/// A data attribute's value.
pub(crate) fn data_attr<'a>(node: &'a blitz_dom::Node, name: &str) -> Option<&'a str> {
    node.attrs()?.iter().find(|a| &*a.name.local == name).map(|a| &*a.value)
}

fn numbers(s: &str) -> Vec<f64> {
    s.split_ascii_whitespace().filter_map(|v| v.parse::<f64>().ok()).collect()
}

const EVERYWHERE: Rect = Rect::new(-1e7, -1e7, 1e7, 1e7);

impl ElementCx<'_, '_> {
    /// Rostrum patch (round 10): an element with `data-shutter-held` draws the picture the painter holds (motion
    /// blur's summed sub-frames) in place of its children, inside its own layers — so its filter (an <Adjust>'s
    /// look) runs once on the shutter's average. False (no attribute, or nothing held) draws the children.
    pub(crate) fn draw_held(&self, scene: &mut impl PaintScene) -> bool {
        data_attr(self.node, "data-shutter-held").is_some() && scene.draw_held()
    }

    /// Draws the element's particles (true) when it has `data-particles`; false leaves it to draw its children.
    pub(crate) fn draw_particles(&self, scene: &mut impl PaintScene) -> bool {
        let Some(data) = data_attr(self.node, "data-particles") else { return false };
        let s = self.scale;
        // Element px → device.
        let device = self.transform * Affine::scale(s);
        let Some(to_local) = (device.determinant().abs() > 1e-12).then(|| device.inverse()) else { return true };
        let tree = self.context.dom.as_ref().tree();
        let sprites: Vec<(Scene, Affine, Rect)> = self
            .node
            .children
            .iter()
            .filter(|&&id| tree[id].is_element())
            .map(|&id| {
                let mut rec = Scene::new();
                self.context.render_node_for(&mut rec, id, self.transform, EVERYWHERE);
                let l = tree[id].final_layout();
                let (w, h) = (l.size.width as f64, l.size.height as f64);
                let centre = Vec2::new(l.location.x as f64 + w / 2.0, l.location.y as f64 + h / 2.0);
                // Device → the sprite's own px around its centre; what it covers there (its box and room for glows).
                let m = w.max(h) * 0.25;
                (rec, Affine::translate(-centre) * to_local, Rect::new(-w / 2.0 - m, -h / 2.0 - m, w / 2.0 + m, h / 2.0 + m))
            })
            .collect();
        if let Some(trails) = data_attr(self.node, "data-trails") {
            let t = numbers(trails);
            let mut i = 0;
            while i + 4 <= t.len() {
                let (n, width, rgb, a) = (t[i] as usize, t[i + 1], t[i + 2] as i64, t[i + 3] as f32);
                i += 4;
                if n < 2 || i + 2 * n > t.len() {
                    break;
                }
                let mut path = BezPath::new();
                for k in 0..n {
                    let p = Point::new(t[i + 2 * k], t[i + 2 * k + 1]);
                    if k == 0 { path.move_to(p) } else { path.line_to(p) }
                }
                let head = Point::new(t[i], t[i + 1]);
                let tail = Point::new(t[i + 2 * n - 2], t[i + 2 * n - 1]);
                i += 2 * n;
                let base = if rgb < 0 { Color::WHITE } else { Color::from_rgb8((rgb >> 16) as u8, (rgb >> 8) as u8, rgb as u8) };
                let brush = Gradient::new_linear(head, tail).with_stops([base.multiply_alpha(a), base.multiply_alpha(0.0)]);
                let stroke = Stroke::new(width).with_caps(Cap::Round).with_join(Join::Round);
                scene.stroke(&stroke, device, &Paint::Gradient(brush), None, &path);
            }
        }
        if sprites.is_empty() {
            return true;
        }
        let v = numbers(data);
        let mut stamps: Vec<Vec<SpriteInstance>> = vec![Vec::new(); sprites.len()];
        for p in v.chunks_exact(8) {
            let (k, x, y, rot, sx, sy, a, rgb) = (p[0] as usize, p[1], p[2], p[3], p[4], p[5], p[6] as f32, p[7] as i64);
            let k = if k < sprites.len() { k } else { 0 };
            let [r, g, b] = if rgb < 0 { [1.0, 1.0, 1.0] } else { [((rgb >> 16) & 255) as f32 / 255.0, ((rgb >> 8) & 255) as f32 / 255.0, (rgb & 255) as f32 / 255.0] };
            let place = device * Affine::translate((x, y)) * Affine::rotate(rot.to_radians()) * Affine::scale_non_uniform(sx, sy);
            stamps[k].push(SpriteInstance { transform: place, color: [r, g, b, a] });
        }
        for ((rec, to_sprite, bounds), list) in sprites.iter().zip(stamps.iter()) {
            if !list.is_empty() {
                scene.draw_instances(rec, *to_sprite, *bounds, list);
            }
        }
        true
    }
}
