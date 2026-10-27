# Rostrum2D guides

## For people using the app

Short pages in everyday words, with the names of the real buttons. The app is one workspace (the picture, the settings of what you picked, and a timeline that is also the layers list), so these pages follow the work, not pages of the screen.

1. [Making your first animation](first-animation.md): start a project, add text, pick and move, animate a value in place with the diamonds, play, do something to several layers, undo.
2. [The screen](the-screen.md): the top bar, the canvas and its tools, select first then act (the settings panel's buttons, right-click, Ctrl+K), the settings panel, the timeline and its two heights, lock and hide, markers.
3. [Drawing](drawing.md): the brush panel and its five tools, the settings panel, strokes, Fill, Draw each frame, hold and onion skin.
4. [Importing pictures and files](importing.md): bring in pictures, video, SVG, PDF, PSD and Figma frames, then work on the pieces.
5. [Exporting a video](exporting.md): the formats in plain words, the settings, and where the file goes.
6. [Files and settings](files.md): saving is automatic; New, Open, Open recent, the sample, Duplicate, versions and the start screen.
7. [Timing to music](timing-to-music.md): hear the project's sound from RostrumSound, the Sound row, mute, pick the soundtrack, show beats, snap and tie to beats and markers, jump beat to beat, open the song in RostrumSound.
8. [Text on a path](text-on-a-path.md): draw a path, put text on it, slide and align it, animate along it.
9. [The curve editor](curve-editor.md): open Curves, read the lines, drag keys and handles, change an ease, the ease keys.
10. [Characters, sound and styles](characters-sound-styles.md): bones, poses, lip sync and blinks, Add a sound here, moving the frame, text Styles, the Library and Brand kit, Add from a file.

## For agents

How-to pages for the tools and the document. They assume MCP tools and operations.

- [start-here.md](start-here.md): the document, ids, keys and the first calls.
- [type-and-kinetic-text.md](type-and-kinetic-text.md): setting type and making it move.
- [shape-and-path-animation.md](shape-and-path-animation.md): vector shapes, point editing, combining, drawing-on.
- [text-on-a-path.md](text-on-a-path.md): text along a path (also a people page above).
- [ui-and-product-animation.md](ui-and-product-animation.md): screens, cards, devices and product shots from boxes, masks, glass and depth.
- [easing-and-overlap.md](easing-and-overlap.md): how a key's ease shapes motion, and overlapping actions.
- [curve-editor.md](curve-editor.md): the curve editor (also a people page above).
- [expressions.md](expressions.md): fields that follow something instead of being keyed.
- [colour-and-blending.md](colour-and-blending.md): blend modes and colour adjustments.
- [frame-parallax-motion-blur.md](frame-parallax-motion-blur.md): the frame, moving and cutting it, looking through it, pinned layers, depth and motion blur.
- [drawing-and-frame-by-frame.md](drawing-and-frame-by-frame.md): drawing layers and frame-by-frame work, by tool.
- [painted-backgrounds.md](painted-backgrounds.md): large painted backgrounds with the painting kit.
- [character-rigging-and-lip-sync.md](character-rigging-and-lip-sync.md): joints, poses and lip sync.
- [import-and-export.md](import-and-export.md): importing and exporting, by tool.
- [3d-renders-in-2d.md](3d-renders-in-2d.md): showing a Rostrum3D render inside a composition.
- Select first, then act, as operations: `group.make`, `group.release`, `mask.make`, `mask.release`, `shape.boolean`, `layer.align`, `layer.distribute`, `layer.match_size`, `layer.anchor` (move the anchor point, `x`, `y` as fractions of the box; `keep_place` keeps the layer where it shows), `style.apply`, `layer.lock`, `layer.unlock`, `layer.hide`, `rig.make` (each takes the layers as its `target`; the screen's action list calls exactly these), and `layer.shift` / `layer.trim` for moving and trimming a layer in time.
