import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Add blinks… (UX_SPEC 3.23 › Blinks): opened by the context bar's action on an eyes swap set, under the bar. How often
// (seconds), how much the gaps vary, which drawing is open, closed and half closed; Apply = one change over the whole
// scene (keys you can move). Esc or a click away closes it with nothing changed (backend.blinks: rig_blinks.py).
QQC.Popup {
    id: pop
    readonly property var bl: backend.blinks
    modal: true; dim: false
    padding: Theme.pad
    width: 340
    closePolicy: QQC.Popup.CloseOnPressOutside | QQC.Popup.CloseOnEscape
    background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    onClosed: bl.close()
    Connections {
        target: pop.bl
        function onOpened() { pop.open() }
        function onChanged() { if (!pop.bl.open && pop.opened) pop.close() }
    }
    component Words: Text { width: 110; anchors.verticalCenter: parent.verticalCenter; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
    component Line: Row { spacing: Theme.grid; height: Theme.row }
    contentItem: Column {
        spacing: Theme.grid
        Text { text: "Blinks on " + pop.bl.what; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold }
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
                    anchors.verticalCenter: parent.verticalCenter; width: 180
                    options: pickRow.modelData.key === "half" ? [{ value: "", label: "None" }].concat(pop.bl.options) : pop.bl.options
                    current: pop.bl.picks[pickRow.modelData.key]
                    onPicked: (v) => pop.bl.setPick(pickRow.modelData.key, v)
                }
            }
        }
        Row {
            anchors.right: parent.right
            spacing: Theme.grid
            Button { text: "Cancel"; onClicked: pop.close() }
            Button { text: "Apply"; kind: "primary"; onClicked: pop.bl.apply()
                     help: "Key blinks over the whole scene: one change you can undo." }
        }
    }
}
