import QtQml
import QtQuick
import RostrumKit

// Rostrum2D, one workspace (apps/2d/DESIGN.md). Left edge: the tool rail (ToolRail.qml); centre: the canvas (the engine's frame). Right: the inspector (from the selected item's field operation, values at the playhead, key marks); while
// the Draw tool is on, the brush (the next stroke's settings, from the brush settings' own rules).
// Bottom, full width, always there: the timeline, which is also the layers list (a row and a bar per layer). Its top
// edge drags to make it taller or shorter.
AppShell {
    id: shell
    bridge: backend
    appName: "Rostrum2D"
    helpEntries: guides                 // Help's guides (screen2d/session.py), in the kit's guide viewer
    documentName: files.hasProject ? files.name : "Untitled"   // the project (the kit's files: rostrum_gui/project_files.py)
    leftWidth: backend.library.open ? Theme.sidePanel : 0      // the Library drawer (LibraryDrawer.qml), beside the rail
    leftOver: true                      // it and the guides float over the canvas: the rail stays put, the canvas keeps its size
    rail: [ ToolRail { id: rail; visible: !startScreen.visible; anchors { top: parent.top; bottom: parent.bottom } } ]   // its own column, never over the canvas
    left: [ LibraryDrawer { anchors.fill: parent; visible: backend.library.open } ]
    onPressedIn: (area) => { if ((area === "right" || area === "bottom") && backend.create.typing) backend.create.commitText(backend.create.body) }   // a click in the settings or the timeline ends typing
    areaNames: ({ centre: "canvas", right: "settings", bottom: "timeline" })   // inspect_screen's words for the focused area
    saveWord: backend.isLive ? "Saved" : ""      // a project is live: every change is already on disk
    // The frame drives the layout (the kit's FrameLayout.js, SPEC 2d-design-v2 §1.2): the settings panel's width and
    // the timeline's size and place (below the frame, or beside it for tall and square scenes) follow the scene's
    // aspect and the window; a panel edge dragged by hand wins (remembered in the person's settings). The canvas fits
    // the frame again only when that layout changes (Stage.qml), never when a panel's contents change.
    // ⊟ folds the timeline to its header (screen state, never the document).
    property bool timelineFolded: false
    // Each tool remembers its own timeline height (the-screen.md §2.7): Brush starts compact, every other tool full
    property var foldedFor: ({ "draw": true })
    readonly property string toolNow: backend.tool
    onToolNowChanged: timelineFolded = foldedFor[toolNow] === true
    function fold(on) { const m = Object.assign({}, foldedFor); m[toolNow] = on; foldedFor = m; timelineFolded = on }
    frameAspect: startScreen.visible ? 0 : (backend.frameInfo.width || 16) / (backend.frameInfo.height || 9)
    frameChrome: Qt.size(rail.width + Theme.gap + 2 * Theme.pad, 2 * Theme.pad)   // the rail's column, then the stage's padding round the well
    timelineLeast: 7 * Theme.row + Theme.gap      // the header row, then 6 rows of 28 px (204: §1.2), never the content
    frameFolded: timelineFolded && !bottomBeside ? timeline.compactHeight : -1
    bottomHeight: -Theme.gap            // the start screen is not the workspace: no timeline under it

    // the tools: V move, P pen, B draw, Esc back to move (screen state, backend.setTool)
    Shortcut { sequence: "V"; enabled: !shell.typing; onActivated: backend.setTool("move") }
    Shortcut { sequence: "P"; enabled: !shell.typing; onActivated: backend.setTool(backend.tool === "pen" ? "move" : "pen") }
    Shortcut { sequence: "B"; enabled: !shell.typing; onActivated: { backend.paintTool.use("brush"); rail.openBrushes() } }   // the brush panel (BrushFlyout.qml)
    // painting: the Brush group's other tools (paint_tool.py), and [ ] size, Shift+[ ] hardness (the brush ring shows it)
    readonly property bool painting: backend.tool === "draw" && !shell.typing
    Shortcut { sequence: "E"; enabled: shell.painting; onActivated: backend.paintTool.use(backend.paintTool.now === "eraser" ? "brush" : "eraser") }
    Shortcut { sequence: "G"; enabled: shell.painting; onActivated: backend.paintTool.use(backend.paintTool.now === "fill" ? "brush" : "fill") }
    Shortcut { sequence: "I"; enabled: shell.painting; onActivated: backend.paintTool.use(backend.paintTool.now === "pick" ? "brush" : "pick") }
    Shortcut { sequence: "S"; enabled: shell.painting; onActivated: backend.paintTool.use(backend.paintTool.now === "select" ? "brush" : "select") }
    function brushBy(name, f, lo, hi) { painter.setValue(name, Math.max(lo, Math.min(hi, Math.round(painter.brushNow[name] * f * 100) / 100))) }
    Shortcut { sequence: "["; enabled: shell.painting; onActivated: shell.brushBy("size", 1 / 1.25, 0.5, 2000) }
    Shortcut { sequence: "]"; enabled: shell.painting; onActivated: shell.brushBy("size", 1.25, 0.5, 2000) }
    Shortcut { sequences: ["Shift+[", "{"]; enabled: shell.painting; onActivated: painter.setValue("hardness", Math.max(0, Math.round(painter.brushNow.hardness * 10 - 1) / 10)) }
    Shortcut { sequences: ["Shift+]", "}"]; enabled: shell.painting; onActivated: painter.setValue("hardness", Math.min(1, Math.round(painter.brushNow.hardness * 10 + 1) / 10)) }
    Shortcut { sequence: "R"; enabled: !shell.typing; onActivated: backend.setTool("rect") }       // creation tools (create.py)
    Shortcut { sequence: "O"; enabled: !shell.typing; onActivated: backend.setTool("ellipse") }
    Shortcut { sequence: "T"; enabled: !shell.typing; onActivated: backend.setTool("text") }
    Shortcut { sequence: "C"; enabled: !shell.typing; onActivated: { if (!backend.cameraTool.available) backend.adder.add("camera")   // the first use adds one
                                                                    backend.setTool("camera") } }
    Shortcut { sequence: "H"; enabled: !shell.typing; onActivated: backend.setTool("hand") }       // view tools (Stage.qml)
    Shortcut { sequence: "Z"; enabled: !shell.typing; onActivated: backend.setTool("zoom") }
    Shortcut { sequence: "Ctrl+I"; enabled: !shell.typing; onActivated: rail.openGroup("media") }  // the kit's add_file: the Media flyout
    Shortcut { sequence: "J"; enabled: !shell.typing && backend.boneTool.available; onActivated: backend.setTool("bone") }   // only with a rig in hand (bone_tool.py)
    Shortcut { sequence: "A"; enabled: !shell.typing; onActivated: backend.showAnimated() }    // only the animated settings of the selection; again folds them
    // Esc steps back one level at a time, the same whichever way the tool was entered (key, rail or a step): a rail menu closes, then
    // picked strokes are let go, then the tool is Select (the Brush's panel closes with the Brush; it is no step of its own)
    Shortcut { sequence: "Escape"; enabled: rail.menuOpen || (backend.tool !== "move" && backend.tool !== "pen" && !(backend.tool === "text" && backend.create.typing))
               onActivated: { if (rail.menuOpen) rail.openGroup("")
                              else if (backend.strokeSelect.count > 0 || backend.strokeSelect.armed) backend.strokeSelect.clear()   // picked strokes first
                              else if (backend.tool === "bone" && backend.boneTool.end()) {}     // the bone chain ends first
                              else { rail.openGroup(""); backend.setTool("move") } } }
    // painting: 1 … 9 = 10 … 90 % brush opacity, 0 = 100 % (as in Photoshop)
    Repeater { model: 10; delegate: Item { required property int index
        Shortcut { sequence: String(index); enabled: shell.painting; onActivated: painter.setValue("opacity", index === 0 ? 1 : index / 10) } } }

    Connections { target: spaceKey; function onTapped() { backend.togglePlay() } }   // a tap of Space plays; held, it pans (spacekey.py)
    // frame by frame, on the selected drawing (INTERACTION Part 2: , and . step drawings, = and − hold; Alt+arrows nudge)
    // , and . : the playhead to the previous / next thing that happens (a key, a marker, a drawing, a layer's start or end)
    // of the selected layers, or of everything when none is selected (backend.stepEvent, screen2d/key_edits.py)
    // A frame-by-frame layer: its drawings, and held down they flip through at the scene's speed (FlipThrough.qml)
    FlipThrough { id: flip }
    Shortcut { sequence: ","; enabled: !shell.typing; onActivated: painter.drawingId !== "" ? flip.press(-1) : backend.stepEvent(-1) }
    Shortcut { sequence: "."; enabled: !shell.typing; onActivated: painter.drawingId !== "" ? flip.press(1) : backend.stepEvent(1) }
    // Shift+, and Shift+. : the previous / next beat of the project's sound (the key map's prev_beat / next_beat;
    // "<" and ">" are what a US keyboard sends for them), only while the sound has a tempo (backend.soundtrack)
    Shortcut { sequences: ["Shift+,", "<"]; enabled: !shell.typing && backend.soundtrack.hasBeats; onActivated: backend.soundtrack.stepBeat(-1) }
    Shortcut { sequences: ["Shift+.", ">"]; enabled: !shell.typing && backend.soundtrack.hasBeats; onActivated: backend.soundtrack.stepBeat(1) }
    Shortcut { sequence: "Alt+N"; onActivated: painter.newFrame(false) }
    Shortcut { sequence: "Alt+Shift+N"; onActivated: painter.newFrame(true) }
    Shortcut { sequences: ["=", "+"]; enabled: !shell.typing && painter.drawingId !== ""; onActivated: painter.holdBy(1) }
    Shortcut { sequence: "-"; enabled: !shell.typing && painter.drawingId !== ""; onActivated: painter.holdBy(-1) }
    Shortcut { sequence: "Alt+O"; onActivated: painter.setOnion(!painter.onionOn) }
    // select, then act: every action's key comes from the one key map (screen2d/keys2d.py) and runs through the one
    // action list (backend.actions): only when valid now, else the status line says why. Not while typing. Delete is
    // run here: keys picked in the timeline go before layers (backend.layerCommand, key_select.py)
    // A text field counts only while it is shown: an editor that closes (rename, typing on the canvas: Esc, Enter, Ctrl+Enter, a click
    // away) can leave the focus on itself, hidden, and every key would stay "typing" for good. The focus then goes back to the window.
    readonly property bool textFocus: shell.activeFocusItem !== null && shell.activeFocusItem.visible && typeof shell.activeFocusItem.selectAll === "function"
    readonly property bool typing: backend.create.typing || textFocus
    property Item lastFocus: null
    onActiveFocusItemChanged: lastFocus = activeFocusItem
    function releaseHiddenFocus() { if (!textFocus && lastFocus && !lastFocus.visible) { lastFocus.focus = false; shell.contentItem.forceActiveFocus() } }
    onTextFocusChanged: Qt.callLater(releaseHiddenFocus)      // later: moving the focus inside its own change is a binding loop
    readonly property bool canvasKeys: backend.tool === "move" && !typing
    KeyMap {
        hub: backend.actions
        enabled: !shell.typing && !startScreen.visible
        skip: backend.actions.keys.map(k => k.job).filter(j => j === "delete" || backend.actions.jobs.indexOf(j) < 0)   // keys run here
    }
    Shortcut { sequences: ["Delete", "Backspace"]; enabled: !shell.typing
               onActivated: { if (backend.strokeSelect.count > 0) backend.strokeSelect.remove(); else backend.layerCommand("delete") } }   // picked strokes first
    Shortcut { sequence: "Ctrl+A"; enabled: shell.canvasKeys; onActivated: backend.selectAllLayers() }
    Shortcut { sequences: ["Return", "Enter"]; enabled: shell.canvasKeys && backend.create.canEdit       // the selected text: type in it
               onActivated: backend.create.editText(backend.selected) }
    Shortcut { sequence: "Ctrl+L"; enabled: !shell.typing; onActivated: backend.library.setOpen(!backend.library.open) }   // the kit's "library" job
    // Esc steps back one level (the kit's ladder, selection_rules.esc_step): close an open panel, else clear
    Shortcut {
        sequence: "Escape"; enabled: shell.canvasKeys
        onActivated: {
            const open = backend.exporter.open || importPanel.shown || fileMenu.menuOpen || rail.flyoutOpen
            if (backend.stepBack({ popover: open }) === "close") {
                shell.setExportOpen(false); shell.setImportOpen(false)
                fileMenu.closeMenu(); rail.openGroup("")
            }
        }
    }
    Shortcut { sequence: "Left"; enabled: shell.canvasKeys; onActivated: backend.nudge(-1, 0) }
    Shortcut { sequence: "Right"; enabled: shell.canvasKeys; onActivated: backend.nudge(1, 0) }
    Shortcut { sequence: "Up"; enabled: shell.canvasKeys; onActivated: backend.nudge(0, -1) }
    Shortcut { sequence: "Down"; enabled: shell.canvasKeys; onActivated: backend.nudge(0, 1) }
    Shortcut { sequence: "Shift+Left"; enabled: shell.canvasKeys; onActivated: backend.nudge(-10, 0) }
    Shortcut { sequence: "Shift+Right"; enabled: shell.canvasKeys; onActivated: backend.nudge(10, 0) }
    Shortcut { sequence: "Shift+Up"; enabled: shell.canvasKeys; onActivated: backend.nudge(0, -10) }
    Shortcut { sequence: "Shift+Down"; enabled: shell.canvasKeys; onActivated: backend.nudge(0, 10) }
    Shortcut { sequence: "Alt+Left"; enabled: shell.canvasKeys; onActivated: backend.nudge(-0.1, 0) }      // the fine step
    Shortcut { sequence: "Alt+Right"; enabled: shell.canvasKeys; onActivated: backend.nudge(0.1, 0) }
    Shortcut { sequence: "Alt+Up"; enabled: shell.canvasKeys; onActivated: backend.nudge(0, -0.1) }
    Shortcut { sequence: "Alt+Down"; enabled: shell.canvasKeys; onActivated: backend.nudge(0, 0.1) }

    function setExportOpen(open) { backend.exporter.setOpen(open); if (open) importPanel.shown = false }
    function setImportOpen(open) { importPanel.shown = open; if (open) backend.exporter.setOpen(false) }
    function setFileMenuOpen(open) { if (open) fileMenu.openMenu(); else fileMenu.closeMenu() }
    function openLayerMenu(id) { timeline.openMenu(id) }
    function openCanvasMenu() { stage.openMenu() }
    function openFlyout(group) { return rail.openGroup(group) }    // a rail group's flyout ("": close it)

    // Export: the kit sheet in the inspector's place (Ctrl+E; Ctrl+Shift+E again), filled with 2D's formats
    // (screen2d/exporter.py); the job chip comes with it. Problems: the kit chip, only while something is wrong.
    exporter: backend.exporter
    exportSettings: ExportSettings { }
    problems: backend.problems
    onLayoutChanged: stage.fitAll()     // the window's layout changed: fit the frame once (never otherwise)
    actions: [
        ViewControls { id: viewControls; view: stage.view; typing: shell.typing; onFitSelection: stage.fitSelection()
                       Component.onCompleted: stage.viewControls = viewControls },   // "Fit · 57 % ▾", off the canvas
        Button { text: "Export"; kind: "primary"; down: backend.exporter.open; onClicked: shell.setExportOpen(!backend.exporter.open) }
    ]
    // the start screen (kit): at launch with nothing to reopen, or ≡ › Start screen…; over everything while shown
    StartScreen { id: startScreen; anchors.fill: parent; z: 100; onGuideAsked: (url) => shell.openGuide(url)
                  anchors.leftMargin: shell.guidesOpen ? (shell.guidesWidth || 0) : 0 }   // a guide opened from it shows beside it
    StaggerPopover { }   // the context bar's Stagger… (stagger.py): under the bar
    DepthPopover { x: (shell.width - width) / 2; y: 104 }     // Set depth ▾ › Other depth… (depth_typed.py): under the bar
    SoundCuePopover { x: (shell.width - width) / 2; y: 104 }  // Add a sound here… (sound_cue_pick.py): under the bar
    centre: [
        Stage { id: stage; anchors.fill: parent; typing: shell.typing },   // typing: F stays a letter (ViewControls.qml)
        EmptyHint {     // a new scene (the kit's empty state, INTERACTION.md 1.16): gone with the first layer
            visible: backend.layers.length === 0 && backend.tool === "move"
            anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: Theme.groupGap * 3 }
            width: Math.min(460, parent.width - 4 * Theme.gap)
            text: "Draw a shape (R), type (T), paint (B), or drop a file here."
        },
        ImportPanel {   // opened by the rail's Media › Import…, on the canvas (opening the Export sheet closes it)
            id: importPanel
            Connections { target: backend.importer; function onWantPanel() { shell.setImportOpen(true) } }
            anchors { right: parent.right; rightMargin: Theme.gap; top: parent.top; topMargin: Theme.gap }
        }
    ]
    menu: FilesMenu { id: fileMenu }    // ≡: New, Open, Open recent, Duplicate, Save a version … (kit; saving is automatic)
    right: [
        Inspector { id: settingsMove; anchors.fill: parent; bridge: backend; keyMarks: true; effects: true; actions: backend.actions
                    visible: backend.tool !== "draw" && !backend.stretch.shown   // typing: the text's settings (typing_session.py selects it)
                    highlight: backend.keys.props         // the settings whose keys are picked (key_select.py)
                    above: Column { width: parent.width    // the picked keys (KeyPanel.qml), then a rig in hand: its pose library (rig_poses.py)
                                    KeyPanel { }
                                    RigPoses { } }
                    below: Column {                       // a frame-by-frame layer: the same drawing tools as in Draw (DrawEachFrame.qml)
                        width: parent.width; visible: painter.drawingId !== ""; topPadding: Theme.gap
                        Text { height: Theme.row; verticalAlignment: Text.AlignVCenter; text: "Draw each frame"
                               color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont }
                        DrawEachFrame { visible: true }
                    }
                    sheets: [   // Lip sync… / Add blinks… in the panel's place; each is made when first opened (FirstUse, H66)
                        FirstUse { anchors.fill: parent; visible: backend.lipsync.open; when: visible; sourceComponent: Component { LipSyncSheet { } } },
                        FirstUse { anchors.fill: parent; visible: backend.blinks.open; when: visible; sourceComponent: Component { BlinkSheet { } } } ] },
        FirstUse { id: settingsDraw; anchors.fill: parent; visible: backend.tool === "draw"; when: visible   // the painting settings: made when Draw is first picked
                   sourceComponent: Component {
                       Inspector { anchors.fill: parent; bridge: painter
                                   above: BrushHead { }      // the brush's own row (or ‹ back while editing it), then its quick rows
                                   below: PaintTarget { } } } },   // Edit brush ›, Painting on (Layer, Inside the outline, Draw each frame), paint layers
        AnimPanel { anchors.fill: parent }    // a stretch picked in the timeline: its animation, over the layer's settings (stretch_select.py)
    ]
    bottom: LayerTimeline {
        id: timeline
        visible: !startScreen.visible
        anchors.fill: parent
        compact: shell.timelineFolded && !shell.bottomBeside
        canCompact: !shell.bottomBeside
        onResized: (h) => { shell.fold(false); shell.setAsked("bottom", h) }   // its top edge, dragged: the person's height
        onCompactAsked: (on) => shell.fold(on)
    }
}
