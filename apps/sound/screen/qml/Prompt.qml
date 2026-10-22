import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// A small question in the middle of the window: a heading, one sentence, and its buttons (the children, in a row).
QQC.Popup {
    id: pop
    property string heading: ""
    property string message: ""
    default property alias buttons: row.data
    parent: QQC.Overlay.overlay
    anchors.centerIn: parent
    width: 400; padding: Theme.pad + Theme.grid
    modal: true; closePolicy: QQC.Popup.CloseOnEscape
    QQC.Overlay.modal: Rectangle { color: Theme.scrim }
    background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    contentItem: Column {
        spacing: Theme.pad
        Text { width: parent.width; text: pop.heading; color: Theme.fg; wrapMode: Text.WordWrap
               font.family: uiFont; font.pixelSize: Theme.heading; font.weight: Font.DemiBold }
        Text { width: parent.width; text: pop.message; color: Theme.fg2; wrapMode: Text.WordWrap
               font.family: uiFont; font.pixelSize: Theme.body; lineHeight: 1.25 }
        Row { id: row; spacing: Theme.gap; anchors.right: parent.right }
    }
}
