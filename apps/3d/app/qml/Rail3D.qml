import QtQuick
import QtQuick.Dialogs
import RostrumKit

// 3D's tool rail (SPEC §2): the kit's ToolRail filled from today's add operations (backend.adder.rail, adding.py).
// Select, then Shapes (R), Type & logo (T: 3D text, Logo from SVG, From a 2D drawing; SPEC §4.4), Lights (L), Camera (C).
// Logo from SVG asks for the file first, From a 2D drawing for the 2D item and its path layer (one list, two levels);
// then, like a shape, the next click in the viewport places it. A shape waits for a click in the viewport and lands on the surface
// there (SPEC §4.1); a light or camera is added at once; both through the operations agents use, the new thing
// selected, the tool Select again. Paint (B) shows while one mesh is selected (paint_mode_qt.py) and stays on while
// painting. The groups that aren't built yet (Simulate, Import) are absent until they work (rule of individuality).
ToolRail {
    id: rail
    current: paintMode.on ? "paint" : "select"
    iconKinds: ({ shape3d: icon3d })
    Component { id: icon3d; Icon3D { } }
    function entries(list) { return list.map(e => ({ name: e.name, icon: e.icon, kind: e.icon === "camera" ? "" : "shape3d", act: e.value })) }
    groups: [
        { id: "select", items: [{ name: "Select", icon: "select", tool: "select", help: "Click a thing in the viewport or the scene list." }] },
        { id: "shapes", name: "Shapes", items: rail.entries(backend.adder.rail.shapes) },
        { id: "type", name: "Type & logo", items: rail.entries(backend.adder.rail.type) },
        { sep: true },
        { id: "lights", name: "Lights", items: rail.entries(backend.adder.rail.lights) },
        { id: "camera", name: "Camera", items: rail.entries(backend.adder.rail.camera) }
    ].concat(paintMode.can || paintMode.on
             ? [{ sep: true }, { id: "paint", items: [{ name: "Paint", icon: "brush", tool: "paint", job: "paint_tool",
                                                       help: "Paint on the selected mesh: colour, roughness, height, metal or glow." }] }]
             : [])
    // a shape waits for a click in the viewport (it lands on the surface there); lights and cameras are added at once
    onPicked: (e) => {
        if (e.tool === "paint" || (e.tool === "select" && paintMode.on)) return paintMode.toggle()
        if (e.act === "mesh:svg") svgDialog.open()
        else if (e.act === "mesh:path2d") rail.openDrawings()
        else if (e.act) (e.act.startsWith("mesh:") ? backend.adder.arm(e.act) : backend.adder.add(e.act))
    }

    FileDialog {    // Logo from SVG: the file, then a click places it
        id: svgDialog
        title: "Logo from SVG"
        nameFilters: ["SVG drawings (*.svg)"]
        onAccepted: backend.adder.armWith("mesh:svg", { svgFile: decodeURIComponent(selectedFile.toString().replace(/^file:\/\/(\/(?=[A-Za-z]:))?/, "")) })
    }
    // From a 2D drawing: the project's 2D items, then the picked one's path layers (one list, two levels)
    function openDrawings() {
        drawings.items = backend.adder.drawings()
        drawings.doc2d = ""
        drawings.entries = drawings.items.length
            ? drawings.items.map(d => ({ value: d.doc2d, label: d.name }))
            : [{ value: "", label: "No 2D drawings in this project yet" }]
        drawings.open()
    }
    Menu {
        id: drawings
        objectName: "drawings2d"
        property var items: []
        property string doc2d: ""
        x: rail.width + Theme.grid; y: 3 * (Theme.button + 8)
        width: 240
        onPicked: (v) => {
            if (!v) return
            if (!doc2d) {
                const d = items.find(i => i.doc2d === v)
                doc2d = v
                entries = d.layers.map(l => ({ value: l.id, label: d.name + "  ›  " + l.name }))
                return Qt.callLater(open)
            }
            backend.adder.armWith("mesh:path2d", { doc2d: doc2d, layer: v })
        }
    }
}
