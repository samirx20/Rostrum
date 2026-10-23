import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Dialogs
import RostrumKit

// The tool rail (design v2 §2.1): icons only, its own column left of the canvas, never over it. Groups from the top:
// Select, Shapes, Pen, Text, Brush | Media, Sound, Camera | Hand / Zoom | Bones. A group with one entry is a plain
// button; a group with more opens its flyout beside the rail (ToolFlyout.qml). A tool group's icon is its last-used
// tool (pick Star once and the Shapes icon is a star), and it reads that from backend.tool, so a key (R, O, H, Z)
// moves it too. The Shapes flyout lists every shape kind (backend.create.kinds = fields.SHAPE_KINDS), each its own icon. Only what can be used now is listed (rule of individuality): a 3D render only with Rostrum3D, Sound
// only while the selection can take a cue, Bones only with a rig in hand. The one tool switch is backend.setTool.
// Brush is its own kind of group: a click turns painting on and opens the brush panel (BrushFlyout.qml: the five
// paint tools and the brushes); its icon is the paint tool last used (backend.paintTool.now).
Rectangle {
    id: rail
    property bool menuAvoid: true          // menus and flyouts open beside the rail, not over it (MenuPlace.js)
    width: 48
    color: Theme.panel; radius: Theme.radiusPanel
    property var last: ({ shapes: "rect", view: "hand" })      // group -> its last-used tool (screen state)
    readonly property bool flyoutOpen: flyout.visible || brushOpen
    readonly property bool menuOpen: flyout.visible       // a group's menu; the brush panel is part of the Brush tool, not a menu
    readonly property bool canCue: { backend.actions.bar; backend.selected; return JSON.stringify(backend.actions.menu()).indexOf('"sound_here"') >= 0 }   // folded menus nest it
    readonly property bool has3d: backend.adder.entries.some(e => e.type === "render3d")

    // entry: {name, icon, job (key map job: the key shown), help, tool (a canvas tool) or act (does it now)}
    readonly property var groups: [
        { id: "select", items: [{ name: "Select", icon: "select", job: "move_tool", tool: "move", help: "Pick layers, move them, and drag their handles." }] },
        { id: "shapes", name: "Shapes", items: backend.create.kinds.map(k => ({ name: k.name, icon: k.kind, shape: true, tool: k.kind,
            job: k.kind === "rect" || k.kind === "ellipse" ? k.kind + "_tool" : "" })) },
        { id: "pen", items: [{ name: "Pen", icon: "pen", job: "pen_tool", tool: "pen", help: "Click and drag points to draw a path." }] },
        { id: "text", items: [{ name: "Text", icon: "text", job: "text_tool", tool: "text", help: "Click or drag a box on the canvas, then type." }] },
        { id: "brush", items: [{ name: "Brush", icon: "brush", job: "paint_tool", tool: "draw", help: "Paint strokes, on a drawing or on the selected layer." }] },
        { sep: true },
        { id: "media", name: "Media", icon: "picture", job: "add_file", items: [
            { name: "Picture", icon: "picture", act: "image" },
            { name: "Video", icon: "video", act: "video" }]
            .concat(rail.has3d ? [{ name: "3D render", icon: "render3d", act: "render3d" }] : [])
            .concat([{ name: "Import…", icon: "import", act: "import" }, { name: "Library", icon: "library", job: "library", act: "library" }]) },
        { id: "sound", items: rail.canCue ? [{ name: "Add a sound", icon: "sound", act: "cue", help: "Tie a sound to the selected layer's start." }] : [] },
        { id: "camera", items: [{ name: "Camera", icon: "camera", job: "camera_tool", tool: "camera",
            help: backend.cameraTool.available ? "Drag to pan the camera; Alt and drag up to push in, down to pull out."
                                               : "Add a camera to the scene and move it." }] },
        { sep: true },
        { id: "view", items: [
            { name: "Hand", icon: "hand", job: "hand_tool", tool: "hand", help: "Drag to move the view." },
            { name: "Zoom", icon: "zoom", job: "zoom_tool", tool: "zoom", help: "Click to zoom in; Alt and click to zoom out." }] },
        { sep: true, when: backend.boneTool.available },      // the Bone tool is its own group, set off from Hand / Zoom
        { id: "bone", items: backend.boneTool.available ? [{ name: "Bone", icon: "bone", job: "bone_tool", tool: "bone",
            help: "Click joint after joint (or drag from a joint to the tip) to draw the rig's bones. Esc ends the chain." }] : [] }
    ].filter(g => g.sep ? g.when !== false : g.items.length > 0)

    function groupOf(tool) { return rail.groups.find(g => !g.sep && g.items.some(e => e.tool === tool)) }
    function shown(g) {        // the entry on the group's icon: its last-used tool, else the first
        return g.items.find(e => e.tool && e.tool === rail.last[g.id]) || g.items[0]
    }
    Connections {
        target: backend
        function onToolChanged() {
            const g = rail.groupOf(backend.tool)
            if (g && g.items.length > 1) { const l = Object.assign({}, rail.last); l[g.id] = backend.tool; rail.last = l }
        }
    }
    function pick(e) {         // a tool goes on; an act happens now
        flyout.close()
        if (e.tool === "camera" && !backend.cameraTool.available) backend.adder.add("camera")   // the first use adds one
        if (e.tool) backend.setTool(e.tool)
        else if (e.act === "import") Window.window.setImportOpen(true)
        else if (e.act === "library") backend.library.setOpen(!backend.library.open)
        else if (e.act === "cue") backend.run("sound_here")
        else backend.adder.add(e.act)          // image / video ask for their file (fileWanted below); 3D render
    }
    function openBrushes() {   // painting on, and the brush panel beside the Brush icon (B; B again reopens it)
        flyout.close()
        if (backend.tool !== "draw") backend.paintTool.use("brush")
        brushes.get().show(buttons.itemAt(rail.groups.findIndex(g => g.id === "brush")))
    }
    function openGroup(id) {   // the flyout of group `id` (Ctrl+I: media; scripted steps), or "" to close it
        if (id === "brush") { openBrushes(); return true }
        if (brushes.item) brushes.item.close()
        const i = rail.groups.findIndex(g => g.id === id)
        if (i < 0 || rail.groups[i].items.length < 2) { flyout.close(); return false }
        flyout.show(rail.groups[i], buttons.itemAt(i))
        return true
    }

    Column {
        id: column
        x: (rail.width - Theme.button - 8) / 2; y: 6
        spacing: 4
        Repeater {
            id: buttons
            model: rail.groups
            delegate: Item {
                id: slot
                required property var modelData
                readonly property var g: modelData
                readonly property var e: g.sep ? null : rail.shown(g)
                readonly property bool many: !!(!g.sep && g.items.length > 1)
                readonly property bool on: !g.sep && g.items.some(x => x.tool && x.tool === backend.tool) || (flyout.visible && flyout.group === g.id)
                readonly property bool brush: g.id === "brush"
                width: Theme.button + 8; height: g.sep ? 9 : Theme.button + 8
                objectName: g.sep ? "" : "rail_" + g.id
                Rectangle { visible: !!slot.g.sep; anchors.centerIn: parent; width: parent.width - 8; height: 1; color: Theme.popupEdge }
                Rectangle {
                    visible: !slot.g.sep
                    anchors.fill: parent; radius: Theme.radiusCtl
                    color: area.pressed || slot.on ? Theme.active : hover.hovered ? Theme.hover : "transparent"
                    Behavior on color { ColorAnimation { duration: Theme.fast } }
                }
                ToolIcon { visible: !slot.g.sep && !slot.brush && !(slot.e && slot.e.shape); anchors.centerIn: parent; name: slot.e ? slot.e.icon : ""
                           ink: slot.on || hover.hovered ? Theme.fg : Theme.fg2 }
                ShapeIcon { visible: !!(slot.e && slot.e.shape); anchors.centerIn: parent; name: slot.e && slot.e.shape ? slot.e.icon : ""
                            ink: slot.on || hover.hovered ? Theme.fg : Theme.fg2 }
                PaintToolIcon { visible: slot.brush; anchors.centerIn: parent; name: backend.paintTool.now
                                ink: slot.on || hover.hovered ? Theme.fg : Theme.fg2 }
                Canvas {   // the corner mark of a group with a flyout
                    visible: slot.many || slot.brush
                    anchors { right: parent.right; bottom: parent.bottom; margins: 3 }
                    width: 5; height: 5
                    onPaint: { const c = getContext("2d"); c.reset(); c.fillStyle = Theme.fg3
                               c.beginPath(); c.moveTo(5, 0); c.lineTo(5, 5); c.lineTo(0, 5); c.closePath(); c.fill() }
                }
                HoverHandler { id: hover; enabled: !slot.g.sep; cursorShape: Qt.PointingHandCursor }
                MouseArea {
                    id: area
                    anchors.fill: parent; enabled: !slot.g.sep
                    onClicked: slot.brush ? (rail.brushOpen ? brushes.item.close() : rail.openBrushes())
                             : slot.many ? (flyout.visible && flyout.group === slot.g.id ? flyout.close() : rail.openGroup(slot.g.id))
                                         : rail.pick(slot.e)
                    pressAndHoldInterval: 350
                    onPressAndHold: if (slot.many) rail.openGroup(slot.g.id)
                }
                HoverTip {   // beside the rail: the name and the key
                    x: slot.width + 6; y: (slot.height - height) / 2
                    text: slot.many ? (slot.g.name || slot.e.name) : slot.e ? slot.e.name : ""
                    help: !slot.many && slot.e && slot.e.help ? slot.e.help : ""
                    key: slot.e && slot.e.job && slot.Window.window && slot.Window.window.keyFor ? slot.Window.window.keyFor(slot.many && slot.g.job ? slot.g.job : slot.e.job) : ""
                    hovered: hover.hovered && !rail.flyoutOpen; pressed: area.pressed
                }
            }
        }
    }
    ToolFlyout { id: flyout; onPicked: (e) => rail.pick(e) }
    readonly property bool brushOpen: !!brushes.item && brushes.item.visible
    FirstUse { id: brushes; sourceComponent: Component { BrushFlyout { } } }   // made at its first opening: its strokes are painted then (H65)

    FileDialog {    // Media › Picture / Video: the file first, then one layer, centred (backend.adder.addFile)
        id: dialog
        property string type: ""
        title: "Choose a " + (type === "image" ? "picture" : type)
        nameFilters: type === "video" ? ["Video (*.mp4 *.mov *.webm *.mkv *.m4v *.avi)"]
                                      : ["Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)"]
        onAccepted: backend.adder.addFile(type, selectedFile.toString())
    }
    Connections {
        target: backend.adder
        function onFileWanted(type) { dialog.type = type; dialog.open() }
    }
}
