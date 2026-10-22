import QtQuick
import QtQuick.Controls as QQC
import "."

// The new marker's name field (INTERACTION.md 1.6 › Markers: M), opened by Ruler.newMarker() under the playhead:
// "Marker 3" selected, Enter keeps it (one accepted(name, shared)), Esc or a click away cancels. The Shared switch
// is there only when the document is in a project (`canShare`), and then starts on. The kit only asks: the app's
// marker operation does the work.
QQC.Popup {
    id: p
    property bool canShare: false
    property bool shared: true
    signal accepted(string name, bool shared)
    function ask(name) { field.text = name; p.shared = p.canShare; open() }
    onOpened: { field.forceActiveFocus(); field.selectAll() }
    padding: Theme.gap
    focus: true
    closePolicy: QQC.Popup.CloseOnEscape | QQC.Popup.CloseOnPressOutside
    background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
    contentItem: Row {
        spacing: Theme.gap
        Rectangle {
            width: 140; height: Theme.field; radius: 4; color: Theme.sunken
            border.color: field.activeFocus ? Theme.accent : Theme.line
            TextInput {
                id: field
                anchors { fill: parent; leftMargin: Theme.gap; rightMargin: Theme.gap }
                verticalAlignment: TextInput.AlignVCenter; clip: true
                color: Theme.fg; selectionColor: Theme.accentSoft; selectByMouse: true
                font.family: uiFont; font.pixelSize: Theme.body
                onAccepted: { const n = text.trim(); if (!n) return; p.close(); p.accepted(n, p.canShare && p.shared) }
            }
        }
        Text { visible: p.canShare; anchors.verticalCenter: parent.verticalCenter; text: "Shared"
               color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
        Toggle { visible: p.canShare; anchors.verticalCenter: parent.verticalCenter; checked: p.shared
                 onToggled: (v) => p.shared = v
                 HoverTip { text: "Shared with the project"; help: "Every app sees it and can tie things to it."
                            hovered: parent.hovered } }
    }
}
