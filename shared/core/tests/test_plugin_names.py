"""Guards the frozen name rule (OPERATIONS.md § 11): built-ins never hold ":", a plugin's op is "<prefix>:area.verb"."""
import pytest

from rostrum_core.registry import Operation, Registry


def _op(name, origin="builtin"):
    return Operation(name, "x", lambda *a: None, None, origin=origin)


def test_plugin_name_rule():
    reg = Registry()
    reg.add(_op("wiggle:shake.add", "hiremylens.wiggle"))
    for name, origin in (("shake.add", "hiremylens.wiggle"), ("wiggle:shake.add", "builtin"), ("Wiggle:shake.add", "a.b")):
        with pytest.raises(ValueError):
            reg.add(_op(name, origin))
    reg.add(_op("shake.add"))
    assert "origin" not in reg.get("shake.add").schema() and reg.get("wiggle:shake.add").schema()["origin"] == "hiremylens.wiggle"
