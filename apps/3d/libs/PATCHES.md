# Our changes to the libraries

Rostrum3D's libraries are used as downloaded, except two MaterialX lamp shaders in USD's resources (below, from
`-r4`) and **Cycles' Hydra plug-in** (`hdCycles.dll`, Cycles commit
`a456b76`, Apache-2.0). Our changes are one patch, `cycles-rostrum.patch`, applied to `src\hydra` only (the GPU
kernels are not touched, so they are copied, not rebuilt). `build_cycles.bat` applies it and builds; `lay_out.py`
lays the result out in the library folder.

| Library folder | What the patch does | Files |
|---|---|---|
| `-r1` (H22) | A dome the camera doesn't see (`rostrum:seenByCamera`); a panel light's `spread`; light linking (`rostrum:lightsOnly`); the background re-read when only a light's visibility changes | `light.cpp`, `geometry.inl`, `session.cpp` |
| `-r2` (3D-11b) | **Object motion blur.** The plug-in read an object's transform at the frame only, so only camera moves blurred. Now the render settings `rostrum:shutterOpen` / `rostrum:shutterClose` (frames, relative to the frame; the engine sets them, `core/src/hydra.cpp`) tell it the shutter, and each object's transform is sampled inside it, as the camera's already was. Instanced copies get the same samples. A mesh whose own points move (deforming) is not sampled yet. Also a Cycles gap: switching `cycles:integrator:motion_blur` on in a running engine left an object that already had motion sharp (the BVH was not rebuilt) or shaded with a dark smear (its motion data was not written); the switch now marks every object's motion changed. | `geometry.h`, `geometry.inl`, `session.h`, `render_delegate.h`, `render_delegate.cpp` |
| `-r3` (3D-15) | **Passes as EXR layers.** The plug-in made only colour, depth, surface direction and prim ids. It now also maps the Hydra outputs `diffuse`, `glossy`, `transmission`, `volume`, `emission`, `background` and `diffuseDirect` to Cycles' passes of the same names (`kAovToPass`, 32-bit RGB each, `GetDefaultAovDescriptor`), with the surface colour included (`include_albedo`), so they add up to the colour before the noise clean-up. And a render setting `rostrum:castShadows` (default on): off, no light casts a shadow (each light's own `shadow:enable` is remembered and given back when it is on again); the Shadow pass renders a frame a second time with it off. The GPU kernels already hold the light passes, so they are not rebuilt. And Cycles' OpenGL display driver is never used (`IsDisplaySupported` false): with it, the colour output is a half-float picture kept on the graphics card, which the engine can't read back beside the passes, and it never got a GL context of its own in our engine ("PathTraceDisplay could not begin update"). Without it every output, colour too, comes through the output driver as 32-bit floats in memory. (The empty pictures seen while building this were the core reading the colour from its framebuffer, which Hydra leaves empty once more outputs than colour are bound; `core/src/hydra.cpp` `draw()` now reads the colour output itself.) | `session.h`, `session.cpp`, `render_delegate.h`, `render_delegate.cpp`, `light.cpp` |
| `-r4` (3D libs) | **Colour per copy.** An instancer's `primvars:rostrumTint` (one colour4f per copy, ENGINE_CONTRACT § copies) becomes each copy's Object Info colour and alpha, which every material's Cycles graph mixes over its base colour, so a copies item's colour Change near shows in Final. | `instancer.h`, `instancer.cpp`, `geometry.h`, `geometry.inl` |

To change the patch: in `proofs\3d-product\.build\cycles`, apply it (`git apply`), edit `src\hydra`, then
`git diff > <repo>\apps\3d\libs\cycles-rostrum.patch`, raise the folder's `-rN` in `lay_out.py`, `rostrum3d/runtime.py`,
`core/build.bat`, `stylized/build.bat` and `build_cycles.bat`, rebuild through the lock and lay out. The Cycles source
and Blender's library bundle are not kept between rebuilds: `proofs\3d-product\README.md` › Steps to rebuild fetches
them (about 3.3 GB; the bundle commit is the one Cycles a456b76 pins, `60d6e96`), and `build_cycles.bat` builds into
`install-rN\` (about 50 min on this laptop from a clean build folder).

## MaterialX's lamp shaders (`usd-overlay\`, from `-r4`)

Storm draws a material with blocks through USD's MaterialX code, which lights it with MaterialX's own lamp shaders,
`mx_point_light.glsl` and `mx_spot_light.glsl` (every Storm lamp but the sun and the sky is a point there). They let
light fall off as 1 / (distance + 1)², while Storm's own materials and Cycles use 1 / distance²: such a material was
darker than Final under every lamp, far darker close to one (a ball 0.3 m from a bulb: 4 instead of 166 out of 255).
Our copies in `usd-overlay\usd\lib\usd\usdMtlx\resources\libraries\lights\genglsl\` drop the "+ 1" and keep MaterialX's
notice (Apache-2.0). They are text files Storm reads at run time, so USD is not rebuilt: `lay_out.py` lays them over
the bundle's files (it stops if one no longer replaces a bundle file) and lists them in `VERSION.json`. Proof:
`C:\Users\Sam\.rostrum\waves\results\3d-libs\`.
