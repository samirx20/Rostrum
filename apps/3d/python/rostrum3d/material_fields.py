"""A material's fields, part of the one table (fields.FIELDS["material"]; imported by fields.py once its helpers exist).

One physically based material type (Cycles' principled BSDF, with a UsdPreviewSurface for Storm). H22 added the
controls product films need: the direction metal is brushed in (`brushDirection`), sheen (fabric, velvet, peach fuzz),
a tinted clear coat over paint (`coatTint`, `coatIor`) and a screen showing a picture or a 2D item's render
(`emissionTexture`, `emissionRender`). What each renderer does with them: ENGINE_CONTRACT.md § 2, guides/materials.md.
"""
from __future__ import annotations

from .field_kit import CH, C, D, IS, N, NOT, S, X

GLOWS = NOT("emissionStrength", 0)
BRUSH = ["uv", "around x", "around y", "around z"]
DOC_ONLY = {"emissionRender"}       # the compiler turns it into emissionTexture, one picture per frame (screen.py)


def ALL(*conditions):
    return {"all": list(conditions)}


MATERIAL = [
    C("baseColor", "Base colour", "Surface", "#cccccc", when=IS("baseColorTexture", "")),
    X("baseColorTexture", "Base colour image", "Surface", "", S, help='Absolute path of an sRGB image on the UVs; replaces the base colour'),
    N("metallic", "Metallic", "Surface", 0, 1, 0.01, help="1 = metal (its colour tints the reflections)"),
    N("roughness", "Roughness", "Surface", 0, 1, 0.01, default=0.5, when=IS("roughnessTexture", ""),
      help="0 = mirror, 1 = chalk. On glass it also blurs what is seen through it (frosted glass)"),
    X("roughnessTexture", "Roughness image", "Surface", "", D, help="A grey image read as raw numbers"),
    N("transmission", "Transmission", "Glass", 0, 1, 0.01, "", S, help="1 = light passes through (glass, water)"),
    N("ior", "Index of refraction", "Glass", 1, 3, 0.01, "", S, default=1.5,
      help="How much light bends: water 1.33, glass 1.5, sapphire 1.77, diamond 2.42"),
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
]
FINAL_ONLY = {"coatTint", "coatIor", "sheen", "anisotropy", "thinFilm"}   # Cycles only (see each help); the panel tags their rows "Final"
