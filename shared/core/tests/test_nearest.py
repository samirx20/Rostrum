""""Did you mean …": the closest real names, one clear match stays one name, and a script's Python error is read for
the wrong name, field / call or keyword argument (names only; nothing is applied)."""
from rostrum_core import nearest
from rostrum_core.errors import did_you_mean


def test_closest_names_best_first():
    assert nearest.closest("domainX", ["domain", "range", "ticks"]) == ["domain"]
    assert nearest.closest("from", ["start", "end"]) == ["start"]
    assert nearest.closest("Fill", ["fill", "stroke"]) == ["fill"]
    assert nearest.closest("zzz", ["fill", "stroke"]) == []
    assert nearest.closest("colr", ["color", "colour", "size"]) == ["color"]
    assert set(nearest.closest("lin", ["line", "link", "size"])) == {"line", "link"}
    assert did_you_mean("shap", ["shape", "w"]) == "Did you mean shape?"
    assert did_you_mean("lin", ["line", "link"]) == "Did you mean line or link?"


def _error(source, scope):
    try:
        exec(compile(source, "s", "exec"), scope)
    except Exception as e:
        return e
    raise AssertionError("ran")


class Chart:
    def key(self, prop, keys, ease="smooth"):
        return self


def test_script_hint_names_the_close_ones():
    scope = {"chart": Chart, "__builtins__": {"len": len}}
    assert nearest.script_hint(_error("chrt()", scope), scope) == '"chrt" isn\'t a name the script knows; did you mean chart?'
    e = _error("c = chart()\nc.kye(1, 2)", scope)
    assert nearest.script_hint(e, scope) == '"kye" isn\'t a field or call of Chart; did you mean key?'
    e = _error("c = chart()\nc.key(1, 2, eas='in')", scope)
    assert nearest.script_hint(e, scope) == '"eas" isn\'t an argument of key(); did you mean ease?'
    e = _error("c = chart()\nc.key(1, 2, zzz='in')", scope)
    assert nearest.script_hint(e, scope) == '"zzz" isn\'t an argument of key(); it takes prop, keys, ease'


def test_script_hint_extra_names_and_not_a_name_error():
    scope = {"chart": Chart}
    e = _error("c = chart()\nc.domainx", scope)
    assert nearest.script_hint(e, scope, lambda obj: ["domain"]).endswith("did you mean domain?")
    assert nearest.script_hint(_error("1 / 0", scope), scope) is None
