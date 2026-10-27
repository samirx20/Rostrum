import QtQuick
import RostrumKit

// Files dragged from Explorer onto the viewport (importing.py): while one 3D can bring in (glTF, GLB, OBJ, FBX,
// Alembic, USD) hovers, a small ring follows the pointer where it will land; dropped, it lands on the surface there
// (picked like a click), selected, the tool Select again. Only file drags: a material ball's drag (keys
// "rostrum-material") passes to the viewport's own DropArea. hoverAt(x, y) shows the ring there (the layout check).
DropArea {
    id: drop
    objectName: "importDrop"
    keys: ["text/uri-list"]
    property real dpr: Screen.devicePixelRatio
    property point shownAt: Qt.point(-1, -1)            // the scripted hover (no real drag)
    readonly property bool hovering: containsDrag || shownAt.x >= 0
    function usable(urls) {
        const exts = backend.importer.extensions
        return urls.some(u => exts.some(e => u.toString().toLowerCase().endsWith(e)))
    }
    function hoverAt(x, y) { shownAt = Qt.point(x, y) }
    onEntered: (d) => { if (!d.hasUrls || !usable(d.urls)) d.accepted = false }
    onDropped: (d) => {
        backend.importer.dropAt(d.urls, d.x * dpr, d.y * dpr)
        d.accept(Qt.CopyAction)
    }

    Rectangle {     // where it lands: a ring with a dot, centred on the pointer
        objectName: "importDropSpot"
        visible: drop.hovering
        readonly property point at: drop.containsDrag ? Qt.point(drop.drag.x, drop.drag.y) : drop.shownAt
        width: 22; height: 22; radius: 11
        x: at.x - width / 2; y: at.y - height / 2
        color: "transparent"; border.width: 2; border.color: Theme.accent
        Rectangle { anchors.centerIn: parent; width: 4; height: 4; radius: 2; color: Theme.accent }
    }
}
