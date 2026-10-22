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
    documentName: files.label           // the project, and a dot while there are unsaved changes (screen2d/files.py)
    property bool leaving: false        // closing without asking (session.py replaces the window, or the answer was given)
    onClosing: (close) => fileFlow.closing(close)
    leftWidth: 0
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
    Shortcut { sequence: "V"; onActivated: backend.setTool("move") }
    Shortcut { sequence: "P"; onActivated: backend.setTool(backend.tool === "pen" ? "move" : "pen") }
    Shortcut { sequence: "B"; onActivated: backend.setTool("draw") }
    Shortcut { sequence: "Escape"; enabled: backend.tool === "draw"; onActivated: backend.setTool("move") }

    Shortcut { sequence: "Space"; onActivated: backend.togglePlay() }
    Shortcut { sequence: "Alt+Left"; onActivated: painter.goFrame(-1) }       // frame by frame, on the selected drawing
    Shortcut { sequence: "Alt+Right"; onActivated: painter.goFrame(1) }
    Shortcut { sequence: "Alt+N"; onActivated: painter.newFrame(false) }
    Shortcut { sequence: "Alt+Shift+N"; onActivated: painter.newFrame(true) }
    Shortcut { sequence: "Alt+Up"; onActivated: painter.holdBy(1) }
    Shortcut { sequence: "Alt+Down"; onActivated: painter.holdBy(-1) }
    Shortcut { sequence: "Alt+O"; onActivated: painter.setOnion(!painter.onionOn) }
    // select, then act: every action's key comes from the one key map (screen2d/keys2d.py) and runs through the one
    // action list (backend.actions): only when valid now, else the status line says why. Not while typing.
    readonly property bool typing: Window.activeFocusItem !== null && typeof Window.activeFocusItem.selectAll === "function"
    readonly property bool canvasKeys: backend.tool === "move" && !typing
    KeyMap {
        hub: backend.actions
        enabled: !shell.typing
        skip: backend.actions.keys.map(k => k.job).filter(j => backend.actions.jobs.indexOf(j) < 0)   // keys run here
    }
    Shortcut { sequence: "Ctrl+A"; enabled: shell.canvasKeys; onActivated: backend.selectAllLayers() }
    // Esc steps back one level (the kit's ladder, selection_rules.esc_step): close an open panel, else clear
    Shortcut {
        sequence: "Escape"; enabled: shell.canvasKeys
        onActivated: {
            const open = exportPanel.shown || importPanel.shown || problemsPanel.shown || fileMenu.menuOpen || addMenu.menuOpen
            if (backend.stepBack({ popover: open }) === "close") {
                shell.setExportOpen(false); shell.setImportOpen(false); shell.setProblemsOpen(false)
                fileMenu.menuOpen = false; addMenu.menuOpen = false
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

    function setExportOpen(open) { exportPanel.shown = open; if (open) { importPanel.shown = false; problemsPanel.shown = false } }
    function setImportOpen(open) { importPanel.shown = open; if (open) { exportPanel.shown = false; problemsPanel.shown = false } }
    function setProblemsOpen(open) { problemsPanel.shown = open; if (open) { exportPanel.shown = false; importPanel.shown = false } }
    function setFileMenuOpen(open) { fileMenu.menuOpen = open }
    function askClose() { shell.close() }
    function openLayerMenu(id) { timeline.openMenu(id) }
    function openCanvasMenu() { stage.openMenu() }
    function setAddOpen(open) { if (open) addMenu.menuOpen = true; else addMenu.menuOpen = false }

    actions: [
        UndoRedo { },
        Button {        // only while something is wrong (screen2d/problems.py)
            visible: backend.problems.count > 0
            text: backend.problems.count + (backend.problems.count === 1 ? " problem" : " problems")
            down: problemsPanel.shown; onClicked: shell.setProblemsOpen(!problemsPanel.shown)
        },
        AddMenu { id: addMenu },
        Button { text: "Import"; down: importPanel.shown; onClicked: shell.setImportOpen(!importPanel.shown) },
        IconButton { glyph: "↗"; tip: "Export"; down: exportPanel.shown; onClicked: shell.setExportOpen(!exportPanel.shown) }
    ]
    FileFlow { id: fileFlow; window: shell }
    centre: [
        Stage { id: stage; anchors.fill: parent },
        ExportPanel {   // opened by the Export button; docked on the canvas's right edge, beside the inspector (never over it)
            id: exportPanel
            anchors { right: parent.right; rightMargin: Theme.gap; top: parent.top; topMargin: Theme.gap }
        },
        ImportPanel {   // opened by the Import button; same place as the export panel (one open at a time)
            id: importPanel
            anchors { right: parent.right; rightMargin: Theme.gap; top: parent.top; topMargin: Theme.gap }
        },
        ProblemsPanel { // opened by the Problems button; same place again
            id: problemsPanel
            anchors { right: parent.right; rightMargin: Theme.gap; top: parent.top; topMargin: Theme.gap }
        }
    ]
    leading: FileMenu { id: fileMenu; onAct: (key) => fileFlow.act(key) }
    right: [
        Inspector { anchors.fill: parent; bridge: backend; keyMarks: true; visible: backend.tool !== "draw" },
        Inspector { anchors.fill: parent; bridge: painter; title: "Brush"; visible: backend.tool === "draw" }
    ]
    bottom: LayerTimeline {
        id: timeline
        anchors.fill: parent
        compact: shell.timelineNow.compact
        onResized: (h) => shell.setTimeline(false, h)   // its top edge, dragged (clamped above): every row again
        onCompactAsked: (on) => shell.setTimeline(on, null)
    }
}
