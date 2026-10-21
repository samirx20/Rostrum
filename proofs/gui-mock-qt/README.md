# gui-mock-qt: the shared screen in Qt Quick (PySide6)

Built from `../gui-mock/controls.json` and `demo.json` only. Rules: `../gui-mock/README.md`.
`Theme.qml`, `Panel.qml`, `TopBar.qml`, `CommandBar.qml` are copied unchanged from `../gui-qt/qml/` (S1 proof). No GL viewport: the centre is a plain stand-in.

## Run
```
.venv\Scripts\python.exe proofs\gui-mock-qt\main.py                      # the window (Ctrl K, Up/Down work)
... main.py --moment camera-dof-on --screenshot out.png [--dump-visible out.json]
... main.py --record <folder>      # plays demo.json's recording in real time, writes BMP frames + frames.txt
ffmpeg -f concat -safe 0 -i <folder>/frames.txt -vf fps=30,format=yuv420p -c:v libx264 -crf 18 out.mp4
```
A missing moment / item / control exits nonzero.

## How conditional showing is done
- `doc.py` keeps the values per item and has the only two operations, `select(itemId)` and `setValue(itemId, param, value)`. Clicks, keys, the command bar and the demo script all call them. The `validWhen` evaluator (is / not / all / any / fact) is in Python there.
- The inspector's rows are one `QAbstractListModel` (`RowsModel`), rebuilt per kind: group headers, every control of the kind (valid or not), and a More row, in README rule 3 order. `valid` and `value` change in place with `dataChanged`, so delegates are never destroyed on a change.
- One delegate (`InspectorRow.qml`) for every row. `reveal: model.valid ? 1 : 0` with `Behavior on reveal` (160 ms, OutCubic); `height = full * reveal`, `opacity = reveal`. Rows below are in a plain `Column`, so they slide as heights change. A group header's `valid` is "any member valid", so empty headers collapse the same way.
- A selection change resets the model: new delegates start at their final `reveal` (a Behavior does not animate an initial value), so the swap is instant, as the rules want.
- The widget comes from `model.type` through a `Loader` (toggle, number, choice, colour, text): five small files. Choice is segmented for 3 options or fewer, a popup list above that.

## What was easy
- The "each row owns its animation" pattern: about 6 lines and no transition code, no flicker, nothing jumping.
- Python model + QML delegates keeps the data rules out of QML.

## What fought
- `Panel { doc: doc }` binds the property to itself (the component's own property wins the name lookup), so the screen was silently empty with no error. The context property is now `backend`.
- `ListModel` can't hold a role whose type changes between rows (bool / number / string `value`), so the model is a small Python `QAbstractListModel` instead.
- Small widgets inside a `Loader` stretch to its anchors; width must be set from the item's `implicitWidth` (fields fill, switches don't).
- No text-entry for numbers (drag, wheel, arrows only); the colour field is display only. Not needed for this proof.

## Lines of code
Inspector code: `doc.py` 185 (data, evaluator, operations, row model), `qml/Inspector.qml` 27, `qml/InspectorRow.qml` 56, `qml/ToggleField.qml` 18, `NumberField.qml` 50, `ChoiceField.qml` 59, `ColorField.qml` 14, `TextBox.qml` 18 = **427**.
The rest: `main.py` 80, `demo.py` 75, `qml/Main.qml` 58, `ProjectPanel.qml` 44, `Viewer.qml` 19, `Timeline.qml` 24, and copied `Theme.qml` 36, `Panel.qml` 35, `TopBar.qml` 41, `CommandBar.qml` 67 = 479.

## Results
`C:\Users\Sam\.rostrum\waves\results\stage1\p-gui-mock\`: `qt-camera-dof-off.png`, `qt-camera-dof-on.png`, `qt-text-animate-on.png` (1600x960), `qt-reveal.mp4` (9 s, 30 fps). The three moments' visible lists equal `expected.json` (checked with `--dump-visible`).
