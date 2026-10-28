"""What a script is told about the document's items it did not make (another script's, a person's): a script reaches
only what it makes itself, so `layer("dot0")` for a dot made by "intro.py", or a second script's `comp("main")` for a
scene "intro.py" made, fails here naming who made it and what to do (add it to that script and re-run it under its
name: the film as one script, guide the-film-as-one-script). Without this, the second scene arrived with a second frame
and the merge refused it with a message about frames. No Qt."""
from __future__ import annotations

from rostrum_core.tree import walk

from .kind import KIND


def maker(doc, name: str, id_: str) -> str | None:
    """Who made `id_` in the document: 'script "x.py"', "a person (the window or edit_document)", or None when the
    document has no such item (or only this script made it)."""
    if doc is None:
        return None
    for other, tree in sorted(doc.script_bases.items(), key=lambda kv: kv[0] != name):     # this script's own first
        if any(i.get("id") == id_ for i in walk(tree, KIND.lists)):
            return None if other == name else f'script "{other}"'
    if any(i.get("id") == id_ for i in walk(doc.data, KIND.lists)):
        return "a person (the window or edit_document)"
    return None


def why_not_here(build, id_: str) -> str:
    """The sentence `layer(id)` adds when the id is the document's but not this script's ('' when it is no one's)."""
    who = maker(getattr(build, "doc", None), getattr(build, "name", ""), id_)
    if who is None:
        return ""
    fix = (f"make it in this script instead, or add these lines to {who} and re-run that one under its name"
           if who.startswith("script") else "change it with edit_document, or make your own in this script")
    return f' "{id_}" is in the document, made by {who}: a script keys only what it makes itself; {fix}.'


def check_comp(build, id_) -> None:
    """comp(id) for a scene the document already holds but this script didn't make: refused, saying who made it."""
    who = id_ and maker(getattr(build, "doc", None), getattr(build, "name", ""), id_)
    if not who:
        return
    if who.startswith("script"):
        raise ValueError(f'comp("{id_}"): scene "{id_}" was made by {who}, and two scripts can\'t both make one scene '
                         f'(it would get a second frame). Write the whole film in {who} and re-run it under that name '
                         f'(guide the-film-as-one-script), or make a scene of your own: comp("{id_}_2", …)')
    raise ValueError(f'comp("{id_}"): scene "{id_}" was made by {who}, not by a script. Make a scene of your own here '
                     f'(comp("{id_}_2", …)), or change "{id_}" with edit_document')
