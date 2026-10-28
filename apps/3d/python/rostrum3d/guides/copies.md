# Copies: one thing, many times

A **copies** item draws what is inside it again and again, laid out for you, without making a thousand items. The scene stays
small (one source, a few numbers); the engine draws the copies as instances, up to 10,000. Use it for rows of lamps, a ring of
chairs, grass, pebbles, buds on a branch, confetti.

## Make them

`copies.make` on one or more items wraps them in a new copies item at their place (they move to the copies item's origin and keep
their turn and size). In a script: `copies("buds", bud, layout="grid", count=12, columns=4)`, or `with copies("buds", layout="circle", count=8):` and
make the source inside. Several sources: each copy picks one of them (by the seed). Any mesh, combine, import, group or clay can be a source.
**Colour variety** is several sources: the same shape two to five times, each with its own material (a red, a cream and a
blue die), `copies("dice", [red, cream, blue], …)`; the seed spreads them over the copies, falling or not. (A colour effector
tints copies near a point instead, and doesn't show on copies still simulating.)

| layout | fields |
|---|---|
| `line` | `count`; `spacingX/Y/Z` = the step from one copy to the next (default 0.2, 0, 0) |
| `grid` | `count` is the total, `columns`; `spacingX` = between columns, `spacingZ` = between rows (rows fill from the first) |
| `circle` | `count`, `radius`; `faceOut` turns each copy to face away from the middle |
| `surface` | `surface` = the item they stand on; `amountBy` count or density (per m²); `minSpacing`; `alongSurface`; `onTop` |
| `pour` | a stream from a mouth at the copies item's origin: `radius` = the mouth's radius (each copy starts somewhere inside that disc, flat in the item's own x z); `pourTime` = seconds the copies leave over, evenly, from `fallStart` (default 2; 0 = all at once); `pourSpeed` = m/s each leaves with along the copies item's own down (0: they just drop; turn the copies item, `rx`/`rz`, to aim it sideways); `pourSpread` = degrees off that aim (default 10), so the stream fans out |

Where the copies sit: a line starts at the copies item's origin and steps by `spacing`; a grid's first copy is at the origin
and the columns and rows go towards +x and +z (not centred: move the copies item back by half the grid to centre it); a circle
and a pour are centred on the origin.

A **pour** only moves once it falls (`simulate("falls")`, the guide *simulate*); before that the copies sit together in the
mouth. Make it the brief's way, in one script: put the source where the spout is, `copies("beans", bean, layout="pour",
count=60, radius=0.02, pourTime=4, pourSpeed=0.8).simulate("falls")`, run the simulation, look, change, re-run. Keep each
copy clear of the one before: `pourTime` / `count` seconds apart at `pourSpeed` (plus gravity) should move it more than its
own size, else they leave the mouth inside each other and burst apart.

`copies.scatter` is `copies.make` with layout surface. The copies item has its own place, turn and size like any item: move the
copies item to move them all, and key it. Framing it (`shot.frame`, Frame the selection) frames all its copies as they stand
at that moment: laid out, held, keyed or fallen.

Vary them a little: `seed`, `varyMove` (metres), `varyTurn` (degrees round the copy's own up only; a falling copy tumbles as it lands), `varyScale` (0–1), and on a falling copies item
`varyStart` (seconds): each copy starts to fall up to that much later than the item's `fallStart`, so they land one after another
instead of all at once (`copies.set` it after `simulate="falls"`; before that it is refused, since nothing falls). With
`varyStart` (and in a pour) a copy is not there until it starts to fall: it appears at its place and drops, so nothing hangs
in the air waiting; renders, looks, framing and picking all leave it out until then. The same seed
gives the same copies and the same waits, whatever else changes; change the seed to shuffle. Nothing about a vary is random
between renders. In the window these are the **Vary** rows in the copies item's settings, right under the layout's: Seed, Move,
Turn, Size, and Start while it falls.

## Run a script again, safely

`copies.make` (and the script's `copies(...)`) with the id of an existing copies item works like `copies.set`: no second item,
and a copy somebody put by hand stays where it is. Change anything with `copies.set` (every field above is a field of the item).

## Keep a copy where it is

`copies.hold` {copy, x, y, z, rx, ry, rz, s} puts one copy somewhere in the copies item's own space and keeps it: a layout change
(count, spacing, a re-run) never moves it. `copies.release` lets one (`copy`) or all go back to their place in the layout.
Copies are counted from 0 in the order the layout makes them. A person does the same by dragging a copy with the gizmo.

`copies.key` {copy, prop (x y z rx ry rz), t, v, ease?} keys one copy: it moves between its keys like any keyed field, the rest
of it stays as laid out. Turn into keys on a falling copies item keys every copy (`sim.to_keys`, the Simulate guide), with only
the keys that matter: a copy at rest keeps two, a bouncing one a key at each bounce and a few per arc (within 1 mm / 0.1°);
`copies.release` lets a keyed copy go back too. In the window, dragging a keyed copy with the gizmo keys it at the
playhead's frame (the handles stand where the copy is then); a copy still simulating is moved where its fall starts.

## Scatter over a surface, and what the camera sees

`surface` can be a plane, a mesh, a clay or an import; copies are spread over its area evenly, `minSpacing` keeps them apart (a scatter starts at the source's own width, so they lie side by side; 0 lets them touch and pile; when the surface is full at that distance the rest come closer, so the count is always met), and
`alongSurface` stands each along the surface's direction there; `onTop` (on by default) uses only the faces that look up, where things can rest (a box's top, not its sides; off for moss on a wall). By default **`onlySeen` is on**: copies the shot camera never
sees (behind it, behind other things, outside the picture, at any of a few frames of the shot) are not drawn or rendered at all,
so a field of 400,000 blades costs what the camera sees. The reply of `look_frame` says it: "Copies: grass 212 of 400 seen by Hero 01";
`inspect_shot` lists the same. Turn `onlySeen` off for a scene seen from other angles (a reflection, a second shot).
Counts that look low after you moved the camera are right: look again after the move so the engine tests with the new camera.

## Change the ones near something

`effector.add` on a copies item: `kind`, `near` (the item the change is centred on), `radius`, `amount`, `falloff`. To centre it on a point you move rather than a real thing, add a small sphere with
`"guide": true` (Display › Only in the view): the view draws it as a handle, renders and `look_frame` never show it.

| kind | amount | also |
|---|---|---|
| `scale` | extra size at the centre: 0.5 = half again bigger, −1 = gone | |
| `turn` | degrees | `axis` x y z |
| `push` | metres away from the centre | |
| `colour` | 0–1 mix | `colour` |

The change fades from the centre to the radius (`falloff` smooth or linear). The centre follows `near` every frame, so move that
item (or key it) and the effect travels through the copies: a ball rolling past a row of grass bends it; a light sphere that
brightens petals as it passes. Key the effector's `amount`, `radius` or `colour` for change over time.
A colour effector shows in Final on a source with a material (laid over its base colour), and in Quick only on a source with no material; a block-view material and a copies item still simulating show no per-copy colour.

## Mistakes the checker names

- A copies item with nothing inside it, or only effectors: "has nothing to copy".
- layout `surface` with no `surface`, or the surface being (inside) the thing copied.
- `count` while `amountBy` is density (the count then comes from the area), `columns` outside a grid, `radius` outside a circle or a pour, `pourTime`/`pourSpeed`/`pourSpread` outside a pour: the
  field is refused until the layout makes it apply.
- `copies.hold` with a copy number past the last one.
