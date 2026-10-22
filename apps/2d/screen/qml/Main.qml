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
    leftWidth: 0
    areaNames: ({ centre: "canvas", right: "settings", bottom: "timeline" })   // inspect_screen's words for the focused area
    saveWord: backend.isLive ? "Saved" : ""      // a project is live: every change is already on disk
    // The timeline's height is remembered per tool (DESIGN.md › two heights): Move and Pen want every row, Draw a big
    // canvas with only the drawing's own row (compact). {compact, asked}: asked = the height its edge was dragged to
    // (-1: the default for this window). Screen state, never the document.
    property var timelineByTool: ({ move: { compact: false, asked: -1 }, pen: { compact: false, asked: -1 },
                                    draw: { compact: true, asked: -1 } })
    readonly property var timelineNow: timelineByTool[backend.tool] || timelineByTool.move
    function setTimeline(compact, asked) {
        const all = Object.assign({}, timelineByTool)
        all[backend.tool] = { compact: compact, asked: asked === undefined || asked === null ? timelineNow.asked : asked }
        timelineByTool = all
    }
    bottomHeight: timelineNow.compact ? timeline.compactHeight
                : Math.round(Math.max(150, Math.min(height * 0.6, timelineNow.asked >= 0 ? timelineNow.asked
                                                                  : Math.max(220, Math.min(380, height * 0.32)))))
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
    // Esc steps back one level (the kit's ladder, selection_rules.esc_step): close an open panel, else clear
    Shortcut {
        sequence: "Escape"; enabled: shell.canvasKeys
        onActivated: {
            const open = backend.exporter.open || importPanel.shown || fileMenu.menuOpen || addMenu.menuOpen
            if (backend.stepBack({ popover: open }) === "close") {
                shell.setExportOpen(false); shell.setImportOpen(false)
                fileMenu.closeMenu(); addMenu.menuOpen = false
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
    function setAddOpen(open) { if (open) addMenu.menuOpen = true; else addMenu.menuOpen = false }

    // Export: the kit sheet in the inspector's place (Ctrl+E; Ctrl+Shift+E again), filled with 2D's formats
    // (screen2d/exporter.py); the job chip comes with it. Problems: the kit chip, only while something is wrong.
    exporter: backend.exporter
    exportSettings: ExportSettings { }
    problems: backend.problems
    actions: [
        AddMenu { id: addMenu },
        Button { text: "Import"; help: "Bring in a file or a design from another app."; down: importPanel.shown; onClicked: shell.setImportOpen(!importPanel.shown) },
        Button { text: "Export"; kind: "primary"; down: backend.exporter.open; onClicked: shell.setExportOpen(!backend.exporter.open) }
    ]
    // the start screen (kit): at launch with nothing to reopen, or ≡ › Start screen…; over everything while shown
    StartScreen { id: startScreen; anchors.fill: parent; z: 100; onGuideAsked: (url) => shell.openGuide(url)
                  anchors.leftMargin: shell.guidesOpen ? (shell.guidesWidth || 0) : 0 }   // a guide opened from it shows beside it
    StaggerPopover { x: (shell.width - width) / 2; y: 104 }   // the context bar's Stagger… (stagger.py): under the bar
    DepthPopover { x: (shell.width - width) / 2; y: 104 }     // Set depth ▾ › Other depth… (depth_typed.py): under the bar
    SoundCuePopover { x: (shell.width - width) / 2; y: 104 }  // Add a sound here… (sound_cue_pick.py): under the bar
    LipSyncSheet { x: (shell.width - width) / 2; y: 104 }     // Lip sync… on a mouth swap set (rig_lipsync.py): under the bar
    BlinkSheet { x: (shell.width - width) / 2; y: 104 }       // Add blinks… on an eyes swap set (rig_blinks.py): under the bar
    centre: [
        Stage { id: stage; anchors.fill: parent; typing: shell.typing },   // typing: F stays a letter (ViewControls.qml)
        EmptyHint {     // a new scene (the kit's empty state, INTERACTION.md 1.16): gone with the first layer
            visible: backend.layers.length === 0 && backend.tool === "move"
            anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: Theme.groupGap * 3 }
            width: Math.min(460, parent.width - 4 * Theme.gap)
            text: "Draw a shape (R), type (T), paint (B), or drop a file here."
        },
        ImportPanel {   // opened by the Import button, on the canvas (opening the Export sheet closes it)
            id: importPanel
            Connections { target: backend.importer; function onWantPanel() { shell.setImportOpen(true) } }
            anchors { right: parent.right; rightMargin: Theme.gap; top: parent.top; topMargin: Theme.gap }
        }
    ]
    menu: FilesMenu { id: fileMenu }    // ≡: New, Open, Open recent, Duplicate, Save a version … (kit; saving is automatic)
    right: [
        Inspector { id: settingsMove; anchors.fill: parent; bridge: backend; keyMarks: true; visible: backend.tool !== "draw"
                    highlight: backend.keys.props         // the settings whose keys are picked (key_select.py)
                    below: RigPoses { } },                // a rig in hand: its pose library (rig_poses.py)
        Inspector { id: settingsDraw; anchors.fill: parent; bridge: painter; title: "Brush"; visible: backend.tool === "draw"
                    below: PaintOn { } }      // under the brush: the paint layers and switches of what it paints on
    ]
    bottom: LayerTimeline {
        id: timeline
        anchors.fill: parent
        compact: shell.timelineNow.compact
        onResized: (h) => shell.setTimeline(false, h)   // its top edge, dragged (clamped above): every row again
        onCompactAsked: (on) => shell.setTimeline(on, null)
    }
}
