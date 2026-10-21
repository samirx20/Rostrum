import QtQuick

// The rows under a Ruler: one per item that moves (all its keys on one line), a field row per animated field.
// Model rows: {row: "layer"|"field", id, owner, label, depth, fold: ""|"open"|"closed", keys: [{id, t}], ...}.
// A diamond sits at ruler.xOf(keyValue(key)); click selects, drag emits keyDragged(value in the ruler's unit).
// `trackExtras` is drawn in every track under the diamonds (its parent is the Loader; `parent.rowData` is the row).
// `dragClamp`, when set, maps the pointer value to the value shown while dragging (rows refresh on release).
ListView {
    id: rows
    property Item ruler
    property int labelWidth: 236
    property var selectedOwner: ""
    property string selectedKey: ""
    property bool foldable: false        // rows with a fold arrow (and a gap for it) in the label
    property var keyValue: (k) => k.t    // a key's place in the ruler's unit
    property var dragClamp: null
    property Component trackExtras
    signal rowSelected(string owner)
    signal folded(string id)
    signal keyPressed(string id)
    signal keyDragged(real value)
    signal keyReleased()
    signal trackScrubbed(real value)

    spacing: 2
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    delegate: Item {
        id: row
        required property var modelData
        readonly property bool isField: modelData.row === "field"
        readonly property bool selected: modelData.owner === rows.selectedOwner
        readonly property bool canFold: rows.foldable && (modelData.fold || "") !== ""
        readonly property int depth: rows.foldable ? modelData.depth || 0 : 0
        width: ListView.view.width; height: isField ? Theme.rowDense - 2 : Theme.rowDense

        Rectangle {  // the label
            width: rows.labelWidth; height: parent.height; radius: Theme.radiusCtl
            color: row.selected && !row.isField ? Theme.accentSoft : "transparent"
            Item {
                id: fold
                x: Theme.gap - 2 + row.depth * 16; width: 14; height: parent.height
                visible: row.canFold
                Chevron { anchors.centerIn: parent; rotation: row.modelData.fold === "open" ? 0 : -90
                          color: foldArea.containsMouse ? Theme.fg : Theme.fg3 }
            }
            Text {
                x: Theme.gap + (rows.foldable ? 16 + row.depth * 16 : (row.isField ? 16 : 0)); width: parent.width - x - Theme.gap
                anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight
                text: row.modelData.label; font.family: uiFont
                font.pixelSize: row.isField ? Theme.label + 1 : Theme.body
                color: row.isField ? Theme.fg2 : Theme.fg
            }
            MouseArea {
                id: foldArea; anchors.fill: parent; hoverEnabled: true
                onClicked: row.canFold && mouseX < fold.x + fold.width + 4
                           ? rows.folded(row.modelData.id) : rows.rowSelected(row.modelData.owner)
            }
        }
        Rectangle {  // the track
            id: track
            x: rows.ruler.x - 8; width: rows.ruler.width + 16; height: parent.height; radius: Theme.radiusCtl
            color: row.isField ? Qt.darker(Theme.panel, 1.15) : Theme.sunken
            MouseArea { anchors.fill: parent; onPressed: (m) => rows.trackScrubbed(rows.ruler.tOf(m.x - 8))
                        onPositionChanged: (m) => rows.trackScrubbed(rows.ruler.tOf(m.x - 8)) }
            Loader { anchors.fill: parent; property var rowData: row.modelData; sourceComponent: rows.trackExtras }
            Repeater {
                model: row.modelData.keys
                delegate: Item {
                    id: key
                    required property var modelData
                    readonly property bool on: modelData.id === rows.selectedKey
                    property bool dragging: false
                    property real dragV: 0         // while dragged: the value under the pointer
                    x: 8 + Math.round(rows.ruler.xOf(dragging ? dragV : rows.keyValue(modelData))) - width / 2
                    width: 16; height: track.height
                    KeyMark {
                        anchors.centerIn: parent; size: row.isField ? 8 : 7
                        color: key.on ? Theme.accent : keyArea.containsMouse ? Theme.fg
                             : row.isField ? Theme.fg2 : Theme.fg3
                    }
                    MouseArea {
                        id: keyArea; anchors.fill: parent; hoverEnabled: true; preventStealing: true
                        cursorShape: Qt.SizeHorCursor
                        onPressed: { if (rows.dragClamp) { key.dragV = rows.keyValue(key.modelData); key.dragging = true }
                                     rows.keyPressed(key.modelData.id) }
                        onPositionChanged: (m) => {
                            var v = rows.ruler.tOf(mapToItem(track, m.x, 0).x - 8)
                            if (rows.dragClamp) key.dragV = rows.dragClamp(v)
                            rows.keyDragged(v)
                        }
                        onReleased: { key.dragging = false; rows.keyReleased() }
                        onCanceled: { key.dragging = false; rows.keyReleased() }
                    }
                }
            }
        }
    }
}
