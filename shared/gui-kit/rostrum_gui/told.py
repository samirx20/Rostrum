"""No action is silent (INTERACTION.md 1.21 rule 9): every action that changes the document says what it did, and to
how many ("Grouped 5 layers", "Auto layout · 3 layers"). The base fix for "More ▾ items act silently" (three critic
rounds running): the action hub watches its host's message line and its document while an action runs, and when the
document changed and nothing was said, it says the action's own words.

    told = Told(host)              # host: the app's bridge (the kit DocBridge: `statusChanged`, `status`, `docChanged`)
    with told.run() as r: ...      # run the action; afterwards r.changed / r.said
    words(action, label, what)     # the sentence: the action's `done` ("Grouped {what}"), else "<label> · <what>"

A host without those signals (a script's fake bridge) watches nothing: `r.changed` stays False, so nothing extra is
said there. An app keeps saying its own, better words (2D's "Keyed 4 settings on 3 layers"): this is only the floor.
"""
from __future__ import annotations

from contextlib import contextmanager


class Run:
    def __init__(self):
        self.changed, self.said = False, False


class Told:
    def __init__(self, host):
        self._host, self._run, self.watching = host, None, False
        sigs = [getattr(host, name, None) for name in ("statusChanged", "docChanged")]
        if all(s is not None and hasattr(s, "connect") for s in sigs):
            sigs[0].connect(self._status)
            sigs[1].connect(self._doc)
            self.watching = True

    def _status(self):
        if self._run is not None and getattr(self._host, "status", ""):
            self._run.said = True

    def _doc(self):
        if self._run is not None:
            self._run.changed = True

    def say(self, text, fallback):
        """Say what was done in the host's message line as plain news (`tell`: never a refusal, which an app's
        `message_fn` may be: Sound's marks a scripted step as refused), else through `fallback`."""
        tell = getattr(self._host, "tell", None)
        (tell if callable(tell) else fallback)(text)

    @contextmanager
    def run(self):
        outer, self._run = self._run, Run()       # an action run inside another (a key routed on): its own record
        try:
            yield self._run
        finally:
            inner, self._run = self._run, outer
            if outer is not None:
                outer.changed |= inner.changed
                outer.said |= inner.said


def words(action, label: str, what: str) -> str:
    """What a silent action says it did: its `done` ("Grouped {what}", or done(what) -> str), else its label and what it
    acted on ("Auto layout · 3 layers"; just the label with nothing selected)."""
    done = getattr(action, "done", "") if action is not None else ""
    if callable(done):
        return done(what)
    if done:
        return done.format(what=what or "it").strip()
    label = label.rstrip("…. ")
    return f"{label} · {what}" if what else label
