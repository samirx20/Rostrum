import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// The take panel: how the next take is made (screen state, not an edit). Its rows come from takeSetup.controls
// (record_setup.py), each there only while it can be used: count-in bars only with count-in on, the punch range
// (dragged on the ruler) only with punch on, "Hear input" only while the microphone is open, the keyboard chooser
// and quantize only on a notes or drum track.
QQC.Popup {
    id: pop
    width: 280; padding: Theme.pad
    visible: takeSetup.open
    onClosed: takeSetup.setOpen(false)
    background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }

    contentItem: Column {
        spacing: Theme.gap
        Text { text: "Take"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
        Repeater {
            model: takeSetup.controls
            delegate: Row {
                id: row
                required property var modelData
                readonly property bool note: modelData.kind === "text"
                spacing: Theme.gap; height: note ? label.implicitHeight + 2 : Theme.field
                Text { id: label; width: row.note ? pop.width - 2 * Theme.pad : 96
                       anchors.verticalCenter: parent.verticalCenter; wrapMode: Text.WordWrap
                       text: row.modelData.label; color: row.note ? Theme.fg3 : Theme.fg2
                       font.family: uiFont; font.pixelSize: row.note ? Theme.label : Theme.body }
                Toggle { visible: row.modelData.kind === "toggle"; checked: !!row.modelData.value
                         anchors.verticalCenter: parent.verticalCenter
                         onToggled: (v) => takeSetup.set(row.modelData.key, v) }
                NumberField { visible: row.modelData.kind === "number"; width: 96
                              value: row.modelData.kind === "number" ? row.modelData.value : 0
                              from: row.modelData.from || 0; to: row.modelData.to || 1e9; step: row.modelData.step || 1
                              unit: row.modelData.unit || ""
                              onEdited: (v) => takeSetup.set(row.modelData.key, v) }
                ChoiceField { visible: row.modelData.kind === "choice"; width: 150
                              options: row.modelData.options || []; current: String(row.modelData.value)
                              onPicked: (v) => takeSetup.set(row.modelData.key, v) }
            }
        }
        Button {   // a keyboard take (keys_record.py): only with a keyboard, on a notes or drum track
            visible: typeof keys !== "undefined" && keys.usable && !recorder.recording
            text: "Record keys"; kind: "ghost"; height: Theme.field
            onClicked: { takeSetup.setOpen(false); keys.toggleRecord() }
        }
    }
}
