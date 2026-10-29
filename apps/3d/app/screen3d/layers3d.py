"""Animation layers on 3D's timeline (SPEC §13): the kit's model (rostrum_gui/anim_layers.py, AnimLayers.qml in the
timeline's play cell) plugged into the bridge, for QML as `backend.animLayers`. Picking a layer lists the rows again
(only its keys show); the weights shown follow the playhead (a faded layer's weight changes over time).
"""
from __future__ import annotations

from rostrum_gui.anim_layers import AnimLayers


def make(bridge) -> AnimLayers:
    model = AnimLayers(bridge)
    model.picked.connect(bridge.outlineChanged)
    bridge.frameChanged.connect(lambda: model.changed.emit() if model.count else None)
    return model
