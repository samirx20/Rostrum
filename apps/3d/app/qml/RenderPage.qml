import QtQuick
import RostrumKit

// The Render page's bottom panel (SPEC §11.3; screen3d/queue.py). Left: the shots, each with its tick (what "Queue
// ticked" renders), its length and when it was last rendered; a click shows the shot, a right-click offers Send to 2D
// (per 2D scene of the project; absent with none) and Open its folder (when it has a render). Send to Editor waits for
// the Editor (absent). Right: the queue, in the order
// it runs: the running render (progress, frames n of m, time left, ✕), the waiting ones (↑ ↓ to reorder, ✕), then the
// ended ones (done: time taken, its folder, a click shows its last frame over the viewport; failed or cancelled: red,
// the reason). One render runs at a time.
Rectangle {
    id: page
    readonly property var q: backend.renderQueue
    readonly property int waiting: q.rows.filter(r => r.status === "queued").length
    readonly property bool canSend: typeof sender !== "undefined" && sender !== null
    color: Theme.panel; radius: Theme.radiusPanel

    function sendShot(shotId, scene) {     // the one call site of Send to 2D (send_qt.py; "" back = sent, else it said why)
        sender.send(shotId, "2d", scene)
    }
    function openShotMenu(row, anchor) {   // Send to 2D (one entry per 2D scene when there are several), Open its folder
        const scenes = page.canSend ? sender.scenes() : []
        shotMenu.shotId = row.id; shotMenu.folder = row.folder
        shotMenu.entries = scenes.map(sc => ({ value: "2d:" + sc.value, label: scenes.length > 1 ? "Send to 2D · " + sc.label : "Send to 2D" }))
                           .concat(row.folder ? [{ value: "folder", label: "Open its folder" }] : [])
        if (shotMenu.entries.length) shotMenu.openFrom(anchor, "left")
    }

    component Caps: Text { color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold
                           font.capitalization: Font.AllUppercase; font.letterSpacing: Theme.capsSpacing }
    component Small: Text { color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; elide: Text.ElideRight }

    Menu {
        id: shotMenu
        property string shotId: ""
        property string folder: ""
        width: 220
        onPicked: (v) => v === "folder" ? page.q.openFolder(folder) : page.sendShot(shotId, v.slice(3))
    }

    Item {   // the shots
        id: shotsPane
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom; margins: Theme.pad }
        width: Math.max(260, Math.round(page.width * 0.36))
        Caps { id: shotsHead; text: "Shots"; height: Theme.button; verticalAlignment: Text.AlignVCenter }
        Button { anchors { right: parent.right; verticalCenter: shotsHead.verticalCenter }
                 visible: page.q.tickedCount > 0; text: "Queue ticked (" + page.q.tickedCount + ")"
                 onClicked: page.q.addTicked() }
        ListView {
            anchors { left: parent.left; right: parent.right; top: shotsHead.bottom; bottom: parent.bottom; topMargin: Theme.grid }
            clip: true; boundsBehavior: Flickable.StopAtBounds
            model: page.q.shots
            delegate: Rectangle {
                id: shotRow
                required property var modelData
                width: ListView.view.width; height: Theme.row
                radius: Theme.radiusCtl
                color: modelData.shown ? Theme.active : rowArea.containsMouse ? Theme.hover : "transparent"
                MouseArea { id: rowArea; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
                            onClicked: (m) => m.button === Qt.RightButton ? page.openShotMenu(shotRow.modelData, shotRow) : backend.showShot(shotRow.modelData.id) }
                Rectangle {   // the tick: this shot is in "Queue ticked"
                    id: tick
                    x: Theme.grid; anchors.verticalCenter: parent.verticalCenter
                    width: 16; height: 16; radius: 3
                    color: shotRow.modelData.ticked ? Theme.accent : "transparent"
                    border.color: shotRow.modelData.ticked ? Theme.accent : Theme.lineHover
                    Text { anchors.centerIn: parent; visible: shotRow.modelData.ticked; text: "✓"; color: "white"
                           font.family: uiFont; font.pixelSize: Theme.label }
                    MouseArea { anchors.fill: parent; anchors.margins: -4; cursorShape: Qt.PointingHandCursor
                                onClicked: page.q.toggleTick(shotRow.modelData.id) }
                }
                Text { id: shotName; anchors { left: tick.right; leftMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                       width: Math.min(implicitWidth, parent.width * 0.45); elide: Text.ElideRight
                       text: shotRow.modelData.label; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
                       font.weight: shotRow.modelData.shown ? Font.DemiBold : Font.Normal }
                Small { anchors { left: shotName.right; leftMargin: Theme.gap; right: parent.right; rightMargin: Theme.gap
                                  verticalCenter: parent.verticalCenter }
                        horizontalAlignment: Text.AlignRight
                        text: shotRow.modelData.length + (shotRow.modelData.last ? "  ·  rendered " + shotRow.modelData.last : "") }
            }
        }
    }

    Rectangle { id: split; x: shotsPane.x + shotsPane.width + Theme.pad; width: 1; color: Theme.border
                anchors { top: parent.top; bottom: parent.bottom; topMargin: Theme.pad; bottomMargin: Theme.pad } }

    Item {   // the queue
        anchors { left: split.right; right: parent.right; top: parent.top; bottom: parent.bottom; margins: Theme.pad }
        Caps { id: queueHead; text: "Queue"; height: Theme.button; verticalAlignment: Text.AlignVCenter }
        EmptyHint {
            visible: page.q.rows.length === 0
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
            text: "Renders wait here and run one at a time: Render or Add to queue a shot."
        }
        ListView {
            id: queueList
            anchors { left: parent.left; right: parent.right; top: queueHead.bottom; bottom: parent.bottom; topMargin: Theme.grid }
            clip: true; boundsBehavior: Flickable.StopAtBounds; spacing: 2
            model: page.q.rows
            delegate: QueueRow { width: queueList.width; queue: page.q; waiting: page.waiting }
        }
    }
}
