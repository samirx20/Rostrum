// USD's simple shapes (Sphere, Cube, Cylinder, Cone, Capsule, Plane) as meshes, made by the core's own shape code
// (primitives.cpp): the same 64 steps around and smooth per-vertex normals as a Rostrum sphere, in every renderer.
// Cycles' Hydra plug-in and our Stylized renderer draw only meshes and silently dropped them (agent-3e, 2026-10-30);
// USD's own implicit-surface filter then made them ~10-sided blocks with faceted shading in Final and Quick alike
// (3d-shapes-smooth, 2026-10-30). Ours goes first for Storm, Cycles and Stylized; USD's filter stays behind it for
// what ours leaves (a cylinder or capsule with different end radii), so nothing is dropped.
#pragma once

namespace r3d {

// register the filter for Hydra's "GL" (Storm), "Cycles" and "Rostrum Stylized"; call once, before any engine is made
void register_implicit_shapes();

}  // namespace r3d
