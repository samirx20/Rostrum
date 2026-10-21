"""The document and its two operations: select(itemId) and setValue(itemId, param, value).

Clicks, keys, the command bar and the demo script all go through these two and nothing else.
The inspector's rows are a list model built from controls.json for the selected item's kind.
"""
import copy
import json
from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, Property, Qt, Signal, Slot

RANK = {"primary": 0, "secondary": 1, "deep": 2}
GLYPH = {"camera": "Ca", "light": "Li", "text": "Tx", "clip": "Cl"}


def valid(cond, values, facts):
    """The whole condition language: is, not, all, any, fact. No condition = always valid."""
    if cond is None:
        return True
    if "is" in cond:
        name, want = cond["is"]
        return values[name] == want
    if "not" in cond:
        return not valid(cond["not"], values, facts)
    if "all" in cond:
        return all(valid(c, values, facts) for c in cond["all"])
    if "any" in cond:
        return any(valid(c, values, facts) for c in cond["any"])
    if "fact" in cond:
        return bool(facts.get(cond["fact"], False))
    raise ValueError(f"unknown condition {cond}")


def layout(kind):
    """Static row order for a kind: group header + its controls (primary first), then a More row + deep controls."""
    groups = list(dict.fromkeys(p["group"] for p in kind["params"]))
    ps = sorted(kind["params"], key=lambda p: (groups.index(p["group"]), RANK[p["importance"]]))
    rows = []
    for g in groups:
        members = [p for p in ps if p["group"] == g and p["importance"] != "deep"]
        if members:
            rows.append({"row": "group", "id": "group:" + g, "label": g, "members": [p["id"] for p in members]})
            rows += [dict(p, row="ctl") for p in members]
    deep = [p for p in ps if p["importance"] == "deep"]
    if deep:
        rows.append({"row": "more", "id": "more", "label": "More", "members": [p["id"] for p in deep]})
        rows += [dict(p, row="ctl") for p in deep]
    return rows


class RowsModel(QAbstractListModel):
    """Roles: row (group|ctl|more), id, label, type, options, min, max, step, unit, deep, valid, value.
    `valid` and `value` change in place (dataChanged), so each delegate keeps living and animates its own reveal."""
    NAMES = ["row", "id", "label", "type", "options", "min", "max", "step", "unit", "deep", "valid", "value"]
    ROLES = {Qt.UserRole + 1 + i: n.encode() for i, n in enumerate(NAMES)}

    def __init__(self):
        super().__init__()
        self.rows = []

    def roleNames(self):
        return self.ROLES

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role):
        return self.rows[index.row()].get(self.ROLES[role].decode())

    def reset(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def update(self, rows):
        for i, (old, new) in enumerate(zip(self.rows, rows)):
            roles = [r for r, n in self.ROLES.items() if n.decode() in ("valid", "value") and old.get(n.decode()) != new.get(n.decode())]
            if roles:
                self.rows[i] = new
                self.dataChanged.emit(self.index(i), self.index(i), roles)


class Doc(QObject):
    changed = Signal()

    def __init__(self, path):
        super().__init__()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.kinds = data["kinds"]
        self.items = {it["id"]: copy.deepcopy(it) for it in data["items"]}
        self.order = [it["id"] for it in data["items"]]
        self.layouts = {k: layout(v) for k, v in self.kinds.items()}
        self.sel = self.order[0]
        self.more_open = False
        self.history = []   # every operation, in order
        self.model = RowsModel()
        self.model.reset(self.rows())

    # --- reads -----------------------------------------------------------------------------------------------
    def item(self, item_id):
        if item_id not in self.items:
            raise KeyError(f"no item {item_id!r}")
        return self.items[item_id]

    def rows(self):
        it = self.items[self.sel]
        out = []
        for r in self.layouts[it["kind"]]:
            r = dict(r)
            if r["row"] == "ctl":
                ok = valid(r.get("validWhen"), it["values"], it["facts"])
                r["valid"] = ok and (not r["importance"] == "deep" or self.more_open)
                r["value"] = it["values"][r["id"]]
                r["deep"] = r["importance"] == "deep"
                r["options"] = r.get("options", [])
            else:
                by_id = {p["id"]: p for p in self.layouts[it["kind"]] if p["row"] == "ctl"}
                r["valid"] = any(valid(by_id[m].get("validWhen"), it["values"], it["facts"]) for m in r["members"])
                r["deep"] = False
            out.append(r)
        return out

    def visible(self):
        """(shown, more): ids of valid controls, deep ones listed apart (they sit behind More)."""
        it = self.items[self.sel]
        ok = [r for r in self.layouts[it["kind"]] if r["row"] == "ctl" and valid(r.get("validWhen"), it["values"], it["facts"])]
        return [r["id"] for r in ok if r["importance"] != "deep"], [r["id"] for r in ok if r["importance"] == "deep"]

    @Slot(result="QVariantList")
    def itemList(self):
        return [{"id": i, "name": self.items[i]["name"], "kind": self.kinds[self.items[i]["kind"]]["label"],
                 "glyph": GLYPH[self.items[i]["kind"]]} for i in self.order]

    @Slot(str, str, result="QVariant")
    def value(self, item_id, param):
        return self.item(item_id)["values"][param]

    @Property(str, notify=changed)
    def selected(self):
        return self.sel

    @Property(QObject, constant=True)
    def rowsModel(self):
        return self.model

    @Property(bool, notify=changed)
    def moreOpen(self):
        return self.more_open

    # --- the two operations ----------------------------------------------------------------------------------
    @Slot(str)
    def select(self, item_id):
        self.item(item_id)
        self.history.append(("select", item_id))
        if item_id != self.sel:
            self.sel = item_id
            self.model.reset(self.rows())
            self.changed.emit()

    @Slot(str, str, "QVariant")
    def setValue(self, item_id, param, value):
        it = self.item(item_id)
        p = next((r for r in self.layouts[it["kind"]] if r["row"] == "ctl" and r["id"] == param), None)
        if p is None:
            raise KeyError(f"{item_id}: no control {param!r}")
        if p["type"] == "toggle" and not isinstance(value, bool):
            raise ValueError(f"{item_id}.{param}: toggle needs true/false")
        if p["type"] == "choice" and value not in p["options"]:
            raise ValueError(f"{item_id}.{param}: {value!r} not in {p['options']}")
        if p["type"] == "number":
            value = max(p["min"], min(p["max"], round(float(value) / p["step"]) * p["step"]))
            value = round(value, 4)
        self.history.append(("set", item_id, param, value))
        if it["values"][param] == value:
            return
        it["values"][param] = value
        if item_id == self.sel:
            self.model.update(self.rows())
        self.changed.emit()

    @Slot()
    def toggleMore(self):
        self.more_open = not self.more_open
        self.model.update(self.rows())
        self.changed.emit()
