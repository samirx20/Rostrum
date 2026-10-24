import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Dialogs
import RostrumKit

// 3D's tool rail (SPEC §2): the kit's ToolRail filled from today's add operations (backend.adder.rail, adding.py).
// Select, then Shapes (R), Type & logo (T: 3D text, Logo from SVG, From a 2D drawing; SPEC §4.4), Lights (L), Camera (C);
// on the Animate page Select, Poses (P), Onion skin (O), Bones (while a mesh is selected: bones_qt.py), Lights, Camera.
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
    readonly property var selectGroup: ({ id: "select", items: [{ name: "Select", icon: "select", tool: "select", help: "Click a thing in the viewport or the scene list." }] })
    // the Animate page (SPEC §2): Select, Poses (P), Onion skin (O), Bones (a mesh selected), Lights, Camera; Simulate joins when built
    groups: backend.page === "animate" ? [
        rail.selectGroup,
        { id: "poses", name: "Poses", panel: true, items: [{ name: "Poses", icon: "pose", kind: "shape3d",
          help: "Save the selected items' pose; click a saved one to key it at the playhead." }] },
        { id: "onion", name: "Onion skin", panel: true, items: [{ name: "Onion skin", icon: "onion", kind: "shape3d",
          help: "Ghosts of the selected item before (red) and after (green), to time its arc by eye." }] },
        { id: "bones", name: "Bones", items: viewport.bones.meshSelected ? [{ name: "Bones", icon: "bone", kind: "shape3d", act: "bones",
          help: "Click points along the selected mesh, root first, then Enter: a bone chain it bends with." }] : [] },   // only with a mesh selected
        { sep: true },
        { id: "lights", name: "Lights", items: rail.entries(backend.adder.rail.lights) },
        { id: "camera", name: "Camera", items: rail.entries(backend.adder.rail.camera) }
    ] : [
        rail.selectGroup,
        { id: "shapes", name: "Shapes", items: rail.entries(backend.adder.rail.shapes) },
        { id: "type", name: "Type & logo", items: rail.entries(backend.adder.rail.type) },
        { sep: true },
        { id: "lights", name: "Lights", items: rail.entries(backend.adder.rail.lights) },
        { id: "camera", name: "Camera", items: rail.entries(backend.adder.rail.camera) }
    ].concat(paintMode.can || paintMode.on       // Paint (B): the Build page, one mesh selected
             ? [{ sep: true }, { id: "paint", items: [{ name: "Paint", icon: "brush", tool: "paint", job: "paint_tool",
                                                       help: "Paint on the selected mesh: colour, roughness, height, metal or glow." }] }]
             : [])
    // Poses and Onion skin each open and close on their own (PosesPanel.qml, OnionPanel.qml): their button toggles its panel,
    // Esc closes the one with the keys, and clicking elsewhere leaves them open (you work in the viewport with the ghosts on).
    // `panelOpen` stays false so the kit's rail never closes one for the other's button.
    function panelOf(id) { return id === "poses" ? posesPanel : id === "onion" ? onionPanel : null }
    onPanelRequested: (g) => rail.openPanel(g.id)
    function openPanel(id) {        // the scripted `panel <id>` step, P, and the buttons: open it, or close it when it is open
        const pop = panelOf(id)
        if (!pop) return
        if (pop.visible) return pop.close()
        const b = rail.buttonOf(id)       // beside the rail, top edges with the button (never over the rail)
        const x = rail.mapToItem(null, rail.width + Theme.gap, 0).x
        const beside = pop === onionPanel && posesPanel.visible ? posesPanel.width + Theme.gap : 0     // both open: side by side
        pop.openAtPoint(x + beside, b ? b.mapToItem(null, 0, 0).y : rail.mapToItem(null, 0, 0).y)
    }
    PosesPanel { id: posesPanel; closePolicy: QQC.Popup.NoAutoClose }
    OnionPanel { id: onionPanel; closePolicy: QQC.Popup.NoAutoClose }
    Connections {       // they belong to the Animate page: leaving it closes them
        target: backend
        function onPageChanged() { if (backend.page !== "animate") { posesPanel.close(); onionPanel.close() } }
    }
    // a shape waits for a click in the viewport (it lands on the surface there); lights and cameras are added at once
    onPicked: (e) => {
        if (e.tool === "paint" || (e.tool === "select" && paintMode.on)) return paintMode.toggle()
        if (e.act === "bones") viewport.bones.start()
        else if (e.act === "mesh:svg") svgDialog.open()
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
