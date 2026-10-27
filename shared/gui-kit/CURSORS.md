# Pointers on the canvas

The pointer always shows what a press will do right there (CANVAS.md 1.1). Every canvas in every app uses the kit's own pointer set, never Qt's stock shapes. Code: `rostrum_gui/cursors.py` (drawing, table), `rostrum_gui/cursor_item.py` (the QML item). Drawings: `icons/cursors/*.svg`. Picture of the full set: `python shared/gui-kit/demo/cursor_sheet.py`.

## The rules
- **The shape is the next press.** It changes when the pointer enters a zone, and the moment Alt, Ctrl or Shift goes down or up, with the mouse still.
- **One shape, one meaning.** `hand` / `hand-grab`: move the view only. `pick`: pick and move. `resize`: change a size. `rotate`: turn. `make`: make something new. The pointing hand is for buttons and links, never on a canvas.
- **Leans with the layer.** `resize` and `rotate` take `angle`: the direction the handle points away from the layer's centre (0 = right, clockwise, degrees), plus the layer's own turn. It snaps to 5° steps and turns about the hotspot, so the press still lands exactly there.
- **Badges, not new shapes.** A held key or a special target adds a badge at the bottom-right. Badges never turn.
- **Locked during a drag.** Once a drag starts, keep its `kind` until release, even when the pointer leaves the handle (the app holds the value; held-key badges still change).
- **Hidden only for the brush.** `none` hides the pointer for painting tools that draw their own ring and centre dot.

## The set
| Kind | Hotspot | Used for |
|---|---|---|
| `pick` | the tip | pick and move |
| `resize` | centre | edge and corner squares (`angle`) |
| `rotate` | centre | just outside a corner, turn zones (`angle`) |
| `anchor` | centre | the anchor point |
| `text` | centre | over text while typing |
| `text-box` | centre | Text tool on empty canvas (click = point text, drag = a wrapping box) |
| `make` | centre | shape tools, new bone |
| `pen` | the nib's tip | Pen (with badges below) |
| `fill` | the paint drop | Fill |
| `dropper` | the tip | eyedropper (Alt with a paint tool) |
| `hand`, `hand-grab` | centre | view pan only |
| `zoom-plus`, `zoom-minus` | lens centre | Zoom tool (Alt = minus) |
| `no` | centre | a press that would do nothing (the status line says why on press) |
| `none` | | hidden: a painting tool's ring |

| Badge | Looks like | Means |
|---|---|---|
| `copy` | blue + | Alt over a layer: drag a copy; pen: add a point |
| `remove` | red − | pen: remove a point |
| `deep` | two squares | Ctrl over a layer inside a group: pick the deepest piece |
| `point` | small square | over a path point, a motion-path key, a gradient stop |
| `bend` | small curve | over a handle end |
| `radius` | corner arc | corner radius dots |
| `shape` | diamond | star / polygon / arc / triangle / spiral handles |
| `close` | ○ | pen: close the path |
| `x` | × | pen: start a new path |
| `caret` | ^ | pen: change a point's handles |
| `slash` | / | pen: carry on from a path's end |
| `wrap` | ¶ | the text box's wrap width |
| `centre` | dot on the hotspot | Alt on a resize square: resize from the centre |

## How an app uses it
```qml
import RostrumCursors 1.0

Item {                                     // a zone: a handle, a layer's body, the whole canvas
    CanvasCursor { kind: "pick"; altBadge: "copy"; ctrlBadge: "deep" }
}
Item {                                     // a corner's turn zone
    CanvasCursor { kind: "rotate"; angle: layer.rotation + cornerAngle }
}
CanvasCursor { kind: altHeld ? "dropper" : "none" }     // a held key can change the kind too
```
- It fills its parent and never takes a press or hover: the zone's own MouseArea / handlers work as before. The topmost item with a pointer under the mouse wins (Qt Quick's rule), so put one inside each zone instead of one big item on top.
- `badge` is the badge with no key held. `altBadge`, `ctrlBadge`, `shiftBadge` replace it while that key is held (the first held of Alt, Ctrl, Shift with a badge wins). `altHeld`, `ctrlHeld`, `shiftHeld` are there for bindings. `shown` says what it shows now (`"pick+copy@0"`), for checks.
- An unknown `kind` or `badge` raises (a scripted run fails) and the pointer shows Qt's "forbidden" shape meanwhile; it never quietly shows nothing.
- From Python: `cursors.cursor(kind, angle, badge, scale, dpr)` gives the `QCursor` (made once, kept); `cursors.picture(...)` the image and hotspot.

## How it works
- **Drawn from SVG** (24 px design: white body, ~1.2 px near-black edge, badges in Theme's accent, `remove` in Theme's danger; the colours are read from `Theme.qml` when drawn). Hotspots live in `cursors.KINDS`, not in the files.
- **Size:** 1x, 1.5x or 2x, the screen's step (the kit draws its windows at 1x, so the step comes from the screen's dpi: a 150 % screen gets 1.5x pointers, the size of the system's own arrow).
- **Keys with the mouse still:** one watcher per window that shows a CanvasCursor hears Alt / Ctrl / Shift going down and up and pokes every CanvasCursor. `QQuickItem.setCursor` applies the new pointer at once when the mouse's last position is inside the item; no hover is needed. The held state is read again on every mouse move and when the app comes back to the front, so an Alt+Tab never leaves a stale badge.
- **Checked by** `tests/test_cursors.py`: a real background window, Alt and Ctrl pressed and let go with no mouse move, the window's pointer compared pixel for pixel; the hotspot under every 5° turn; snapping; one cursor per key; unknown names.
- **Adding a shape:** draw `icons/cursors/<name>.svg` (or `badge-<name>.svg`, 10 px) in the same style, add its hotspot to `KINDS` (even numbers, so it stays a whole pixel at 1.5x) or its place to `BADGES`, update Theme's list, and look at the sheet.
