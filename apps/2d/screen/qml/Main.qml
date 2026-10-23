import QtQml
import QtQuick
import RostrumKit

// Rostrum2D, one workspace (apps/2d/DESIGN.md). Centre: the canvas (the engine's frame) with the tool strip (Move,
// Pen, Draw). Right: the inspector (from the selected item's field operation, values at the playhead, key marks); while
// the Draw tool is on, the brush (the next stroke's settings, from the brush settings' own rules).
// Bottom, full width, always there: the timeline, which is also the layers list (a row and a bar per layer). Its top
// edge drags to make it taller or shorter.
AppShell {
    id: shell
    bridge: backend
    appName: "Rostrum2D"
    helpEntries: guides                 // Help's guides (screen2d/session.py), in the kit's guide viewer
    documentName: files.hasProject ? files.name : "Untitled"   // the project (the kit's files: rostrum_gui/project_files.py)
    leftWidth: backend.library.open ? Theme.sidePanel : 0      // the Library drawer (LibraryDrawer.qml) pushes the canvas
    left: [ LibraryDrawer { anchors.fill: parent; visible: backend.library.open } ]
    areaNames: ({ centre: "canvas", right: "settings", bottom: "timeline" })   // inspect_screen's words for the focused area
    saveWord: backend.isLive ? "Saved" : ""      // a project is live: every change is already on disk
    // The timeline's height is the person's choice (⊟ compact, or its edge dragged), never changed by a tool.
    // {compact, asked}: asked = the height its edge was dragged to (-1: the default for this window). Screen state,
    // never the document.
    property var timelineNow: ({ compact: false, asked: -1 })
    function setTimeline(compact, asked) {
        timelineNow = { compact: compact, asked: asked === undefined || asked === null ? timelineNow.asked : asked }
    }
    // the start screen is not the workspace: no timeline under it (a guide opened from it takes the full height)
    bottomHeight: startScreen.visible ? -Theme.gap : timelineNow.compact ? timeline.compactHeight
                : Math.round(Math.max(150, Math.min(height * 0.6, timelineNow.asked >= 0 ? timelineNow.asked
                                                                  : Math.min(timeline.wantedHeight, Math.max(220, Math.min(380, height * 0.32))))))
    Behavior on bottomHeight { NumberAnimation { duration: Theme.reveal; easing.type: Theme.revealEasing } }

    // the tools: V move, P pen, B draw, Esc back to move (screen state, backend.setTool)
    Shortcut { sequence: "V"; enabled: !shell.typing; onActivated: backend.setTool("move") }
    Shortcut { sequence: "P"; enabled: !shell.typing; onActivated: backend.setTool(backend.tool === "pen" ? "move" : "pen") }
    Shortcut { sequence: "B"; enabled: !shell.typing; onActivated: backend.setTool("draw") }
    Shortcut { sequence: "R"; enabled: !shell.typing; onActivated: backend.setTool("rect") }       // creation tools (create.py)
    Shortcut { sequence: "O"; enabled: !shell.typing; onActivated: backend.setTool("ellipse") }
    Shortcut { sequence: "T"; enabled: !shell.typing; onActivated: backend.setTool("text") }
    Shortcut { sequence: "C"; enabled: !shell.typing; onActivated: backend.setTool("camera") }     // only with a camera (camera_tool.py)
    Shortcut { sequence: "J"; enabled: !shell.typing && backend.boneTool.available; onActivated: backend.setTool("bone") }   // only with a rig in hand (bone_tool.py)
    Shortcut { sequence: "A"; enabled: !shell.typing; onActivated: backend.showAnimated() }    // only the animated settings of the selection; again folds them
    Shortcut { sequence: "Escape"; enabled: backend.tool === "draw" || backend.tool === "rect" || backend.tool === "ellipse" || backend.tool === "camera"
                                            || backend.tool === "bone" || (backend.tool === "text" && !backend.create.typing)
               onActivated: { if (backend.strokeSelect.count > 0 || backend.strokeSelect.armed) backend.strokeSelect.clear()   // picked strokes first
                              else if (backend.tool === "bone" && backend.boneTool.end()) {}     // the bone chain ends first
                              else backend.setTool("move") } }

    Connections { target: spaceKey; function onTapped() { backend.togglePlay() } }   // a tap of Space plays; held, it pans (spacekey.py)
    // frame by frame, on the selected drawing (INTERACTION Part 2: , and . step drawings, = and − hold; Alt+arrows nudge)
    // , and . : the playhead to the previous / next thing that happens (a key, a marker, a drawing, a layer's start or end)
    // of the selected layers, or of everything when none is selected (backend.stepEvent, screen2d/key_edits.py)
    Shortcut { sequence: ","; enabled: !shell.typing; onActivated: backend.stepEvent(-1) }
    Shortcut { sequence: "."; enabled: !shell.typing; onActivated: backend.stepEvent(1) }
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
    readonly property bool typing: backend.create.typing || shell.activeFocusItem !== null && typeof shell.activeFocusItem.selectAll === "function"
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
            const open = backend.exporter.open || importPanel.shown || fileMenu.menuOpen || stage.addMenu.menuOpen
            if (backend.stepBack({ popover: open }) === "close") {
                shell.setExportOpen(false); shell.setImportOpen(false)
                fileMenu.closeMenu(); stage.addMenu.menuOpen = false
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
    function setAddOpen(open) { stage.addMenu.menuOpen = open }

    // Export: the kit sheet in the inspector's place (Ctrl+E; Ctrl+Shift+E again), filled with 2D's formats
    // (screen2d/exporter.py); the job chip comes with it. Problems: the kit chip, only while something is wrong.
    exporter: backend.exporter
    exportSettings: ExportSettings { }
    problems: backend.problems
    actions: [
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
        ImportPanel {   // opened by the + menu's Import…, on the canvas (opening the Export sheet closes it)
            id: importPanel
            Connections { target: backend.importer; function onWantPanel() { shell.setImportOpen(true) } }
            anchors { right: parent.right; rightMargin: Theme.gap; top: parent.top; topMargin: Theme.gap }
        }
    ]
    menu: FilesMenu { id: fileMenu }    // ≡: New, Open, Open recent, Duplicate, Save a version … (kit; saving is automatic)
    right: [
        Inspector { id: settingsMove; anchors.fill: parent; bridge: backend; keyMarks: true; effects: true
                    visible: backend.tool !== "draw" && !(backend.create.typing && backend.selected === "")   // a new text: no layer to show yet
                    highlight: backend.keys.props         // the settings whose keys are picked (key_select.py)
                    above: RigPoses { }                   // a rig in hand: its pose library first (rig_poses.py)
                    sheets: [LipSyncSheet { }, BlinkSheet { }] },   // Lip sync… / Add blinks… in the panel's place
        Inspector { id: settingsDraw; anchors.fill: parent; bridge: painter; visible: backend.tool === "draw"
                    below: PaintOn { } }      // under the brush: the paint layers and switches of what it paints on
    ]
    bottom: LayerTimeline {
        id: timeline
        visible: !startScreen.visible
        anchors.fill: parent
        compact: shell.timelineNow.compact
        onResized: (h) => shell.setTimeline(false, h)   // its top edge, dragged (clamped above): every row again
        onCompactAsked: (on) => shell.setTimeline(on, null)
    }
}
