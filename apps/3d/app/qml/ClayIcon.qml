import QtQuick
import QtQuick.Shapes
import RostrumKit

// A Clay tile's picture (3d-visual DESIGN § "Brushes you can tell apart"): a cut through the clay in grey, and what the
// tool does to it in `ink` (white, blue when chosen). Filled shapes, not thin lines, so they read apart at a glance.
// Drawn on a 40 × 30 box: lump (a ball on the ground), add (a bump), carve (a groove), smooth (a bar planing it flat).
Item {
    id: icon
    property string name: ""
    property color ink: Theme.fg
    property color clay: Theme.lineHover
    width: 40; height: 30
    readonly property var base: ({
        lump: "M0 24H40V30H0Z",
        add: "M0 20H40V30H0Z",
        carve: "M0 12H11L20 23L29 12H40V30H0Z",
        smooth: "M0 18H40V30H0Z"
    })
    readonly property var mark: ({
        lump: "M11 14a9 9 0 1 0 18 0a9 9 0 1 0 -18 0Z",
        add: "M5 20C11 20 13 7 20 7S29 20 35 20Z",
        carve: "M9 9.5H12.2L20 19.2L27.8 9.5H31L20 23Z",
        smooth: "M5 11.5Q5 10 6.5 10H33.5Q35 10 35 11.5V13.5Q35 15 33.5 15H6.5Q5 15 5 13.5Z"
    })
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath { strokeWidth: -1; fillColor: icon.clay; PathSvg { path: icon.base[icon.name] || "" } }
        ShapePath { strokeWidth: -1; fillColor: icon.ink; PathSvg { path: icon.mark[icon.name] || "" } }
    }
}
