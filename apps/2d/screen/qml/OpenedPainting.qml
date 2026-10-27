import QtQuick
import RostrumKit

// A painting opened on its own (screen2d/painting_open.py, design 2d-painted-fill § 3.4, mock-4), in world px: the
// painting at (0, 0), its own px being world px, outlined, its size above it. A seamless painting shows its repeats all
// round, a little darker, as many as the view shows; the stroke being drawn shows in the painting and the eight round it
// (a stroke leaving an edge comes back on the opposite side, as it will land; the farther ones show it once it lands). One that isn't seamless shows alone, its wet ink inside it.
// The picture is the painting kit's own PNG (the file every use and the export read).
Item {
    id: op
    property real zoom: 1
    property rect visibleWorld: Qt.rect(0, 0, 0, 0)       // the world px the well shows (Stage.inWell)
    readonly property var info: backend.opened.info
    readonly property real pw: info.w || 1
    readonly property real ph: info.h || 1
    readonly property bool seamless: info.seamless === true
    readonly property var wet: painter.wet
    readonly property int most: 12                         // repeats each way at most (a tiny painting zoomed out)
    readonly property int i0: seamless ? Math.max(-most, Math.floor(visibleWorld.x / pw)) : 0
    readonly property int i1: seamless ? Math.min(most, Math.ceil((visibleWorld.x + visibleWorld.width) / pw)) : 1
    readonly property int j0: seamless ? Math.max(-most, Math.floor(visibleWorld.y / ph)) : 0
    readonly property int j1: seamless ? Math.min(most, Math.ceil((visibleWorld.y + visibleWorld.height) / ph)) : 1

    component Wet: WetInk { zoom: op.zoom }     // the wet ink moved by one repeat (dx, dy world px)

    Image {         // the painting, and with Seamless its repeats: ONE tiled picture in the painting's own px, scaled
                    // by the zoom (an Image per repeat made up to 625 of them on opening and on every pan: ~60 ms)
        visible: op.visible
        x: op.i0 * op.pw * op.zoom; y: op.j0 * op.ph * op.zoom
        width: (op.i1 - op.i0) * op.pw; height: (op.j1 - op.j0) * op.ph
        transformOrigin: Item.TopLeft; scale: op.zoom
        fillMode: Image.Tile; horizontalAlignment: Image.AlignLeft; verticalAlignment: Image.AlignTop
        source: backend.opened.picture; smooth: op.zoom < 2; mipmap: op.zoom < 1
    }
    Repeater {      // the stroke being drawn, in the painting and the eight repeats round it
        model: op.seamless ? 9 : 0
        delegate: Wet { required property int index
                        dx: (index % 3 - 1) * op.pw; dy: (Math.floor(index / 3) - 1) * op.ph }
    }
    Item {          // not seamless: the stroke shows inside the painting only (paint outside it is not kept)
        visible: !op.seamless
        width: op.pw * op.zoom; height: op.ph * op.zoom; clip: true
        Wet { }
    }
    Item {          // the repeats a little darker: four bands round the painting
        visible: op.seamless
        readonly property real x0: op.i0 * op.pw * op.zoom
        readonly property real y0: op.j0 * op.ph * op.zoom
        readonly property real x1: op.i1 * op.pw * op.zoom
        readonly property real y1: op.j1 * op.ph * op.zoom
        readonly property color shade: Qt.rgba(0, 0, 0, 0.45)
        Rectangle { x: parent.x0; y: parent.y0; width: parent.x1 - parent.x0; height: -parent.y0; color: parent.shade }
        Rectangle { x: parent.x0; y: op.ph * op.zoom; width: parent.x1 - parent.x0; height: parent.y1 - op.ph * op.zoom; color: parent.shade }
        Rectangle { x: parent.x0; y: 0; width: -parent.x0; height: op.ph * op.zoom; color: parent.shade }
        Rectangle { x: op.pw * op.zoom; y: 0; width: parent.x1 - op.pw * op.zoom; height: op.ph * op.zoom; color: parent.shade }
    }
    Rectangle {     // its edge
        x: -1; y: -1; width: op.pw * op.zoom + 2; height: op.ph * op.zoom + 2
        color: "transparent"; border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.55)
    }
    Text {          // its size, just above it
        objectName: "openedSize"
        x: 0; y: -height - Theme.grid
        text: op.pw + " × " + op.ph; color: Qt.rgba(1, 1, 1, 0.55)
        font.family: uiFont; font.pixelSize: Theme.label; font.features: { "tnum": 1 }
    }
}
