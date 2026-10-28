"""A material's fields, part of the one table (fields.FIELDS["material"]; imported by fields.py once its helpers exist).

One physically based material type (Cycles' principled BSDF, with a UsdPreviewSurface for Storm). H22 added the
controls product films need: the direction metal is brushed in (`brushDirection`), sheen (fabric, velvet, peach fuzz),
a tinted clear coat over paint (`coatTint`, `coatIor`) and a screen showing a picture or a 2D item's render
(`emissionTexture`, `emissionRender`). Brief 22 added the stylized blocks (SPEC §6.4): Lines and Halftone (the Stylized
look only) and Light to colour (Final and Stylized), each a group its toggle turns on (one click on its name in the
material's row of names). What each renderer does with them: ENGINE_CONTRACT.md § 2, guides/materials.md.
"""
from __future__ import annotations

import dataclasses

from .field_kit import CH, C, D, IS, N, NOT, S, T, X

GLOWS = NOT("emissionStrength", 0)
UNDER = NOT("subsurface", 0)
BRUSH = ["uv", "around x", "around y", "around z"]
LINES, TONE, HALF = IS("lines", True), IS("lightToColor", True), IS("halftone", True)
DOC_ONLY = {"emissionRender"}       # the compiler turns it into emissionTexture, one picture per frame (screen.py)


def ALL(*conditions):
    return {"all": list(conditions)}


MATERIAL = [
    C("baseColor", "Base colour", "Surface", "#cccccc", when=IS("baseColorTexture", "")),
    X("baseColorTexture", "Base colour image", "Surface", "", S, help='Absolute path of an sRGB image on the UVs; replaces the base colour'),
    N("metallic", "Metallic", "Surface", 0, 1, 0.01, when=IS("metallicTexture", ""),
      help="1 = metal (its colour tints the reflections)"),
    X("metallicTexture", "Metallic image", "Surface", "", D, help="A grey image read as raw numbers: white = metal"),
    N("roughness", "Roughness", "Surface", 0, 1, 0.01, default=0.5, when=IS("roughnessTexture", ""),
      help="0 = mirror, 1 = chalk. On glass it also blurs what is seen through it (frosted glass)"),
    X("roughnessTexture", "Roughness image", "Surface", "", D, help="A grey image read as raw numbers"),
    N("transmission", "Transmission", "Glass", 0, 1, 0.01, "", S,
      help="1 = light passes through (glass, water, juice). Below 1 the rest is an opaque painted surface mixed in: "
           "clear and tinted glass and liquids need 1 (the base colour tints what is seen through)"),
    N("ior", "Index of refraction", "Glass", 1, 3, 0.01, "", S, default=1.5,
      help="How much light bends: water 1.33, glass 1.5, sapphire 1.77, diamond 2.42"),
    T("thinWalled", "Thin walled", "Glass", False, D, NOT("transmission", 0),
      help="The surface is one sheet with no inside (a window pane, a bubble, a bottle made as a single surface): "
           "light passes through it without bending. Off: a solid or a closed shell, bent going in and out (Cycles)"),
    N("coat", "Clear coat", "Coat", 0, 1, 0.01, "", S, help="A thin varnish layer over the surface"),
    N("coatRoughness", "Coat roughness", "Coat", 0, 1, 0.01, "", S, NOT("coat", 0), default=0.03),
    C("coatTint", "Coat colour", "Coat", "#ffffff", D, NOT("coat", 0),
      help="Colours the light passing through the coat, twice (in and out): deeper where it is seen edge-on, "
           "like candy paint; white = clear (Cycles)"),
    N("coatIor", "Coat index of refraction", "Coat", 1, 3, 0.01, "", D, NOT("coat", 0), default=1.5,
      help="How strong the coat's reflection is: higher = a brighter coat highlight (Cycles)"),
    N("sheen", "Sheen", "Sheen", 0, 1, 0.01, "", D,
      help="A soft glow at grazing angles from tiny fibres (fabric, velvet, dust, peach fuzz) (Cycles)"),
    N("sheenRoughness", "Sheen roughness", "Sheen", 0, 1, 0.01, "", D, NOT("sheen", 0), default=0.5,
      help="Low = a narrow rim along the outline; high = spread over the whole surface"),
    C("sheenTint", "Sheen colour", "Sheen", "#ffffff", D, NOT("sheen", 0)),
    N("anisotropy", "Anisotropy", "Brushed", 0, 1, 0.01, "", D, help="Stretches highlights along one direction (brushed metal) (Cycles)"),
    CH("brushDirection", BRUSH, "Brushed along", "Brushed", "uv", D, NOT("anisotropy", 0),
       help="uv = along the mesh's U (straight brushing); around x / y / z = circles round that axis of the item, "
            "through its origin (spun brushing, like a watch back or a knob's face)"),
    N("anisotropyRotation", "Brush turn", "Brushed", 0, 1, 0.01, "", D, NOT("anisotropy", 0),
      help="Turns the brushing on the surface: 0..1 = 0..360°"),
    N("subsurface", "Light under the surface", "Under the surface", 0, 1, 0.01, "", S,
      help="How much light goes into the surface, spreads inside and comes out elsewhere (skin, wax, soap, marble, "
           "milk): shadows soften and thin parts (an ear, a finger) glow against a light behind them. 0 = off"),
    C("subsurfaceColor", "Colour inside", "Under the surface", "#ffffff", S, UNDER,
      help="Which colours travel farthest inside: thin parts lit from behind glow this colour (skin: a warm red). "
           "White = all colours travel the same distance. The surface's own colour stays the base colour"),
    N("subsurfaceRadius", "How far it travels", "Under the surface", 0, 500, 0.1, "mm", S, UNDER, default=4.0,
      help="How far light gets inside before it comes back out, in real millimetres: skin about 4, wax and soap "
           "about 8, marble about 5. A small object shows it more than a big one with the same value"),
    X("bumpTexture", "Bump image", "Relief", "", D, help="A grey height image: white is raised"),
    N("bumpStrength", "Bump strength", "Relief", 0, 1, 0.01, "", D, NOT("bumpTexture", ""), default=0.5),
    N("emissionStrength", "Glow strength", "Glow", 0, 1e4, 0.1, "", D, help="The surface gives off light (screens, LEDs)"),
    C("emissionColor", "Glow colour", "Glow", "#ffffff", D,
      ALL(GLOWS, IS("emissionTexture", ""), IS("emissionRender", ""))),
    X("emissionTexture", "Glow image", "Glow", "", D, ALL(GLOWS, IS("emissionRender", "")),
      help="Absolute path of an sRGB image on the UVs: the glow takes its colours (a screen's picture)"),
    X("emissionRender", "Glow from 2D item", "Glow", "", D, ALL(GLOWS, IS("emissionTexture", "")),
      help="The id of a 2D item of this project: its newest PNG-sequence render plays on the surface, its frame "
           "at each moment of the shot (held at the ends). Read-only: change it in Rostrum2D and render again"),
    N("thinFilm", "Thin film", "Coat", 0, 2000, 1, "nm", D, help="Rainbow coating thickness (anodizing, soap); 0 = off (Cycles)"),
    T("lines", "Lines", "Lines", False, S,
      help="Ink lines along the outline and the creases of every surface with this material (Stylized look)"),
    N("linesWidth", "Width", "Lines", 0.25, 12, 0.05, "px", S, LINES, default=1.5,
      help="How thick a line is, in pixels of the finished picture"),
    C("linesColor", "Colour", "Lines", "#1a1a1a", S, LINES),
    N("linesTaper", "Taper", "Lines", 0, 1, 0.01, "", S, LINES, default=0.5,
      help="Lines get thinner where the surface is lit: 0 = the same width everywhere, 1 = thinnest in full light"),
    N("linesWobble", "Wobble", "Lines", 0, 1, 0.01, "", S, LINES, default=0.3,
      help="How much the width changes along a line, like a hand-held pen: 0 = steady"),
    N("linesCreaseAngle", "Crease angle", "Lines", 1, 180, 1, "°", S, LINES, default=40,
      help="A fold sharper than this angle gets a line too; 180 = the outline only"),
    T("lightToColor", "Light to colour", "Light to colour", False, S,
      help="Colours the surface by how much light reaches it (the scene's real lights and cast shadows): one colour "
           "where it is lit, one in between, one in shadow. Final and Stylized looks"),
    C("litColor", "Lit colour", "Light to colour", "#ffffff", S, TONE,
      help="Where the surface is lit. Multiplies the base colour (or base colour image): white = the base colour itself"),
    C("midColor", "Middle colour", "Light to colour", "#b3b3b3", S, TONE,
      help="Between shadow and lit. Multiplies the base colour"),
    C("shadowColor", "Shadow colour", "Light to colour", "#4d4d4d", S, TONE,
      help="In shadow. Multiplies the base colour"),
    N("shadowBelow", "Shadow below", "Light to colour", 0, 1, 0.01, "", S, TONE, default=0.15,
      help="How lit a point is, from 0 (no light) to 1 (white paper under these lights looks white): below this it "
           "takes the shadow colour"),
    N("litFrom", "Lit from", "Light to colour", 0, 1, 0.01, "", S, TONE, default=0.5,
      help="From this much light up the surface takes the lit colour; between Shadow below and this, the middle "
           "colour. Below Shadow below, Lit from counts for both"),
    dataclasses.replace(CH("lightEdges", ["steps", "smooth"], "Edges", "Light to colour", "steps", S, TONE,
                           help="Steps = hard edges between the colours; Smooth = each edge blends over Softness"),
                        labels={"steps": "Steps", "smooth": "Smooth"}),
    N("lightSoftness", "Softness", "Light to colour", 0.01, 0.5, 0.01, "", S, ALL(TONE, IS("lightEdges", "smooth")),
      default=0.1, help="How far each edge blends, on the same 0–1 scale of how lit: either side of Shadow below and Lit from"),
    T("halftone", "Halftone", "Halftone", False, S,
      help="Printed dots or lines over the surface, bigger where it is darker: none in full light, solid in full "
           "shadow (Stylized look)"),
    dataclasses.replace(CH("halftoneShape", ["dots", "lines"], "Shape", "Halftone", "dots", S, HALF),
                        labels={"dots": "Dots", "lines": "Lines"}),
    N("halftoneSize", "Size", "Halftone", 2, 40, 0.5, "px", S, HALF, default=6,
      help="The spacing of the dots or lines, in pixels of the finished picture"),
    N("halftoneAngle", "Angle", "Halftone", -90, 90, 1, "°", S, HALF, default=45,
      help="The screen's turn: the rows of dots or the lines run at this angle"),
    C("halftoneColor", "Colour", "Halftone", "#1a1a1a", S, HALF),
]
FINAL_ONLY = {"thinWalled", "coatTint", "coatIor", "sheen", "anisotropy", "thinFilm", "subsurfaceRadius"}   # Cycles only (see each help); the panel tags their rows "Final"
QUICK_APPROX = {"subsurface", "subsurfaceColor"}   # Final shows them fully, the quick view only a tint (ENGINE_CONTRACT § 2); also tagged "Final"
# The stylized blocks' tags go on each group's switch and its first row only (the row right under the group's heading):
# one tag says it for the whole group, the same word on every row would only repeat it.
STYLIZED_ONLY = {"lines", "linesWidth", "halftone", "halftoneShape"}   # the Stylized look only: tagged "Stylized"
FINAL_STYLIZED = {"lightToColor", "litColor"}                           # Final and Stylized: tagged "Final · Stylized"


def stylized(material: dict) -> bool:
    """The material uses a block only the Stylized look shows (Lines or Halftone on): the Look offers Stylized while
    any material of the project does (SPEC §6.4)."""
    return bool(material.get("lines")) or bool(material.get("halftone"))


def any_stylized(data: dict) -> bool:
    """A material of the document uses a Stylized-only block: the Look and the render sheet's Quality offer Stylized."""
    return any(stylized(m) for m in data.get("materials", []))
