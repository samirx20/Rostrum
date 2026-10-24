"""A new selection keeps every settings-row delegate (model_pick.py): the panel shows exactly the new rows, in order,
every kept row after them is absent, and going back to a kind makes nothing (its rows wait, parked)."""
from rostrum_gui.model import RowsModel

ROLES = ("row", "id", "type", "control", "half", "valid", "value")


def _r(id_, type_="number", value=0):
    return {"row": "param", "id": id_, "type": type_, "control": "", "half": None, "valid": True, "value": value}


def _view(m):
    return [(m.data(m.index(i), m._ids["id"]), m.data(m.index(i), m._ids["value"]), m.data(m.index(i), m._ids["valid"]))
            for i in range(m.rowCount())]


def test_a_pick_shows_its_rows_in_order_and_parks_the_rest():
    m = RowsModel(ROLES)
    made = []
    m.rowsInserted.connect(lambda _p, a, b: made.append(b - a + 1))
    shape = [_r("w", value=100), _r("h"), _r("radius"), _r("x", value=1)]
    text = [_r("font", "choice"), _r("size"), _r("x", value=2)]
    m.update(shape, instant=True)
    m.update(text, instant=True)
    view = _view(m)
    assert [v[:2] for v in view[:3]] == [("font", 0), ("size", 0), ("x", 2)]          # the new rows, their values
    assert {v[0] for v in view[3:]} == {"w", "h", "radius"} and not any(v[2] for v in view[3:])   # the rest absent
    made.clear()
    m.update(shape, instant=True)                                          # back to the shape: nothing is made
    assert made == [] and [v[:2] for v in _view(m)[:4]] == [("w", 100), ("h", 0), ("radius", 0), ("x", 1)]
    assert not any(v[2] for v in _view(m)[4:])
