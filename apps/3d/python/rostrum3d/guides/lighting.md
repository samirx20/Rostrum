# Lighting: what each light and field does

Lights are items (`light.add`, `light.set`). This guide explains the kinds of light, every field, and the techniques product and object lighting is built from. It doesn't give finished setups: build the light your shot needs and judge it in a render from the shot's camera.

## Kinds

- **`rect`** — a rectangular panel (`width`, `height` in metres) shining along its −Z: **Soft light** in the Lights list. The softbox of a photo studio. The workhorse of product lighting.
- **`disk`** — a round panel (`radius`), also shining along −Z. Gives round highlights (a beauty dish).
- **`strip`** — a long thin panel: `length` along its X, `width` across it (along its Y), shining along −Z. The strip softbox of a product studio (a `rect` with its own two sizes, so you think in length and width).
- **`sphere`** — a ball of light (`radius`) shining every way: a bulb, a candle flame, a practical lamp in the scene.
- **`spot`** — a small bulb whose light is cut to a cone along its −Z: a pool of light on a floor or a wall. **`cone`** is the cone's full width in degrees; **`softness`** (0–1) how gradually the pool's edge fades (0 = a hard edge). A new spot starts as a 0.05 m bulb (`radius`). The Quick view and Final draw the same pool: the same size, edge and brightness (the Quick view's soft edge is a close match of Final's, brief 10b); only Final shows the spot's shadows. The cone is saved in the scene as UsdLux shaping, which other USD programs read.
- **`distant`** — parallel light from far away: the sun. Only its rotation matters; **`angle`** is how wide the sun looks (0.53° is the real sun; bigger = softer shadows).
- **`dome`** — light from all around, an infinitely large sphere. With **`texture`** (an HDR or EXR image) it lights and reflects a real place; without, an even sky in `color`. **`turn`** spins it around the up axis (moves the sun and the horizon's features; a dome has no other rotation or position). **`seenByCamera`** off: the dome still lights the scene and shows in reflections, but behind the object the camera sees the shot's `background` colour (Cycles needs the patched plug-in, see the contract; Storm: yes).

## Fields

- **`intensity`** and **`exposure`** — brightness, in USD's units (the same in Storm and Cycles): an HDR dome at intensity 1, exposure 0 lights the scene with the photo's own values; a sun (`distant`, `normalize` on) gives `intensity` lux, so a white floor facing it reads intensity ÷ π — daylight floors near 1 need a sun of about 3, a real midday sun is far brighter and is brought down with the render's `exposure`. `exposure` is in stops: +1 doubles, −1 halves. Use `exposure` to balance lights against each other, so the ratios read in stops like a photographer's.
- **`color`** and **`temperature`** — `temperature` in kelvin (2700 a warm bulb, 4000 neutral, 5600 daylight, 7500 cool shade) gives physically right white light; 0 turns it off and only `color` counts. A little warm/cool contrast between two lights separates forms.
- **`normalize`** — off (default): `intensity` is the panel's own brightness, so a bigger light gives more light. On: `intensity` is shared out over the panel's area, so the size changes only the softness and you can resize without rebalancing. Numbers for both: *Brightness at product scale* below.
- **`shadows`** — whether it casts shadows. Leave it on unless a fill light's shadows clutter the picture.
- **Size and distance** — softness depends on how big the light looks from the object. A large panel close by gives soft light with gentle shadows; the same panel far away gets small and hard. Brightness also falls off with distance (four times dimmer at twice the distance).

## Brightness at product scale (measured)

Light falls off with the square of the distance, so a product a few centimetres across, lit from half a metre, needs very different numbers from a room. Measured in Cycles (H23) on a 92 mm pale grey puck (`#bdbdbd`, roughness 0.55), one 0.3 m square panel at 45° above, `normalize` on, no other light, the PNG value of the puck's top (0–255):

| Panel distance | intensity 0.1 | 0.3 | 1 | 3 | 10 | 30 |
|---|---|---|---|---|---|---|
| 0.25 m | 70 | 127 | 190 | 227 | 246 | 253 (white) |
| 0.5 m | 27 | 70 | 132 | 189 | 230 | 246 |
| 1 m | 3 | 21 | 65 | 121 | 184 | 224 |

- **Starting number, `normalize` on:** intensity ≈ **4 × distance²** (metres) puts a pale surface in the middle of the range: 0.25 at 0.25 m, 1 at 0.5 m, 4 at 1 m. A key light is usually that or up to 3× more; a fill 4–8× less (2–3 stops, `exposure` −2 to −3).
- **`normalize` off:** divide by the panel's area (width × height, or length × width for a strip, π × radius² for a disk): the same 0.3 m panel at 0.5 m needs about 1 ÷ 0.09 ≈ 11 for the same picture.
- **Metal and gloss show the panel itself**, not the light it throws: a strip's reflection reads about intensity ÷ its area (with `normalize` on), so a small strip looks much brighter in a reflection than its light on a matte surface. Judge highlights in `look_frame quality=final`.
- **Check it:** `look_frame what "exposure"` renders one quick frame and says how much is blown out or crushed and where the brightest and darkest parts are (and what is there). Use `quality=final` for metal, glass and anything a panel reflects in.
- **Quick and Final give the same brightness** for a bulb (any size, `normalize` on or off), a spot and a sun's light by its units; a softbox close to what it lights reads about 10 % brighter in the quick view (Storm treats a panel as a point; farther away it matches), strips about 20 %. The quick view ignores `spread`. (Measured by `apps/3d/python/tests/test_quick_matches_final.py`; brief 10b fixed a small bulb that rendered hundreds of times brighter in Final.) On the person's screen, the viewport's Final look (Shift+F) is Cycles itself and shows `spread`, reflections of panels and the rest, cleaning up sample by sample.

## Placing a light by its highlight

A product photographer moves a light until its highlight sits where they want it. Do the same:

- **On the screen:** pick **Lights › Soft light** (a `rect`, the photographers' softbox; **Round soft light** is a `disk`) or any light in the tool rail, then click the spot on the item where its highlight should land. The light is placed where that spot reflects it towards the camera, 4 × the item's size away, aimed at the spot, with a **starting brightness** worked out from that distance, so the first look is neither black nor blown out. A new panel is also sized for where it lands: at most 0.6 × its distance across (a softbox's size, still soft) and small enough that its lowest edge stays above the ground (a 1 m panel 0.3 m from a small figure reached under the floor and lit it in a hard-edged wedge). Make it bigger afterwards for softer light. Later, with a light selected, **Alt+click** any surface to move its highlight there (its distance and brightness stay). A sun is turned so it shines straight onto the spot (its lit side). A strip stands on end. When the exact spot would need a light under the floor (a side seen from a little above bounces the view downwards), the light takes the same angle from above the ground instead: it lights the spot as much, and its highlight shows a little lower.
- **Agents:** `edit_place_on what "highlight"` with the light's id and the pixel (`x`, `y`) of the last `look_frame` picture (its `width`); `fresh=true` for a light just added (distance and starting brightness too). In operations: `light.place_highlight` with the world `point`, the surface's `normal`, the camera's `eye` (and `distance`, `brightness`).
- **Starting brightness:** `light.add` without an `intensity` works it out from the distance to what the light aims at (else the scene's middle) and the light's size and `exposure`: about 3 units of light on the spot, so a pale surface facing it reads light grey. Then trim with `exposure`.

## Aiming

Give a light `aim` = `item` and `aimItem` = the object (or `item.aim` with `at`), and it keeps pointing at it as either moves. `aim` = `point` aims at a fixed spot. Then place the light with `x y z` only. Aim for the part of the object you want lit, not always its centre. An aimed light lies level; `roll` turns it around the way it points (`light.aim(target, roll=90)` in a script): 90 stands a strip on end so its reflection runs up a side instead of across.

## The roles lights play

These are the jobs a light does; a shot may need some, all, or others.

- **Key** — the main light, which decides where light comes from and where shadows fall. Usually a large `rect` or `disk` to one side and above.
- **Fill** — lifts the shadow side so it isn't black. Large, soft, much weaker than the key (try 2–3 stops less). Often a big `rect` or a `dome`.
- **Rim / back light** — behind the object, pointing towards the camera, drawing a bright edge that separates it from the background. Narrow `rect`s work well; check that it doesn't shine straight into the lens.
- **Strip lights** — `strip` lights placed so their *reflection* runs along a glossy or metal edge. On polished metal and glass you light what the surface reflects, not the surface: move the strip until its reflection lands where the edge should glow.
- **Background / kicker** — light on the background or floor alone, to shape the space behind the object (a gradient, a pool of light).
- **Practicals** — lights that are part of the scene (a lamp, a screen); use `sphere` lights or emissive materials.

## Panel tools

- **`spread`** (rect, disk, strip; degrees, 180 by default) — how wide the panel throws its light. 180 is a bare softbox: light all around its front, so it spills onto the floor and background. Smaller is a honeycomb grid on the box: a tighter pool, less spill, while the panel keeps its size, so shadows stay soft and reflections keep their shape. Like a real grid, it doesn't make the middle of the pool brighter: the light fades from full straight ahead to nothing at half the spread off its axis (measured within a few % of that in Cycles, H23). Use it when a light must reach the object and not the backdrop. **Cycles only** (with the patched plug-in): the quick view throws the light all around, and its reply says so (`notInQuickView`).
- **`card`** (rect, disk, strip; off by default) — the panel itself shows to the camera as a bright card of the light's own brightness. Off, a panel is invisible to the camera (it still lights, and in Cycles still shows in glossy and metal reflections). Turn it on when the light is in frame on purpose, or to see in the quick view where a panel stands. In Storm the card is drawn but not reflected (Storm reflects only the dome).

## Strip reflections along a curved edge

A strip reflected in a curved, polished edge becomes a thin line of light that follows the curve. To place one:

1. Make the surface reflective: low `roughness` (and `metallic` 1 for metal, or `coat` for paint and plastic).
2. Add a `strip` whose `length` is along the edge and aim it at the object (`aim` = `item`).
3. Find where it must stand: a reflection is seen where the angle from the camera to the surface equals the angle from the surface to the light. Put the strip roughly where the camera's view would bounce off the edge (opposite the camera across the edge's normal).
4. Render from the shot's camera in Cycles (`look_frame quality=final`) and move the strip in small steps until its reflection lies along the edge. Moving it sideways slides the line across the curve; making `width` smaller thins the line; `length` sets how far along the curve it runs. Storm doesn't show reflections of panels, so judge this in Cycles.
5. A rounder edge needs the strip closer or longer for the line to run the whole way.

## Light linking: lighting only some items

On the screen: right-click a light › **Pick what it lights**, then click items in the viewport, or a collection's chip under the scene list: each click adds it, a second click takes it out; the line at the bottom names them. Esc (or selecting something else) finishes.

**`lightsOnly`**: item ids separated by spaces (`"bottle label"`); the light then lights only those items and what is inside them (a group's or an import's children). `""` lights everything. Use it to put a highlight on the product without lighting the floor, or to give one part its own rim. Every id must be a real item or a **collection** (a named set, `collection.add`): a collection lights all its members, including ones that join it later (a collection with a material rule: every item using that material). A wrong id is an error, never a light quietly lighting everything. **Cycles only** (with the patched plug-in): the quick view lights every item with every light, and its reply names the linked lights (`notInQuickView`). The saved `.usda` carries it as UsdLux light linking, which other USD programs read.

## What shows only in Final

`spread` and `lightsOnly` are applied by Cycles only. In the settings panel their rows carry a small **Final** badge: you see their effect in the Final look (Shift+F) or a render, not in the Quick view. Agents: `look_frame`'s reply ends with **"Applied in Final: spread on rim, linking on rim"** when a quick look leaves such settings out, and always with **"Clipped: N % of pixels"**, the share of the picture blown to white (2 % or more says so: lower `exposure`).

## Aiming through the light

To see what a light sees, look through it: in the screen's viewport select a rect, disk, strip, sphere or sun light and pick **Through the selected light** in the top bar's camera button (**Shot camera · Quick ▾**) (or right-click it › **Look through**); the view stands where the light is and looks the way it shines, and follows the light when it is moved or aimed. What lies in the middle of the view is what the light points at. Dragging in that view continues freely from it (the light stays). Agents: `look_frame` with `through` = the light's id. The view is level with the horizon (it ignores a light's roll).

## Working method

A new project already holds a key and a rim aimed at the middle of the ground (`key_light`, `rim_light`) with the Studio sky as
fill, so a thing put there reads at once. They are ordinary lights: move, aim, re-balance with `exposure`, or delete them and
start from nothing as below. A script that makes a dome of its own takes the start sky out; any other light of its own adds to the key and rim unless made with `replace_start_lights=True` (guide `script`). To set a light in plain stops: `brightness=0` lights its subject as the start key lights its own (+1 twice, -1 half), at the distance to what it aims at or `at_distance=` metres; it sets `intensity` (Same brightness at any size) and `exposure`. A script light given no `intensity`, `exposure` or `brightness` that aims at something gets `brightness=0` (the reply says so): at the old default intensity 1 a panel was about 4 stops under the sky's fill and the subject came out flat and dim. `replace_start_lights=True` takes out the key and rim only: the Studio sky stays as the low fill (its `exposure`, −1.5, sets how dark the shadow side goes), and every new light casts shadows unless `shadows=False`.

**Flat light** is something to look for in the frame. With `notes: true`, a look measures the biggest subject in the picture: its lit tenth against its dark tenth, in stops. Under 0.75 stops it notes `flat_light:<item>` ("flat: cube's lit and dark sides differ by 0.4 stops"), adding when no light casts a shadow. A key "from the left" placed in front of a box that faces the camera lights its front and top alike: that is flat however bright. To get more shape: bring the key to the side and lower, beside the subject and about level with its top, so it rakes across the faces the camera sees; turn the subject or the camera so two faces show; lower the fill (the sky's `exposure`) so the far side drops about 2 stops under the key; keep the key's shadows on and high enough to drop a shadow beside it. If flat is meant (a flat graphic look), leave it.

The start Studio sky lights and reflects but the camera doesn't see it (`seenByCamera` off): past the ground's far edge a low or level camera sees the shot's plain `background`, set to the start floor's tone, so the floor runs to a soft horizon instead of showing the photographed room's walls and lamps. Recolour the ground and set the shot's `background` to the far floor's colour too (else the horizon is a line between two colours). A sky photo the camera sees in the picture past the floor shows as the note `backdrop_edge:<dome>`; leave it when that photo is meant to be the backdrop (an outdoor sky).

1. Start with one light (the key) and nothing else. Render; judge the shape and the shadow.
2. Add one light at a time, each with one job. Turn each off and on (`visible`) to see what it adds; remove lights that add nothing.
3. Balance with `exposure` in stops.
4. For glossy and metal objects, look at the reflections first and move lights to shape them.
5. Check from the shot's camera at the first, middle and last frames: an object that turns catches the light differently as it moves.
