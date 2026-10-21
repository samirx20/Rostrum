//! Rostrum patch (round 8): a raster deform / puppet warp. Rostrum writes it as the first primitive of the
//! element's `filter: url(#id)`, `<fewarp x y w h cols rows pts>` (src/engine/deform/rasterWarp.ts): a regular
//! grid over the rest rect (element px) and each grid point's deformed position. The painter records the
//! element as usual and draws the recording on that mesh (anyrender `draw_warped`).

use anyrender::WarpMesh;
use blitz_dom::{BaseDocument, Node};
use kurbo::{Affine, Point, Rect};

use crate::particles::data_attr;

/// The element's warp mesh (`transform`: element px → device), if its filter leads with `<fewarp>`.
pub(crate) fn mesh_of(dom: &BaseDocument, node: &Node, transform: Affine) -> Option<WarpMesh> {
    let id = crate::filters::url_filter_id(node)?;
    let filter = dom.get_node(dom.get_element_by_id(&id)?)?;
    let warp = filter.children.iter().filter_map(|&c| dom.get_node(c)).find(|n| n.element_data().is_some_and(|e| &*e.name.local == "fewarp"))?;
    let n = |k: &str| data_attr(warp, k).and_then(|v| v.trim().parse::<f64>().ok());
    let (x, y, w, h) = (n("x")?, n("y")?, n("w")?, n("h")?);
    let nums = |k: &str| data_attr(warp, k).map(|s| s.split_ascii_whitespace().filter_map(|t| t.parse::<f64>().ok()).collect::<Vec<f64>>());
    let points = |v: Vec<f64>| v.chunks_exact(2).map(|p| Point::new(p[0], p[1])).collect::<Vec<_>>();
    let rest = Rect::new(x, y, x + w, y + h);
    if !(w > 0.0 && h > 0.0) {
        return None;
    }
    // Free triangles: `pts` (deformed), `uvs` (rest) and `tris` (corner indices).
    if let Some(tris) = data_attr(warp, "tris") {
        let tris: Vec<u32> = tris.split_ascii_whitespace().filter_map(|t| t.parse().ok()).collect();
        let mesh = WarpMesh { transform, rest, points: points(nums("pts")?), uvs: points(nums("uvs")?), tris };
        return mesh.is_valid().then_some(mesh);
    }
    let (cols, rows) = (n("cols")? as usize, n("rows")? as usize);
    let v = nums("pts")?;
    if cols < 1 || rows < 1 || v.len() != 2 * (cols + 1) * (rows + 1) {
        return None;
    }
    Some(WarpMesh::grid(transform, rest, cols, rows, points(v)))
}
