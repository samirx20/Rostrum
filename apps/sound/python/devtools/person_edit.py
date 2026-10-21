"""Stand-in for the Sound screen until it exists: applies operations to a saved Sound document as a *person*,
through the same door the screen will use (`Document.apply`, recorded in the one history). Run it while no
server has the document open.

    python devtools/person_edit.py --folder <project folder> --item cue '{"op": "track.set", "target": ["strings"], "args": {"volume": 0.5}}'
"""
from __future__ import annotations

import argparse
import json

from rostrum_core import Document, Who

from rostrum_sound.doc import KIND


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("ops", nargs="+", help="Operation calls as JSON.")
    p.add_argument("--folder", required=True)
    p.add_argument("--item", default="cue")
    p.add_argument("--name", default="sam", help="The person's name in the history.")
    a = p.parse_args()
    doc = Document.open(a.folder, a.item, KIND)
    change = doc.apply([json.loads(o) for o in a.ops], Who.person(a.name))
    doc.save()
    print(f"change {change.seq} by person:{a.name}: {[c['op'] for c in change.calls]}" if change else "nothing changed")


if __name__ == "__main__":
    main()
