// 2D outlines for extruded meshes (ENGINE_CONTRACT.md § 2, shape `outline`): reading them strictly, and
// moving each contour in or out along its corner directions (the bevel's inset). Metres, in XY seen from +Z.
// After reading, every contour has the solid on its left: outers counter-clockwise, holes clockwise.
#pragma once
#include <string>
#include <vector>

#include <pxr/base/gf/vec2d.h>
#include <pxr/base/js/value.h>

namespace r3d {

using Contour = std::vector<PXR_NS::GfVec2d>;  // closed, no repeated closing point

struct OutlineShape {
  Contour outer;
  std::vector<Contour> holes;
};

// Per corner of a contour: the unit normals of the edge arriving and the edge leaving (pointing away from
// the solid), the mitred offset direction (a point offset by d moves to p + miter * d, with the edges
// staying parallel), and whether the outline turns more than `sharp_deg` there.
struct ContourFrame {
  std::vector<PXR_NS::GfVec2d> n_in, n_out, miter;
  std::vector<bool> sharp;
};

double signed_area(const Contour& c);
ContourFrame frame_of(const Contour& c, double sharp_deg);
// Per corner, the share (kMinInsetShare .. 1) of an inset `d` it can take without an inset edge turning backwards.
// Where the outline curves tighter than `d` (the tip of an "s", a small round end), moving every corner the full
// `d` along its miter makes neighbouring corners overtake each other: the bevel folds over itself, which shades as a
// dark, jagged rim, and on a finely cut curve the folds cross and the bevel is refused. There the bevel gets
// narrower instead (same height, less inset), easing back to full width over about 2 × d along the outline.
std::vector<double> inset_share(const Contour& c, const ContourFrame& f, double d);
constexpr double kMinInsetShare = 0.1;
// The contour moved `d` (times each corner's inset_share) towards the solid's inside (a hole grows, an outer shrinks).
Contour inset(const Contour& c, const ContourFrame& f, double d);
// The shapes with stray short edges merged away: an edge much shorter than both its neighbours and than
// the bevel (an SVG's closing nub, a font's tiny segment at an extreme) would turn backwards when inset,
// because its two ends move sideways along different corner directions. Each such edge becomes one point
// at its middle, which moves the outline by under a sixth of the bevel, hidden under the rounding.
std::vector<OutlineShape> without_stray_edges(std::vector<OutlineShape> shapes, double bevel);
// Any two edges of these contours cross (edges meeting at a shared corner don't count).
bool crosses(const std::vector<Contour>& contours);

// scene `outline`: [{"outer": [[x, y], …], "holes": [[[x, y], …], …]}, …]. Throws r3d::Error at `where`.
// Orientation is fixed by signed area; consecutive repeated points (and a closing point) are dropped.
std::vector<OutlineShape> read_outline(const PXR_NS::JsArray& a, const std::string& where);

}  // namespace r3d
