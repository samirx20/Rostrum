# Rostrum2D guides

## For people using the app

Short pages in everyday words, with the names of the real buttons. The app is one workspace (the picture, the settings of what you picked, and a timeline that is also the layers list), so these pages follow the work, not pages of the screen.

1. [Making your first animation](first-animation.md): start a project, add text, pick and move, animate a value in place with the diamonds, play, do something to several layers, undo.
2. [The screen](the-screen.md): the top bar, the canvas and its tools, select first then act (the settings panel's buttons, right-click, Ctrl+K), the settings panel (Animate on included), the timeline and its two heights, lock and hide, markers.
3. [Drawing](drawing.md): the brush panel and its five tools, the settings panel, strokes, Fill, Draw each frame, hold and onion skin.
4. [Importing pictures and files](importing.md): bring in pictures, video, SVG, PDF, PSD and Figma frames, then work on the pieces.
5. [Exporting a video](exporting.md): the formats in plain words, the settings, and where the file goes.
6. [Files and settings](files.md): saving is automatic; New, Open, Open recent, the sample, Duplicate, versions and the start screen.
7. [Timing to music](timing-to-music.md): hear the project's sound from RostrumSound, the Sound row, mute, pick the soundtrack, show beats, snap and tie to beats and markers, jump beat to beat, open the song in RostrumSound.
8. [Text on a path](text-on-a-path.md): draw a path, put text on it, slide and align it, animate along it.
9. [The curve editor](curve-editor.md): open Curves, read the lines, drag keys and handles, change an ease, the ease keys.
   [Animation layers](animation-layers.md): ⧉ in the timeline, a move laid over the animation with a weight, Add or Replace, fade a layer in.
10. [Characters, sound and styles](characters-sound-styles.md): bones, poses, lip sync and blinks, Add a sound here, moving the frame, text Styles, the Library and Brand kit, Add from a file.

## For agents

How-to pages for the tools and the document. They assume MCP tools and operations. Build the film as one `run_script` program; the operations are for quick changes. `inspect_guide {"topic": ...}` gives a long guide's first sections and the headings of the rest; ask for one with `section` (words of its heading) or `"section": "all"`. Each guide says what exists today, with the tool, operation or field name; where something is planned but missing, it says "not yet".

- [start-here.md](start-here.md): **read first**. The loop (one script, `run_script` with `look`, fix, re-run under the same name, `render_export`), layout first, time by name, keys and ease, the five core tools, where next.
- [script-reference.md](script-reference.md): every script function and field, ids, keys and ease, effects and masks, how a re-run merges, the words from CSS / SVG that work, the first-time surprises, reading errors.
- [the-film-as-one-script.md](the-film-as-one-script.md): **the way to build a whole film**: one script, scenes as functions of a start time, shared timing, loops, your own helpers, `look` on each run; every look tool and how to use your time.
- [lay-out-a-screen.md](lay-out-a-screen.md): arranging anything on screen (a title lock-up, a row of cards, a phone screen, a dashboard) with `row`, `column`, `grid`, `stack` (padding, gap, align), `origin=`, Tailwind words (`tw=`), instead of x / y.
- [timing-to-music.md](timing-to-music.md): markers, layers and keys timed from a marker, beats, the song from RostrumSound (also a people page above).
- [type-and-kinetic-text.md](type-and-kinetic-text.md): setting type and making it move: fonts, variable axes, OpenType features, per-letter animation, gradient letters, scrambling characters into words, building a title in steps.
- [ui-and-product-animation.md](ui-and-product-animation.md): screens, cards, devices and product shots: devices and screen blocks in one call (`device`, `list_rows`, `card`, `bars` …), counting numbers (`counter`), boxes, masks, frosted glass, shadows, tilt and depth.
- [styled-words.md](styled-words.md): a few words of one text in another colour, weight, size or opacity, each keyable (`body=["… ", ("words", {…})]`, `text.run("words").key(…)`).
- [transitions-and-carry-overs.md](transitions-and-carry-overs.md): one section into the next in one call (`transition()`: cut, fade, push, slide, wipe, iris, zoom, blur) and a layer carried over into the next section (`carry()`), as plain keys, masks and effects.
- [tap-and-react.md](tap-and-react.md): a cursor tap that aims at the centre, chases a moving target and reacts by itself (`then=` press, ripple, highlight or your own function).
- [lower-thirds-and-charts.md](lower-thirds-and-charts.md): a name and role on a bar (`lower_third`) and a bar or line chart with axes (`chart`): placing, colours, timing on a marker, taking them apart.
- [shape-and-path-animation.md](shape-and-path-animation.md): vector shapes, the pen, point editing, combining, drawing a stroke on, dashes.
- [text-on-a-path.md](text-on-a-path.md): text along a path (also a people page above).
- [easing-and-overlap.md](easing-and-overlap.md): how a key's ease shapes motion, and checking that moves overlap as you meant.
- [curve-editor.md](curve-editor.md): shaping the easing by hand (also a people page above).
- [animation-layers.md](animation-layers.md): a weighted stack of moves over the keys (`animlayer.add`, `key.add {layer}`), Add or Replace, fades (also a people page above).
- [expressions.md](expressions.md): fields driven by a formula or following something instead of being keyed.
- [data-math-and-graphs.md](data-math-and-graphs.md): equations, function plots, axes and ticks, 3D-looking surfaces, charts from a table, one design filled in from many rows.
- [colour-and-blending.md](colour-and-blending.md): blend modes (screen, multiply, overlay …) and grading a layer: exposure, levels, curves, a .cube LUT.
- [frame-parallax-motion-blur.md](frame-parallax-motion-blur.md): the frame, moving and cutting it, looking through it, pinned titles, depth between layers, motion blur, smears, trails.
- [drawing-and-frame-by-frame.md](drawing-and-frame-by-frame.md): brush strokes and one picture per frame, by tool.
- [painted-backgrounds.md](painted-backgrounds.md): big backgrounds painted in depth layers (far / mid / near) for the frame's moves and parallax, or a title hand-lettered as brush strokes.
- [character-rigging-and-lip-sync.md](character-rigging-and-lip-sync.md): a figure moved from bones and IK (`limb`, `walk`, `idle`, `follow`, `blink`, `layer(id)` in a script), and a mouth that follows a voice.
- [import-and-export.md](import-and-export.md): bringing in SVG, PDF, PSD, Figma, and handing over MP4, WebM, GIF, ProRes 4444, PNG sequence, Lottie, by tool.
- [3d-renders-in-2d.md](3d-renders-in-2d.md): a Rostrum3D item's render (a product shot) inside a composition, following new renders.
- [files.md](files.md): opening or making a project as an agent (`run_open_project`), and the file menu (a people page above).
- Select first, then act, as operations: `group.make`, `group.release`, `mask.make`, `mask.release`, `shape.boolean`, `layer.align`, `layer.distribute`, `layer.match_size`, `layer.anchor` (move the anchor point, `x`, `y` as fractions of the box; `keep_place` keeps the layer where it shows), `style.apply`, `layer.lock`, `layer.unlock`, `layer.hide`, `rig.make` (each takes the layers as its `target`; the screen's action list calls exactly these), and `layer.shift` / `layer.trim` for moving and trimming a layer in time.
