# Rostrum2D

Motion design, type, UI animation, drawing, frame-by-frame and 2D characters.

- **Engine:** Rust (`engine/`, see `engine/README.md`): the Blitz + Skia renderer (moved in and four gaps fixed in H5), and the per-frame evaluation of the scene description ([`ENGINE_CONTRACT.md`](ENGINE_CONTRACT.md)).
- **Python layer** (`python/rostrum2d/`, on `rostrum_core`): the 2D document, its operations, the script layer, the engine handle, the MCP server `rostrum-2d`.
- **Screen:** `screen/`, Qt Quick on `shared/gui-kit/`.
- **Guides:** `guides/`, how-to guides for people and agents (techniques, not styles).

## The document

```
doc ─ comps ─ comp (width, height, fps, duration, background)
               └ layers ─ shape | path | text | image | video | drawing | group (a group holds layers) | rig
                          rig = a group that also holds bones, IK chains and binds (`RIG.md`, `guides/character-rigging-and-lip-sync.md`)
                          each layer ─ effects (blur, glow, gradient, backdrop, shadow) ─ keys
                                     ─ masks ─ keys
                                     ─ keys
```

- **One fields table** (`fields.py`): every field's type, range, group, importance and `valid_when`. The field operations (`text.set`, `glow.set`, `key.set` …), the inspector, the script layer's checks and the scene's defaults all read it.
- **One animation model** (`evaluate.py`, `easing.py`, `ops_keys.py`): a field is still, or animated by keys. Keys are items (`title.opacity.k1500`: id from owner, field and time; kept when moved), so a script re-run merges key by key and field by field. `value.set` is "change it as I see it now": a still field changes, an animated one gets a key at `at`.
- **Operations:** `comp.add`, `layer.add / remove / arrange`, `item.rename`, `effect.add / remove`, `mask.add`, `key.add / remove / clear`, `value.set`, and one `<type>.set` per item type.
- **Drawing** (`ops_draw.py`, `drawing.py`, the kit `shared/painting-kit/`): a drawing layer holds drawings (`frame`s),
  each shown from its frame number until the next one (held). Strokes are kit items (`stroke.add`, one call list = one
  undo step). Guide: `guides/drawing-and-frame-by-frame.md`.
- **Vectors** (`pathdata.py`, `ops_path.py`, `ops_boolean.py`): a path layer's `d` (absolute M / L / C / Z) is the one
  truth; `path.add_point / set_point / remove_point / close / fit`, `shape.to_path`, `path.boolean` (skia-pathops). The
  pen on the Design page (`screen/screen2d/pen.py`) writes the same `d`.
- **Video** (`video.py`): decoded once with `ffmpeg` into a cache keyed by the file's content; the engine picks the
  frame by the frame time, so preview ≡ export.
- **Script layer** (`script.py`): `comp(...)`, `shape / text / image / group(...)`, `.key(field, {time: value}, ease=)`, `.effect(type, ...)`, `.mask(...)`, `with group(...):`. See its docstring.

## Use

```
uv pip install --python .venv\Scripts\python.exe -e apps\2d\python
.venv\Scripts\python.exe -m pytest -q apps\2d\python\tests       # well under a second
```

```python
from rostrum_core import Document
from rostrum2d import KIND, run_source
from rostrum2d.scene import describe
from rostrum2d.engine import Engine

doc = Document.new(KIND, folder=r"C:\...\My Film", item="intro")
doc.run_script("intro.py", run_source(open("intro.py").read(), "intro.py"))
with Engine() as eng:                      # one renderer process, ended on exit
    eng.load(describe(doc.data))
    eng.still(1.2, r"C:\...\frame.png")
    eng.video(r"C:\...\intro.mp4")
```

The engine handle finds the engine in `ROSTRUM2D_ENGINE`, else `engine/target/release/` or `engine/target/agent/` `rostrum*.exe`, and fails loudly if there is none. Python only describes the scene (`scene.describe`); the engine evaluates and draws every frame (ENGINE_CONTRACT.md), for the canvas, the look tools and export alike.
