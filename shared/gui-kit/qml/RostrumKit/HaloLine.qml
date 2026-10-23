import QtQuick
import "."

// An outline that shows on any colour, the accent itself included: the accent line with a 1 px dark halo on each
// side (as Figma and After Effects draw selections). Use for every selection box, handle and hover outline on the
// canvas, filling the item it outlines: HaloLine { anchors.fill: parent; anchors.margins: -1 }.
Item {
    id: h
    property color color: Theme.accent
    property real lineWidth: 1
    property real fillOpacity: 0                   // a tint inside the line (the rubber band)
    property color tint: Qt.rgba(color.r, color.g, color.b, fillOpacity)
    property real radius: 0
    property color halo: Qt.rgba(0, 0, 0, 0.6)
    enabled: false                                 // only a sign: never takes a click
    Rectangle {    // outer halo
        anchors.fill: parent; anchors.margins: -h.lineWidth; radius: h.radius > 0 ? h.radius + h.lineWidth : 0
        color: "transparent"; border.width: 1; border.color: h.halo
    }
    Rectangle {    // the line
        anchors.fill: parent; radius: h.radius
        color: h.tint; border.width: h.lineWidth; border.color: h.color
    }
    Rectangle {    // inner halo
        anchors.fill: parent; anchors.margins: h.lineWidth; radius: h.radius > 0 ? Math.max(0, h.radius - h.lineWidth) : 0
        color: "transparent"; border.width: 1; border.color: h.halo
    }
}
