import QtQuick

// The stroke being drawn (screen2d/wet.py), in world px (one world px is `zoom` screen px), moved by dx, dy (a seamless
// painting's repeat). Two boxes: its settled part and its tip. When the stroke works on a layer, each box shows, in
// order, the world under the stroke, the ink, then the layers above the layer alone (painter.wet.layered:
// screen2d/wet_layers.py): the stroke lies in its layer's place, under the layers above, as it will land. Each box is
// whole on its own (`under` is opaque), so the tip over the settled part counts nothing twice.
Item {
    id: wi
    property real zoom: 1
    property real dx: 0
    property real dy: 0
    readonly property var w: painter.wet
    readonly property var under: w.layered.under || null
    readonly property var above: w.layered.above || null

    component Lay: Image {          // a world picture (under / above) seen through its box
        required property var pic
        required property string part
        required property var box
        visible: pic !== null
        x: ((pic ? pic.x : 0) - (box.x || 0)) * wi.zoom; y: ((pic ? pic.y : 0) - (box.y || 0)) * wi.zoom
        width: (pic ? pic.w : 0) * wi.zoom; height: (pic ? pic.h : 0) * wi.zoom
        source: pic ? "image://wet/" + part + "-" + pic.serial : ""
        cache: false; smooth: true; asynchronous: false
    }
    component Box: Item {
        id: bx
        property var box: ({})
        property string src: ""
        clip: wi.under !== null || wi.above !== null
        x: ((box.x || 0) + wi.dx) * wi.zoom; y: ((box.y || 0) + wi.dy) * wi.zoom
        width: (box.w || 0) * wi.zoom; height: (box.h || 0) * wi.zoom
        Lay { pic: wi.under; part: "under"; box: bx.box }
        Image { anchors.fill: parent; source: bx.src; cache: false; smooth: true; asynchronous: false }
        Lay { pic: wi.above; part: "above"; box: bx.box }
    }
    Box {   // its settled part
        visible: wi.w.drySerial > 0
        box: wi.w.dryBox
        src: wi.w.drySerial > 0 ? "image://wet/dry-" + wi.w.drySerial : ""
    }
    Box {   // its tip: the newest points
        visible: wi.w.serial > 0
        box: wi.w.box
        src: wi.w.serial > 0 ? "image://wet/tip-" + wi.w.serial : ""
    }
}
