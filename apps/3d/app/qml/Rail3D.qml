import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Dialogs
import RostrumKit

// 3D's tool rail (SPEC §2): the kit's ToolRail filled from today's add operations (backend.adder.rail, adding.py).
// Select, then Clay (Q: Lump and the brushes; its choices live in its settings panel, ClayPanel.qml, so it has no flyout),
// Shapes (R), Type & logo (T: 3D text, Logo from SVG, From a 2D drawing; SPEC §4.4), Lights (L), Camera (C);
// on the Animate page Select, Poses (P), Onion skin (O), Bones (Shift+B, while a mesh is selected: bones_qt.py), Lights, Camera.
// Pose (Shift+P) on both pages while one clay is selected: drag its parts to pose it (pose_qt.py).
// Logo from SVG asks for the file first, From a 2D drawing for the 2D item and its path layer (one list, two levels);
// then, like a shape, the next click in the viewport places it. A shape waits for a click in the viewport and lands on the surface
// there (SPEC §4.1); a light or camera is added at once; both through the operations agents use, the new thing
// selected, the tool Select again. Paint (B) shows while one mesh or clay is selected (paint_mode_qt.py) and stays on while
// painting. Last on both pages, the Materials ball: the project's materials (MaterialsList) beside the rail, a library
// of things to put in the scene like the rest of the rail (header SPEC §3; also Ctrl+K). Import (Ctrl+I, Build page): a file
// per format, landing at once on the surface in the middle of the view, then Asset library (ImportFiles.qml, importing.py).
// Simulate isn't built yet: absent until it works (rule of individuality).
ToolRail {
    id: rail
    current: paintMode.on ? "paint" : viewport.clay.on ? "clay" : viewport.pose.on ? "pose" : "select"
    iconKinds: ({ shape3d: icon3d })
    Component { id: icon3d; Icon3D { } }
    // `job` on an entry or a group: the key map job whose key its hover shows (keys3d.py: V, P, O, B; R T L C open the
    // groups, but the kit's rail shows a group's key only through its entries, which would put "R" on every shape)
    function entries(list) { return list.map(e => ({ name: e.name, icon: e.icon, kind: e.icon === "camera" ? "" : "shape3d", act: e.value })) }
    readonly property var selectGroup: ({ id: "select", items: [{ name: "Select", icon: "select", tool: "select", job: "move_tool", help: "Click a thing in the viewport or the scene list." }] })
    // Pose (Shift+P): both pages, one clay selected (pose_qt.py); stays while it is on
    readonly property var poseGroups: viewport.pose.can || viewport.pose.on ? [{ id: "pose", items: [{ name: "Pose", icon: "pose-drag",
        kind: "shape3d", tool: "pose", job: "pose_tool", help: "Drag a part of the clay to pose it; click a spot to hold it still." }] }] : []
    readonly property var materialsGroup: ({ id: "materials", name: "Materials", panel: true, items: [{ name: "Materials", icon: "material",
        kind: "shape3d", job: "materials_list", help: "The project's materials: click one to edit it, drag one onto an item to give it that material." }] })
    // the Animate page (SPEC §2): Select, Poses (P), Onion skin (O), Bones (a mesh selected), Lights, Camera; Simulate joins when built
    groups: backend.page === "animate" ? [
        rail.selectGroup,
        { id: "poses", name: "Poses", panel: true, items: [{ name: "Poses", icon: "pose", kind: "shape3d", job: "poses_panel",
          help: "Save the selected items' pose; click a saved one to key it at the playhead." }] },
        { id: "onion", name: "Onion skin", panel: true, items: [{ name: "Onion skin", icon: "onion", kind: "shape3d", job: "onion",
          help: "Ghosts of the selected item before (red) and after (green), to time its arc by eye." }] },
        { id: "bones", name: "Bones", items: viewport.bones.meshSelected ? [{ name: "Bones", icon: "bone", kind: "shape3d", act: "bones", job: "bones_tool",
          help: "Click points along the selected mesh, root first, then Enter: a bone chain it bends with." }] : [] },   // only with a mesh selected
    ].concat(rail.poseGroups, [
        { sep: true },
        { id: "lights", name: "Lights", job: "lights_menu", items: rail.entries(backend.adder.rail.lights) },
        { id: "camera", name: "Camera", job: "camera_menu", items: rail.entries(backend.adder.rail.camera) },
        { sep: true },
        rail.materialsGroup
    ]) : [
        rail.selectGroup,
        { id: "clay", items: [{ name: "Clay", icon: "clay", kind: "shape3d", tool: "clay", job: "clay_tool",
                                help: "Draw an outline: it puffs into clay. Then sculpt it: Add, Carve, Smooth." }] },
        { id: "shapes", name: "Shapes", job: "shapes_menu", items: rail.entries(backend.adder.rail.shapes) },
        { id: "type", name: "Type & logo", job: "type_menu", items: rail.entries(backend.adder.rail.type) },
        { id: "import", name: "Import", job: "add_file", items: backend.importer.rail },     // absent while it has no entries
        { sep: true },
        { id: "lights", name: "Lights", job: "lights_menu", items: rail.entries(backend.adder.rail.lights) },
        { id: "camera", name: "Camera", job: "camera_menu", items: rail.entries(backend.adder.rail.camera) }
    ].concat([{ sep: true }], paintMode.can || paintMode.on       // Paint (B): the Build page, one mesh or clay selected
             ? [{ id: "paint", items: [{ name: "Paint", icon: "brush", tool: "paint", job: "paint_tool",
                                         help: "Paint on the selected mesh or clay: colour, roughness, relief, metal or glow." }] }]
             : [], rail.poseGroups, [rail.materialsGroup])
    // Poses and Onion skin each open and close on their own (PosesPanel.qml, OnionPanel.qml): their button toggles its panel,
    // Esc closes the one with the keys, and clicking elsewhere leaves them open (you work in the viewport with the ghosts on).
    // `panelOpen` stays false so the kit's rail never closes one for the other's button.
    function panelOf(id) { return id === "poses" ? posesPanel : id === "onion" ? onionPanel : null }
    onPanelRequested: (g) => rail.openPanel(g.id)
    function openPanel(id) {        // the scripted `panel <id>` step, P, and the buttons: open it, or close it when it is open
        if (id === "materials") return openMaterials()
        const pop = panelOf(id)
        if (!pop) return
        if (pop.visible) return pop.close()
        const b = rail.buttonOf(id)       // beside the rail, top edges with the button (never over the rail)
        const x = rail.mapToItem(null, rail.width + Theme.gap, 0).x
        const beside = pop === onionPanel && posesPanel.visible ? posesPanel.width + Theme.gap : 0     // both open: side by side
        pop.openAtPoint(x + beside, b ? b.mapToItem(null, 0, 0).y : rail.mapToItem(null, 0, 0).y)
    }
    // Materials closes on a click outside like any list; the press on its own ball closes it first, so the click that
    // follows must not open it again (closedAt)
    function openMaterials() {
        if (materialsList.visible) return materialsList.close()
        if (Date.now() - materialsList.closedAt < 300) return
        const b = rail.buttonOf("materials")
        matSpot.y = (b ? b.mapToItem(rail, 0, 0).y : 0) - Theme.grid     // its top edge with the button's
        materialsList.openFrom(matSpot)
    }
    Item { id: matSpot; x: rail.width + Theme.gap; width: 0; height: 0 }    // what the list opens under: beside the ball
    MaterialsList { id: materialsList; property real closedAt: 0; onClosed: closedAt = Date.now() }
    PosesPanel { id: posesPanel; closePolicy: QQC.Popup.NoAutoClose }
    OnionPanel { id: onionPanel; closePolicy: QQC.Popup.NoAutoClose }
    Connections {       // they belong to the Animate page: leaving it closes them
        target: backend
        function onPageChanged() { if (backend.page !== "animate") { posesPanel.close(); onionPanel.close() } }
    }
    // a shape waits for a click in the viewport (it lands on the surface there); lights and cameras are added at once
    onPicked: (e) => {
        if (e.tool === "pose") return viewport.pose.toggle()               // (it leaves Clay, Paint, Edit mesh itself)
        if (viewport.pose.on && (e.tool === "select" || e.tool === "clay" || e.tool === "paint")) viewport.pose.leave()
        if (e.tool === "clay") { if (paintMode.on) paintMode.leave(); return viewport.clay.toggle() }
        if (viewport.clay.on && (e.tool === "select" || e.tool === "paint")) viewport.clay.leave()
        if (e.tool === "paint" || (e.tool === "select" && paintMode.on)) return paintMode.toggle()
        if (e.act === "bones") viewport.bones.start()
        else if (e.act === "mesh:svg") svgDialog.open()
        else if (e.act === "mesh:path2d") rail.openDrawings()
        else if (e.act && e.act.startsWith("import:")) importFiles.open(e.act.slice(7))
        else if (e.act) (e.act.startsWith("mesh:") ? backend.adder.arm(e.act) : backend.adder.add(e.act))
    }

    ImportFiles { id: importFiles }     // the Import group's picks: a file dialog per format, or the Asset library
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
