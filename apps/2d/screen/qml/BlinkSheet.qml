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
    bodyPad: Theme.padLeft
    readonly property real availableWidth: width - Theme.padLeft - Theme.padRight     // the inspector's row width: the same label and field columns
    readonly property int labelColumn: Theme.labelColumnFor(availableWidth)
    readonly property int fieldWidth: Theme.fieldFor(availableWidth)
    visible: pop.bl.open
    title: "Blinks on " + pop.bl.what
    onVisibleChanged: if (visible) forceActiveFocus()
    Keys.onEscapePressed: pop.close()
    function close() { pop.bl.close() }
    headerRight: IconButton { glyph: "×"; kind: "ghost"; tip: "Close  Esc"; onClicked: pop.close() }
    component Words: Text { width: pop.labelColumn - Theme.gap; anchors.verticalCenter: parent.verticalCenter; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
    component Line: Row { spacing: Theme.grid; height: Theme.row }
    SheetScroll {
        spacing: Theme.grid
        Line {
            Words { text: "Every" }
            NumberField { anchors.verticalCenter: parent.verticalCenter; width: pop.fieldWidth; value: pop.bl.every; from: 0.1; to: 60; step: 0.1; unit: " s"
                          onEdited: (v) => pop.bl.setEvery(v)
                          onScrubbed: (v) => pop.bl.setEvery(v) }
        }
        Line {
            Words { text: "Varies by" }
            Item {
                width: pop.fieldWidth; height: parent.height
                Slider { anchors.left: parent.left; anchors.right: varyField.left; anchors.rightMargin: Theme.gap + 2
                         anchors.verticalCenter: parent.verticalCenter; from: 0; to: 1; value: pop.bl.vary; display: "percent"
                         onEdited: (v) => pop.bl.setVary(v)
                         onScrubbed: (v) => pop.bl.setVary(v) }
                NumberField { id: varyField; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                              width: Theme.amountFieldShort; value: pop.bl.vary; from: 0; to: 1; step: 0.01; display: "percent"
                              onEdited: (v) => pop.bl.setVary(v)
                              onScrubbed: (v) => pop.bl.setVary(v) }
            }
        }
        Repeater {
            model: [{ key: "open", label: "Open" }, { key: "closed", label: "Closed" }, { key: "half", label: "Half" }]
            delegate: Line {
                id: pickRow
                required property var modelData
                Words { text: pickRow.modelData.label }
                ChoiceField {
                    anchors.verticalCenter: parent.verticalCenter; width: pop.fieldWidth
                    options: pickRow.modelData.key === "half" ? [{ value: "", label: "None" }].concat(pop.bl.options) : pop.bl.options
                    current: pop.bl.picks[pickRow.modelData.key]
                    onPicked: (v) => pop.bl.setPick(pickRow.modelData.key, v)
                }
            }
        }
        Button { x: pop.labelColumn + pop.fieldWidth - width; text: "Apply"; kind: "primary"; onClicked: pop.bl.apply()
                 help: "Key blinks over the whole scene: one change you can undo." }   // × or Esc closes: no second way
    }
}
