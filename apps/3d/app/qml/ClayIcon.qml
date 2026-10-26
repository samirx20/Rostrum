import QtQuick
import QtQuick.Shapes
import RostrumKit

// A Clay tile's picture (3d-visual DESIGN § "Brushes you can tell apart"): a cut through the clay in grey, and what the
// tool does to it in `ink` (white, blue when chosen). Filled shapes, not thin lines, so they read apart at a glance.
// Drawn on a 40 × 30 box: lump (a ball on the ground), add (a round bump), carve (a wide groove), smooth (a bar planing
// it flat), pull (a peak drawn up and over to one side), flatten (a mound with its top cut flat), crease (a narrow blade
// pressed into a slit), mask (a striped band of tape lying on the surface: the part kept as it is). Each a different
// outline, so the seven read apart at a glance and at 0.8 scale.
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
        smooth: "M0 18H40V30H0Z",
        pull: "M0 22H40V30H0Z",
        flatten: "M0 24H40V30H0Z",
        crease: "M0 16H16L20 28L24 16H40V30H0Z",
        mask: "M0 20H40V30H0Z"
    })
    readonly property var mark: ({
        lump: "M11 14a9 9 0 1 0 18 0a9 9 0 1 0 -18 0Z",
        add: "M5 20C11 20 13 7 20 7S29 20 35 20Z",
        carve: "M9 9.5H12.2L20 19.2L27.8 9.5H31L20 23Z",
        smooth: "M5 11.5Q5 10 6.5 10H33.5Q35 10 35 11.5V13.5Q35 15 33.5 15H6.5Q5 15 5 13.5Z",
        pull: "M6 22C13 22 17 19 22 12C25 8 28 5 33 4C34.2 3.8 34.8 5 34 6C30.5 10 28.5 14 28 22Z",
        flatten: "M4 24L11.5 12.5H28.5L36 24Z",
        crease: "M17 5H23L20 25Z",
        mask: "M5 13H35V20H5Z M9 20L13 13H16.5L12.5 20Z M17.5 20L21.5 13H25L21 20Z M26 20L30 13H33.5L29.5 20Z"
    })
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath { strokeWidth: -1; fillColor: icon.clay; PathSvg { path: icon.base[icon.name] || "" } }
        ShapePath { strokeWidth: -1; fillColor: icon.ink; fillRule: ShapePath.OddEvenFill   // mask's stripes are holes
                    PathSvg { path: icon.mark[icon.name] || "" } }
    }
}
