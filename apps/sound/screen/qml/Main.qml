import QtQuick
import RostrumKit

// RostrumSound: one workspace (apps/sound/DESIGN.md §2, shared/gui-kit/INTERACTION.md §1.1). Top bar: project-wide
// things only — ≡ (the menu), the song's name, the message and change count, the Loudness chip and Export once the
// song makes a sound, Search, Help. Centre: the arrangement, always, with its header strip (+ Add, ⏮ ▶, Record while
// armed, position, tempo · beats · key, zoom); under it the dock (Editor E / Mixer X; folds away). Left: the Library
// (Ctrl+L), pushing the arrangement on a wide window and floating over it below 1500 px. Right: the settings panel —
// the selection's settings, or the song while nothing is selected — or a kit sheet in its place (Export Ctrl+E, History Ctrl+H).
// Saving is automatic: there is no Save and no question on closing.
AppShell {
    id: shell
    bridge: backend
    appName: "RostrumSound"
    documentName: backend.docName
    saveWord: backend.isLive ? "Saved" : ""      // a song in a project folder is saved after every change
    helpEntries: guides
    readonly property bool wide: width >= 1500                       // the Library pushes instead of floating
    readonly property bool hasTracks: backend.tracks.some(r => !r.mix)
    readonly property bool hasSound: backend.tracks.some(r => !r.mix && r.sound)
    leftWidth: wide && workspace.library ? (width >= 1920 ? 280 : 260) : 0
    rightWidth: width >= 1920 ? 320 : width >= 1646 ? 296 : width >= 1366 ? 264 : 256
    bottomHeight: -Theme.gap        // no full-width bottom panel: the dock sits under the arrangement only (kit request)

    function openFileMenu() { fileMenu.openMenu() }      // (the scripted `file-menu` step)
    function openSettings() { settingsPanel.open() }     // (`settings`: Preferences)
    function openSong() { backend.clearSelection() }   // (`song-open`: the song in the settings panel; the header's tempo does the same)
    function openLibrary() { workspace.setLibrary(true) }   // (`library`)
    function openInKey() { dock.openInKey() }                // (`inkey-open`: the In key menu, open)
    function openGrid() { arrangement.openGrid() }          // (`grid-open`: the Grid menu, open)
    function openPicturePick() { backend.setPictureOpen(true); arrangement.picture.openItems() }     // (`picture-pick`)
    function openExport() { if (shell.hasSound) mixer.export.setOpen(true) }
    // Export: the kit's sheet in the settings panel's place (Ctrl+E; Ctrl+Shift+E again: AppShell), filled with Sound's
    // targets and settings (screensound/export.py, ExportSettings.qml); the job chip comes with it. Problems: the kit chip.
    exporter: shell.hasSound ? mixer.export : null
    noExportWhy: "Nothing to export yet: add a sound first"
    exportSettings: ExportSettings { }
    problems: mixer.problems
    // Ctrl+K named a key-map job only the window can run (palette.py): the file jobs, Preferences, Quit, the song's tempo, the grid,
    // else the kit's own (undo, Export, History, Guides, the Keys list ...: AppShell.runJob, the same call their keys make)
    function runSoundJob(job) {
        const files = { new: "new", open: "open", save_version: "version", duplicate_file: "duplicate" }
        if (files[job]) fileMenu.source.pickLater(files[job])
        else if (job === "preferences") settingsPanel.open()
        else if (job === "quit") Qt.quit()
        else if (job === "add_file") arrangement.addFromFile()
        else if (job === "record") recorder.toggleRecord()
        else if (job === "loudness") workspace.setDock("mixer")        // what a click on the loudness chip does
        else if (job === "sample_rate") settingsPanel.open()           // Preferences: where it is set
        else if (job === "tempo") openSong()
        else if (job === "grid") openGrid()
        else shell.runJob(job)
    }
    Connections { target: backend; function onJobWanted(job) { shell.runSoundJob(job) } }
    function used() { if (!shell.wide) workspace.setLibrary(false) }   // a narrow window's Library closes after use
    // Ctrl+N, Ctrl+O, Ctrl+S, Ctrl+Shift+S: the kit's FilesMenu makes them (from the key map)
    Shortcut { sequence: "Ctrl+I"; enabled: !OpenPopups.takes(["Ctrl+I"]); onActivated: arrangement.addFromFile() }
    Shortcut { sequence: "Ctrl+,"; enabled: !OpenPopups.takes(["Ctrl+,"]); onActivated: settingsPanel.open() }
    Shortcut { sequence: "Ctrl+Q"; enabled: !OpenPopups.takes(["Ctrl+Q"]); onActivated: Qt.quit() }
    Shortcut { sequence: "R"; enabled: !OpenPopups.takes(["R"]); onActivated: recorder.toggleRecord() }

    // ONE key map for the window (the kit's KeyMap, INTERACTION.md Part 2): every shared key and Sound's own
    // (screensound/keys.py) call backend.actions.key(job): an action on the selection when it applies (else the
    // message line says why), or Sound's own job (play, the playhead, nudges, the loop, zoom: keys.ROUTES). The jobs
    // in `skip` (files, undo, Ctrl+K, F1, R) keep their own Shortcuts here and in the kit's AppShell.
    readonly property bool typing: OpenPopups.typing      // a text field has the keys (the kit's one test of it)
    KeyMap { hub: backend.actions; typing: shell.typing; whileTyping: ["library"]; skip: backend.actions.skip }
    // A new selection (a click in the arrangement, the Editor or the Mixer, or a track made from the Library) gives the
    // keys back to the work: a text field (the Library's search, a settings row) never keeps them silently.
    // (A name field opened in place — a new section, M, F2 — keeps them: it is the work.)
    Connections { target: backend; function onPicksChanged() { if (shell.typing && backend.renaming === "") shell.contentItem.forceActiveFocus() } }
    menu: FilesMenu {    // ≡ (kit): New, Open, Open recent, Duplicate, Save a version, Show folder, Start screen; then Sound's own
        id: fileMenu
        extra: (shell.hasSound ? [{ value: "export", label: "Export…", keys: "Ctrl+E", group: "app" }] : []).concat([
                { value: "settings", label: "Preferences…", keys: "Ctrl+,", group: "app" },
                { value: "quit", label: "Quit", keys: "Ctrl+Q", group: "app" }])
        onPicked: (v) => { if (v === "export") shell.exporter.setOpen(true); else if (v === "settings") settingsPanel.open(); else if (v === "quit") Qt.quit() }
    }
    // the start screen (kit): at launch with nothing to reopen, or ≡ › Start screen…; over everything while shown
    StartScreen { id: startScreen; anchors.fill: parent; z: 100; onGuideAsked: (url) => shell.openGuide(url)
                  anchors.leftMargin: shell.guidesOpen ? (shell.guidesWidth || 0) : 0 }   // a guide opened from it shows beside it
    SettingsPanel { id: settingsPanel }
    actions: [          // the top bar's chips, then Export (kit TopBar: its `actions` slot sits before Search)
        Item {   // the chip's place is held too (an empty song leaves it empty), as Export's
            width: loudness.slotWidth; height: Theme.button
            LoudnessReadout { id: loudness; visible: shell.hasSound; compact: shell.width < 1366; anchors.verticalCenter: parent.verticalCenter }
        },
        Item {   // Export's place is always held (an empty song leaves it empty), so it showing never moves the bar's other items
            width: exportButton.implicitWidth; height: Theme.button
            Button { id: exportButton; visible: shell.hasSound; text: "Export"; kind: "primary"; down: mixer.export.open
                     anchors.verticalCenter: parent.verticalCenter
                     onClicked: mixer.export.setOpen(!mixer.export.open)
                     HoverTip { text: "Export the song (Ctrl+E). Ctrl+Shift+E exports again with the last settings"; hovered: parent.hovered } }
        }
    ]
    left: Library { anchors.fill: parent; visible: shell.wide && workspace.library; onUsed: shell.used() }
    centre: [
        Arrangement {
            id: arrangement
            anchors { left: parent.left; right: parent.right; top: parent.top; bottom: dock.visible ? dock.top : parent.bottom
                      bottomMargin: dock.visible ? Theme.gap : 0 }
            headerWidth: shell.width >= 1920 ? 200 : shell.width >= 1646 ? 180 : shell.width >= 1366 ? 160 : 140
            compact: shell.width < 1366
            onAddTrack: workspace.setLibrary(true)
        },
        Dock {
            id: dock
            visible: shell.hasTracks
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            // the arrangement keeps every row (the Master last) up to half the window, at least the ruler and two tracks
            room: parent.height - Math.max(160, Math.min(arrangement.needs, parent.height / 2)) - Theme.gap
            preferred: shell.width >= 1920 ? 460 : shell.width >= 1646 ? 380 : shell.width >= 1366 ? 320 : 300
        },
        Library {   // a narrow window: floats over the arrangement, closes after use
            visible: !shell.wide && workspace.library
            width: 260; z: 10
            anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
            onUsed: shell.used()
        }
    ]
    right: Item {   // the selection's actions first (backend.actions: kit ActionsSection), then its settings
        id: side
        anchors.fill: parent
        Inspector { visible: backend.selected !== ""; bridge: backend; actions: backend.actions   // the clean-up's result: under Cleanup
                    below: [LayerRows { }, CleanTakeBar { width: parent ? parent.width : 0; height: implicitHeight }]
                    anchors.fill: parent }
        SongSettings { visible: backend.selected === ""; anchors.fill: parent }
        // the amounts popover (kit): Quantise ▾, Humanise ▾, Transpose ▾ › By…, Repeat…, Start a bar here…; it opens
        // under the button or menu that asked for it, changes the song live, Enter keeps it as one step, Esc puts it back
        AmountsPopover { hub: backend.actions }
        Connections {
            target: backend
            function onCleanWanted() { backend.revealField("isolate") }
        }
    }
}
