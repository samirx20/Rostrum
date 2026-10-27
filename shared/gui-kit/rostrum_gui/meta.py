"""A Qt object's class and members, read without leaving a stale Python handle behind.

`obj.metaObject()` hands Python a QMetaObject that PySide keeps (on the object's own wrapper) and files under the
metaobject's address. A QML-made type ("Foo_QMLTYPE_3", "QQuickItem_QML_0": a QML file's root, an item declaring its own
properties) has a metaobject of its own that is freed with the item, but the Python QMetaObject stayed filed at that
address; the next Qt object made there came back to Python as that QMetaObject ("'QMetaObject' object has no attribute
'childItems'": Sound's screen tests after the Editor folded and opened, the layout checker on a CanvasCursor declared in
a QML file of its own). Every read here lets go of such a metaobject at once. A built-in class's metaobject lives for
the whole run and is shared (`QQuickItem.staticMetaObject` is the same Python object), so it is never let go.
"""
from __future__ import annotations

from contextlib import contextmanager

import shiboken6


def let_go(mo) -> None:
    """Unfile `mo` when it is a QML-made metaobject (one that dies with its item or type)."""
    if mo is not None and shiboken6.isValid(mo) and "_QML" in mo.className():
        shiboken6.invalidate(mo)


@contextmanager
def meta(obj):
    """`with meta(item) as mo:` its metaobject, let go of at the end."""
    mo = obj.metaObject()
    try:
        yield mo
    finally:
        let_go(mo)


def class_name(obj) -> str:
    with meta(obj) as mo:
        return mo.className()


def has_property(obj, name: str) -> bool:
    with meta(obj) as mo:
        return mo.indexOfProperty(name) >= 0


def has_method(obj, signature: str) -> bool:
    """`signature` as Qt writes it: "pressedAt(QVariant,QVariant)"."""
    with meta(obj) as mo:
        return mo.indexOfMethod(signature) >= 0


def class_chain(obj) -> list[str]:
    """The class names from `obj`'s own up to QObject."""
    out, mo = [], obj.metaObject()
    while mo is not None:
        out.append(mo.className())
        up = mo.superClass()
        let_go(mo)
        mo = up
    return out
