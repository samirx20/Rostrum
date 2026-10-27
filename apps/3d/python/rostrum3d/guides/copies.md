# Copies: one thing, many times

A **copies** item draws what is inside it again and again, laid out for you, without making a thousand items. The scene stays
small (one source, a few numbers); the engine draws the copies as instances, up to 10,000. Use it for rows of lamps, a ring of
chairs, grass, pebbles, buds on a branch, confetti.

## Make them

`copies.make` on one or more items wraps them in a new copies item at their place (they move to the copies item's origin and keep
their turn and size). In a script: `copies("buds", bud, layout="grid", count=12, columns=4)`, or `with copies("buds", layout="circle", count=8):` and
make the source inside. Several sources: each copy picks one of them (by the seed). Any mesh, combine, import, group or clay can be a source.

| layout | fields |
|---|---|
| `line` | `count`; `spacingX/Y/Z` = the step from one copy to the next (default 0.2, 0, 0) |
| `grid` | `count` is the total, `columns`; `spacingX` = between columns, `spacingZ` = between rows (rows fill from the first) |
| `circle` | `count`, `radius`; `faceOut` turns each copy to face away from the middle |
| `surface` | `surface` = the item they stand on; `amountBy` count or density (per m²); `minSpacing`; `alongSurface`; `onTop` |

`copies.scatter` is `copies.make` with layout surface. The copies item has its own place, turn and size like any item: move the
copies item to move them all, and key it.

Vary them a little: `seed`, `varyMove` (metres), `varyTurn` (degrees round up), `varyScale` (0–1). The same seed gives the same copies,
whatever else changes; change the seed to shuffle. Nothing about a vary is random between renders.

## Run a script again, safely

`copies.make` (and the script's `copies(...)`) with the id of an existing copies item works like `copies.set`: no second item,
and a copy somebody put by hand stays where it is. Change anything with `copies.set` (every field above is a field of the item).

## Keep a copy where it is

`copies.hold` {copy, x, y, z, rx, ry, rz, s} puts one copy somewhere in the copies item's own space and keeps it: a layout change
(count, spacing, a re-run) never moves it. `copies.release` lets one (`copy`) or all go back to their place in the layout.
Copies are counted from 0 in the order the layout makes them. A person does the same by dragging a copy with the gizmo.

## Scatter over a surface, and what the camera sees

`surface` can be a plane, a mesh, a clay or an import; copies are spread over its area evenly, `minSpacing` keeps them apart (a scatter starts at the source's own width, so they lie side by side; 0 lets them touch and pile; when the surface is full at that distance the rest come closer, so the count is always met), and
`alongSurface` stands each along the surface's direction there; `onTop` (on by default) uses only the faces that look up, where things can rest (a box's top, not its sides; off for moss on a wall). By default **`onlySeen` is on**: copies the shot camera never
sees (behind it, behind other things, outside the picture, at any of a few frames of the shot) are not drawn or rendered at all,
so a field of 400,000 blades costs what the camera sees. The reply of `look_frame` says it: "Copies: grass 212 of 400 seen by Hero 01";
`inspect_shot` lists the same. Turn `onlySeen` off for a scene seen from other angles (a reflection, a second shot).
Counts that look low after you moved the camera are right: look again after the move so the engine tests with the new camera.

## Change the ones near something

`effector.add` on a copies item: `kind`, `near` (the item the change is centred on), `radius`, `amount`, `falloff`.

| kind | amount | also |
|---|---|---|
| `scale` | extra size at the centre: 0.5 = half again bigger, −1 = gone | |
| `turn` | degrees | `axis` x y z |
| `push` | metres away from the centre | |
| `colour` | 0–1 mix | `colour` |

The change fades from the centre to the radius (`falloff` smooth or linear). The centre follows `near` every frame, so move that
item (or key it) and the effect travels through the copies: a ball rolling past a row of grass bends it; a light sphere that
brightens petals as it passes. Key the effector's `amount`, `radius` or `colour` for change over time.
A colour effector needs the source's material to read per-copy colour; if the renderer can't show it, the reply says so.

## Mistakes the checker names

- A copies item with nothing inside it, or only effectors: "has nothing to copy".
- layout `surface` with no `surface`, or the surface being (inside) the thing copied.
- `count` while `amountBy` is density (the count then comes from the area), `columns` outside a grid, `radius` outside a circle: the
  field is refused until the layout makes it apply.
- `copies.hold` with a copy number past the last one.
