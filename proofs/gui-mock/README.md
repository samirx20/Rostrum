# P-GUI-MOCK · The same screen in Qt and in web, built from one description

**Status:** done, 2026-10-21 (Team Sam, brief S3). **Verdict: pass. Qt handles the rule as well as web does; keep Qt.**

**In plain words.** We built the same screen twice, once in Qt (what we chose) and once in web tech (React), from one shared list of controls that says when each control applies. Both show only what you can use right now: turn on depth of field and focus distance, aperture and bokeh slide in; turn it off and they slide out; pick a different item and its own controls appear. Side by side the two look and move almost the same, which backs Sam's view: the simplicity comes from the data and the layout, not from the toolkit. Web needed about half the code; Qt keeps the one thing web hasn't shown, a live 3D view inside the same window (S2), so we stay with Qt.

## The question

Sam's rule of individuality: *you only see on screen what you can control at that moment: not greyed out, missing.* Does Qt Quick handle that kind of conditional showing as well as web tech does? Same screen, same data, same look, built twice.

## The shared description (Package A)

- `controls.json`: four kinds of thing (camera, light, text layer, clip) and six items. Each control has an `importance` (`primary`, `secondary`, `deep`) and, if it only applies sometimes, a `validWhen` condition.
- `demo.json`: the same scripted steps for both mockups (three screenshot moments, one ~9 s recording). Each step is an operation (`select`, `set`), the same ones a click makes.
- `check_controls.py`: checks the data and prints what each moment must show. `python -I check_controls.py --json expected.json` writes the reference (`expected.json`).

### Rules both mockups follow

1. **Conditions** (the whole language): `{"is": [control, value]}`, `{"not": c}`, `{"all": [c…]}`, `{"any": [c…]}`, `{"fact": name}` (a fact about the item, e.g. a clip has audio). No `validWhen` = always valid.
2. **Shown:** a control whose condition is false is **absent**, never greyed. `primary` and `secondary` show in the inspector; `deep` ones sit behind a "More" row at the bottom (closed by default).
3. **Order:** groups in the order they first appear in the data; inside a group, primary before secondary, then data order. A group with nothing valid in it is absent too (no empty header).
4. **Selection** changes the inspector to that item's kind. Values are kept per item (select away and back: nothing lost).
5. **Reveal:** a control that becomes valid grows from 0 to its row height while fading in, 160 ms, ease-out; one that stops being valid does the reverse. Rows below slide, nothing jumps. Selection changes swap the whole list at once (no animation).
6. **Nothing hand-placed per panel:** the inspector is one generic list built from the data; the row's widget comes from the control's `type` (`toggle`, `number`, `choice`, `color`, `text`).

The layout and look are the S1 Qt proof's (`proofs/gui-qt/`, tokens in `proofs/gui-qt/qml/Theme.qml`): top bar with the Ctrl K button, project panel left (the six items), a stand-in viewport in the centre, a stand-in timeline below it, the inspector right (280 px). 1600 × 960.

## Results

All in `C:\Users\Sam\.rostrum\waves\results\stage1\p-gui-mock\`:

| Moment | Qt | Web | Side by side |
|---|---|---|---|
| Camera, depth of field off | `qt-camera-dof-off.png` | `web-camera-dof-off.png` | `compare-camera-dof-off.png` |
| Camera, depth of field on | `qt-camera-dof-on.png` | `web-camera-dof-on.png` | `compare-camera-dof-on.png` |
| Text layer, animate on | `qt-text-animate-on.png` | `web-text-animate-on.png` | `compare-text-animate-on.png` |
| 9 s recording (`demo.json` › recording) | `qt-reveal.mp4` | `web-reveal.mp4` | `compare-reveal.mp4` |

Checked: in both, the controls on screen for each moment equal `expected.json` (Qt `main.py --dump-visible`, web `npm run shoot`, which fails on a mismatch). Both recordings are 9.03 s at 30 fps, driven by the same timeline through the same two operations a click uses (`select`, `setValue`). The side-by-sides are made by `ffmpeg` (hstack, labels).

What the lead saw: the two screens are nearly identical in layout, spacing and type. Frame strips of the depth-of-field reveal (0.75 s to 1.0 s) show the same thing in both: three rows open over ~5 frames, fading in, and "Shutter" / "Motion blur" / "More" slide down; nothing jumps or flickers. Selection changes swap the list at once in both. Small differences, none caused by the toolkit: web shows a thin accent bar under number fields and left-aligned numbers, Qt centres them; web's 4-option dropdowns use the browser's own list; both cut "Shadow softness" at the 88 px label column (fix: ~100 px in the real kit).

## The comparison (Package C)

**How each does conditional showing.** The same idea in both: every control of the selected kind stays in the list, and each row animates its own height and opacity between 0 and full by whether its `validWhen` holds. Rows below follow on their own.
- **Qt Quick:** a Python list model (`QAbstractListModel`) of rows; `valid` changes in place (`dataChanged`), so delegates live on. One delegate, `InspectorRow.qml`: `reveal: model.valid ? 1 : 0`, `Behavior on reveal { NumberAnimation { 160 ms } }`, `height: full * reveal`, `opacity: reveal`, in a plain `Column`. The widget comes from `type` through a `Loader`. About 6 lines for the whole reveal. Qt also offers `visible` bindings (instant, no animation), `ListView` add/remove/displaced transitions and `states`/`transitions`; the per-row `Behavior` was the simplest and smoothest.
- **Web (React):** render from state; each row sits in a wrapper with CSS `grid-template-rows: 0fr → 1fr` plus opacity, 160 ms. CSS can't animate `height: auto`, so rows must stay mounted (marked `inert` while collapsed) — the same "keep every row, animate its size" shape as Qt. The widget comes from `type` through a lookup table.

**Lines of code (same screen, same behaviour).**

| | Qt Quick | Web |
|---|---|---|
| Inspector: list, row, reveal, five widgets | 242 (QML) | 189 (TSX + CSS) |
| Data: values per item, conditions, ordering, `select` / `setValue` | 185 (`doc.py`, incl. the list model) | 70 (`logic.ts`, `store.ts`) |
| Rest of the screen (shell, panels, stand-ins, command bar) | 340 (179 copied from S1) | 230 |
| Screenshot / record tooling | 155 (`main.py`, `demo.py`) | 120 (`shoot.mjs`) |

Web is about half the code. Where Qt's extra goes: the Python list model's boilerplate (roles, `dataChanged`) and hand-made widgets (we didn't use Qt Quick Controls, to keep the look). In the real apps the model is written once in the shared GUI kit, not per screen.

**Smoothness.** Equal by eye and in the frame strips. Both at 160 ms ease-out, no layout jumps, no flicker.

**What one could do that the other couldn't.** Nothing in the rule itself. Qt: a live native GPU viewport and video in the same window, proven in S1/S2 (Hydra at a locked 60 fps). Web: that is **still unproven** — a web screen over a live native engine view needs a native window under a transparent web layer or a frame copy every frame; neither was tried. Web had smaller snags: native `<select>` lists can't be styled, focus rings get clipped by collapsing rows. Qt had two quiet traps: a property named like the context property binds to itself (empty screen, no error), and `ListModel` can't hold a value whose type changes between rows.

**Recommendation.** Keep Qt. The rule of individuality is data plus one generic row; both toolkits do it cleanly and look the same. The extra Qt code is a one-time cost in the shared GUI kit. Carry into the kit: the `controls.json` shape (`validWhen`, `importance`, `group`), one generic row that owns its reveal, groups that collapse when empty, a "More" row for deep controls, and a wider label column.

## Attribution rows

Dev tools for the web mockup only; nothing ships. (Qt side adds nothing new: PySide6 is already recorded.)

| Component | Version | Licence | Source | Used in | Linking | Notes | Added |
|---|---|---|---|---|---|---|---|
| React / React DOM | 19.3.1 | MIT | https://github.com/facebook/react | proofs/gui-mock-web | bundled (proof only) | UI for the web mockup | 2026-10-21 |
| Vite, @vitejs/plugin-react | 8.3.5 / 6.1.2 | MIT | https://github.com/vitejs/vite | proofs/gui-mock-web | dev tool | build only | 2026-10-21 |
| TypeScript | 7.0.2 | Apache-2.0 | https://github.com/microsoft/typescript-go | proofs/gui-mock-web | dev tool | type check only | 2026-10-21 |
| Playwright | 1.64.1 | Apache-2.0 | https://github.com/microsoft/playwright | proofs/gui-mock-web | dev tool | screenshots / recording only | 2026-10-21 |
