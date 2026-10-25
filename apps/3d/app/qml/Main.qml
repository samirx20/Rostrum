import QtQuick
import RostrumKit

// Rostrum3D's window (docs/3d-design/SPEC.md §1, mockup 01). Header: ≡ (the kit's File menu), Rostrum3D, the project ›
// shot crumb, Saved · N changes, the Build | Animate | Render pages, ↶ ↷, Search, View (shot / free camera), Look
// (Quick | Final, when the viewport offers it), Materials, Render (F12), ?. Left edge: the tool rail (Rail3D). Centre:
// the viewport, and over it the last render while one is shown. Right: the settings panel (the kit's grid: the kind's
// own group open, changed groups open, the rest a row of names; while a stretch is picked on the timeline, the kit's
// animation panel over it). Bottom, full width: the kit's key timeline, its rows the scene list with its keys on the
// same rows (SceneList), taller on the Animate page. The start screen (kit) covers it all at a launch with
// nothing to reopen. The render sheet (F12, Render, Ctrl+E) is the kit's export sheet in the settings panel's place.
// The Render page (Ctrl+3): the shots and the render queue at the bottom (RenderPage), the shot's render settings on
// the right (RenderSettings), no header Render (a control never shows twice).
AppShell {
    id: shell
    bridge: backend
    appName: "Rostrum3D"
    helpEntries: guides                 // Help's guides (main.py), in the kit's guide viewer
    documentName: backend.docName
    saveWord: typeof files !== "undefined" && files.hasProject ? "Saved" : ""   // a scene in a project folder saves after every change
    leftWidth: 0
    rightWidth: width >= 1920 ? 340 : width >= 1646 ? 300 : 280
    bottomHeight: backend.page === "build" ? 204 : 284   // Animate: more key rows; Render: the shots and the queue
    Behavior on bottomHeight { NumberAnimation { duration: Theme.reveal; easing.type: Theme.revealEasing } }
    exporter: backend.exporter
    exportSettings: ExportSettings3D { }
    exportSummary: RenderEstimate { }

    function openFileMenu() { fileMenu.openMenu() }               // (the scripted `file-menu` step)
    function openRailGroup(id) { return rail.openGroup(id) }      // (the scripted `rail <group>` step)
    function openRailPanel(id) { rail.openPanel(id) }             // (the scripted `panel <id>` step)
    function openDrawings() { rail.openDrawings() }                // (the scripted `drawings` step)
    function openContext(id) { vp3d.openContext(id) }              // (the scripted `context <id | ->` step)
    function openMaterials() { materialsList.openFrom(materialsChip) }
    function openPicker() { materialRow.openPicker() }           // (the scripted `picker` step)
    function openShots() {         // read as it opens: the shown shot checked, "from this view" only off the shot camera
        shotsMenu.entries = backend.shotEntries(viewport.mode)
        shotsMenu.openFrom(crumb, "left")
    }
    function openView() {          // its choices are read as it opens (the light choice follows the selection)
        viewMenu.entries = [{ value: "shot", label: "Shot camera", checked: viewport.mode === "shot" },
                            { value: "free", label: "Free camera", checked: viewport.mode === "free" }]
                           .concat(viewport.canThroughLight ? [{ value: "light", label: "Through the selected light", checked: viewport.mode === "light" }] : [])
        viewMenu.openFrom(viewChip, "right")
    }

    KeyShortcut { sequence: "Space"; onActivated: backend.togglePlay() }
    KeyShortcut { sequence: "Left"; onActivated: backend.setFrame(backend.frame - 1) }
    KeyShortcut { sequence: "Right"; onActivated: backend.setFrame(backend.frame + 1) }
    KeyShortcut { sequence: "F12"   // the render sheet; on the Render page, the shown shot's Render (next in the queue)
               onActivated: backend.page === "render" ? backend.renderQueue.renderNext(backend.shotInfo.id) : backend.exporter.openFor() }
    KeyShortcut { sequence: "Shift+F"; onActivated: viewport.toggleLook() }   // Look: Quick <-> Final
    KeyShortcut { sequence: "Escape"; enabled: backend.renderJob.state === "done" || backend.renderJob.state === "failed"
               onActivated: backend.renderJob.dismiss() }
    KeyShortcut { sequence: "Escape"; enabled: backend.renderJob.state === "running"; onActivated: backend.renderJob.cancel() }
    KeyShortcut { sequence: "Escape"; enabled: backend.renderQueue.shown.state === "done"; onActivated: backend.renderQueue.shown.dismiss() }
    readonly property bool renderIdle: (backend.renderJob.state === "idle" || backend.renderJob.state === "") && backend.renderQueue.shown.state === ""
    KeyShortcut { sequence: "Escape"; enabled: backend.stretch.shown && !meshEdit.on && !paintMode.on && shell.renderIdle; onActivated: backend.stretch.clear() }   // back to the item
    KeyShortcut { sequence: "Escape"; enabled: !backend.stretch.shown && backend.keys.count > 1 && !meshEdit.on && !paintMode.on && shell.renderIdle; onActivated: backend.keys.clear() }
    KeyShortcut { sequence: "Escape"   // nothing else wants it: let go of the selection (the Scene panel shows)
               enabled: !backend.stretch.shown && backend.keys.count <= 1 && backend.selected !== "" && !meshEdit.on && !paintMode.on && !viewport.bones.on && !startScreen.visible && shell.renderIdle
               onActivated: backend.select("") }
    readonly property bool typing: activeFocusItem !== null && activeFocusItem.cursorPosition !== undefined
    // Edit mesh (mesh_edit_qt.py): Tab in and out (Esc leaves too), 1 points, 2 edges, 3 faces
    // not while typing in a field: there Tab goes to the next field (Width, Tab, Height)
    KeyShortcut { sequence: "Tab"; enabled: !startScreen.visible && (meshEdit.on || backend.selected !== "") && !typing
               onActivated: meshEdit.toggle() }
    // Paint (paint_mode_qt.py): B in and out on the selected mesh (Esc leaves too)
    KeyShortcut { sequence: "B"; enabled: !startScreen.visible && (paintMode.on || paintMode.can) && !typing; onActivated: paintMode.toggle() }
    KeyShortcut { sequence: "Escape"; enabled: paintMode.on; onActivated: paintMode.leave() }
    KeyShortcut { sequence: "Escape"; enabled: meshEdit.on; onActivated: meshEdit.escape() }   // the Knife drops its line first
    KeyShortcut { sequence: "Alt+Z"; enabled: meshEdit.on && !meshEdit.needsEdit; onActivated: meshEdit.toggleXray() }   // X-ray
    KeyShortcut { sequence: "K"; enabled: meshEdit.on && !meshEdit.needsEdit && !typing; onActivated: meshEdit.toggleKnife() }
    KeyShortcut { sequence: "Return"; enabled: meshEdit.knifing; onActivated: meshEdit.knifeApply() }
    KeyShortcut { sequence: "Enter"; enabled: meshEdit.knifing; onActivated: meshEdit.knifeApply() }
    KeyShortcut { sequence: "1"; enabled: meshEdit.on && !meshEdit.needsEdit; onActivated: meshEdit.setKind("points") }
    KeyShortcut { sequence: "2"; enabled: meshEdit.on && !meshEdit.needsEdit; onActivated: meshEdit.setKind("edges") }
    KeyShortcut { sequence: "3"; enabled: meshEdit.on && !meshEdit.needsEdit; onActivated: meshEdit.setKind("faces") }
    KeyShortcut { sequence: "`"; enabled: viewport.hasShot && !startScreen.visible   // shot camera <-> free camera
               onActivated: viewport.setMode(viewport.mode === "shot" ? "free" : "shot") }
    KeyShortcut { sequence: "Delete"; enabled: backend.adder.canDelete; onActivated: backend.adder.remove() }
    KeyShortcut { sequence: "Ctrl+D"; enabled: backend.adder.canDuplicate; onActivated: backend.adder.duplicate() }
    KeyShortcut { sequence: "Ctrl+1"; onActivated: backend.setPage("build") }
    KeyShortcut { sequence: "Ctrl+2"; onActivated: backend.setPage("animate") }
    KeyShortcut { sequence: "Ctrl+3"; onActivated: backend.setPage("render") }
    KeyShortcut { sequence: "R"; enabled: !startScreen.visible; onActivated: rail.openGroup("shapes") }
    KeyShortcut { sequence: "T"; enabled: !startScreen.visible; onActivated: rail.openGroup("type") }
    KeyShortcut { sequence: "L"; enabled: !startScreen.visible; onActivated: rail.openGroup("lights") }
    KeyShortcut { sequence: "C"; enabled: !startScreen.visible; onActivated: rail.openGroup("camera") }
    KeyShortcut { sequence: "P"; enabled: !startScreen.visible && backend.page === "animate" && !typing; onActivated: rail.openPanel("poses") }
    KeyShortcut { sequence: "O"; enabled: !startScreen.visible && backend.page === "animate" && !typing; onActivated: viewport.onionSkin.toggle() }
    // the gizmo (gizmo_qt.py): V all handles, W move, E turn, S scale; K keys what it moved; D held: the pivot
    KeyShortcut { sequence: "V"; enabled: !startScreen.visible; onActivated: gizmo.setShow("all") }
    KeyShortcut { sequence: "W"; enabled: !startScreen.visible; onActivated: gizmo.setShow("move") }
    KeyShortcut { sequence: "E"; enabled: !startScreen.visible; onActivated: gizmo.setShow("turn") }
    KeyShortcut { sequence: "S"; enabled: !startScreen.visible; onActivated: gizmo.setShow("scale") }
    KeyShortcut { sequence: "K"; enabled: !startScreen.visible && backend.selected !== "" && !meshEdit.on; onActivated: gizmo.keyMoved() }

    menu: FilesMenu {    // ≡ (kit): New, Open, Open recent, Duplicate, Save a version, Show folder, Start screen; then Export
        id: fileMenu
        extra: [{ value: "export", label: "Export…", keys: "Ctrl+E", group: "app" }]
        onPicked: (v) => { if (v === "export") shell.exporter.setOpen(true) }
    }
    StartScreen { id: startScreen; anchors.fill: parent; z: 100; onGuideAsked: (url) => shell.openGuide(url)
                  anchors.leftMargin: shell.guidesOpen ? (shell.guidesWidth || 0) : 0 }

    crumb: Item {   // "› Hero 01 ▾": the shot this screen shows; its list switches to another shot or makes a new one
        id: crumb
        implicitWidth: crumbRow.implicitWidth + 2 * Theme.grid; implicitHeight: Theme.button
        Rectangle { anchors.fill: parent; radius: Theme.radiusCtl; color: crumbArea.containsMouse ? Theme.hover : "transparent" }
        Row {
            id: crumbRow
            x: Theme.grid; anchors.verticalCenter: parent.verticalCenter; spacing: Theme.grid
            Text { visible: shell.documentName !== ""; text: "›"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body; anchors.verticalCenter: parent.verticalCenter }
            Text { text: backend.shotInfo.label; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
                   font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
            Chevron { color: Theme.fg3; anchors.verticalCenter: parent.verticalCenter }
        }
        MouseArea { id: crumbArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: shell.openShots() }
        Menu {
            id: shotsMenu
            width: 200
            onPicked: (v) => v === "+view" ? backend.newShotFromView() : v === "+shot" ? backend.showShot(backend.adder.add("shot")) : backend.showShot(v)
        }
    }
    tools: Segmented {   // the pages (Ctrl+1 / 2 / 3)
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        options: [{ value: "build", label: "Build" }, { value: "animate", label: "Animate" }, { value: "render", label: "Render" }]
        current: backend.page
        onPicked: (v) => backend.setPage(v)
    }
    actions: [
        Button {    // View: which camera the viewport looks through
            id: viewChip
            anchors.verticalCenter: parent.verticalCenter
            kind: "ghost"
            text: "View  " + (({ shot: "Shot camera", free: "Free camera", light: "Through the light" })[viewport.mode] || "Shot camera")
            onClicked: shell.openView()
            Menu {
                id: viewMenu
                width: 210
                onPicked: (v) => viewport.setMode(v)
            }
        },
        Row {        // Look: Quick | Final (Shift+F)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.gap
            Text { text: "Look"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body; anchors.verticalCenter: parent.verticalCenter }
            Segmented {
                anchors.verticalCenter: parent.verticalCenter
                options: [{ value: "quick", label: "Quick" }, { value: "final", label: "Final" }]
                current: viewport.look
                onPicked: (v) => viewport.setLook(v)
            }
        },
        Button {    // the project's materials: pick one to edit it, or make a new one
            id: materialsChip
            anchors.verticalCenter: parent.verticalCenter
            kind: "ghost"; text: "Materials"
            onClicked: shell.openMaterials()
            MaterialsList { id: materialsList }    // ball, name, how many use it; click edits, drag gives
        },
        RenderButton { anchors.verticalCenter: parent.verticalCenter; visible: backend.page !== "render" }   // the Render page has its own
    ]
    rail: Rail3D { id: rail; height: parent ? parent.height : 0 }
    centre: [
        Viewport { id: vp3d; anchors.fill: parent },
        RenderView { anchors.fill: parent },
        RenderView { anchors.fill: parent; job: backend.renderQueue.shown }   // a finished render picked in the queue
    ]
    right: Item {   anchors.fill: parent   // the selection's settings, or the Scene (the shot's view, sky and values) with nothing selected
        Inspector {
            anchors.fill: parent; bridge: backend; keyMarks: true; actions: backend.actions; visible: backend.selected !== "" && !meshEdit.on && !paintMode.on && !backend.stretch.shown
            below: Column {     // the item's material (SPEC §6.1): its row with the picker, then the material's own settings inline
                width: parent ? parent.width : 0
                MaterialRow { id: materialRow; width: parent.width }
                Repeater {
                    model: backend.mats.rows
                    delegate: InspectorRow { bridge: backend.mats; instant: backend.mats.rows.instant }
                }
            }
        }
        ScenePanel { anchors.fill: parent; visible: backend.selected === "" && backend.page !== "render" }
        RenderSettings { anchors.fill: parent; visible: backend.selected === "" && backend.page === "render" }   // the shot's render settings
        MeshEditPanel { anchors.fill: parent; visible: meshEdit.on }   // Edit mesh: points / edges / faces and their actions
        PaintPanel { anchors.fill: parent; visible: paintMode.on }     // Paint: Brush, then Paint layers (mockup 06)
        FirstUse { anchors.fill: parent; visible: backend.lipsync.open; when: visible; sourceComponent: Component { LipSyncSheet { } } }   // Lip sync… on a mouth group (the kit's sheet)
        AnimPanel { anchors.fill: parent; allowed: !meshEdit.on && !paintMode.on }      // a stretch picked on the timeline: that animation (‹ or Esc: back)
    }
    bottom: [
        SceneList { anchors.fill: parent; visible: backend.page !== "render" },
        RenderPage { anchors.fill: parent; visible: backend.page === "render" }   // the shots and the render queue
    ]
}
