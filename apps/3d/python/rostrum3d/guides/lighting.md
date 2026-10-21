# Lighting: what each light and field does

Lights are items (`light.add`, `light.set`). This guide explains the kinds of light, every field, and the techniques product and object lighting is built from. It doesn't give finished setups: build the light your shot needs and judge it in a render from the shot's camera.

## Kinds

- **`rect`** — a rectangular panel (`width`, `height` in metres) shining along its −Z. The softbox and the strip light of a photo studio. The workhorse of product lighting.
- **`disk`** — a round panel (`radius`), also shining along −Z. Gives round highlights (a beauty dish).
- **`sphere`** — a ball of light (`radius`) shining every way: a bulb, a candle flame, a practical lamp in the scene.
- **`distant`** — parallel light from far away: the sun. Only its rotation matters; **`angle`** is how wide the sun looks (0.53° is the real sun; bigger = softer shadows).
- **`dome`** — light from all around, an infinitely large sphere. With **`texture`** (an HDR or EXR image) it lights and reflects a real place; without, an even sky in `color`.

## Fields

- **`intensity`** and **`exposure`** — brightness. `exposure` is in stops: +1 doubles, −1 halves. Use `exposure` to balance lights against each other, so the ratios read in stops like a photographer's.
- **`color`** and **`temperature`** — `temperature` in kelvin (2700 a warm bulb, 4000 neutral, 5600 daylight, 7500 cool shade) gives physically right white light; 0 turns it off and only `color` counts. A little warm/cool contrast between two lights separates forms.
- **`normalize`** — off (default): a bigger light gives more light. On: the size changes only the softness, so you can resize without rebalancing.
- **`shadows`** — whether it casts shadows. Leave it on unless a fill light's shadows clutter the picture.
- **Size and distance** — softness depends on how big the light looks from the object. A large panel close by gives soft light with gentle shadows; the same panel far away gets small and hard. Brightness also falls off with distance (four times dimmer at twice the distance).

## Aiming

Give a light `aim` = `item` and `aimItem` = the object (or `item.aim` with `at`), and it keeps pointing at it as either moves. `aim` = `point` aims at a fixed spot. Then place the light with `x y z` only. Aim for the part of the object you want lit, not always its centre.

## The roles lights play

These are the jobs a light does; a shot may need some, all, or others.

- **Key** — the main light, which decides where light comes from and where shadows fall. Usually a large `rect` or `disk` to one side and above.
- **Fill** — lifts the shadow side so it isn't black. Large, soft, much weaker than the key (try 2–3 stops less). Often a big `rect` or a `dome`.
- **Rim / back light** — behind the object, pointing towards the camera, drawing a bright edge that separates it from the background. Narrow `rect`s work well; check that it doesn't shine straight into the lens.
- **Strip lights** — long thin `rect`s (e.g. 0.1 × 1.5 m) placed so their *reflection* runs along a glossy or metal edge. On polished metal and glass you light what the surface reflects, not the surface: move the strip until its reflection lands where the edge should glow.
- **Background / kicker** — light on the background or floor alone, to shape the space behind the object (a gradient, a pool of light).
- **Practicals** — lights that are part of the scene (a lamp, a screen); use `sphere` lights or emissive materials.

## Working method

1. Start with one light (the key) and nothing else. Render; judge the shape and the shadow.
2. Add one light at a time, each with one job. Turn each off and on (`visible`) to see what it adds; remove lights that add nothing.
3. Balance with `exposure` in stops.
4. For glossy and metal objects, look at the reflections first and move lights to shape them.
5. Check from the shot's camera at the first, middle and last frames: an object that turns catches the light differently as it moves.
