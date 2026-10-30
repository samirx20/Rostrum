"""Standard parts by the names agents write in web code, for every app.

Icons: `icon("arrow-right")`, `icon("lucide:arrow-right")`, `icon("tabler:heart-filled")`, React names (`ArrowRight`,
`IconHeart`) too: the SVG text, Lucide first, then Tabler. Both sets ship with Rostrum (data/, with their licences).
Fonts: any Google Fonts family by name (`font_files("Playfair Display", weights=[700], italic=True)`), fetched once from
github.com/google/fonts into the shared cache and kept. A name that doesn't exist answers with the five nearest names.
"""
from .icons import IconNotFound, icon, icon_names, icon_sets
from .icon_paths import icon_paths
from .icons_html import expand_icons
from .fonts import FontNeedsInternet, FontNotFound, font_files, google_family, google_families
from .fonts_css import engine_font, face_css, families_in_css, google_css_url

__all__ = ["icon", "icon_paths", "expand_icons", "icon_names", "icon_sets", "IconNotFound", "font_files", "google_family", "google_families",
           "FontNotFound", "FontNeedsInternet", "engine_font", "face_css", "families_in_css", "google_css_url"]
