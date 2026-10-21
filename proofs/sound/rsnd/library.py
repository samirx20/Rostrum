"""Recorded sounds by name ("impact.metal-light"), from the experiment's catalogue: name -> takes, each
[pack, file, seconds, in-point?] under the installed packs (~/.rostrum/assets/sounds/<pack>/).

    lib = Library()
    lib.take("impact.metal-light", 2)  ->  {"path": ..., "offset": 0.0, "length": 0.236}
    lib.search("door")                 ->  names
Use with Track.sample(at=..., **lib.take(...))."""
import json
import subprocess
from pathlib import Path

PACKS = Path.home() / ".rostrum" / "assets" / "sounds"
ARCHIVE = Path(r"C:\Users\Sam\Documents\CODE\OLD-EXPERIMENT")
CATALOG_AT_TAG = "experiment-final:src/engine/sound/library/catalog.json"


def _archive_catalog() -> str:
    """The catalogue read straight from the archive's tag (read-only)."""
    p = subprocess.run(["git", "-C", str(ARCHIVE), "show", CATALOG_AT_TAG], capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise FileNotFoundError(f"sound catalogue: git show {CATALOG_AT_TAG} failed: {p.stderr.strip()}")
    return p.stdout


class Library:
    def __init__(self, catalog=None, packs=PACKS):
        text = Path(catalog).read_text(encoding="utf-8") if catalog else _archive_catalog()
        self.sounds = json.loads(text)["sounds"]
        self.packs = Path(packs)

    def search(self, word):
        return sorted(n for n in self.sounds if word in n)

    def takes(self, name):
        if name not in self.sounds:
            near = self.search(name.split(".")[-1].split("-")[0])
            raise KeyError(f'no sound "{name}"; nearby: {near[:12]}')
        return self.sounds[name]

    def take(self, name, n=0):
        t = self.takes(name)
        pack, file, secs, *inpoint = t[n % len(t)]
        path = self.packs / pack / file
        if not path.is_file():
            raise FileNotFoundError(f'"{name}" take {n}: pack "{pack}" is not installed ({path})')
        return {"path": path, "offset": float(inpoint[0]) if inpoint else 0.0, "length": float(secs)}
