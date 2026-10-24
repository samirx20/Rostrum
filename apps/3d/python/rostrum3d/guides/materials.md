# Materials: how the fields make real surfaces

Rostrum3D has one material type: a physically based surface (`material.add`, `material.set`). Glass, metal and paint are not presets; they are values of the same fields. This guide explains what each field does to light, so you can reach any surface yourself and judge it in a render.

Look at the result, not the numbers: render a still with `cycles`. Storm, the fast view, only approximates glass and coat, and doesn't show brushing, sheen, coat colour or thin film at all (see "What the fast view can't show" below).

## Giving an item a material (on the screen)

Select a mesh (or a combine, or an imported part). Its **Material** row in the settings panel shows the material's ball and name.

1. **Click the ball** — the picker opens under it: **This project** (every material the project has, each as a rendered ball, with how many items use it), then **Start from** (the starting points, below).
2. **Click one.** A project material is given to the item. A starting point makes a **new** material from that substance's settings, named after the item ("case material"), and gives it to the item. Then change anything in the settings under it.

Two clicks, one undo step.

- **The settings under the Material row are the material's own:** Surface (colour, metallic, roughness) always open; Glass, Coat, Sheen, Brushed, Relief, Glow open once changed, the rest as one row of names you click to open.
- **Shared materials.** When other items use the same material, a grey line says **Used by 3 items**: changing a setting changes every one of them (that is what sharing is). **Make its own** gives this item its own copy in one click; the others keep the original.
- **Edit** opens the material alone in the settings panel.
- **Drag a ball** (from the picker or the Materials list) onto an item in the viewport or the scene list to give it that material.
- **The header's Materials chip** lists the project's materials (ball, name, how many items use each). Click one to edit it; **+ New material** makes one.
- **Colours** are a swatch and a hex code: type the hex, or click the swatch for the colour picker.

The balls are real renders through the same fast view as the viewport, made once per material setting and kept (a changed material is drawn again).

### Starting points

Matte plastic, Glossy plastic, Rubber, Polished metal, Brushed metal, Glass, Frosted glass, Ceramic, Fabric, Wood, Car paint, Screen. Each is the physical settings of a substance (glass = transmission 1, index of refraction 1.5, roughness 0), never a colour scheme or a lighting look; the colour is yours to set. The rest of this guide explains each setting they use.

## For agents: the same, as operations

- **`material.from`** `start` (one of the starting points above, e.g. `"brushed metal"`), optional `name`, `id`, any material field to override, and `to` (a list of item ids): makes one new material from the start's values and gives it to those items, as one undo step. In a script: `material("alu", start="brushed metal", baseColor="#c9ccd1")`.
- **`material.split`** on items: each gets its own copy of the material it shares ("<item> material"); the other users keep the original. It refuses loudly when the item has no material or is already its only user.
- `material.add / set / assign / remove` as before. Check the result with `look_frame` (`final` for glass, metal and coat).

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

## Lettering and marks on a dark product

Bare metal shows only what it reflects. Metal lettering on a dark face in a dark set mirrors the dark and reads as broken shapes. Give a mark a non-metal (pale enamel or paint, `metallic` 0, perhaps a touch of `emissionStrength`), or put a light or a bright card where the lettering reflects it. Raise it slightly above any glass over it, or the glass bends its edges.

## Painted and printed surfaces

- **`baseColorTexture`**: an image painted or printed onto the surface along its UVs (a label, a painted pattern). It replaces `baseColor`.
- **`roughnessTexture`**: a grey image for where the surface is shinier or duller (fingerprints, worn edges, glossy print on matte card).
- **`bumpTexture`** with **`bumpStrength`**: a grey height image (white is raised) for small relief that catches light: embossing, brush strokes, grain. Bump doesn't change the outline; the shape itself comes from the mesh.
- **`metallicTexture`**: a grey image for where the surface is metal (white) or not (black): bare metal where paint wore off.
- Any image file works. To paint them by hand on the model instead, use Paint (B): its layers paint colour, roughness,
  height, metal or glow over this material, and the material's own values stay where nothing is painted (guide `painting`).

## Things that glow

**`emissionStrength`** above 0 makes the surface give off light in **`emissionColor`** (screens, LEDs, a neon tube). In Cycles a glowing surface also lights what's near it; for a strong light source, a real light is cleaner and faster.

### A screen showing a picture

- **`emissionTexture`**: an image file on the surface's UVs; the glow takes its colours. With `emissionStrength` 1 the picture shows at its own brightness; raise it for a screen that should bloom against a dark set, lower it for a screen seen in daylight.
- **`emissionRender`**: the id of a **2D item of the same project**. Its newest finished render plays on the surface: at every moment of the shot the screen shows the 2D frame of the same moment (second 1.5 of the 3D shot shows second 1.5 of the 2D render); before its first frame and after its last, the screen holds that first or last picture. It is read-only: to change the picture, change the 2D item and render it again (as a PNG sequence, `render_export` format `png`; an mp4 can't be put on a surface). A 3D render made before the new 2D render keeps the old picture until it is rendered again.
- A screen is mostly its picture: give the screen surface a near-black `baseColor` and low `roughness` so it also reflects the room like real glass. For a cover glass over the screen, add a second, thin item with `transmission` 1 in front.
- The picture is placed on the item's UVs. A `plane` shows the whole picture once (U along its width, V along its depth), so a screen is a plane laid on the device's face (`rx` 90 stands it up facing +Z). A `box`'s UVs wrap round its sides like a label on a can, so a picture on a box is stretched round all four sides. Check with `look_frame` that it reads the right way up; turn the plane (`rz` 180) if not.

## What the fast view can't show

Storm (the fast view and `quality: fast`) shows base colour, metal, roughness, glass (without blur), clear coat, glow and the screen picture. It **doesn't** show brushing and its direction, sheen, coat colour and coat IOR, thin film or bump. Always judge those in a Cycles still.

## Checking your surface

1. Render one still from the shot's camera with `cycles`.
2. Judge highlights: are they the size and softness the real material would have? If not, change `roughness` before anything else.
3. Judge reflections: is there something for the surface to reflect? Most "flat" metal and glass is a lighting problem, not a material one.
4. Look at the item from a second angle; some surfaces only reveal themselves at grazing angles (coat, thin film, glass edges).
