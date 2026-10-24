import QtQuick
import RostrumKit

// Onion skin (SPEC §9, Animate rail › Onion skin, O toggles it): ghosts of the selected item at other frames in the
// viewport, the frames before red, after green. Which frames: at its previous and next keys, or 2 and 4 frames
// each way. viewport.onionSkin (onion_qt.py) is screen state; the core draws the ghosts.
Popover {
    id: pop
    objectName: "onionPanel"
    title: "Onion skin"
    width: 248
    Column {
        width: pop.availableWidth
        spacing: Theme.gap
        SwitchRow { label: "Show"; labelColumn: 64; height: Theme.row; switchName: "onionOn"
                    checked: viewport.onionSkin.on; onToggled: (v) => viewport.onionSkin.setOn(v) }
        Segmented { visible: viewport.onionSkin.on; objectName: "onionMode"
                    options: viewport.onionSkin.modes; current: viewport.onionSkin.mode
                    onPicked: (v) => viewport.onionSkin.setMode(v) }
    }
}
