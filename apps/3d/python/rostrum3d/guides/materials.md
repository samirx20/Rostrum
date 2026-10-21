# Materials: how the fields make real surfaces

Rostrum3D has one material type: a physically based surface (`material.add`, `material.set`). Glass, metal and paint are not presets; they are values of the same fields. This guide explains what each field does to light, so you can reach any surface yourself and judge it in a render.

Look at the result, not the numbers: render a still with `cycles` (Storm, the fast view, only approximates glass, coat and brushed metal).

## The four fields that decide most surfaces

- **`metallic`** — 0 for everything that isn't bare metal (plastic, paint, glass, wood, skin, rubber). 1 for bare metal. In between is almost never physical; use it only for dirt or wear seen through a texture.
- **`baseColor`** — for a non-metal, the colour of the diffuse light (paint colour). For a metal, the colour of its *reflections*: gold, copper and anodized aluminium get their colour here, and there is no diffuse colour at all. Real surfaces are rarely pure white or black: very bright paint is around `#e6e6e6`, very dark around `#161616`.
- **`roughness`** — how blurred reflections are. 0 is a mirror, 0.2 polished, 0.4 satin, 0.7 matte, 1 chalk. Most of the "look" of a surface lives here; small changes (0.25 → 0.32) are visible on large smooth areas.
- **`ior`** — how much light bends going in (water 1.33, glass 1.5, sapphire 1.77, diamond 2.42). For non-metals it also sets how strong the reflection is when you look straight on.

## Glass and clear things

Light passes through when **`transmission`** is 1. Then:
- `roughness` 0 gives clear glass; 0.1–0.3 frosted glass (blurred through, not just on the surface).
- `ior` sets how much the scene behind it bends. Thick glass with a higher `ior` distorts more.
- `baseColor` tints the light passing through: keep it near white for clear glass; a faint tint reads much stronger in thick parts.
- Glass needs **something to refract and reflect**: a plain black world makes glass invisible. Give it a background, a dome light with an HDR image, or strip lights whose reflections run along its edges (see lighting.md).
- A screen under a cover glass: two items, the glass on top with `transmission` 1, the screen below with `emissionStrength` for the image.

## Metals

`metallic` 1 and the metal's own reflection colour in `baseColor`. The difference between metal finishes is mostly roughness and direction:
- **Polished:** low `roughness` (0.05–0.2). A polished metal shows its surroundings almost perfectly, so what it *reflects* is the look: shape your lights and background, not the material.
- **Brushed:** `roughness` around 0.3–0.45 and **`anisotropy`** 0.5–0.9, which stretches highlights along one direction. **`anisotropyRotation`** turns that direction (0..1 = 0..360°). The brushing follows the mesh's UVs.
- **Anodized:** a coloured metal. Use the colour in `baseColor`, `roughness` 0.3–0.5 (anodizing is usually satin). For a rainbow sheen at grazing angles, try **`thinFilm`** (the coating's thickness in nanometres, a few hundred).
- **Coated / lacquered** (car paint, a varnished part): a **`coat`** of 1 adds a thin clear layer with its own **`coatRoughness`**, so you get a sharp reflection over a softer base.

## Painted and printed surfaces

- **`baseColorTexture`**: an image painted or printed onto the surface along its UVs (a label, a painted pattern). It replaces `baseColor`.
- **`roughnessTexture`**: a grey image for where the surface is shinier or duller (fingerprints, worn edges, glossy print on matte card).
- **`bumpTexture`** with **`bumpStrength`**: a grey height image (white is raised) for small relief that catches light: embossing, brush strokes, grain. Bump doesn't change the outline; the shape itself comes from the mesh.
- Our own painting tools (the painting kit) can make these images; any image file works.

## Things that glow

**`emissionStrength`** above 0 makes the surface give off light in **`emissionColor`** (screens, LEDs, a neon tube). In Cycles a glowing surface also lights what's near it; for a strong light source, a real light is cleaner and faster.

## Checking your surface

1. Render one still from the shot's camera with `cycles`.
2. Judge highlights: are they the size and softness the real material would have? If not, change `roughness` before anything else.
3. Judge reflections: is there something for the surface to reflect? Most "flat" metal and glass is a lighting problem, not a material one.
4. Look at the item from a second angle; some surfaces only reveal themselves at grazing angles (coat, thin film, glass edges).
