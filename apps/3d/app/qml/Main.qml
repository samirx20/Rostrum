import QtQuick
import RostrumKit

// Rostrum3D's window (docs/3d-design/SPEC.md §1, mockup 01). Header (the kit's one merged bar, header-design SPEC §3):
// the app mark ▾ (the kit's File menu), the project › shot crumb and, beside it while the view isn't the shot's, Make this
// the shot, the Build | Animate | Render pages (centred), Undo, Redo, History, Search, the camera and look in one button
// ("Shot camera · Quick ▾": ViewLookButton), Render, ?.
// Left edge: the tool rail (Rail3D; the Materials list opens from its ball). Centre:
// the viewport, and over it the last render while one is shown. Right: the settings panel (the kit's grid: the kind's
// own group open, changed groups open, the rest a row of names; while a stretch is picked on the timeline, the kit's
// animation panel over it). Bottom, full width: the kit's key timeline, its rows the scene list with its keys on the
// same rows (SceneList), taller on the Animate page. The start screen (kit) covers it all at a launch with
// nothing to reopen. The render sheet (F12, Render, Ctrl+E) is the kit's export sheet in the settings panel's place.
// The Render page (Alt+3): the shots and the render queue at the bottom (RenderPage), the shot's render settings on
// the right (RenderSettings), no header Render (a control never shows twice).
AppShell {
    id: shell
    bridge: backend
    appName: "Rostrum3D"
    appIcon: "app-3d"                   // the kit's stand-in mark until the real icon is drawn
    // a scene in a project folder saves after every change (the bar says nothing); the sample or a scratch scene does not
    saveState: typeof files !== "undefined" && files.hasProject ? "" : "unsaved"
    saveWords: "Changes to this scene are not kept: it is not in a project folder."
    helpEntries: guides                 // Help's guides (main.py), in the kit's guide viewer
    documentName: backend.docName
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
    function openMaterials() { rail.openPanel("materials") }    // (the scripted `materials` step; Ctrl+K)
    function openPicker() { materialRow.openPicker() }           // (the scripted `picker` step)
    function openShots() {         // read as it opens: the shown shot checked, Frame the selection while something is
                                   // selected, "from this view" only off the shot camera
        shotsMenu.entries = backend.shotEntries(viewport.mode)
        shotsMenu.openFrom(crumbBox, "left")
    }
    function openView() { viewLook.openMenu() }                  // (the scripted `view` step)

    // Every key comes from the one key map (screen3d/keys3d.py: the shared keys mean what they mean in 2D and Sound, 3D's
    // own on keys no shared job uses), the same list as the Keys sheet (Ctrl+/) and Ctrl+K. A pressed key goes to the hub
    // (key_routes3d.KeyHub3D): a mode under way first (the Knife's Enter, the bones being placed), then a route, an
    // action, or one of the window's own jobs below. Esc: the kit's one Esc closes the newest popup or sheet first (its
    // KeyMap shortcut waits meanwhile), then the hub takes one step of 3D's written order (screen3d/esc3d.py).
    readonly property bool typing: activeFocusItem !== null && activeFocusItem.cursorPosition !== undefined
    KeyMap { hub: backend.actions; typing: shell.typing; skip: backend.actions.skip }
    readonly property var windowJobs: ({
        clay_tool: () => viewport.clay.toggle(),
        shapes_menu: () => rail.openGroup("shapes"), type_menu: () => rail.openGroup("type"),
        lights_menu: () => rail.openGroup("lights"), camera_menu: () => rail.openGroup("camera"),
        add_file: () => { if (backend.page === "build") rail.openGroup("import") },     // Ctrl+I: the Import group
        poses_panel: () => { if (backend.page === "animate") rail.openPanel("poses") },
        materials_list: () => rail.openPanel("materials"),
        quit: () => Qt.quit()
    })
    Connections { target: backend.actions; function onWindowJob(job) { const run = shell.windowJobs[job]; if (run) run(); else shell.runJob(job) } }   // else the kit's (undo, Export, History, Guides, Keys …)

    menu: FilesMenu {    // the mark's menu (kit): New, Open, Open recent, Duplicate, Save a version, Show folder, Start screen; then Export
        id: fileMenu
        extra: [{ value: "export", label: "Export…", keys: "Ctrl+E", group: "app" }]
        onPicked: (v) => { if (v === "export") shell.exporter.setOpen(true) }
    }
    StartScreen { id: startScreen; anchors.fill: parent; z: 100; onGuideAsked: (url) => shell.openGuide(url)
                  anchors.leftMargin: shell.guidesOpen ? (shell.guidesWidth || 0) : 0 }

    crumb: Row {   // "› Hero 01 ▾": the shot this screen shows; its list switches to another shot or makes a new one. Then,
                   // only while the view isn't the shot's, Make this the shot (3d-simplicity SPEC §5): the shown shot's
                   // camera to this view, one undo step; resting on it draws, in the view, the frame the shot would take.
                   // Only empty space and the pages are to its right, so its going after the click moves nothing under
                   // the pointer
        id: crumb
        spacing: Theme.gap
        Item {
            id: crumbBox
            implicitWidth: crumbRow.implicitWidth + 2 * Theme.grid; implicitHeight: Theme.button
            width: implicitWidth; height: implicitHeight
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
                onPicked: (v) => v === "+view" ? backend.newShotFromView() : v === "+frame" ? backend.frameSelection()
                                 : v === "+shot" ? backend.showShot(backend.adder.add("shot")) : backend.showShot(v)
            }
        }
        Button {
            id: takeShot
            objectName: "takeShot"
            anchors.verticalCenter: parent.verticalCenter
            visible: viewport.hasShot && viewport.mode !== "shot"
            text: shell.width >= 1400 ? "Make this the shot" : "Make shot"
            tip: "Make this the shot"
            help: backend.shotInfo.label + "'s camera moves to this view (the frame shown); Undo puts it back."
            job: "take_view"
            onHoveredChanged: viewport.setPreview(hovered && visible)
            onVisibleChanged: if (!visible) viewport.setPreview(false)
            onClicked: backend.takeView()
        }
    }
    tools: Segmented {   // the pages (Alt+1 / 2 / 3)
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        options: [{ value: "build", label: "Build" }, { value: "animate", label: "Animate" }, { value: "render", label: "Render" }]
        current: backend.page
        onPicked: (v) => backend.setPage(v)
    }
    actions: [
        ViewLookButton { id: viewLook; anchors.verticalCenter: parent.verticalCenter },   // which camera, and Quick / Final
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
            anchors.fill: parent; bridge: backend; keyMarks: true; actions: backend.actions; visible: backend.selected !== "" && !meshEdit.on && !paintMode.on && !viewport.clay.on && !viewport.pose.on && !backend.stretch.shown
            below: Column {     // the item's material (SPEC §6.1): its row with the picker, then the material's own settings inline
                width: parent ? parent.width : 0
                KeepSizeRow { width: parent.width }       // an import just rescaled to metres: Keep original size (importing.py)
                MaterialRow { id: materialRow; width: parent.width }
                Repeater {
                    model: backend.mats.rows
                    delegate: InspectorRow { bridge: backend.mats; instant: backend.mats.rows.instant }
                }
            }
        }
        ScenePanel { anchors.fill: parent; visible: backend.selected === "" && backend.page !== "render" && !viewport.clay.on }
        RenderSettings { anchors.fill: parent; visible: backend.selected === "" && backend.page === "render" }   // the shot's render settings
        MeshEditPanel { anchors.fill: parent; visible: meshEdit.on }   // Edit mesh: points / edges / faces and their actions
        PaintPanel { anchors.fill: parent; visible: paintMode.on }     // Paint: Brush, then Paint layers (mockup 06)
        ClayPanel { anchors.fill: parent; visible: viewport.clay.on }  // Clay: Make, Brush, Size, Strength, Mirror (DESIGN mockup 2)
        PosePanel { anchors.fill: parent; visible: viewport.pose.on }  // Pose: Joints, Names, Holds
        FirstUse { anchors.fill: parent; visible: backend.lipsync.open; when: visible; sourceComponent: Component { LipSyncSheet { } } }   // Lip sync… on a mouth group (the kit's sheet)
        FirstUse { anchors.fill: parent; visible: backend.assets.shown; when: visible; sourceComponent: Component { AssetSheet { } } }   // Import › Asset library
        AnimPanel { anchors.fill: parent; allowed: !meshEdit.on && !paintMode.on && !viewport.clay.on && !viewport.pose.on }      // a stretch picked on the timeline: that animation (‹ or Esc: back)
    }
    bottom: [
        SceneList { anchors.fill: parent; visible: backend.page !== "render" },
        RenderPage { anchors.fill: parent; visible: backend.page === "render" }   // the shots and the render queue
    ]
}
