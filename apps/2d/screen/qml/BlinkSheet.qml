import QtQuick
import RostrumKit

// Add blinks… (UX_SPEC 3.23 › Blinks): opened by the context bar's action on an eyes swap set, a sheet in the settings
// panel's place (Inspector `sheets`). How often (seconds), how much the gaps vary, which drawing is open, closed and half
// closed; Apply = one change over the whole scene (keys you can move). Esc or × closes it with nothing changed
// (backend.blinks: rig_blinks.py).
Panel {
    id: pop
    anchors.fill: parent
    readonly property var bl: backend.blinks
    readonly property real availableWidth: width - 2 * bodyPad
    visible: pop.bl.open
    title: "Blinks on " + pop.bl.what
    onVisibleChanged: if (visible) forceActiveFocus()
    Keys.onEscapePressed: pop.close()
    function close() { pop.bl.close() }
    headerRight: IconButton { glyph: "×"; kind: "ghost"; tip: "Close  Esc"; onClicked: pop.close() }
    component Words: Text { width: 110; anchors.verticalCenter: parent.verticalCenter; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
    component Line: Row { spacing: Theme.grid; height: Theme.row }
    SheetScroll {
        spacing: Theme.grid
        Line {
            Words { text: "Every" }
            NumberField { anchors.verticalCenter: parent.verticalCenter; width: 80; value: pop.bl.every; from: 0.1; to: 60; step: 0.1; unit: " s"
                          onEdited: (v) => pop.bl.setEvery(v)
                          onScrubbed: (v) => pop.bl.setEvery(v) }
        }
        Line {
            Words { text: "Varies by" }
            Slider { anchors.verticalCenter: parent.verticalCenter; width: 140; from: 0; to: 1; value: pop.bl.vary
                     onEdited: (v) => pop.bl.setVary(v)
                     onScrubbed: (v) => pop.bl.setVary(v) }
        }
        Repeater {
            model: [{ key: "open", label: "Eyes open" }, { key: "closed", label: "Eyes closed" }, { key: "half", label: "Half closed" }]
            delegate: Line {
                id: pickRow
                required property var modelData
                Words { text: pickRow.modelData.label }
                ChoiceField {
                    anchors.verticalCenter: parent.verticalCenter; width: pop.availableWidth - 110 - Theme.grid
                    options: pickRow.modelData.key === "half" ? [{ value: "", label: "None" }].concat(pop.bl.options) : pop.bl.options
                    current: pop.bl.picks[pickRow.modelData.key]
                    onPicked: (v) => pop.bl.setPick(pickRow.modelData.key, v)
                }
            }
        }
        Button { anchors.right: parent.right; text: "Apply"; kind: "primary"; onClicked: pop.bl.apply()
                 help: "Key blinks over the whole scene: one change you can undo." }   // × or Esc closes: no second way
    }
}
