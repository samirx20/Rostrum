# P-GUI-MOCK · The same screen in Qt and in web, built from one description

**Status:** in progress (Team Sam, brief S3, 2026-10-21).

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
