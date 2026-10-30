"""Makes the list of Google Fonts families Rostrum knows by name (shared/core/rostrum_core/byname/data/google-fonts.json):
family name -> its folder in github.com/google/fonts (ofl/… or apache/…). Only OFL and Apache families (the Ubuntu
Font Licence ones are left out). The font files themselves are fetched on first use (rostrum_core/byname/fonts.py).

    python tools/assets/google_fonts_list.py
"""
from __future__ import annotations

import datetime
import json
import re
import sys
from pathlib import Path

BYNAME = Path(__file__).resolve().parents[2] / "shared" / "core" / "rostrum_core" / "byname"
sys.path.insert(0, str(BYNAME))
import net  # noqa: E402  (byname/net.py alone: the package needs this list to import)

OUT = BYNAME / "data" / "google-fonts.json"
API = "https://api.github.com/repos/google/fonts/git/trees/"


def get(url: str) -> str:
    return net.get(url).decode("utf-8")


def key(family: str) -> str:
    return re.sub(r"[^a-z0-9]", "", family.lower())


def main() -> None:
    root = json.loads(get(API + "main"))
    folders = {}
    for top in root["tree"]:
        if top["path"] in ("ofl", "apache"):
            folders.update({e["path"]: f'{top["path"]}/{e["path"]}' for e in json.loads(get(API + top["sha"]))["tree"]
                            if e["type"] == "tree"})
    meta = get("https://fonts.google.com/metadata/fonts")
    listed = [f["family"] for f in json.loads(meta[meta.index("{"):])["familyMetadataList"]]
    families = {f: folders[key(f)] for f in sorted(listed) if key(f) in folders}
    OUT.write_text(json.dumps({"source": "github.com/google/fonts@" + root["sha"], "made": str(datetime.date.today()),
                               "families": families}, indent=0, ensure_ascii=False), "utf-8")
    print(OUT, len(families), "of", len(listed))


if __name__ == "__main__":
    main()
