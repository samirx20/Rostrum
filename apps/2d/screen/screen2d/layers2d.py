"""Animation layers on 2D's timeline (rostrum_core.keys.layers): the kit's model (rostrum_gui/anim_layers.py,
AnimLayers.qml beside Keys | Curves) plugged into the bridge, for QML as `backend.animLayers`. Picking a layer lists
the rows again (only its keys show: outline.rows' `layer`); a faded layer's weight shown follows the playhead. What the canvas,
looks and export draw is laid in once, in the scene (rostrum2d/layerbake.py).
"""
from __future__ import annotations

from rostrum_core.keys.layers import stack_of
from rostrum_gui.anim_layers import AnimLayers


def make(bridge) -> AnimLayers:
    model = AnimLayers(bridge)
    at = model.route
    bridge.doc.routes[bridge.doc.routes.index(at)] = lambda calls: at(_own_times(bridge, model, calls))
    model.picked.connect(bridge.outlineChanged)
    bridge.timeChanged.connect(lambda: model.changed.emit() if _faded(bridge) else None)
    return model


def _faded(bridge) -> bool:
    """Some layer's weight has keys: the weights shown change with the playhead. Only the playhead, never a new picture
    (2D draws one per drag step: the popover's rows made again then would drop a weight drag under the pointer)."""
    return any(k.get("prop") == "weight" for x in stack_of(bridge.doc.data) for k in x.get("keys", []))


def _own_times(bridge, model, calls):
    """A still field set while a layer is chosen becomes a key at the playhead: in the item's own seconds (an item timed
    from a marker has its own time 0 elsewhere: bridge.own_t), the way every 2D write at a time is made."""
    if not model.active:
        return calls
    return [{**c, "args": {**c["args"], "at": round(bridge.own_t(c["target"][0]), 6)}}
            if c.get("op") == "value.set" and not {"at", "by"} & c.get("args", {}).keys() and len(c.get("target") or []) == 1 else c
            for c in calls]
