"""Styled runs inside one text (text_runs.py): the body list becomes one body + run fields, a run is found by its
words, and a re-run with fewer runs leaves none behind."""
import pytest

from rostrum2d.script import run_source

HEAD = 'comp("c", width=1920, height=1080, duration=4)\n'


def _line(doc):
    return next(n for n in doc["comps"][0]["layers"] if n["id"] == "line")


def test_runs_are_one_text_and_keyable_by_their_words():
    src = HEAD + ('t = text("line", body=["Make it ", ("move", {"color": "#ff5a36", "weight": 800}), " on cue"], color="#eeeeee")\n'
                  't.run("move").key("color", {1: "#eeeeee", 1.3: "#ff5a36"})\n')
    n = _line(run_source(src, "s.py"))
    assert n["body"] == "Make it move on cue"
    assert (n["run1From"], n["run1To"], n["run1Weight"]) == (8, 12, 800)
    assert {k["prop"] for k in n["keys"]} == {"run1Color"}


def test_a_plain_body_clears_old_runs_and_bad_parts_fail_loudly():
    n = _line(run_source(HEAD + 't = text("line", body=["a ", ("b", {})])\nt.set(body="plain")\nt.set(body=["x"])\n', "s.py"))
    assert n["body"] == "x" and n["run1To"] == 0
    with pytest.raises(Exception, match="a run takes color"):
        run_source(HEAD + 'text("line", body=["a ", ("b", {"size": 3})])\n', "s.py")
    with pytest.raises(Exception, match="no such run"):
        run_source(HEAD + 'text("line", body=["a ", ("b", {})]).run("c")\n', "s.py")
