import QtQuick
import QtQuick.Dialogs
import RostrumKit

// 2D's tool rail (design v2 §2.1): the kit's ToolRail (RostrumKit/ToolRail.qml) filled with 2D's tools. Groups from the
// top: Select, Shapes, Pen, Text, Brush | Media, Sound, Camera | Hand / Zoom | Bones. A tool group's icon is its
// last-used tool (pick Star once and the Shapes icon is a star), read from backend.tool, so a key (R, O, H, Z) moves it
// too. The Shapes flyout lists every shape kind (backend.create.kinds = fields.SHAPE_KINDS), each its own icon
// (ShapeIcon.qml). Only what can be used now is listed (rule of individuality): a 3D render only for a rendered 3D item
// of the project (one entry per item: backend.adder.entries, read again as Media opens), Sound only while the selection
// can take a cue, Bones only with a rig in hand. Every entry does its job on the click: Picture, Video and Import… open
// the file picker at once, and the chosen file comes in (Import… as a file let go on the canvas: importer.dropFiles). The one tool switch is backend.setTool.
// Brush is its own kind of group (`panel`): a click turns painting on and opens the brush panel (BrushFlyout.qml: the
// five paint tools and the brushes); its icon is the paint tool last used (backend.paintTool.now).
ToolRail {
    id: rail
    current: backend.tool
    last: ({ shapes: "rect", view: "hand" })
    panelOpen: !!brushes.item && brushes.item.visible
    readonly property bool canCue: { backend.actions.bar; backend.selected; return JSON.stringify(backend.actions.menu()).indexOf('"sound_here"') >= 0 }   // folded menus nest it
    readonly property var renders3d: backend.adder.entries.filter(e => e.type === "render3d")

    iconKinds: ({ shape: shapeIcon, paint: paintIcon })
    Component { id: shapeIcon; ShapeIcon { } }
    Component { id: paintIcon; Item { property string name; property color ink; width: 20; height: 20
                                      PaintToolIcon { name: backend.paintTool.now; ink: parent.ink } } }   // follows the tool last used

    // entry: {name, icon, job (key map job: the key shown), help, tool (a canvas tool) or act (does it now)}
    groups: [
        { id: "select", items: [{ name: "Select", icon: "select", job: "move_tool", tool: "move", help: "Pick layers, move them, and drag their handles." }] },
        { id: "shapes", name: "Shapes", items: backend.create.kinds.map(k => ({ name: k.name, icon: k.kind, kind: "shape", tool: k.kind,
            job: k.kind === "rect" || k.kind === "ellipse" ? k.kind + "_tool" : "" })) },
        { id: "pen", items: [{ name: "Pen", icon: "pen", job: "pen_tool", tool: "pen", help: "Click: a corner. Drag: a curve. Click the first point to close; Enter to finish." }] },
        { id: "text", items: [{ name: "Text", icon: "text", job: "text_tool", tool: "text", help: "Click or drag a box on the canvas, then type." }] },
        { id: "brush", panel: true, items: [{ name: "Brush", icon: "brush", kind: "paint", job: "paint_tool", tool: "draw", help: "Paint strokes, on a drawing or on the selected layer." }] },
        { sep: true },
        { id: "media", name: "Media", icon: "picture", job: "add_file", items: [
            { name: "Picture", icon: "picture", act: "image" },
            { name: "Video", icon: "video", act: "video" }]
            .concat(rail.renders3d.map(e => ({ name: e.label, icon: "render3d", act: "render3d:" + e.item })))
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
    ]

    onPicked: (e) => {         // a tool goes on; an act happens now
        if (e.tool === "camera" && !backend.cameraTool.available) backend.adder.add("camera")   // the first use adds one
        if (e.tool) backend.setTool(e.tool)
        else if (e.act === "import") importDialog.open()
        else if (e.act === "library") backend.library.setOpen(!backend.library.open)
        else if (e.act === "cue") backend.run("sound_here")
        else backend.adder.add(e.act)          // image / video ask for their file (fileWanted below); render3d:<item>
    }
    onPanelRequested: rail.openBrushes()
    onPanelCloseRequested: brushes.item.close()
    onGroupOpening: (id) => { if (brushes.item) brushes.item.close()    // a flyout (or "") replaces the brush panel
                              if (id === "media") backend.adder.refresh() }   // a 3D render may have landed since
    function openBrushes() {   // painting on, and the brush panel beside the Brush icon (B; B again reopens it)
        rail.closeFlyout()
        if (backend.tool !== "draw") backend.paintTool.use("brush")
        brushes.get().show(rail.buttonOf("brush"))
    }
    FirstUse { id: brushes; sourceComponent: Component { BrushFlyout { } } }   // made at its first opening: its strokes are painted then (H65)

    FileDialog {    // Media › Picture / Video: the file first, then one layer, centred (backend.adder.addFile)
        id: dialog
        property string type: ""
        title: "Choose a " + (type === "image" ? "picture" : type)
        nameFilters: type === "video" ? ["Video (*.mp4 *.mov *.webm *.mkv *.m4v *.avi)"]
                                      : ["Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)"]
        onAccepted: backend.adder.addFile(type, selectedFile.toString())
    }
    FileDialog {    // Media › Import…: the file, then in at once, centred (as if let go on the canvas: one change per file)
        id: importDialog
        objectName: "importDialog"
        title: "Import a file"
        nameFilters: [backend.importer.filters]
        onAccepted: backend.importer.dropFiles([selectedFile.toString()], NaN, NaN)
    }
    Connections {
        target: backend.adder
        function onFileWanted(type) { dialog.type = type; dialog.open() }
    }
}
