"""Scripted steps for the scene's paintings (steps.py hands these over); each is the call an agent or a click makes.

    paintingop <op> <target|-> [<json args>]   one operation as one change (painting.add, painting.set, frame.add …); a
                                               refusal fails the step. A painting's id is its name's, lower-cased: painting_1 …
    paintingsay                                print each Library row (name, line) and the top bar's words
"""
from __future__ import annotations

import json

WORDS = ("paintingop", "paintingsay")


def do_painting_step(bridge, word, rest, step):
    if word == "paintingsay":
        for r in bridge.library.paintings.rows:
            print(f'painting {r["id"]}: {r["name"]} | {r["line"]}')
        print(f"status: {bridge.status!r}")
        return
    op, target = rest[0], rest[1]
    call = {"op": op, **({} if target == "-" else {"target": target.split(",")}),
            **({"args": json.loads(" ".join(rest[2:]))} if rest[2:] else {})}
    bridge._apply([call], op)
