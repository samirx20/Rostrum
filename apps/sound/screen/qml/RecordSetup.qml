import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// The take panel: how the next take is made (screen state, not an edit). Its rows come from takeSetup.controls
// (record_setup.py), each there only while it can be used: count-in bars only with count-in on, the punch times
// only with punch on, the keyboard chooser and quantize only on a notes or drum track.
QQC.Popup {
    id: pop
    width: 264; padding: Theme.pad
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
                spacing: Theme.gap; height: Theme.field
                Text { width: row.modelData.kind === "text" ? 220 : 84; anchors.verticalCenter: parent.verticalCenter
                       text: row.modelData.label; color: row.modelData.kind === "text" ? Theme.fg3 : Theme.fg2
                       font.family: uiFont; font.pixelSize: Theme.body }
                Toggle { visible: row.modelData.kind === "toggle"; checked: !!row.modelData.value
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
    }
}
