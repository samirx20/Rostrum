# Import and export

What can come into a Rostrum2D document, and what can go out. Read `start-here` first.

**Where each is today.** An agent has MCP tools for both: `run_import` (SVG, PDF, PSD, an image or video, or a Figma frame, into a composition as one undo step) and `render_export` (mp4, webm, prores4444, gif, png, exr, lottie, motion; always a job: the call waits for its own file (`wait_s`, default 120 s) and replies with it; past that, `inspect_job` with `wait_s` follows it). `render_export` with `what: "video"` is the project render (an mp4 in the renders folder that Sound and the Editor find). The Python calls below are the library, `rostrum2d.io`, for code running next to the document (the screen, a Python agent).

## Import

Every importer returns the same **import tree**; `import_into(doc, tree, into, who)` turns it into ordinary layers in
**one undo step** (`into` = a comp or group id). It returns a report: what could not be carried over, in plain words. Read it.
Images with pixels are written to `<project folder>/imports/<file stem>/` (a document with no folder yet: a scratch folder of the computer, `media.import_dir`; the import never fails for that). Colours with transparency (`#rrggbbaa`) fold into the
layer's opacity. A font that is neither in the app nor installed on this computer is set in the default font, and the import report says so (install the font and pick it in Font to get it back). The report names each kind once, with how many layers it touched (`tree.collapse`); `report` is what did NOT come across, the tree's `notes` is what came across in another form (as a mask, kept hidden).

```python
from rostrum2d.io import svg_tree, pdf_tree, psd_tree, figma_tree, import_into
report = import_into(doc, svg_tree("logo.svg", text="text"), into="main", who="agent:me")
```

| Source | Call | What comes in |
|---|---|---|
| **SVG** | `svg_tree(path, text="text" \| "outline")` | Shapes → `path` layers; groups → groups; images → `image`. Text → editable `text` layers (`"text"`) or paths that look exactly like the source (`"outline"`). CSS, `use`, units are resolved by the engine's reader. |
| **PDF** | `pdf_tree(path, page=0, scale=1.0)` | One page: paths → `path` layers, text → `text`, images → `image`, forms → groups. 1 pt = 1 px unless `scale`. Shadings and clip paths are reported, not carried. Text keeps its bold (weight) and italic (slant) from the font's name, flags and angle. Text objects that follow each other on one baseline in one style (a PDF that stores every letter or word apart) are joined into one text layer per line (`io/pdf_lines.py`). |
| **PSD** | `psd_tree(path)` | Pixel layers → `image` layers, groups → groups. Text, shape, smart-object and adjustment layers arrive as rendered pixels; effects are baked in; a pixel or vector mask is carried as a `mask` or a track-matte layer beside its layer (said in the tree's `notes`, not in `report`); a hidden layer gets `hidden: true` (and so does its matte); unsupported blend modes become `normal` and are reported. |
| **Figma** | `figma_tree(file_key, frame=None, token=None)` | One frame (by name, else the first): frames and groups → groups, rectangles / ellipses → shapes, vectors → paths, text → `text`, nodes with image fills → `image`. Needs the user's own token (the `token` argument or `FIGMA_TOKEN`; without one the importer raises `NoToken`, which the screen shows as "Type your Figma token in the Token box"); never stored or logged. Hidden nodes get `hidden: true`. Built from the API docs, **not yet tested against the live API**. |

Check an import: `look_frame` at full width next to the source, `inspect_item` (no id) for the layer tree, then read the report.

## Export

`render_export` (MCP) exports any format below; `render_export` with `what: "video"` exports the project render as an **mp4** (H.264, Rec.709) of a composition, always a job: the call waits for its own file (`wait_s`, default 120 s) and replies with it; past that, `inspect_job` with `wait_s` to follow
it. In a project it lands in `renders/<item>/vNNN/` with a manifest Sound and the Editor can find; a failed export stays in a
`.partial` folder and is never listed. `start` and `end` (seconds) pick a range.

**MP4 quality.** An mp4 takes one setting, `quality`: `standard`, `high` (the default) or `best`. It sets how much detail the
file keeps, and so its size. Each frame gets the bits its picture needs, so flat motion graphics stay at a few Mbit/s on
every step and only a busy, grainy picture grows. The worst case measured, a 15 s 1080p24 painted piece with a film-grain
overlay: `standard` about 9 MB (smooths fine grain), `high` about 35 MB (keeps it, looks like `best` at normal size), `best`
about 108 MB (for hand-offs and re-grading, not for sending). `bitrate` (Mbit/s, up to 160) asks for an exact number instead. On the screen the
Export panel shows **Quality** only while MP4 is chosen. Both take `quality` and `bitrate`.

The Python `rostrum2d.io.export(engine, fmt, out, alpha=None, depth=None, start=0.0, end=None, quality=None, bitrate=None, gif=None)` goes through the **same engine
path as `look_frame`**, then reads the file back (frame count, size, alpha, depth) and **fails loudly** if it does not match.

| `fmt` | File | Alpha | Bits per channel |
|---|---|---|---|
| `mp4` | one `.mp4` (H.264) | no | 8 |
| `webm` | one `.webm` (VP9) | yes | 8 |
| `gif` | one `.gif` (`gif={"size": "half", "rate": "15"}` by default) | yes | 8 |
| `prores4444` | one `.mov` (ProRes 4444) | yes | 16 |
| `png` | a **sequence**: `out` holds `{frame}` (or is a folder / stem: `<stem>_{frame}.png`), numbered from the first frame of the range | yes | 8 or 16 |

Asking a format for what it cannot carry (alpha on mp4; 16 bits on gif; a quality on png) is refused with the list of ones
that can. The mp4 is made by Windows' own H.264 encoder (the graphics card's encoder when it has one), with no FFmpeg; its width
and height must be even numbers (H.264 needs it), and an odd size is refused at once, before any frame is drawn (the reply says to make the scene one pixel wider or taller). A see-through part of
the picture comes out black. webm and ProRes go through FFmpeg; PNG and EXR are written by the engine, and a GIF by `io/gif_encode.py` (one palette for the whole GIF, a fixed ordered dither, only the changed part of each frame stored).

**GIF size and rate:** `render_export` takes `size` (`full` | `half` | `480`, 480 px wide; default `half`) and `rate` (`15` | `scene`; default `15`) for `gif` only (other formats refuse them). A GIF is for chats and pages: a full-HD one at the scene's rate is many times the size of a half-size 15 fps one. The facts it returns give the GIF's own size, rate and `seconds` (its exact length) with `frames`, the frames it plays at that rate; the Export sheet says the length ("4 s at 15 fps") because the file's stored pictures are fewer. A GIF stores identical neighbouring frames once and holds them longer (the time is still exact), so the read-back `checked.frames` can be a little under the frames asked for; `checked.merged` says how many were joined. Files are named after the item (`loop.gif`), see exporting.md.

### Lottie

`write_lottie(scene, path, progress=None)` (and `to_lottie(scene)`) writes bodymovin 5.x JSON from the scene description and returns a
**report** of everything Lottie could not carry. Today:

- Carried: shapes, paths, images (embedded), groups (as precomps, `clip` as a mask), keys with ease, the background as the
  bottom solid. A solid fill's `fillOpacity` goes to the Lottie fill's own opacity, keyed when it is keyed.
- Text is exported as glyph outlines, with line baselines placed by the engine's own line-box rule (whole-pixel ascent, descent and line tops), so a wrapped paragraph sits where the engine draws it.
- Not exported, always listed in the report: drawings (frame-by-frame), video, tilt, effects, motion blur, conic gradients, soft mask edges, and a text whose font is not found on this computer.
- `progress(done, total)` (optional, as for the other exports) is called as each of the scene's layers is done; the Export sheet's bar follows it.

## Seeing and checking an export

- Before: `look_frame` (`what: "sheet"`) over the whole time range, `look_frame` at the first and last frame.
- After: the facts the export reads back (frames, size, alpha, depth) come with its reply; open the file and compare a frame with
  `look_frame` at the same time. They are drawn by one path, so they should match.
- A video layer's source frames are decoded once at the composition's fps (`ffmpeg` needed).

## Not yet

MP4 on the Mac (it will use the Mac's own encoder; today it says it is not built yet).
