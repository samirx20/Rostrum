# Lighting: what each light and field does

Lights are items (`light.add`, `light.set`). This guide explains the kinds of light, every field, and the techniques product and object lighting is built from. It doesn't give finished setups: build the light your shot needs and judge it in a render from the shot's camera.

## Kinds

- **`rect`** — a rectangular panel (`width`, `height` in metres) shining along its −Z. The softbox and the strip light of a photo studio. The workhorse of product lighting.
- **`disk`** — a round panel (`radius`), also shining along −Z. Gives round highlights (a beauty dish).
- **`strip`** — a long thin panel: `length` along its X, `width` across it (along its Y), shining along −Z. The strip softbox of a product studio (a `rect` with its own two sizes, so you think in length and width).
- **`sphere`** — a ball of light (`radius`) shining every way: a bulb, a candle flame, a practical lamp in the scene.
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
- **Check it:** `inspect_exposure` renders one quick frame and says how much is blown out or crushed and where the brightest and darkest parts are (and what is there). Use `quality=final` for metal, glass and anything a panel reflects in.
- The quick view (Storm) is within about 10 % of these numbers for rect and disk panels and about 20 % brighter for strips; it ignores `spread`. On the person's screen, the viewport's Final look (Shift+F) is Cycles itself and shows `spread`, reflections of panels and the rest, cleaning up sample by sample.

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

**`lightsOnly`**: item ids separated by spaces (`"bottle label"`); the light then lights only those items and what is inside them (a group's or an import's children). `""` lights everything. Use it to put a highlight on the product without lighting the floor, or to give one part its own rim. Every id must be a real item; a wrong id is an error, never a light quietly lighting everything. **Cycles only** (with the patched plug-in): the quick view lights every item with every light, and its reply names the linked lights (`notInQuickView`). The saved `.usda` carries it as UsdLux light linking, which other USD programs read.

## Aiming through the light

To see what a light sees, look through it: in the screen's viewport select a rect, disk, strip, sphere or sun light and pick **View › Through the selected light** in the top bar (or right-click it › **Look through**); the view stands where the light is and looks the way it shines, and follows the light when it is moved or aimed. What lies in the middle of the view is what the light points at. Dragging in that view continues freely from it (the light stays). Agents: `look_frame` with `through` = the light's id. The view is level with the horizon (it ignores a light's roll).

## Working method

1. Start with one light (the key) and nothing else. Render; judge the shape and the shadow.
2. Add one light at a time, each with one job. Turn each off and on (`visible`) to see what it adds; remove lights that add nothing.
3. Balance with `exposure` in stops.
4. For glossy and metal objects, look at the reflections first and move lights to shape them.
5. Check from the shot's camera at the first, middle and last frames: an object that turns catches the light differently as it moves.
