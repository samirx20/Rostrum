import QtQuick
import RostrumKit

// The bottom panel (SPEC §1): the scene list on the left (240 px), the keys on the same rows at the right, so you
// never read across two lists. Top row: play and the playhead's time | the ruler (the shot's frames, the shared
// markers). A row: fold arrow, kind icon, name, its material dim (click the material: edit it). Click a row selects
// the item; the selected item opens a row per animated field. A diamond: click selects the key, drag moves it
// (key.set in whole frames, one undo step). The ruler and the tracks scrub the playhead.
Rectangle {
    id: panel
    readonly property int listWidth: 240
    readonly property var shot: backend.shotInfo
    color: Theme.panel; radius: Theme.radiusPanel

    Row {   // play, the time
        x: Theme.gap; height: 30; spacing: Theme.gap
        PlayButton { anchors.verticalCenter: parent.verticalCenter; playing: backend.playing; onClicked: backend.togglePlay()
                     implicitHeight: 24; implicitWidth: 24 }
        Text { anchors.verticalCenter: parent.verticalCenter; font.family: uiFont; font.pixelSize: Theme.body
               font.features: { "tnum": 1 }; color: Theme.fg; textFormat: Text.StyledText
               text: backend.time.toFixed(2) + " s <font color='" + Theme.fg3 + "'>/ "
                     + ((panel.shot.end + 1) / panel.shot.fps).toFixed(2) + " s</font>" }
    }
    Button {
        visible: backend.markerEdit.available; text: "Add marker"; kind: "ghost"; implicitHeight: 24
        anchors { right: ruler.left; rightMargin: Theme.gap + 8 }
        y: 3
        onClicked: backend.markerEdit.add(backend.time)
    }
    Ruler {
        id: ruler
        unit: "frames"
        x: panel.listWidth + 8; width: parent.width - x - Theme.gap - 8; height: 30   // 8: room for a key at the ends
        first: panel.shot.start; last: panel.shot.end; value: backend.frame
        fps: panel.shot.fps
        markers: backend.markers
        editMarkers: backend.markerEdit.available
        onMarkerMoved: (id, at) => backend.markerEdit.move(id, at)
        onMarkerRenamed: (id, name) => backend.markerEdit.rename(id, name)
        onMarkerRemoved: (id) => backend.markerEdit.remove(id)
        onScrubbed: (f) => backend.setFrame(Math.round(f))
    }

    ListView {      // the scene list (labels)
        id: list
        x: Theme.grid; y: ruler.height + Theme.grid; width: panel.listWidth - Theme.grid; height: parent.height - y - Theme.grid
        model: backend.sceneRows
        spacing: 2; clip: true; boundsBehavior: Flickable.StopAtBounds
        delegate: SceneRow { width: ListView.view.width }
    }
    KeyRows {       // the keys, on the same rows (scrolls with the list; its own labels are 0 wide: the list's are shown)
        x: 0; y: list.y; width: parent.width - Theme.grid; height: list.height
        contentY: list.contentY; interactive: false
        model: backend.sceneRows
        ruler: ruler; labelWidth: 0
        selectedOwner: backend.selectedOwner; selectedKey: backend.selected
        keyValue: (k) => k.t * panel.shot.fps
        dragClamp: (f) => Math.min(Math.max(Math.round(f), panel.shot.start), panel.shot.end + 1)
        onRowSelected: (owner) => backend.select(owner)
        onTrackScrubbed: (f) => backend.setFrame(Math.round(f))
        keyBegin: (id) => backend.beginKeyDrag(id)
        onKeyDragged: (f) => backend.keyDragTo(f, 6 / ruler.perUnit)   // lands on a marker within 6 px
        onKeyReleased: backend.endDrag()
    }
    Rectangle {  // the playhead line, across every row
        x: ruler.x + Math.round(ruler.xOf(backend.frame)); y: ruler.height
        width: 1; height: parent.height - y - Theme.grid; color: Theme.accent; opacity: 0.8
    }

    component SceneRow: Rectangle {
        id: row
        required property var modelData
        readonly property bool field: modelData.row === "field"
        readonly property bool selected: !field && (modelData.id === backend.selected || backend.selectedRows.length > 1 && backend.selectedRows.indexOf(modelData.id) >= 0)
        readonly property bool inSelected: !selected && modelData.owner === backend.selectedOwner && !field
        readonly property int indent: Theme.gap + modelData.depth * 16
        height: field ? Theme.rowDense - 2 : Theme.rowDense; radius: Theme.radiusCtl
        color: selected ? Theme.accentSoft : hover.containsMouse || inSelected ? Theme.hover : "transparent"
        MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; onClicked: (m) => {   // Ctrl+click adds or takes out; Shift+click picks the run from the primary
            if (row.field) backend.select(row.modelData.owner)
            else if (m.modifiers & Qt.ControlModifier) backend.toggleInSelection(row.modelData.id)
            else if (m.modifiers & Qt.ShiftModifier) backend.selectRange(row.modelData.id)
            else backend.select(row.modelData.owner) } }
        DropArea {  // a material dragged from the picker or the Materials list: this item gets it (the row lights while it hovers)
            anchors.fill: parent; keys: ["rostrum-material"]; enabled: !row.field
            onDropped: (d) => { backend.mats.dropOn(d.source.materialId, row.modelData.id); d.accept() }
            Rectangle { anchors.fill: parent; radius: Theme.radiusCtl; color: "transparent"; visible: parent.containsDrag
                        border.width: 1; border.color: Theme.accent }
        }
        Item {  // the fold arrow (absent when there is nothing to fold)
            x: row.indent - 2; width: 14; height: parent.height
            visible: row.modelData.fold !== ""
            Chevron { anchors.centerIn: parent; rotation: row.modelData.fold === "open" ? 0 : -90
                      color: foldArea.containsMouse ? Theme.fg : Theme.fg3 }
            MouseArea { id: foldArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: backend.toggleFold(row.modelData.id) }
        }
        KindIcon {
            id: icon
            visible: !row.field
            x: row.indent + 16; anchors.verticalCenter: parent.verticalCenter
            kind: row.modelData.kind
            ink: row.selected ? Theme.accentHover : row.modelData.row === "part" ? Theme.fg3 : Theme.fg2
        }
        Text {
            id: name
            anchors { left: icon.left; leftMargin: row.field ? 0 : icon.width + Theme.gap; verticalCenter: parent.verticalCenter
                      right: matName.visible ? matName.left : parent.right; rightMargin: Theme.gap }
            text: (row.modelData.cutter ? "− " : "") + row.modelData.label; elide: Text.ElideRight; font.family: uiFont
            font.pixelSize: row.field ? Theme.label + 1 : Theme.body
            color: row.field || row.modelData.row === "part" && !row.selected ? Theme.fg2 : Theme.fg
            HoverHandler { id: nameHover }
            HoverTip { text: name.truncated ? name.text : ""; hovered: nameHover.hovered }
        }
        Text {  // its material: click to edit it (only while the name has its whole room: the name comes first)
            id: matName
            readonly property real room: row.width - name.x - Theme.gap * 2
            visible: row.modelData.material !== "" && name.implicitWidth + Theme.gap + implicitWidth <= room
            anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
            text: row.modelData.material; font.family: uiFont; font.pixelSize: Theme.label
            color: matArea.containsMouse ? Theme.fg : Theme.fg3
            MouseArea { id: matArea; anchors.fill: parent; anchors.margins: -4; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { const m = backend.materials.find(x => x.label === row.modelData.material); if (m) backend.select(m.value) } }
        }
    }
}
