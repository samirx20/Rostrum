import QtQuick
import QtQuick.Shapes
import RostrumKit

// The rail's 3D icons (the kit ToolRail's `iconKinds`: an Item with `name` and `ink`), 18 px line drawings from the
// mockups' set (docs/3d-design/mockups/icons3d.py): each shape, each light kind, the camera rig.
Item {
    id: icon
    property string name: ""
    property color ink: Theme.fg2
    width: 20; height: 20
    function e(cx, cy, rx, ry) { return `M${cx - rx} ${cy}a${rx} ${ry} 0 1 0 ${2 * rx} 0a${rx} ${ry} 0 1 0 ${-2 * rx} 0` }
    readonly property var paths: ({
        box: "M9 2l6.5 3.5v7L9 16l-6.5-3.5v-7zM2.5 5.5L9 9l6.5-3.5M9 9v7",
        sphere: e(9, 9, 6.5, 6.5) + e(9, 9, 6.5, 2.4),
        cylinder: e(9, 4.5, 5.5, 2) + "M3.5 4.5v9c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2v-9",
        torus: e(9, 9, 7, 4.6) + e(9, 8.4, 2.8, 1.3),
        plane: "M2 12.5l4-6h10l-4 6z",
        disc: e(9, 9.5, 7, 3.6) + "M2 9.5v1.2c0 2 3.1 3.6 7 3.6s7-1.6 7-3.6V9.5",
        "light-rect": "M3 3h12v6H3zM5 12l-1 3M9 12v3.5M13 12l1 3",
        "light-disk": e(9, 6, 6, 4) + "M5 12l-1 3M9 12v3.5M13 12l1 3",
        "light-strip": "M7 2h4v14H7zM13.5 5v8M4.5 5v8",
        "light-sphere": e(9, 7.5, 5, 5) + "M7 14.5h4M7.5 16.5h3",
        "light-distant": e(9, 9, 3.2, 3.2) + "M9 1.5v2M9 14.5v2M1.5 9h2M14.5 9h2M3.7 3.7l1.4 1.4M12.9 12.9l1.4 1.4M3.7 14.3l1.4-1.4M12.9 5.1l1.4-1.4",
        "light-dome": "M2 14a7 7 0 0 1 14 0zM5 14a4 4 0 0 1 8 0",
        rig: e(9, 11, 7, 3.5) + "M5 3h7v5.5H5z"
    })
    Shape {
        x: 1; y: 1
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: icon.ink; strokeWidth: 1.5; fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin; capStyle: ShapePath.RoundCap
            PathSvg { path: icon.paths[icon.name] || icon.paths.box }
        }
    }
}
