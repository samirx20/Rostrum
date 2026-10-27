import QtQuick
import QtQuick.Shapes
import RostrumKit

// The rail's 3D icons (the kit ToolRail's `iconKinds`: an Item with `name` and `ink`), 18 px line drawings from the
// mockups' set (docs/3d-design/mockups/icons3d.py): each shape, each light kind, the camera rig, the Materials ball.
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
        cone: "M9 2L3 13.5M9 2l6 11.5" + e(9, 13.5, 6, 2),
        torus: e(9, 9, 7, 4.6) + e(9, 8.4, 2.8, 1.3),
        capsule: "M5.5 6a3.5 3.5 0 0 1 7 0v6a3.5 3.5 0 0 1-7 0z" + e(9, 9, 3.5, 1.2),
        plane: "M2 12.5l4-6h10l-4 6z",
        disc: e(9, 9.5, 7, 3.6) + "M2 9.5v1.2c0 2 3.1 3.6 7 3.6s7-1.6 7-3.6V9.5",
        "light-rect": "M3 3h12v6H3zM5 12l-1 3M9 12v3.5M13 12l1 3",
        "light-disk": e(9, 6, 6, 4) + "M5 12l-1 3M9 12v3.5M13 12l1 3",
        "light-strip": "M7 2h4v14H7zM13.5 5v8M4.5 5v8",
        "light-sphere": e(9, 7.5, 5, 5) + "M7 14.5h4M7.5 16.5h3",
        "light-spot": "M7 2h4v3.5H7zM7 5.5L3.5 13M11 5.5l3.5 7.5" + e(9, 13.5, 5.5, 2),
        "light-distant": e(9, 9, 3.2, 3.2) + "M9 1.5v2M9 14.5v2M1.5 9h2M14.5 9h2M3.7 3.7l1.4 1.4M12.9 12.9l1.4 1.4M3.7 14.3l1.4-1.4M12.9 5.1l1.4-1.4",
        "light-dome": "M2 14a7 7 0 0 1 14 0zM5 14a4 4 0 0 1 8 0",
        clay: "M4.5 15.5c-2.6 0-3.3-3.4-1.2-5 .2-3.6 3.4-6 6.7-5.2 2.9-1.7 6.3.4 6.2 3.8 1.7 1.6 1.2 4.6-1 5.4-.6.6-1.3 1-2.2 1z"
              + "M7 9.5c.8-1.4 2.4-2 3.8-1.6",
        text: "M3.5 3h11M9 3v12M6.5 15h5",
        svg: "M3 15c2-8 4-12 6-12s4 4 6 12M5 15h8" + e(9, 3, 1.3, 1.3),
        path2d: "M2.5 13.5c3-1 2.5-8 6.5-8s3.5 6 6.5 7M2.5 13.5v-.01M15.5 12.5v-.01" + e(9, 5.5, 1.2, 1.2),
        rig: e(9, 11, 7, 3.5) + "M5 3h7v5.5H5z",
        pose: e(9, 3.2, 1.7, 1.7) + "M9 5v6M4 6.5l5 1.5 4.5-3M9 11l-3 5M9 11l3.5 4.5",    // a figure mid-move
        onion: e(5.5, 9, 3.5, 3.5) + e(9, 9, 3.5, 3.5) + e(12.5, 9, 3.5, 3.5),               // three steps of one shape
        bone: e(4, 14, 2, 2) + "M5.5 12.5L8 7.5 15 3 10.5 10z",                                  // a bone: head and diamond
        material: e(9, 9, 6.5, 6.5) + "M5.6 7.6a3.8 3.8 0 0 1 2.6-2.8"                              // a material ball and its shine
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
