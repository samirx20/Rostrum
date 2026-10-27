# The block view: blocks joined by wires

*Team Hem, K5, 2026-10-28.* One view for every app that joins things with wires: 3D's material blocks first, the
Editor's compositing next. The app gives plain data and gets requests as signals; it changes its own document (one
operation each, so undo and agents see the same change) and hands the new data back. Words on screen: "block",
"wire", never "node" or "socket".

| Piece | File | Does |
|---|---|---|
| View | `qml/RostrumKit/BlockView.qml` | The canvas: blocks, wires, pan / zoom, the hands, the keys, the "+ Add block" button. |
| Block | `BlockItem.qml`, `BlockPort.qml` | One block (header, grey summary line, note) and its port rows. |
| Wire | `BlockWire.qml` | One smooth cubic wire (QtQuick.Shapes, curve renderer). |
| Add list | `BlockAddList.qml` | The popup with a search line on top. |
| Rules (QML) | `Blocks.js` | Port layout, wire rules, loops, search, for the view. |
| Rules (Python) | `rostrum_gui/blocks.py` | The same rules for the app and agents, no Qt; `refusal`, `first_input`, `port_under`, `KIND_COLOURS`. |
| Demo | `demo/blocks_preview.py` | A toy material graph (10 types, 30 blocks), pictures and drag timings. |

`tests/test_blocks.py` checks loops, kinds and search, and that `Blocks.js` and `blocks.py` answer the same.

## Hooking it up

```qml
BlockView {
    objectName: "blockView"                     // (its own default)
    catalogue: app.blockTypes                    // what the add list offers
    blocks: app.blocks; wires: app.wires; selected: app.selectedBlock
    kindColours: app.kindColours                 // blocks.KIND_COLOURS, or the app's own
    converts: app.converts                       // {"number": ["colour"], "colour": ["number"]}: kinds that also feed others
    onAddRequested: (type, x, y, fromPort) => app.addBlock(type, x, y, fromPort)
    onMoved: (id, x, y) => app.moveBlock(id, x, y)
    onConnectRequested: (from, to) => app.connect(from, to)
    onDisconnectRequested: (to) => app.disconnect(to)
    onRemoveRequested: (ids) => app.remove(ids)
    onPicked: (id) => app.pickBlock(id)          // "" = a click on empty space
    onEscaped: app.stepBack()
}
```

Data (plain lists and maps; x / y in canvas units, the view's zoom scales them):
- `catalogue`: `[{type, label, group, words?, inputs: [{name, label, kind}], outputs: [{name, label, kind}]}]`. The add
  list shows it by `group` (in catalogue order) and searches label, then group and `words`.
- `blocks`: `[{id, type, label, x, y, summary?, note?, removable?, inputs: [{name, label, kind, linked}], outputs: [...]}]`.
  `summary` is the short grey line ("Scale 8"); `note` sits at its right in the warning colour ("Final only");
  `removable: false` (a Surface) ignores Delete.
- `wires`: `[{from: "id.output", to: "id.input"}]`. One wire per input; an output feeds any number.
- `selected`: the picked block's id (outlined; its wires drawn a little stronger).

Signals, and what the app does with them:
- `addRequested(type, x, y, fromPort)`: make the block at x, y. `fromPort` is "" or "id.output" when the list opened
  from a wire dropped on nothing: also wire it into the new block, `blocks.first_input(entry, kind, converts)` says
  which input (the view already placed the block so that input sits level with the drop).
- `moved(id, x, y)`: once, at the release. The view draws the move itself; the block stays where dropped until new
  data comes.
- `connectRequested(from, to)`: check `blocks.refusal(blocks, wires, from, to, converts)` ("" = fine; else `unknown`,
  `same-block`, `kind`, `loop`), then replace the input's old wire. The view never offers a refused one, but an
  agent or a stale screen can.
- `disconnectRequested(to)`: remove the wire into that input. Moving a wire end from one input to another sends
  `disconnectRequested(old)` then `connectRequested(from, new)`.
- `removeRequested(ids)`, `picked(id)`, `escaped()` (Esc with no drag, wire or list open; named so because
  `escape` is a reserved word in QML's JavaScript).

## What a person does

| Hand | Result |
|---|---|
| Drag a block | Moves it (4 px before it counts, so a click only picks). |
| Drag from a port to another | Wires them. The ports it may land on light up, the rest dim; over a block it snaps to the nearest port that takes it. Works from an output or from an empty input. |
| Drag a wired input's end | Picks the wire up: drop it on another input to move it, on nothing to remove it. |
| Drop a new wire on nothing | The add list opens there with only the types that wire can feed; the pick is added and wired. |
| Drag empty space, middle-drag, Space + drag | Pans. |
| Wheel | Zooms about the pointer, 25 % to 200 %. |
| F | Fits every block (at most 100 %). The view fits once by itself when the first blocks arrive. |
| Delete / Backspace | Removes the picked block (not one with `removable: false`). |
| Tab, double-click or right-click on empty space, "+ Add block" | The add list: type to filter, Up / Down + Enter or a click, Esc closes. |
| Esc | Drops the wire or the block drag in hand (the block goes back); otherwise `escaped()`. |

Pointers (CURSORS.md): empty space `hand` (`hand-grab` while panning), a block `pick`, a port `make` (a wired input:
`pick`, it picks the wire up).

## Names for scripted hands

`blockView`, `block:<id>`, `blockHeader:<id>`, `port:<id>:in:<name>`, `port:<id>:out:<name>`, `blockAddButton`,
`blockAddList`, `blockAddSearch`, `blockAddItem:<type>`. Read-only checks may call `portState(id, side, name, kind)`
(0 at rest, 1 may take the wire being drawn, 2 dimmed).

## Speed

A drag moves one block item (or the live wire's end) and redraws only the wires bound to that block; nothing is rebuilt
until the app sends new data at the release. The demo measures it with real mouse moves, 30 blocks, 1646 × 900,
offscreen on this laptop: a block drag 0.5 ms per move (95th: 1.8), 3.2 ms with the frame drawn (95th: 4.9; that
includes reading the picture back); a wire drag 0.5 ms (95th: 2.0), 2.6 ms with the frame (95th: 4.8).

## Layout numbers

Every block is 180 wide: a 28 header, an 18 summary line when it has a summary or note, then 22 per port row (outputs
first, then inputs), 4 above and 6 below the rows; a port is a 10 px circle on the edge. `blocks.height(b)` and
`blocks.port_at(b, side, name)` give the same numbers in Python (an agent placing blocks so they don't overlap).

## Not built yet

- The kind colours live in `blocks.KIND_COLOURS` (the app passes them); a Theme token set would put them with the
  other colours.
- Box-select, copy / paste of blocks, frames around groups of blocks, a mini map.
- No layout-check states yet (the demo takes its pictures directly).
