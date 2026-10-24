# Our changes to the libraries

Rostrum3D's libraries are used as downloaded, except one: **Cycles' Hydra plug-in** (`hdCycles.dll`, Cycles commit
`a456b76`, Apache-2.0). Our changes are one patch, `cycles-rostrum.patch`, applied to `src\hydra` only (the GPU
kernels are not touched, so they are copied, not rebuilt). `build_cycles.bat` applies it and builds; `lay_out.py`
lays the result out in the library folder.

| Library folder | What the patch does | Files |
|---|---|---|
| `-r1` (H22) | A dome the camera doesn't see (`rostrum:seenByCamera`); a panel light's `spread`; light linking (`rostrum:lightsOnly`); the background re-read when only a light's visibility changes | `light.cpp`, `geometry.inl`, `session.cpp` |
| `-r2` (3D-11b) | **Object motion blur.** The plug-in read an object's transform at the frame only, so only camera moves blurred. Now the render settings `rostrum:shutterOpen` / `rostrum:shutterClose` (frames, relative to the frame; the engine sets them, `core/src/hydra.cpp`) tell it the shutter, and each object's transform is sampled inside it, as the camera's already was. Instanced copies get the same samples. A mesh whose own points move (deforming) is not sampled yet. Also a Cycles gap: switching `cycles:integrator:motion_blur` on in a running engine left an object that already had motion sharp (the BVH was not rebuilt) or shaded with a dark smear (its motion data was not written); the switch now marks every object's motion changed. | `geometry.h`, `geometry.inl`, `session.h`, `render_delegate.h`, `render_delegate.cpp` |
| `-r3` (3D-15) | **Passes as EXR layers.** The plug-in made only colour, depth, surface direction and prim ids. It now also maps the Hydra outputs `diffuse`, `glossy`, `transmission`, `volume`, `emission`, `background` and `diffuseDirect` to Cycles' passes of the same names (`kAovToPass`, 32-bit RGB each, `GetDefaultAovDescriptor`), with the surface colour included (`include_albedo`), so they add up to the colour before the noise clean-up. And a render setting `rostrum:castShadows` (default on): off, no light casts a shadow (each light's own `shadow:enable` is remembered and given back when it is on again); the Shadow pass renders a frame a second time with it off. The GPU kernels already hold the light passes, so they are not rebuilt. And Cycles' OpenGL display driver is never used (`IsDisplaySupported` false): it could not make its own GL context in our engine ("PathTraceDisplay could not begin update"), and once it took the colour output (with more outputs than colour bound, and in the Final look) the picture stayed black; now every output, colour too, comes through the output driver. | `session.h`, `session.cpp`, `render_delegate.h`, `render_delegate.cpp`, `light.cpp` |

To change the patch: in `proofs\3d-product\.build\cycles`, apply it (`git apply`), edit `src\hydra`, then
`git diff > <repo>\apps\3d\libs\cycles-rostrum.patch`, raise the folder's `-rN` in `lay_out.py`, `rostrum3d/runtime.py`
and `core/build.bat`, rebuild through the lock and lay out.
