# Materials: how the fields make real surfaces

Rostrum3D has one material type: a physically based surface (`material.add`, `material.set`). Glass, metal and paint are not presets; they are values of the same fields. This guide explains what each field does to light, so you can reach any surface yourself and judge it in a render.

Look at the result, not the numbers: render a still with `cycles`. Storm, the fast view, only approximates glass, coat and light under the surface, and doesn't show brushing, sheen, coat colour or thin film at all (see "What the fast view can't show" below).

## Giving an item a material (on the screen)

Select a mesh (or a combine, or an imported part). Its **Material** row in the settings panel shows the material's ball and name.

1. **Click the ball** — the picker opens under it: **This project** (every material the project has, each as a rendered ball, with how many items use it), then **Start from** (the starting points, below).
2. **Click one.** A project material is given to the item. A starting point makes a **new** material from that substance's settings, named after the item ("case material"), and gives it to the item. Then change anything in the settings under it.

Two clicks, one undo step.

- **The settings under the Material row are the material's own:** Surface (colour, metallic, roughness) always open; Glass, Coat, Under the surface, Sheen, Brushed, Relief, Glow open once changed, the rest as one row of names you click to open.
- **Shared materials.** When other items use the same material, a grey line says **Used by 3 items**: changing a setting changes every one of them (that is what sharing is). **Make its own** gives this item its own copy in one click; the others keep the original.
- **Edit** opens the material alone in the settings panel.
- **Edit as blocks** (the material's last settings row, under an item or with the material itself selected) shows the
  material as **blocks** in the bottom panel: see "Blocks" below.
- **Drag a ball** (from the picker or the Materials list) onto an item in the viewport or the scene list to give it that material.
- **The Materials ball** at the bottom of the tool rail (or Ctrl+K › Materials) lists the project's materials (ball, name, how many items use each). Click one to edit it; **+ New material** makes one.
- **Colours** are a swatch and a hex code: type the hex, or click the swatch for the colour picker.

The balls are real renders through the same fast view as the viewport, made once per material setting and kept (a changed material is drawn again).

### Starting points

Clay, Skin, Wax / soap, Stone, Matte plastic, Glossy plastic, Rubber, Polished metal, Brushed metal, Glass, Frosted glass, Ceramic, Fabric, Wood, Car paint, Painted (ramp), Ink & flat, Screen. Each is the physical settings of a substance (glass = transmission 1, index of refraction 1.5, roughness 0), never a colour scheme or a lighting look; the colour is yours to set. The first four are for sculpting with clay (a new clay starts with the project's **Clay** material, grey; see "Light under the surface" below). A selected clay shows its **Material ▾** and, under it, the material's settings with **Base colour**'s square, as a mesh does; the first change there gives that clay its own copy of the shared "Clay" (one more undo step, "Make its own material"), so the other clays keep theirs. The rest of this guide explains each setting they use.

### Blocks (on the screen)

The bottom panel shows the material as blocks joined by wires, in the timeline's place; its header reads **‹ Back ·
Brass blocks**. It opens at full size (100 %) with Surface on the right, room on the left for what feeds it. Today's settings are one **Surface** block; its ports on the left are what a wire may set: Base colour,
Roughness, Metallic, Glow colour, Normal, Style.

- **Add a block:** **+ Add block**, Tab, a double-click or a right-click on empty space opens the list; type to filter
  ("noi" finds Noise), then Enter or a click. Image, Noise, Mix, Ramp, Curve, Colour adjust, Bevel shading, Ambient
  occlusion, and the stylized Lines, Light to colour and Halftone. From **+ Add block** or Tab the new block lands left
  of the leftmost block, level with Surface (wires run left to right); from a double-click or right-click, where you
  clicked.
- **Wire:** drag from a block's output (right side) to an input (left side). The ports a wire may reach light up; colour
  and number join either way (a number as grey, a colour as its brightness), a normal and a style only their own kind.
  An input takes one wire: a new one replaces it. Drop a wire on empty space to add a block it feeds.
- **Unwire:** drag a wired input's end away (drop it on another input to move it). **Delete** removes the picked block
  (Surface stays: it is the material).
- **Move and look around:** drag a block by its title; drag empty space (or middle-drag, or Space + drag) to pan; the
  wheel zooms; F fits every block.
- **Settings:** click a block and its settings show in the settings panel: Surface's are the material's own rows (as
  under the item); Noise has Scale, Detail, Roughness, Distortion; Ramp its colour stops; Curve its points. A setting a
  wire feeds says **Set by a wire**. Lines, Light to colour and Halftone carry the material's own fields of that name:
  wiring one into Surface's **Style** switches it on, taking it out switches it off.
- Each add, wire, move or change is one undo step. **‹ Back** or **Esc** goes back to the timeline; the blocks stay.
- A block marked **Final only** (Bevel shading, Ambient occlusion) shows in the Final look and renders, not in Quick.

## For agents: the same, as operations

- **`material.from`** `start` (one of the starting points above, e.g. `"brushed metal"`), optional `name`, `id`, any material field to override, and `to` (a list of item ids): makes one new material from the start's values and gives it to those items, as one undo step. In a script: `material("alu", start="brushed metal", baseColor="#c9ccd1")`.
- **`material.split`** on items: each gets its own copy of the material it shares ("<item> material"); the other users keep the original. It refuses loudly when the item has no material or is already its only user.
- **Blocks** (the Blocks view above, as operations; each one undo step, target = the material):
  - `graph.add` `type` (`image`, `noise`, `mix`, `ramp`, `curve`, `colourAdjust`, `bevel`, `occlusion`, `lines`,
    `lightToColour`, `halftone`), optional `id` (else `noise_1`, `noise_2` …), `x`, `y` (its place in the view) and
    `values` (`{"scale": 8}`). Returns the block.
  - `graph.connect` `from: "noise_1.value"`, `to: "surface.roughness"`. Surface's inputs: `baseColor`, `roughness`,
    `metallic`, `emissionColor`, `normal`, `style`. A new wire into an input replaces its old one. Refused: a wire between
    kinds that don't join (a normal or style into a colour), a loop, a name that isn't there (the reply lists the right ones).
  - `graph.set` `block`, then `values` and / or `x`, `y`. `block: "surface"` changes the material's own fields.
  - `graph.remove` `blocks: ["noise_1"]` (their wires go too) and / or `wires: ["surface.roughness"]` (the input whose wire goes).
  - What each block offers: Image (`file`, `colourData` colour / data → `colour`, `value`), Noise (`scale`, `detail`,
    `roughness`, `distortion` → `value`, `colour`), Mix (`factor`, `a`, `b`, `blend` mix / multiply / add / screen /
    overlay / darken / lighten → `colour`), Ramp (`factor`, `stops` `[[0, "#000000"], [1, "#ffffff"]]` 2 to 8,
    `interpolate` linear / constant / smooth → `colour`, `value`), Curve (`value`, `points` `[[0, 0], [1, 1]]` 2 to 8 →
    `value`), Colour adjust (`colour`, `hue`, `saturation`, `brightness`, `contrast` → `colour`), Bevel shading (`radius`,
    `samples` → `normal`, Final only), Ambient occlusion (`distance`, `colour` → `value`, `colour`, Final only).
  - Lines, Light to colour and Halftone take the material's own fields as `values` (`linesWidth`, `litColor`,
    `halftoneSize` …) and output `style`: wired into `surface.style` the setting is on. To use two or three at once, chain
    them: each has a `then` input taking another one (`halftone_1.style` → `lines_1.then`, `lines_1.style` →
    `surface.style`). Taking one out (or its wire) switches it off.
  - `look_material` draws the material with its blocks and lists them in its reply (blocks, settings, wires), so check
    the result there. In Python, `graph.describe(material)` gives every block with its ports, what is wired and its values.
- `material.add / set / assign / remove` as before. Check the result with `look_frame` (`final` for glass, metal and coat); to judge one material on its own, `look_material` shows it on a ball in a strip of angles under the scene's lights and picks Final for you when it needs it.

## The four fields that decide most surfaces

- **`metallic`** — 0 for everything that isn't bare metal (plastic, paint, glass, wood, skin, rubber). 1 for bare metal. In between is almost never physical; use it only for dirt or wear seen through a texture.
- **`baseColor`** — for a non-metal, the colour of the diffuse light (paint colour). For a metal, the colour of its *reflections*: gold, copper and anodized aluminium get their colour here, and there is no diffuse colour at all. Real surfaces are rarely pure white or black: very bright paint is around `#e6e6e6`, very dark around `#161616`.
- **`roughness`** — how blurred reflections are. 0 is a mirror, 0.2 polished, 0.4 satin, 0.7 matte, 1 chalk. Most of the "look" of a surface lives here; small changes (0.25 → 0.32) are visible on large smooth areas.
- **`ior`** — how much light bends going in (water 1.33, glass 1.5, sapphire 1.77, diamond 2.42). For non-metals it also sets how strong the reflection is when you look straight on.

## Glass and clear things

Light passes through when **`transmission`** is 1. Then:
- `roughness` 0 gives clear glass. **Frosted glass is the same glass with `roughness` 0.1–0.4**: there is one roughness, and on glass it blurs both the reflections and everything seen through it (Cycles bends each ray through the rough surface). There is no separate "frost" control. Low values (0.05–0.15) read as lightly etched glass where nearby things stay readable; higher values hide what is behind and leave only light and colour. Frost only shows when there is something behind the glass to blur: a shape, a light, a colour. In the fast view, rough glass is drawn milkier and less see-through instead of blurred.
- `ior` sets how much the scene behind it bends. Thick glass with a higher `ior` distorts more.
- `baseColor` tints the light passing through: keep it near white for clear glass; a faint tint reads much stronger in thick parts.
- Glass needs **something to refract and reflect**: a plain black world makes glass invisible. Give it a background, a dome light with an HDR image, or strip lights whose reflections run along its edges (see lighting.md).
- A screen under a cover glass: two items, the glass on top with `transmission` 1, the screen below with `emissionStrength` for the image.

## Metals

`metallic` 1 and the metal's own reflection colour in `baseColor`. The difference between metal finishes is mostly roughness and direction:
- **Polished:** low `roughness` (0.05–0.2). A polished metal shows its surroundings almost perfectly, so what it *reflects* is the look: shape your lights and background, not the material.
- **Brushed:** `roughness` around 0.3–0.45 and **`anisotropy`** 0.5–0.9, which stretches highlights *across* the brushing lines, like the long streak of light on a brushed steel panel. Where the lines run is **`brushDirection`**:
  - `uv` — straight lines along the mesh's U direction (a panel, a laptop lid, a bar). A box's, cylinder's or extruded outline's UVs wrap round its sides (U runs round, V from bottom to top), so the brushing runs round them; a `plane` has U along its width.
  - `around x`, `around y`, `around z` — circles round that axis of the item, centred on the item's origin: spun brushing, as on a watch back, a speaker grille's rim, a knob's face or a lens ring. Choose the axis the round part turns about: a `cylinder` or `disc` stands on its Y axis, so `around y`. The highlight then forms a bright cross or bow-tie that turns as the object or the light moves, which is how spun metal is recognised.
  - **`anisotropyRotation`** turns the lines on the surface (0..1 = 0..360°); 0.25 makes `uv` brushing run along V instead.
  The streaks only read when there is a long, bright light for them to stretch: strip lights or an HDR with bright windows (lighting.md).
- **Anodized:** a coloured metal. Use the colour in `baseColor`, `roughness` 0.3–0.5 (anodizing is usually satin). For a rainbow sheen at grazing angles, try **`thinFilm`** (the coating's thickness in nanometres, a few hundred).
- **Coated / lacquered** (car paint, a varnished part): a **`coat`** of 1 adds a thin clear layer with its own **`coatRoughness`**, so you get a sharp reflection over a softer base.

## Paint under a clear coat

A painted product (a car body, a coloured phone back, a lacquered toy) is two layers: the paint (`baseColor`, `roughness`, often 0.3–0.6) and a clear varnish on top (`coat` 1, `coatRoughness` low). The coat gives the crisp reflection of the lights; the paint underneath gives the colour and a softer second highlight.

- **`coatTint`** colours the varnish itself. Light passes through it on the way in and again on the way out, and travels further through it where the surface turns away from you, so a tinted coat goes deeper and richer toward the edges of the shape (candy and "flake-free metallic" paints). Keep it white for a clear varnish; a little colour goes a long way.
- **`coatIor`** sets how strongly the varnish reflects (1.5 for most lacquers; higher gives a brighter, glassier coat highlight).
- Over a metal (`metallic` 1 plus `coat`), you get anodized or lacquered metal with a separate sharp top reflection.

## Fabric, velvet and soft fuzz: sheen

**`sheen`** adds the soft light that tiny fibres catch when you look along a surface: the bright rim on a velvet cushion, the pale glow at the edges of a knitted strap or a felt pad, the fuzz on a peach.

- `sheen` 0.3–1 for cloth; leave `baseColor` the fibre's colour and `roughness` high (0.7–1).
- **`sheenRoughness`**: low makes a narrow, bright rim along the outline (velvet); high spreads a soft haze over the whole surface (brushed cotton, felt).
- **`sheenTint`**: the colour of that glow. White reads as dust or fine fibres catching light; the fibre's own colour, lighter, reads as a dyed fabric.
- Sheen shows at grazing angles, so judge it on curved shapes and at the edges, lit from the side or from behind.

## Light under the surface: skin, wax, soap, marble

In skin, wax, soap, marble, milk or jade, light doesn't bounce off the top: it goes in, spreads around inside and comes out a little way off. Shadows get soft edges, and thin parts (an ear, a finger, a candle's rim) glow when a light is behind them.

- **`subsurface`** (Light under the surface) 0..1: how much of the light goes in. Skin, wax and soap are about 1; 0 is off.
- **`subsurfaceRadius`** (How far it travels), in millimetres: how far the light gets inside before it comes out. Measured values: skin about 4, marble about 5–8, wax and soap about 8. The distance is real: the same value looks more see-through on a small object than on a big one, so a 5 cm toy in Skin glows much more than a life-size head. Keep it real for a real size; raise it on purpose for a smaller, glowier look.
- **`subsurfaceColor`** (Colour inside): which colours travel farthest. Skin's red travels about five times farther than its blue, so thin skin lit from behind glows red; that is a warm red-orange here. White = every colour travels the same distance (wax, soap). The surface's own colour stays `baseColor`.
- **The starts:** **Skin** (`subsurface` 1, 3.7 mm, colour inside `#ffa477`, a neutral-warm base colour to change to the skin you want), **Wax / soap** (`subsurface` 1, 8 mm, nearly white inside), **Clay** (modelling clay: grey, matte, soft highlights, no light inside) and **Stone** (rough, grey, no light inside; for marble, add `subsurface` 1 with about 6 mm).
- **To see it:** put a light behind or beside the thin part, facing the camera through it, and render a Final still. Front light alone hides most of it.
- **The Quick view** only leans the colour a little toward the colour inside; the soft shadows and the glow of thin parts show in Final only (the rows carry the **Final** tag).

## Lettering and marks on a dark product

Bare metal shows only what it reflects. Metal lettering on a dark face in a dark set mirrors the dark and reads as broken shapes. Give a mark a non-metal (pale enamel or paint, `metallic` 0, perhaps a touch of `emissionStrength`), or put a light or a bright card where the lettering reflects it. Raise it slightly above any glass over it, or the glass bends its edges.

## Painted and printed surfaces

- **`baseColorTexture`**: an image painted or printed onto the surface along its UVs (a label, a painted pattern). It replaces `baseColor`.
- **`roughnessTexture`**: a grey image for where the surface is shinier or duller (fingerprints, worn edges, glossy print on matte card).
- **`bumpTexture`** with **`bumpStrength`**: a grey height image (white is raised) for small relief that catches light: embossing, brush strokes, grain. Bump doesn't change the outline; the shape itself comes from the mesh.
- **`metallicTexture`**: a grey image for where the surface is metal (white) or not (black): bare metal where paint wore off.
- Any image file works. To paint them by hand on the model instead, use Paint (B): its layers paint colour, roughness,
  relief, metal or glow over this material, and the material's own values stay where nothing is painted (guide `painting`).

## Things that glow

**`emissionStrength`** above 0 makes the surface give off light in **`emissionColor`** (screens, LEDs, a neon tube). In Cycles a glowing surface also lights what's near it; for a strong light source, a real light is cleaner and faster.

### A screen showing a picture

- **`emissionTexture`**: an image file on the surface's UVs; the glow takes its colours. With `emissionStrength` 1 the picture shows at its own brightness; raise it for a screen that should bloom against a dark set, lower it for a screen seen in daylight.
- **`emissionRender`**: the id of a **2D item of the same project**. Its newest finished render plays on the surface: at every moment of the shot the screen shows the 2D frame of the same moment (second 1.5 of the 3D shot shows second 1.5 of the 2D render); before its first frame and after its last, the screen holds that first or last picture. It is read-only: to change the picture, change the 2D item and render it again (as a PNG sequence, `render_export` format `png`; an mp4 can't be put on a surface). A 3D render made before the new 2D render keeps the old picture until it is rendered again.
- A screen is mostly its picture: give the screen surface a near-black `baseColor` and low `roughness` so it also reflects the room like real glass. For a cover glass over the screen, add a second, thin item with `transmission` 1 in front.
- The picture is placed on the item's UVs. A `plane` shows the whole picture once (U along its width, V along its depth), so a screen is a plane laid on the device's face (`rx` 90 stands it up facing +Z). A `box`'s UVs wrap round its sides like a label on a can, so a picture on a box is stretched round all four sides. Check with `look_frame` that it reads the right way up; turn the plane (`rz` 180) if not.

## Stylized blocks: Lines, Light to colour, Halftone

Three groups of settings turn a material from a physical surface into a drawn or printed one. Each is off until you turn it
on: in the material's row of names click **Lines**, **Light to colour** or **Halftone** (one click turns it on and opens its
settings; the **×** on its heading turns it off again). Agents: `material.set` with `lines`, `lightToColor` or `halftone`
`true`, then the group's other fields. The other fields of a group exist only while its switch is on.

**Ink & flat** and **Painted (ramp)** in Start from are a matte surface with these switched on (below); like every start,
they are settings, not a look: the colours are yours.

### How lit: the one scale all three read

Every stylized block reads **how lit** each point of the surface is, from 0 to 1, from the scene's real lights: their
brightness (intensity and exposure), their falloff with distance, the angle the surface turns to each, and cast shadows.
1 is the light that makes white paper look white on screen at exposure 0; 0 is no light. Coloured lights count by their
brightness. A dome adds a soft light from above. So the same scene lit for Final gives the same "how lit" in Stylized:
brighten a light and more of the surface crosses into the lit colour; move it and the shadow band follows.

### Lines (Stylized look)

Ink lines along the outline of every surface with this material and along its creases.

- **Width** (`linesWidth`, 0.25–12 px): the line's thickness in pixels of the finished picture, so a render at double
  size has lines of the same thickness in pixels (thinner in proportion).
- **Colour** (`linesColor`).
- **Taper** (`linesTaper`, 0–1): lines get thinner where the surface is lit; 0 keeps the width the same everywhere, 1
  thins them most in full light.
- **Wobble** (`linesWobble`, 0–1): how much the width changes along a line, like a hand-held pen; 0 is steady.
- **Crease angle** (`linesCreaseAngle`, 1–180°): a fold sharper than this gets a line too (a box's edges at 40°); 180
  draws the outline only. Lower values add lines on gentler folds.

Dragging Width (or any number or colour of a material) in the settings panel redraws the live view as you drag; the
change is written once, when you let go (one undo step).

### Light to colour (Final and Stylized)

Colours the surface by how lit it is: **Lit colour** (`litColor`) where it is lit, **Middle colour** (`midColor`) in
between, **Shadow colour** (`shadowColor`) in shadow. Each **multiplies** the base colour (or the base colour image):
white shows the base colour itself, grey darkens it, a colour tints it. So one base colour (or a painted image) keeps
its own colours in every band.

- **Shadow below** (`shadowBelow`, 0–1): below this much light, the shadow colour.
- **Lit from** (`litFrom`, 0–1): from this much light up, the lit colour. Between the two, the middle colour. When Shadow
  below is higher than Lit from, Lit from counts for both: two bands, no middle.
- **Edges** (`lightEdges`): **Steps** = hard edges between the bands; **Smooth** = each edge blends over **Softness**
  (`lightSoftness`, 0.01–0.5), measured on the same how-lit scale either side of Shadow below and Lit from.
- The surface's own shading is replaced by the bands: no highlights or reflections (roughness, metal, coat and glass
  don't show on it); glow still adds on top.
- Final (Cycles) and Stylized compute the bands the same way, with Cycles' real cast shadows in Final.

### Halftone (Stylized look)

Printed dots or lines over the surface whose size follows how lit it is: none where it is fully lit, solid where it is in
full shadow, in between in proportion.

- **Shape** (`halftoneShape`): **Dots** or **Lines**.
- **Size** (`halftoneSize`, 2–40 px): the spacing of the dots or lines, in pixels of the finished picture.
- **Angle** (`halftoneAngle`, −90–90°): the turn of the rows of dots or of the lines.
- **Colour** (`halftoneColor`): the ink's colour, over the surface's own colour.

### What each Look shows

- **Quick** (the live view, Storm) shows the material's physical settings only: no lines, no bands, no halftone.
- **Final** (Cycles) shows Light to colour, not Lines or Halftone. The rows carry the tags **Final · Stylized** (Light to
  colour) and **Stylized** (Lines, Halftone).
- **Stylized** (the stylized renderer) shows all three, and draws every other material with plain light: its colour
  times the light reaching it, with cast shadows, so the scene keeps the brightness it has in Final. It shows base colour,
  base colour image, glow and see-through (opacity); not reflections, roughness, glass bending, coat, sheen, light under
  the surface or bump.
- **Look: Stylized** appears in the viewport's Camera and look menu (and **Stylized** in the render sheet's Quality) while
  any material of the project has Lines or Halftone on. When the last one is turned off the view goes back to Quick and
  says so. Shift+F still flips Quick and Final.
- A render with Quality **Stylized** uses the same renderer as the view, drawn at twice the size and smoothed down for
  clean edges, so the render is the view you saw. Agents: `look_frame` / `render_still` / `render_video` with
  `renderer: "stylized"`.

## What the fast view can't show

Storm (the fast view and `quality: fast`) shows base colour, metal, roughness, glass (without blur), clear coat, glow and the screen picture. Light under the surface shows only as a slight tint toward the colour inside. It **doesn't** show brushing and its direction, sheen, coat colour and coat IOR, thin film or bump. Always judge those in a Cycles still.

## Checking your surface

1. Render one still from the shot's camera with `cycles`.
2. Judge highlights: are they the size and softness the real material would have? If not, change `roughness` before anything else.
3. Judge reflections: is there something for the surface to reflect? Most "flat" metal and glass is a lighting problem, not a material one.
4. Look at the item from a second angle; some surfaces only reveal themselves at grazing angles (coat, thin film, glass edges).
