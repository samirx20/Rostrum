# Rostrum3D design round — the lead's frame (Team Hem, 2026-10-24)

Both members follow this. Disagree only with a written reason in your report.

## Fixed decisions (the lead's calls)

1. **Same window as 2D v2, same kit.** 1646×900: header 44 px · icon tool rail 48 px left · viewport centre · settings
   panel 300 px right · bottom panel 284 px (items column 240 px on the left = the scene list, keys on the right).
   The scene list (today's "Outliner") moves into the bottom panel's left column, exactly like 2D's layers list. Materials
   and Shots are not tabs of a left outliner any more: Materials live in the settings panel and a header "Materials"
   chip; Shots are the header crumb (Shot ▾). Same colours, type, radii as 2D (see
   `C:\Users\Sam\.rostrum\waves\results\2d-design-v2\mockups\build_v2.py` CSS: bg #111214, panels #17181b, accent #4d8dff).
2. **Pages: Build · Animate · Render** as three header tabs (PLAN). Build: rail = making tools, bottom panel collapses
   to the scene list + a thin timeline. Animate: rail adds pose/rig tools, bottom panel full timeline. Render: viewport
   shows the final renderer progressively, settings panel = render settings + estimate, bottom panel = shots list and
   render queue. Same document, same viewport position in all three.
3. **Tool rail, icons only, grouped flyouts** (last-used tool shows on the group icon, a small corner triangle marks a
   flyout). Groups, top to bottom: Select/Move (move, rotate, scale) · Shapes (box, sphere, cylinder, cone, torus,
   capsule, plane, disc) · Type & logo (3D text, SVG/logo, from a 2D drawing) · Edit mesh (faces/edges/points, extrude,
   bevel, inset, loop cut, knife) · Sculpt (later) · Paint (brushes from the shared painting kit) · Lights (softbox,
   strip, spot, sun, HDRI sky, light card) · Camera (camera, orbit / crane / dolly rigs, handheld) · Simulate (rigid
   bodies, cloth, particles, smoke & fire) · Import (USD, glTF, FBX, OBJ, Alembic, a 2D item, asset libraries) .
   Booleans are NOT a tool: they are actions in the settings panel when two or more solids are selected (2D's rule).
4. **No floating bars over the viewport.** Only the selected item's gizmo (move/rotate/scale handles) and, in paint
   mode, the brush cursor. View options (shot camera ↔ free camera, exposure, contact shadows, studio light) live in
   the settings panel when nothing is selected (the "Scene" state), and the camera switch is one header control
   "View: Shot camera ▾". Right-click is short: ≤ 6 items (Duplicate, Delete, Group, Frame it, Look through (camera
   or light), Copy material).
5. **Settings panel = 2D's rule.** Only what applies. Groups that hold a changed (non-default) value are open; the
   rest sit as one row of names ("Bevel · Shadow · Visibility · Motion blur") — click a name to open it. Label | field |
   key diamond grid. Colour = swatch + hex; swatch opens the shared colour picker. Multi-select: actions that fit the
   mix first (Combine: union / subtract / intersect; Group; Align; Copy material), then shared values with "Mixed".
6. **Timeline = 2D's.** No full-width selection band. One row per item; a slim blank bar spans first to last key;
   a stretch between two keys is clickable → the settings panel becomes that animation (from → to, start, length,
   easing presets + curve). A second line only where animations overlap. Shared markers as named flags.
7. **Rendering.** The viewport is always the live quick view (Storm). "Look: Quick | Final" in the header switches the
   viewport to progressive Cycles in place (same camera, same size). The **Render** button (header, F12) opens 2D's
   shared export sheet: what (this frame / the shot / all shots), quality (Draft / Good / Final = samples + denoise
   preset, numbers visible under "More"), size, passes for the Editor, and a **time estimate** from a 1-tile probe
   ("about 6 min for 120 frames · 3 s a frame on the RTX 3050"), updated as settings change. Renders run as jobs; the
   viewport stays usable.
8. **Export to the Editor and 2D** = layered EXR sequence (shared/HANDOFFS.md) and live link: a 3D shot placed in 2D or
   the Editor updates when re-rendered. "Send to 2D" / "Send to Editor" are actions on a shot.
9. **Built for the camera.** Everything has "seen by the shot camera" awareness: the viewport can dim what the camera
   can't see; simulation, scatter and paint coverage report what the camera sees first.
10. **Agents.** Every click above is an operation (existing names in `apps/3d/DOCUMENT.md`; new ones marked **(new)**).
    Look tools: existing `look_frame look_sheet look_at render_still render_video inspect_usd_file inspect_shot`; the
    spec adds what's missing (what's here, coverage map, motion check, paint strokes, estimate).

## Running example for every job and mockup (real content, no lorem ipsum)

A product film: **"Aurora" — a matte black wireless earbud case** (rounded box, bevelled; lid; two earbuds) on a
plinth, a bevelled 3D wordmark "AURORA" in brushed aluminium, a softbox key, a strip rim light, an HDRI fill
("studio_small_09"), shot "Hero 01" 1920×1080 24 fps 5 s with an orbit rig; the lid opens 0.8–1.6 s, the buds lift
1.4–2.2 s; the logo lands at the shared marker "logo lands" (3.2 s). A second shot "Close 02". A rigid-body shot drops
twelve buds into a bowl ("Drop 03").
