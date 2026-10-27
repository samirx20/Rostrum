import QtQml
import QtQuick
import QtQuick.Dialogs
import QtQuick.Templates as T
import RostrumKit

// Rostrum2D, one workspace (apps/2d/DESIGN.md). Left edge: the tool rail (Rail2D.qml, the kit's ToolRail); centre: the canvas (the engine's frame). Right: the inspector (from the selected item's field operation, values at the playhead, key marks); while
// the Draw tool is on, the brush (the next stroke's settings, from the brush settings' own rules).
// Bottom, full width, always there: the timeline, which is also the layers list (a row and a bar per layer). Its top
// edge drags to make it taller or shorter.
AppShell {
    id: shell
    bridge: backend
    appName: "Rostrum2D"
    appIcon: "app-2d"                   // the kit's stand-in mark (shapes on blue) until the real icon is drawn
    helpEntries: guides                 // Help's guides (screen2d/session.py), in the kit's guide viewer
    documentName: files.hasProject ? files.name : "Untitled"   // the project (the kit's files: rostrum_gui/project_files.py)
    leftWidth: backend.library.open ? Theme.sidePanel : 0      // the Library drawer (LibraryDrawer.qml), beside the rail
    leftOver: true                      // it and the guides float over the canvas: the rail stays put, the canvas keeps its size
    rail: [ Rail2D { id: rail; visible: !startScreen.visible; anchors { top: parent.top; bottom: parent.bottom } } ]   // its own column, never over the canvas
    left: [ LibraryDrawer { anchors.fill: parent; visible: backend.library.open } ]
    onPressedIn: (area) => { if ((area === "right" || area === "bottom") && backend.create.typing) backend.create.commitText(backend.create.body) }   // a click in the settings or the timeline ends typing
    areaNames: ({ centre: "canvas", right: "settings", bottom: "timeline" })   // inspect_screen's words for the focused area
    // a project is live: every change is already on disk (the bar says nothing); a file outside a project is not
    saveState: backend.isLive ? "" : "unsaved"
    saveWords: "Changes here are not kept: this file is not in a project folder."
    // The frame drives the layout (the kit's FrameLayout.js, SPEC 2d-design-v2 §1.2): the settings panel's width and
    // the timeline's size and place (below the frame, or beside it for tall and square scenes) follow the scene's
    // aspect and the window; a panel edge dragged by hand wins (remembered in the person's settings). The canvas fits
    // the frame again only when that layout changes (Stage.qml), never when a panel's contents change.
    // ⊟ folds the timeline to its header (screen state, never the document).
    property bool timelineFolded: false
    // Each tool remembers its own timeline height (the-screen.md §2.7): every tool starts at the full height, so opening the Brush never resizes the canvas
    property var foldedFor: ({})
    readonly property string toolNow: backend.tool
    onToolNowChanged: timelineFolded = foldedFor[toolNow] === true
    function fold(on) { const m = Object.assign({}, foldedFor); m[toolNow] = on; foldedFor = m; timelineFolded = on }
    frameAspect: startScreen.visible ? 0 : (backend.frameInfo.width || 16) / (backend.frameInfo.height || 9)
    frameChrome: Qt.size(rail.width + Theme.gap + 2 * Theme.pad, 2 * Theme.pad)   // the rail's column, then the stage's padding round the well
    timelineLeast: 7 * Theme.row + Theme.gap      // the header row, then 6 rows of 28 px (204: §1.2), never the content
    frameFolded: timelineFolded && !bottomBeside ? timeline.compactHeight : -1
    bottomHeight: -Theme.gap            // the start screen is not the workspace: no timeline under it
    rightWidth: 0                       // ... and no settings panel under it (frameAspect is 0 only while it shows)

    // the tools: V move, P pen, B draw, Esc back to move (screen state, backend.setTool)
    // painting: the Brush group's other tools (paint_tool.py), and [ ] size, Shift+[ ] hardness (the brush ring shows it)
    readonly property bool painting: backend.tool === "draw" && !shell.typing && !OpenPopups.covered
    KeyShortcut { sequence: "E"; enabled: shell.painting; onActivated: backend.paintTool.use(backend.paintTool.now === "eraser" ? "brush" : "eraser") }
    KeyShortcut { sequence: "G"; enabled: shell.painting; onActivated: backend.paintTool.use(backend.paintTool.now === "fill" ? "brush" : "fill") }
    KeyShortcut { sequence: "I"; enabled: shell.painting; onActivated: backend.paintTool.use(backend.paintTool.now === "pick" ? "brush" : "pick") }
    KeyShortcut { sequence: "S"; enabled: shell.painting; onActivated: backend.paintTool.use(backend.paintTool.now === "select" ? "brush" : "select") }
    function brushBy(name, f, lo, hi) { painter.setValue(name, Math.max(lo, Math.min(hi, Math.round(painter.brushNow[name] * f * 100) / 100))) }
    KeyShortcut { sequence: "["; enabled: shell.painting; onActivated: shell.brushBy("size", 1 / 1.25, 0.5, 2000) }
    KeyShortcut { sequence: "]"; enabled: shell.painting; onActivated: shell.brushBy("size", 1.25, 0.5, 2000) }
    KeyShortcut { sequences: ["Shift+[", "{"]; enabled: shell.painting; onActivated: painter.setValue("hardness", Math.max(0, Math.round(painter.brushNow.hardness * 10 - 1) / 10)) }
    KeyShortcut { sequences: ["Shift+]", "}"]; enabled: shell.painting; onActivated: painter.setValue("hardness", Math.min(1, Math.round(painter.brushNow.hardness * 10 + 1) / 10)) }
    // Esc steps back one level at a time, the same whichever way the tool was entered (key, rail or a step): a rail menu closes, then
    // picked strokes are let go, then the tool is Select (the Brush's panel closes with the Brush; it is no step of its own)
    KeyShortcut { sequence: "Escape"; enabled: !OpenPopups.takes(["Esc"]) && (rail.menuOpen || (backend.tool !== "move" && backend.tool !== "pen" && !(backend.tool === "text" && backend.create.typing)))
               onActivated: { if (rail.menuOpen) rail.openGroup("")
                              else if (backend.strokeSelect.count > 0 || backend.strokeSelect.armed) backend.strokeSelect.clear()   // picked strokes first
                              else if (backend.tool === "bone" && backend.boneTool.end()) {}     // the bone chain ends first
                              else { rail.openGroup(""); backend.setTool("move") } } }
    // painting: 1 … 9 = 10 … 90 % brush opacity, 0 = 100 % (as in Photoshop)
    Repeater { model: 10; delegate: Item { required property int index
        KeyShortcut { sequence: String(index); enabled: shell.painting; onActivated: painter.setValue("opacity", index === 0 ? 1 : index / 10) } } }

    Connections { target: spaceKey; function onTapped() { if (!OpenPopups.covered) backend.togglePlay() } }   // a tap of Space plays; held, it pans (spacekey.py)
    // frame by frame, on the selected drawing (INTERACTION Part 2: , and . step drawings, = and − hold; Alt+arrows nudge)
    // , and . : the playhead to the previous / next thing that happens (a key, a marker, a drawing, a layer's start or end)
    // of the selected layers, or of everything when none is selected (backend.stepEvent, screen2d/key_edits.py)
    // A frame-by-frame layer: its drawings, and held down they flip through at the scene's speed (FlipThrough.qml)
    FlipThrough { id: flip }
    // The jobs of the key map that need the canvas, the rail or the painter (keys2d.WINDOW): the hub emits windowJob(job) and one
    // map answers it here. Every other key runs in Python (keys2d.ROUTES, the action list) or is bound where it is made (keys2d.SKIP).
    readonly property var windowJobs: ({
        paint_tool: () => { backend.paintTool.use("brush"); rail.openBrushes() },          // the brush panel (BrushFlyout.qml)
        pick_frame: () => backend.frameDrag.pick(),                                          // picks the frame (frame_drag.py)
        prev_event: () => painter.drawingId !== "" ? flip.press(-1) : backend.stepEvent(-1),  // , and . : the drawings, else the previous / next thing that happens
        next_event: () => painter.drawingId !== "" ? flip.press(1) : backend.stepEvent(1),
        prev_beat: () => { if (backend.soundtrack.hasBeats) backend.soundtrack.stepBeat(-1) },   // the project's sound, while it has a tempo
        next_beat: () => { if (backend.soundtrack.hasBeats) backend.soundtrack.stepBeat(1) },
        delete: () => { if (backend.strokeSelect.count > 0) backend.strokeSelect.remove(); else backend.layerCommand("delete") },   // picked strokes first
        library: () => backend.library.setOpen(!backend.library.open),
        add_file: () => rail.addFile(),                                                      // the kit's add_file: the file picker
        quit: () => Qt.quit(),
        new_drawing: () => painter.newFrame(false),
        copy_drawing: () => painter.newFrame(true),
        onion: () => painter.setOnion(!painter.onionOn),
        hold_longer: () => { if (painter.drawingId !== "") painter.holdBy(1) },
        hold_shorter: () => { if (painter.drawingId !== "") painter.holdBy(-1) },
        zoom_in: () => viewControls.key("zoom_in"), zoom_out: () => viewControls.key("zoom_out"),
        fit_all: () => viewControls.key("fit_all"), actual_size: () => viewControls.key("actual_size"),
        fit: () => viewControls.key("fit"), fit_everything: () => viewControls.key("fit_everything"), look_through: () => viewControls.key("look_through")
    })
    Connections { target: backend.actions; function onWindowJob(job) { const run = shell.windowJobs[job]; if (run) run(); else shell.runJob(job) } }   // else the kit's (undo, Export, History, Guides, Keys, About ...)
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
        typing: shell.typing            // a Ctrl command a text box doesn't use still runs from a kit field (KeyMap)
        skip: backend.actions.skip
    }
    KeyShortcut { sequences: ["Return", "Enter"]; enabled: shell.canvasKeys && !OpenPopups.takes(["Enter"]) && backend.create.canEdit       // the selected text: type in it
               onActivated: backend.create.editText(backend.selected) }
    KeyShortcut { sequences: ["Return", "Enter"]; enabled: shell.canvasKeys && !OpenPopups.takes(["Enter"]) && backend.pen.canEditPoints
               onActivated: backend.pen.editPoints(true) }                                               // the selected path: edit its points
    KeyShortcut { sequences: ["Return", "Enter"]; enabled: shell.canvasKeys && !OpenPopups.takes(["Enter"]) && (backend.selected, backend.canGoIn())
               onActivated: backend.goIn() }                                                             // the picked group: its first layer (levels.py)
    // Esc steps back one level (the kit's ladder, selection_rules.esc_step): close an open panel, else clear
    KeyShortcut {
        sequence: "Escape"; enabled: shell.canvasKeys && !OpenPopups.takes(["Esc"])
        onActivated: {
            const open = shell.guidesOpen || backend.exporter.open || importPanel.shown || fileMenu.menuOpen || rail.flyoutOpen
            if (backend.stepBack({ popover: open }) === "close") {
                shell.closeGuides(); shell.setExportOpen(false); shell.setImportOpen(false)
                fileMenu.closeMenu(); rail.openGroup("")
            }
        }
    }

    function setExportOpen(open) { backend.exporter.setOpen(open); if (open) importPanel.shown = false }
    function setImportOpen(open) { importPanel.shown = open; if (open) backend.exporter.setOpen(false) }
    function setFileMenuOpen(open) { if (open) fileMenu.openMenu(); else fileMenu.closeMenu() }
    function openSceneMenu() { sceneCrumb.open() }       // (the scripted `scenemenu open` step)
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
        ViewControls { id: viewControls; view: stage.view; look: stage.look; typing: shell.typing; onFitSelection: stage.fitSelection()
                       Component.onCompleted: stage.viewControls = viewControls },   // "Fit · 57 % ▾", off the canvas
        Button { text: "Export"; kind: "primary"; down: backend.exporter.open; onClicked: shell.setExportOpen(!backend.exporter.open) }
    ]
    // the start screen (kit): at launch with nothing to reopen, or the menu › Start screen…; over everything while shown
    StartScreen { id: startScreen; anchors.fill: parent; z: 100; onGuideAsked: (url) => shell.openGuide(url)
                  anchors.leftMargin: shell.guidesOpen ? (shell.guidesWidth || 0) : 0 }   // a guide opened from it shows beside it
    Connections { target: startScreen; function onVisibleChanged() { if (startScreen.visible) shell.closeGuides() } }   // the start screen is over everything: no drawer left open beside it
    StaggerPopover { }   // the context bar's Stagger… (stagger.py): under the bar
    DepthPopover { x: (shell.width - width) / 2; y: 104 }     // Set depth ▾ › Other depth… (depth_typed.py): under the bar
    SoundCuePopover { x: (shell.width - width) / 2; y: 104 }  // Add a sound here… (sound_cue_pick.py): under the bar
    centre: [
        Stage { id: stage; anchors.fill: parent; typing: shell.typing; coverLeft: shell.overLeft; drawerRight: rail.brushPanelRight },   // typing: F stays a letter (ViewControls.qml)
        SnapMarks { stage: stage },     // a drag's equal-gap brackets and gap sizes, over the snap lines (SnapMarks.qml)
        ImportPanel {   // opened by the rail's Media › Import…, on the canvas (opening the Export sheet closes it)
            id: importPanel
            Connections { target: backend.importer; function onWantPanel() { shell.setImportOpen(true) } }
            anchors { right: parent.right; rightMargin: Theme.gap; top: parent.top; topMargin: Theme.gap }
        }
    ]
    crumb: SceneCrumb { id: sceneCrumb }   // › Main ▾: the scene shown; its list switches scene or makes a New scene (scenes.py)
    menu: FilesMenu { id: fileMenu       // and 2D's own row: a song made in RostrumSound, copied into this project (song_add.py)
                      extra: [{ value: "add_song", label: "Add a song from RostrumSound…", group: "app" }]
                      onPicked: (v) => { if (v === "add_song") songDialog.open() } }
    FileDialog {     // a Sound project's song (its docs\<name>.trk); copied in, the original stays
        popupType: T.Popup.Item     // inside the window, never a window of its own (a check window's dialog drew nowhere it could be seen or clicked)
        id: songDialog
        objectName: "songDialog"
        title: "Add a song from RostrumSound"
        nameFilters: ["RostrumSound songs (*.trk)"]
        onAccepted: backend.soundtrack.addSong(selectedFile.toString())
    }    // the app mark's menu: New, Open, Open recent, Duplicate, Save a version … (kit; saving is automatic)
    right: [
        Inspector { id: settingsMove; anchors.fill: parent; bridge: backend; keyMarks: true; effects: true; actions: backend.actions
                    visible: backend.tool !== "draw" && !backend.stretch.shown   // typing: the text's settings (typing_session.py selects it)
                    highlight: backend.keys.props         // the settings whose keys are picked (key_select.py)
                    above: Column { width: parent.width    // the picked keys (KeyPanel.qml), then a rig in hand: its pose library (rig_poses.py)
                                    GapRow { }             // 3+ layers evenly apart: their Gap (GapRow.qml)
                                    KeyPanel { }
                                    RigPoses { } }
                    below: Column {                       // a frame-by-frame layer: the same drawing tools as in Draw (DrawEachFrame.qml)
                        width: parent.width; visible: painter.drawingId !== ""; topPadding: Theme.gap
                        Text { height: Theme.row; verticalAlignment: Text.AlignVCenter; text: "Drawings"
                               color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont }
                        DrawEachFrame { visible: true }
                    }
                    sheets: [   // Lip sync… / Add blinks… in the panel's place; each is made when first opened (FirstUse, H66)
                        FirstUse { anchors.fill: parent; visible: backend.lipsync.open; when: visible; sourceComponent: Component { LipSyncSheet { } } },
                        FirstUse { anchors.fill: parent; visible: backend.blinks.open; when: visible; sourceComponent: Component { BlinkSheet { } } } ] },
        FirstUse { id: settingsDraw; anchors.fill: parent; visible: backend.tool === "draw"; when: visible; ahead: true   // the painting settings: made while idle after the window shows
                   sourceComponent: Component {
                       Inspector { anchors.fill: parent; bridge: painter
                                   above: BrushHead { }      // the brush's own row (or ‹ back while editing it), then its quick rows
                                   below: PaintTarget { } } } },   // Edit brush ›, Painting on (Layer, Inside the outline, Draw each frame), paint layers
        AnimPanel { anchors.fill: parent; allowed: backend.tool !== "draw" }    // a stretch picked in the timeline: its animation, over the layer's settings (stretch_select.py)
    ]
    bottom: LayerTimeline {
        id: timeline
        visible: !startScreen.visible
        anchors.fill: parent
        compact: shell.timelineFolded && !shell.bottomBeside
        canCompact: !shell.bottomBeside
        onResized: (h) => { shell.fold(false); shell.setAsked("bottom", h) }   // its top edge, dragged: the person's height
        // the person asked for the room (the button): a view at Fit fits the frame to it, so no empty band is left (critic
        // r10); a tool's own remembered height and a zoomed-in view keep the picture where it is
        onCompactAsked: (on) => { const fit = stage.view.fitted; shell.fold(on); if (fit) Qt.callLater(stage.fitAll) }
        compactExtra: backend.soundtrack.present ? Theme.row + 2 : 0      // the Sound row stays
        frameTicks: painter.drawingId !== ""
        rows: LayerRows { ruler: timeline.ruler; labelWidth: timeline.labelWidth; compact: timeline.compact }
        curves: CurveEditor { visible: backend.curves.on; ruler: timeline.ruler; labelWidth: timeline.labelWidth }
        overlay: Item {
            BeatLines { ruler: timeline.ruler; bottomY: timeline.height - Theme.gap }   // Show beats (the Sound row's menu): beat and bar lines
            ReadyLine { ruler: timeline.ruler }     // the frames a scrub shows at once (scrub_ahead.py)
        }
        Connections { target: timeline.ruler; function onScrubbed(t) { backend.soundtrack.scrub(t) } }   // a scrub plays a short burst of the sound
        RulerMenu { ruler: timeline.ruler }     // the ruler's right-click (markers, work area, go to) and the work area band
    }
}
