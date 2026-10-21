# H12 · Rostrum3D starts: an agent makes a product shot through `rostrum-3d` only

**Question:** can an agent, using only the `rostrum-3d` MCP server, build a product shot of our own with a slow camera move, look at it, render a Cycles still and a Storm preview, and does a person's edit (moving the key light) survive the agent's script re-run?

**Verdict: pass.** The whole chain runs: script → document (one history) → scene description → `rostrum3d-core` → USD stage → Hydra (Cycles / Storm) → EXR + OpenColorIO PNG → MP4. The Cycles still is clean (glass, polished steel, anodized edges, real depth of field). A key light moved by a person stayed where they put it when the agent ran its script again. Conditions: the fast Storm preview draws the glass cover as solid grey, and the lighting is a first setup, not yet Apple-level craft.

## Results (private, not in the repo)

| File | What |
|---|---|
| `C:\Users\Sam\.rostrum\waves\results\stage2\3d\product-still-cycles-1080p.png` | the still: frame 24, 1920×1080, Cycles 256 samples + denoise, through OCIO (ACES 2.0 SDR view) |
| `C:\Users\Sam\.rostrum\waves\results\stage2\3d\product-still-cycles-1080p.exr` | the same frame, scene-linear half-float EXR (for the Editor) |
| `C:\Users\Sam\.rostrum\waves\results\stage2\3d\product-move-storm-2s.mp4` | 2 s preview of the camera move (48 frames, 24 fps, Storm, 1080p) |
| `C:\Users\Sam\.rostrum\waves\results\stage2\3d\contact-sheet-storm.png` | `look_sheet`: 6 frames over the shot, labelled |
| `C:\Users\Sam\.rostrum\waves\results\stage2\3d\agent-script-shot.py` | the agent's script (`run_script` source) |

## What the agent did (every step an MCP call, `shared/mcp/call.py` as the client)

1. `run_script` with `agent-script-shot.py`: 7 materials, the device (body, screen, glass cover, dial with steel ring, lens and sensor), floor, backdrop, 4 rect lights aimed at the device, an 85 mm camera with depth of field and two keys (a slow drift across and in), a 2 s shot.
2. `look_frame` (final = Cycles, fast = Storm), saw the framing was too tight, changed the camera in the script and ran it again; `look_sheet` to check the move over time.
3. A second client (`person-sam`) moved the key light with `edit_document` (`light.set` x 0.3, z 0.05).
4. The agent ran its script again: the key light kept the person's position (`inspect_item key` → x 0.3, z 0.05).
5. `render_still` (Cycles, job) and `render_video` (Storm, job, then ffmpeg); both written as project renders with a manifest.
6. `look_at` on frame 24 at three pixels: the glass cover (material glass, 0.57 m away), the lens (lensglass) and the floor, matching the still.

## Numbers (RTX 3050 laptop, 4 GB)

| | |
|---|---|
| Core build | ~1 min (`-j 4`), 15 sources, 0.35 MB program |
| Scene build (15 items, 48 frames of samples) | 12–40 ms |
| Storm frame, 960×540 | 0.8–1.8 s first frame (engine start), then fast |
| Cycles frame, 960×540, 64 samples | 2.1 s; process video memory 0.9 GB |
| Cycles still, 1920×1080, 256 samples + denoise | 28.2 s |
| Storm 2 s preview, 1080p, 48 frames + encode | within one 25 s `inspect_job` wait |
| RAM | 0.3 GB (Storm), 0.6 GB (Cycles) |

## Judged against the quality bar (iPhone Pro film product close-ups)

What holds: clean, physically right materials; the lens dome and ring read as real glass and steel; soft focus falls off like a real lens. What doesn't yet: the screen reads as a flat black slab (no subtle reflections of a softbox across it), the floor is a plain grey, and there is one gradient on the side. That is lighting craft and look tools (a light-rig editor, gradients on cards, HDR environments), the same conditions as P-3D-1, not renderer limits.

## Found and fixed on the way

- Replies were pretty-printed JSON over several lines; now one line each (the conversation is one JSON object per line).
- Material bindings were silently dropped: a helper called `bind(...)` resolved to `std::bind` through argument lookup. Renamed; a failed binding now fails the build loudly.
- The compiler sends every field (contract § 2); the stage builder refused shape fields a shape doesn't use. It now accepts them unread.

## Attribution rows

No new dependency. Existing rows now also used by `apps/3d` (manager: extend "Used for"):

| Name | Version | Licence | Used for | How linked | Ships? | Obligations | Source |
|---|---|---|---|---|---|---|---|
| OpenUSD with Hydra imaging (from Blender's lib-windows_x64) | 26.03 build (`usd_ms.dll`) | Apache-2.0 (Pixar modified) | `apps/3d/core` scene + Hydra | dynamic | yes, with Rostrum3D | Keep the notice | https://openusd.org |
| OpenImageIO + OpenColorIO (+ the ASWF CG config built into OpenColorIO) | from the same bundle | Apache-2.0 / BSD-3-Clause | `apps/3d/core` EXR and PNG out, view transform | dynamic | yes | Keep the notices | https://github.com/AcademySoftwareFoundation |
| libepoxy | from the same bundle | MIT | `apps/3d/core` OpenGL context | dynamic | yes | Keep the MIT notice | https://github.com/anholt/libepoxy |
| Pillow | 13.0.0 | MIT-CMU (HPND) | `rostrum3d` contact sheets | Python package | yes | Keep the notice | https://pypi.org/project/pillow/ |
| ffmpeg (program) | as used by 2D | LGPL/GPL build, separate program | `render_video` encode | separate program | as decided for 2D | — | https://ffmpeg.org |
