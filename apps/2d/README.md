# Rostrum2D

Motion design, type, UI animation, drawing, frame-by-frame and 2D characters.

- **Engine:** Rust (`engine/`, Team Hem): the Blitz + Skia renderer, and the per-frame evaluation of the scene description ([`ENGINE_CONTRACT.md`](ENGINE_CONTRACT.md)).
- **Python layer** (`python/rostrum2d/`, on `rostrum_core`): the 2D document, its operations, the script layer, the engine handle, the MCP server `rostrum-2d`.
- **Screen:** `screen/`, Qt Quick on `shared/gui-kit/`.
- **Guides:** `skills/`, how-to guides for people and agents (techniques, not styles).

## The document

```
doc ─ comps ─ comp (width, height, fps, duration, background)
               └ layers ─ shape | text | image | group (a group holds layers)
                          each layer ─ effects (blur, glow, gradient, shadow) ─ keys
                                     ─ masks ─ keys
                                     ─ keys
```

- **One fields table** (`fields.py`): every field's type, range, group, importance and `valid_when`. The field operations (`text.set`, `glow.set`, `key.set` …), the inspector, the script layer's checks and the scene's defaults all read it.
- **One animation model** (`evaluate.py`, `easing.py`, `ops_keys.py`): a field is still, or animated by keys. Keys are items (`title.opacity.k1500`: id from owner, field and time; kept when moved), so a script re-run merges key by key and field by field. `value.set` is "change it as I see it now": a still field changes, an animated one gets a key at `at`.
- **Operations:** `comp.add`, `layer.add / remove / arrange`, `item.rename`, `effect.add / remove`, `mask.add`, `key.add / remove / clear`, `value.set`, and one `<type>.set` per item type.
- **Drawing** (`ops_draw.py`, `drawing.py`, the kit `shared/painting-kit/`): a drawing layer holds drawings (`frame`s),
  each shown from its frame number until the next one (held). Strokes are kit items (`stroke.add`, one call list = one
  undo step). Guide: `skills/drawing.md`.
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

The engine handle finds the renderer in `ROSTRUM2D_ENGINE`, else `engine/target/release/rostrum*.exe`, else the archive's `rostrum-motion.exe`. Until the engine evaluates scenes itself, Python evaluates each frame and sends page markup (`stopgap_html.py`, TEMPORARY; limits in ENGINE_CONTRACT.md § 7).
