"""Recorded sounds by name ("impact.metal-light"), from the experiment's catalogue: name -> takes, each
[pack, file, seconds, in-point?] under the installed packs (~/.rostrum/assets/sounds/<pack>/).

    lib = Library()
    lib.take("impact.metal-light", 2)  ->  {"path": ..., "offset": 0.0, "length": 0.236}
    lib.search("door")                 ->  names
Use with Track.sample(**lib.take(...)) or Track.sound(name, at, ...)."""
import json
from pathlib import Path

PACKS = Path.home() / ".rostrum" / "assets" / "sounds"
CATALOG = Path(r"C:\Users\Sam\.rostrum\waves\scratch\priyam-p1\catalog.json")  # experiment-final:src/engine/sound/library/catalog.json


class Library:
    def __init__(self, catalog=CATALOG, packs=PACKS):
        self.sounds = json.loads(Path(catalog).read_text(encoding="utf-8"))["sounds"]
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
