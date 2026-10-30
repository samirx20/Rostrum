// USD's simple shapes (Sphere, Cube, Cylinder, Cone, Capsule, Plane) as meshes for the renderers that draw only meshes.
// Storm turns them into meshes itself (its own scene index plug-in), so an imported .usda with `def Sphere` showed in
// Quick. Cycles' Hydra plug-in and our Stylized renderer support only mesh rprims and silently dropped them: the same
// file rendered empty in Final (agent-3e, 2026-10-30). USD's own HdsiImplicitSurfaceSceneIndex, set to "toMesh" for
// every shape, is put in front of both, so all three renderers draw the same shapes from the same tessellation rules.
#pragma once

namespace r3d {

// register the filter for Hydra's "Cycles" and "Rostrum Stylized" renderers; call once, before any engine is made
void register_implicit_shapes();

}  // namespace r3d
