import QtQuick
import QtQuick.Controls as QQC
import "."

// Help → Report a problem. Says what to send and gives both pieces in one click each: Open log folder, Copy details (the
// app, its version, the system and the newest log's name). The line under the buttons says what the last click did.
// `data` is the app's `notices` object (reportDetails, reportFolder, openLogs(), copyDetails()). Esc or the × closes it.
SmallPopup {
    id: dlg
    property var data
    property string said: ""
    parent: QQC.Overlay.overlay
    x: Math.round((parent.width - width) / 2); y: Math.round((parent.height - height) / 2)
    width: 560; height: body.height + 2 * (Theme.groupGap + Theme.grid)
    padding: 0
    objectName: "reportDialog"
    modal: true; focus: true
    onOpened: said = ""
    QQC.Overlay.modal: Rectangle { color: Theme.scrim }
    background: Rectangle { color: Theme.panel; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }

    IconButton {
        glyph: "×"; kind: "ghost"; tip: "Close"; z: 2
        anchors { right: parent.right; top: parent.top; margins: Theme.gap }
        onClicked: dlg.close()
    }
    Column {
        id: body
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.groupGap + Theme.grid }
        spacing: Theme.groupGap
        Text { text: "Report a problem"; color: Theme.fg; font.family: uiFont; font.pixelSize: 20; font.weight: Font.DemiBold }
        Text {
            width: parent.width; wrapMode: Text.WordWrap
            text: "Tell us what you were doing and what went wrong, and send the details below with the newest log from the log folder."
            color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
        }
        Rectangle {
            width: parent.width; height: details.height + 2 * Theme.gap; color: Theme.sunken; radius: Theme.radiusCtl
            Text {
                id: details
                x: Theme.gap; y: Theme.gap; width: parent.width - 2 * Theme.gap; wrapMode: Text.Wrap
                text: dlg.data ? dlg.data.reportDetails : ""
                color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
            }
        }
        Row {
            spacing: Theme.gap
            Button { objectName: "reportOpenLogs"; text: "Open log folder"; kind: "normal"
                     onClicked: dlg.said = dlg.data.openLogs() }
            Button { objectName: "reportCopy"; text: "Copy details"; kind: "primary"
                     onClicked: dlg.said = dlg.data.copyDetails() }
        }
        Text {
            visible: dlg.said !== ""; width: parent.width; wrapMode: Text.WordWrap
            text: dlg.said; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
        }
    }
}
