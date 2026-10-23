import QtQuick
import QtQuick.Controls as QQC
import "."

// Help → About and licences. Top: the app's name, version and own licence, and where the full licence texts are.
// Below: every component the app ships, with its licence and what that licence asks of us. `data` is the app's
// `notices` object (appName, version, items [{name, version, licence, asks}], where). Esc or the × closes it.
QQC.Popup {
    id: dlg
    property var data
    // read only once the screen is opened; grouped by licence, so what a licence asks is said once over its run (F5, audit 51)
    readonly property var items: opened && data ? data.items.slice().sort((a, b) => (a.licence || "").localeCompare(b.licence || "")) : []
    parent: QQC.Overlay.overlay
    x: Math.round((parent.width - width) / 2); y: Math.round((parent.height - height) / 2)
    width: 680; height: Math.min(parent.height - 2 * Theme.groupGap * 2, 620)
    padding: 0
    objectName: "noticesDialog"
    modal: true; focus: true
    QQC.Overlay.modal: Rectangle { color: Theme.scrim }
    background: Rectangle { color: Theme.panel; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }

    IconButton {
        glyph: "×"; kind: "ghost"; tip: "Close"
        anchors { right: parent.right; top: parent.top; margins: Theme.gap }
        onClicked: dlg.close()
    }
    Column {
        id: about
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.groupGap + Theme.grid }
        spacing: Theme.grid
        Row {
            spacing: Theme.gap
            Text { text: dlg.data ? dlg.data.appName : ""; color: Theme.fg; font.family: uiFont; font.pixelSize: 20; font.weight: Font.DemiBold }
            Text { text: dlg.data ? dlg.data.version : ""; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body; y: 9 }
        }
        Text { text: "MIT licence, HireMyLens Media"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
        Text {
            width: parent.width; wrapMode: Text.WordWrap
            text: (dlg.data ? dlg.data.where + " " : "") + "Each component below is used under its own licence, and each asks that its notice is kept; a line says when one asks more."
            color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
        }
    }
    Text {
        id: listTitle
        anchors { left: parent.left; leftMargin: Theme.groupGap + Theme.grid; top: about.bottom; topMargin: Theme.groupGap + Theme.grid }
        text: "Components this app ships" + (dlg.items.length ? "  ·  " + dlg.items.length : "")
        color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold
        font.letterSpacing: Theme.capsSpacing; font.capitalization: Font.AllUppercase
    }
    Rectangle {  // the list sits in a sunken well
        anchors { left: parent.left; right: parent.right; top: listTitle.bottom; bottom: parent.bottom
                  leftMargin: Theme.groupGap; rightMargin: Theme.groupGap; bottomMargin: Theme.groupGap; topMargin: Theme.gap }
        color: Theme.sunken; radius: Theme.radiusCtl; clip: true
        Text {
            visible: dlg.items.length === 0; anchors.centerIn: parent
            text: "No components listed for this app yet."; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
        }
        ListView {
            id: list
            anchors { fill: parent; margins: Theme.grid; rightMargin: Theme.gap }
            model: dlg.items
            clip: true; boundsBehavior: Flickable.StopAtBounds
            delegate: Item {
                id: row
                required property var modelData
                required property int index
                // what a licence asks is said once, on its first row; the usual "Keep the notice" is said once at the top
                readonly property bool sameAsks: modelData.asks === "Keep the notice" || dlg.items.findIndex(i => i.asks === modelData.asks) < index
                // a licence cell may carry notes ("MIT-0 (metadata); its LICENSE text is …"): the name sits at the right,
                // the notes wrap under what the licence asks, never cut
                readonly property var cut: /^(.*?)(?:; |\. | \()(.*)$/.exec(modelData.licence || "")
                readonly property string licenceName: cut ? cut[1] : (modelData.licence || "")
                readonly property string notes: cut ? (modelData.licence.slice(cut[1].length).replace(/^[;.]?\s*/, "")) : ""
                width: ListView.view.width; height: Math.max(askText.y + askText.height, licenceText.y + licenceText.height) + Theme.gap
                Text {
                    id: nameText
                    anchors { left: parent.left; leftMargin: Theme.gap; top: parent.top; topMargin: Theme.gap }
                    // the name wraps in what is left beside the licence; nothing is cut or runs into its neighbour
                    width: parent.width - licenceText.width - 3 * Theme.gap; wrapMode: Text.Wrap
                    text: row.modelData.name; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
                }
                Text {
                    id: licenceText
                    anchors { right: parent.right; rightMargin: Theme.gap; top: nameText.top }
                    width: Math.min(implicitWidth, parent.width * 0.3); wrapMode: Text.Wrap; horizontalAlignment: Text.AlignRight
                    text: row.licenceName; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
                }
                Text {  // the version has its own line: a long one ("12Hz, GGUFs from …") wraps there
                    id: versionText
                    anchors { left: nameText.left; right: parent.right; rightMargin: Theme.gap; top: nameText.bottom
                              // a licence that wraps to several lines is taller than the name: the version starts below it
                              topMargin: 2 + Math.max(0, licenceText.height - nameText.height) }
                    visible: text !== ""; height: visible ? implicitHeight : 0; wrapMode: Text.Wrap
                    text: row.modelData.version; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
                }
                Text {
                    id: askText
                    anchors { left: parent.left; leftMargin: Theme.gap; right: parent.right; rightMargin: Theme.gap
                              top: versionText.bottom; topMargin: 3 }
                    visible: text !== ""; height: visible ? implicitHeight : 0
                    text: row.notes ? (row.sameAsks ? "" : row.modelData.asks + " · ") + "Licence: " + row.notes
                                    : row.sameAsks ? "" : row.modelData.asks
                    wrapMode: Text.WordWrap
                    color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
                }
            }
        }
        EdgeFade { flick: list; anchors.fill: list; color: Theme.sunken }
        VScrollBar { flick: list; anchors.rightMargin: 0 }
    }
}
