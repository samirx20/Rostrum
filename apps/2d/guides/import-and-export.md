# Import and export

What can come into a Rostrum2D document, and what can go out. Read `start-here` first.

**Where each is today.** Import (SVG, PDF, PSD, Figma) and export (every format but the project mp4) are a **Python
library**, `rostrum2d.io`, used by the screen; they are **not yet MCP tools**. From an MCP-only agent the way out is
`render_video` (mp4). The Python calls below are for code running next to the document (a screen, a Python agent).

## Import

Every importer returns the same **import tree**; `import_into(doc, tree, into, who)` turns it into ordinary layers in
**one undo step** (`into` = a comp or group id). It returns a report: what could not be carried over, in plain words. Read it.
Images with pixels are written to `<project folder>/imports/<file stem>/`. Colours with transparency (`#rrggbbaa`) fold into the
layer's opacity. A font the app lacks is replaced by the default and reported.

```python
from rostrum2d.io import svg_tree, pdf_tree, psd_tree, figma_tree, import_into
report = import_into(doc, svg_tree("logo.svg", text="text"), into="main", who="agent:me")
```

| Source | Call | What comes in |
|---|---|---|
| **SVG** | `svg_tree(path, text="text" \| "outline")` | Shapes → `path` layers; groups → groups; images → `image`. Text → editable `text` layers (`"text"`) or paths that look exactly like the source (`"outline"`). CSS, `use`, units are resolved by the engine's reader. |
| **PDF** | `pdf_tree(path, page=0, scale=1.0)` | One page: paths → `path` layers, text → `text`, images → `image`, forms → groups. 1 pt = 1 px unless `scale`. Shadings and clip paths are reported, not carried. |
| **PSD** | `psd_tree(path)` | Pixel layers → `image` layers, groups → groups. Text, shape, smart-object and adjustment layers arrive as rendered pixels; masks and effects are baked in; unsupported blend modes become `normal` and are reported. |
| **Figma** | `figma_tree(file_key, frame=None, token=None)` | One frame (by name, else the first): frames and groups → groups, rectangles / ellipses → shapes, vectors → paths, text → `text`, nodes with image fills → `image`. Needs the user's own token (the `token` argument or `FIGMA_TOKEN`); never stored or logged. Built from the API docs, **not yet tested against the live API**. |

Check an import: `look_frame` at full width next to the source, `inspect_item` (no id) for the layer tree, then read the report.

## Export

`render_video` (MCP) exports an **mp4** (H.264, Rec.709) of a composition, always a job: `inspect_job` with `wait_s` to follow
it. In a project it lands in `renders/<item>/vNNN/` with a manifest Sound and the Editor can find; a failed export stays in a
`.partial` folder and is never listed. `start` and `end` (seconds) pick a range.

The Python `rostrum2d.io.export(engine, fmt, out, alpha=None, depth=None, start=0.0, end=None)` goes through the **same engine
path as `look_frame`**, then reads the file back (frame count, size, alpha, depth) and **fails loudly** if it does not match.

| `fmt` | File | Alpha | Bits per channel |
|---|---|---|---|
| `mp4` | one `.mp4` (H.264) | no | 8 |
| `webm` | one `.webm` (VP9) | yes | 8 |
| `gif` | one `.gif` | yes | 8 |
| `prores4444` | one `.mov` (ProRes 4444) | yes | 16 |
| `png` | a **sequence**: `out` holds `{frame}` (or is a folder / stem: `<stem>_{frame}.png`), numbered from the first frame of the range | yes | 8 or 16 |

Asking a format for what it cannot carry (alpha on mp4; 16 bits on gif) is refused with the list of ones that can. mp4, webm and
ProRes go through FFmpeg; GIF and PNG are written by the engine. In the shipped app the mp4 will use the system encoder
(the x264 build used here is for development).

### Lottie

`write_lottie(scene, path)` (and `to_lottie(scene)`) writes bodymovin 5.x JSON from the scene description and returns a
**report** of everything Lottie could not carry. Today:

- Carried: shapes, paths, images (embedded), groups (as precomps, `clip` as a mask), keys with ease, the background as the
  bottom solid.
- Not exported, always listed in the report: text, drawings, video, tilt, effects, conic gradients, soft mask edges.

## Seeing and checking an export

- Before: `look_sheet` over the whole time range, `look_frame` at the first and last frame.
- After: the facts the export reads back (frames, size, alpha, depth) come with its reply; open the file and compare a frame with
  `look_frame` at the same time. They are drawn by one path, so they should match.
- A video layer's source frames are decoded once at the composition's fps (`ffmpeg` needed).

## Not yet

MCP tools for import and for the formats other than mp4; sound in a 2D video export (sound is RostrumSound's: 2D mp4 has none);
Mac H.264 through the system encoder.
