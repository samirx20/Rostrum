import QtQuick
import QtQuick.Dialogs
import RostrumKit

// 2D's tool rail (design v2 §2.1): the kit's ToolRail (RostrumKit/ToolRail.qml) filled with 2D's tools. Groups from the
// top: Select, Shapes, Pen, Text, Brush | Add (a file), Library, Sound | Bones. Hand and Zoom are keys (H, Z), Space-drag and the View menu. A tool group's icon is its
// last-used tool (pick Star once and the Shapes icon is a star), read from backend.tool, so a key (R, O, H, Z) moves it
// too. The Shapes flyout lists every shape kind (backend.create.kinds = fields.SHAPE_KINDS), each its own icon
// (ShapeIcon.qml). Only what can be used now is listed (rule of individuality): a 3D render only for a rendered 3D item
// of the project (one entry per item: backend.adder.entries, read again as Media opens), Sound only while the selection
// can take a cue, Bones only with a rig in hand. Every entry does its job on the click: Add from a file… opens
// the file picker at once, and the chosen file comes in (as a file let go on the canvas: importer.dropFiles). The one tool switch is backend.setTool.
// Brush is its own kind of group (`panel`): a click turns painting on and opens the brush panel (BrushFlyout.qml: the
// five paint tools and the brushes); its icon is the paint tool last used (backend.paintTool.now).
ToolRail {
    id: rail
    current: backend.tool
    last: ({ shapes: "rect" })
    panelOpen: !!brushes.item && brushes.item.visible
    readonly property bool canCue: backend.actions.offered.indexOf("sound_here") >= 0   // allowed now (folded in menus or not)
    readonly property var renders3d: backend.adder.entries.filter(e => e.type === "render3d")

    iconKinds: ({ shape: shapeIcon, paint: paintIcon })
    Component { id: shapeIcon; ShapeIcon { } }
    Component { id: paintIcon; Item { property string name; property color ink; width: 20; height: 20
                                      PaintToolIcon { name: backend.paintTool.now; ink: parent.ink } } }   // follows the tool last used

    // entry: {name, icon, job (key map job: the key shown), help, tool (a canvas tool) or act (does it now)}
    groups: [
        { id: "select", items: [{ name: "Select", icon: "select", job: "move_tool", tool: "move", help: "Pick layers, move them, and drag their handles." }] },
        { id: "shapes", name: "Shapes", pickOnClick: true, items: backend.create.kinds.map(k => ({ name: k.name, icon: k.kind, kind: "shape", tool: k.kind,
            job: k.kind === "rect" || k.kind === "ellipse" ? k.kind + "_tool" : "" })) },
        { id: "pen", items: [{ name: "Pen", icon: "pen", job: "pen_tool", tool: "pen", help: "Click: a corner. Drag: a curve. Click the first point to close; Enter to finish." }] },
        { id: "text", items: [{ name: "Text", icon: "text", job: "text_tool", tool: "text", help: "Click or drag a box on the canvas, then type." }] },
        { id: "brush", panel: true, items: [{ name: "Brush", icon: "brush", kind: "paint", job: "paint_tool", tool: "draw", help: "Paint strokes, on a drawing or on the selected layer." }] },
        { sep: true },
        { id: "media", name: "Add", icon: "picture", job: "add_file", items: [{ name: "Add from a file…", icon: "picture", job: "add_file", act: "file",
                help: "A picture, video, SVG, Lottie, PDF or PSD." }]
            .concat(rail.renders3d.map(e => ({ name: e.label, icon: "render3d", act: "render3d:" + e.item }))) },
        { id: "library", items: [{ name: "Library", icon: "library", job: "library", act: "library", help: "Colours, text styles and logos kept in this project." }] },
        { id: "sound", items: rail.canCue ? [{ name: "Add a sound", icon: "sound", act: "cue", help: "Tie a sound to the selected layer's start." }] : [] },
        { sep: true, when: backend.boneTool.available },      // the Bone tool is its own group, set off from Hand / Zoom
        { id: "bone", items: backend.boneTool.available ? [{ name: "Bone", icon: "bone", job: "bone_tool", tool: "bone",
            help: "Click joint after joint (or drag from a joint to the tip) to draw the rig's bones. Esc ends the chain." }] : [] }
    ]

    onPicked: (e) => {         // a tool goes on; an act happens now
        if (e.tool) backend.setTool(e.tool)
        else if (e.act === "file") rail.addFile()
        else if (e.act === "library") backend.library.setOpen(!backend.library.open)
        else if (e.act === "cue") backend.run("sound_here")
        else backend.adder.add(e.act)          // image / video ask for their file (fileWanted below); render3d:<item>
    }
    function addFile() { importDialog.open() }       // Ctrl+I and the Add button: the one door for a file
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

    FileDialog {    // Ctrl+K's Add picture / Add video (scripted: add image <file>): the file first, then one layer, centred (backend.adder.addFile)
        id: dialog
        property string type: ""
        title: "Choose a " + (type === "image" ? "picture" : type)
        nameFilters: type === "video" ? ["Video (*.mp4 *.mov *.webm *.mkv *.m4v *.avi)"]
                                      : ["Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)"]
        onAccepted: backend.adder.addFile(type, selectedFile.toString())
    }
    FileDialog {    // Add from a file…: the file, then in at once, centred (as if let go on the canvas: one change per file;
        id: importDialog     // a PDF of several pages asks which page first)
        objectName: "importDialog"
        title: "Add from a file"
        nameFilters: [backend.importer.filters]
        onAccepted: backend.importer.dropFiles([selectedFile.toString()], NaN, NaN)
    }
    Connections {
        target: backend.adder
        function onFileWanted(type) { if (type === "file") importDialog.open(); else { dialog.type = type; dialog.open() } }
    }
}
