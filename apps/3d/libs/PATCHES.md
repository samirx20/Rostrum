# Our changes to the libraries

Rostrum3D's libraries are used as downloaded, except one: **Cycles' Hydra plug-in** (`hdCycles.dll`, Cycles commit
`a456b76`, Apache-2.0). Our changes are one patch, `cycles-rostrum.patch`, applied to `src\hydra` only (the GPU
kernels are not touched, so they are copied, not rebuilt). `build_cycles.bat` applies it and builds; `lay_out.py`
lays the result out in the library folder.

| Library folder | What the patch does | Files |
|---|---|---|
| `-r1` (H22) | A dome the camera doesn't see (`rostrum:seenByCamera`); a panel light's `spread`; light linking (`rostrum:lightsOnly`); the background re-read when only a light's visibility changes | `light.cpp`, `geometry.inl`, `session.cpp` |
| `-r2` (3D-11b) | **Object motion blur.** The plug-in read an object's transform at the frame only, so only camera moves blurred. Now the render settings `rostrum:shutterOpen` / `rostrum:shutterClose` (frames, relative to the frame; the engine sets them, `core/src/hydra.cpp`) tell it the shutter, and each object's transform is sampled inside it, as the camera's already was. Instanced copies get the same samples. A mesh whose own points move (deforming) is not sampled yet. Also a Cycles gap: switching `cycles:integrator:motion_blur` on in a running engine left an object that already had motion sharp (the BVH was not rebuilt) or shaded with a dark smear (its motion data was not written); the switch now marks every object's motion changed. | `geometry.h`, `geometry.inl`, `session.h`, `render_delegate.h`, `render_delegate.cpp` |

To change the patch: in `proofs\3d-product\.build\cycles`, apply it (`git apply`), edit `src\hydra`, then
`git diff > <repo>\apps\3d\libs\cycles-rostrum.patch`, raise the folder's `-rN` in `lay_out.py`, `rostrum3d/runtime.py`
and `core/build.bat`, rebuild through the lock and lay out.
