"""What a 2D document may hold that is valid but probably not meant. Replies to edit_document and run_script carry
what a call made new (rostrum_core DocKind.advise): a drawing set that has several drawings but shows only the first."""
from __future__ import annotations

_HOLDERS = ("comps", "paintings", "layers")        # never down into drawings: thousands of strokes live there


def _items(holder: dict):
    for key in _HOLDERS:
        for item in holder.get(key, []):
            yield item
            yield from _items(item)


def advise(data: dict) -> list[str]:
    out = []
    for item in _items(data):
        n = len(item.get("frames", []))
        if n > 1 and not item.get("eachFrame"):
            out.append(f'"{item["id"]}" holds {n} drawings but shows only the first one, because "Draw each frame" is off. '
                       f'Turn it on to play them in turn: in a script {item["id"]}.set(eachFrame=True), in an edit '
                       f'"{item["type"]}.set" with {{"eachFrame": true}} on "{item["id"]}".')
    return out
