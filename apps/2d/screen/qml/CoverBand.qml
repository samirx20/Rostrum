import QtQuick
import RostrumKit

// The warning band (2d-camera SPEC §4.12, screen2d/cover_band.py): on the picked layer, a striped amber / black strip
// just inside each edge the frame sees past over the piece, with when it starts ("shows past the right edge from
// 3.2 s"). It lies on the layer's box as the canvas shows it (`box`: a bounds.boxes entry, world px; `fit`: screen px
// per world px), turned with the layer like its outline (Handles.qml). It never catches a click.
Item {
    id: band
    property var box: ({})
    property real fit: 1
    readonly property var edges: backend.coverBand.edges
    readonly property real bw: (box.w || 0) * fit
    readonly property real bh: (box.h || 0) * fit
    readonly property real thick: 10
    x: (box.x || 0) * fit; y: (box.y || 0) * fit; width: bw; height: bh

    transform: Rotation { origin.x: (band.box.ax || 0) * band.bw; origin.y: (band.box.ay || 0) * band.bh; angle: band.box.rot || 0 }

    Repeater {
        model: band.edges
        delegate: Item {
            id: edge
            required property var modelData
            readonly property string side: modelData.edge
            readonly property bool across: side === "top" || side === "bottom"
            x: side === "right" ? band.bw - band.thick : 0
            y: side === "bottom" ? band.bh - band.thick : 0
            width: across ? band.bw : band.thick
            height: across ? band.thick : band.bh
            Item {      // the stripes: dark bars at 45° over amber, cut to the strip
                anchors.fill: parent; clip: true; opacity: 0.85
                Rectangle { anchors.fill: parent; color: Theme.warn }
                Item {      // vertical bars on a square turned 45° about the strip's centre
                    id: bars
                    readonly property real side: edge.width + edge.height
                    width: side; height: side; x: (edge.width - side) / 2; y: (edge.height - side) / 2; rotation: 45
                    Row {
                        spacing: 6
                        Repeater {
                            model: Math.ceil(bars.side / 12)
                            delegate: Rectangle { width: 6; height: bars.side; color: "#111111" }
                        }
                    }
                }
            }
            Rectangle {     // when it starts, on the band's middle, inside the layer
                color: Theme.warn; radius: 3
                width: words.implicitWidth + 10; height: words.implicitHeight + 4
                x: edge.side === "left" ? band.thick + 4 : edge.side === "right" ? -width - 4 : (edge.width - width) / 2
                y: edge.side === "top" ? band.thick + 4 : edge.side === "bottom" ? -height - 4 : (edge.height - height) / 2
                Text { id: words; anchors.centerIn: parent; text: edge.modelData.words; color: "#111111"; font.pixelSize: Theme.label }
            }
        }
    }
}
