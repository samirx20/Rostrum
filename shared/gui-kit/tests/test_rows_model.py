"""The timeline's rows keep their identity when the list changes (a row's delegate, and a key being dragged on it, must
survive every document change): only rows that came or went are inserted or removed, the rest are updated in place."""
from rostrum_gui.rows_model import RowsModel


def watch(model):
    log = []
    model.rowsInserted.connect(lambda _p, a, b: log.append(("in", a)))
    model.rowsRemoved.connect(lambda _p, a, b: log.append(("out", a)))
    model.rowsMoved.connect(lambda *a: log.append(("move", a[1], a[4])))
    model.dataChanged.connect(lambda a, b: log.append(("data", a.row())))
    return log


def ids(model):
    return [model.data(model.index(i))["id"] for i in range(model.rowCount())]


def test_changes_are_row_by_row():
    m = RowsModel()
    m.set([{"id": "a", "t": 1}, {"id": "b", "t": 1}, {"id": "c", "t": 1}])
    log = watch(m)
    m.set([{"id": "a", "t": 2}, {"id": "x", "t": 1}, {"id": "b", "t": 1}, {"id": "c", "t": 1}])      # a moved a key; x came in
    assert log == [("data", 0), ("in", 1)] and ids(m) == ["a", "x", "b", "c"]
    log.clear()
    m.set([{"id": "c", "t": 1}, {"id": "a", "t": 2}, {"id": "x", "t": 1}])                          # b went; c moved up
    assert ("out", 2) in log and [e[0] for e in log].count("move") == 1
    assert ids(m) == ["c", "a", "x"]
    log.clear()
    m.set([{"id": "c", "t": 1}, {"id": "a", "t": 2}, {"id": "x", "t": 1}])                          # nothing changed: nothing announced
    assert log == []


def test_rows_by_id_and_place():
    """QML finds a row through these (LayerRows.qml), never by reading every row."""
    m = RowsModel()
    m.set([{"id": "a"}, {"id": "b"}])
    assert (m.indexOf("b"), m.indexOf("nope"), m.at(1), m.at(5)) == (1, -1, {"id": "b"}, {})
