import QtQuick
import RostrumKit

// Rostrum3D's window (docs/3d-design/SPEC.md §1, mockup 01). Header: ≡ (the kit's File menu), Rostrum3D, the project ›
// shot crumb, Saved · N changes, the Build | Animate | Render pages, ↶ ↷, Search, View (shot / free camera), Look
// (Quick | Final, when the viewport offers it), Materials, Render (F12), ?. Left edge: the tool rail (Rail3D). Centre:
// the viewport, and over it the last render while one is shown. Right: the settings panel (the kit's grid: the kind's
// own group open, changed groups open, the rest a row of names). Bottom, full width: the scene list with its keys on
// the same rows (SceneList), taller on the Animate page. The start screen (kit) covers it all at a launch with
// nothing to reopen. Export (Ctrl+E) is the kit's sheet in the settings panel's place.
AppShell {
    id: shell
    bridge: backend
    appName: "Rostrum3D"
    helpEntries: guides                 // Help's guides (main.py), in the kit's guide viewer
    documentName: backend.docName
    saveWord: typeof files !== "undefined" && files.hasProject ? "Saved" : ""   // a scene in a project folder saves after every change
    leftWidth: 0
    rightWidth: width >= 1920 ? 340 : width >= 1646 ? 300 : 280
    bottomHeight: backend.page === "animate" ? 284 : 204
    Behavior on bottomHeight { NumberAnimation { duration: Theme.reveal; easing.type: Theme.revealEasing } }
    exporter: backend.exporter
    exportSettings: ExportSettings3D { }

    function openFileMenu() { fileMenu.openMenu() }               // (the scripted `file-menu` step)
    function openRailGroup(id) { return rail.openGroup(id) }      // (the scripted `rail <group>` step)
    function openMaterials() { materialsMenu.openFrom(materialsChip, "right") }
    function openShots() { shotsMenu.openFrom(crumb, "left") }
    function openView() {          // its choices are read as it opens (the light choice follows the selection)
        viewMenu.entries = [{ value: "shot", label: "Shot camera", checked: viewport.mode === "shot" },
                            { value: "free", label: "Free camera", checked: viewport.mode === "free" }]
                           .concat(viewport.canThroughLight ? [{ value: "light", label: "Through the selected light", checked: viewport.mode === "light" }] : [])
        viewMenu.openFrom(viewChip, "right")
    }

    Shortcut { sequence: "Space"; onActivated: backend.togglePlay() }
    Shortcut { sequence: "Left"; onActivated: backend.setFrame(backend.frame - 1) }
    Shortcut { sequence: "Right"; onActivated: backend.setFrame(backend.frame + 1) }
    Shortcut { sequence: "F12"; onActivated: backend.renderStill() }
    Shortcut { sequence: "Escape"; enabled: backend.renderJob.state === "done" || backend.renderJob.state === "failed"
               onActivated: backend.renderJob.dismiss() }
    Shortcut { sequence: "Escape"; enabled: backend.renderJob.state === "running"; onActivated: backend.renderJob.cancel() }
    Shortcut { sequence: "Delete"; enabled: backend.adder.canDelete; onActivated: backend.adder.remove() }
    Shortcut { sequence: "Ctrl+D"; enabled: backend.adder.canDuplicate; onActivated: backend.adder.duplicate() }
    Shortcut { sequence: "Ctrl+1"; onActivated: backend.setPage("build") }
    Shortcut { sequence: "Ctrl+2"; onActivated: backend.setPage("animate") }
    Shortcut { sequence: "Ctrl+3"; onActivated: backend.setPage("render") }
    Shortcut { sequence: "R"; enabled: !startScreen.visible; onActivated: rail.openGroup("shapes") }
    Shortcut { sequence: "L"; enabled: !startScreen.visible; onActivated: rail.openGroup("lights") }
    Shortcut { sequence: "C"; enabled: !startScreen.visible; onActivated: rail.openGroup("camera") }

    menu: FilesMenu {    // ≡ (kit): New, Open, Open recent, Duplicate, Save a version, Show folder, Start screen; then Export
        id: fileMenu
        extra: [{ value: "export", label: "Export…", keys: "Ctrl+E", group: "app" }]
        onPicked: (v) => { if (v === "export") shell.exporter.setOpen(true) }
    }
    StartScreen { id: startScreen; anchors.fill: parent; z: 100; onGuideAsked: (url) => shell.openGuide(url)
                  anchors.leftMargin: shell.guidesOpen ? (shell.guidesWidth || 0) : 0 }

    crumb: Item {   // "› Hero 01 ▾": the shot this screen shows; its list opens a shot's settings or makes a new one
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
            entries: backend.shots.concat(backend.adder.canAddShot ? [{ value: "+shot", label: "New shot" }] : [])
            onPicked: (v) => v === "+shot" ? backend.adder.add("shot") : backend.select(v)
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
            text: ({ shot: "Shot camera", free: "Free camera", light: "Through the light" })[viewport.mode] || "Shot camera"
            onClicked: shell.openView()
            Menu {
                id: viewMenu
                width: 210
                onPicked: (v) => viewport.setMode(v)
            }
        },
        Segmented {  // Look: Quick | Final, once the viewport offers Final (Team Priyam's brief 12: viewport.look / setLook)
            visible: viewport.look !== undefined
            anchors.verticalCenter: parent.verticalCenter
            options: [{ value: "quick", label: "Quick" }, { value: "final", label: "Final" }]
            current: viewport.look || "quick"
            onPicked: (v) => viewport.setLook(v)
        },
        Button {    // the project's materials: pick one to edit it, or make a new one
            id: materialsChip
            anchors.verticalCenter: parent.verticalCenter
            kind: "ghost"; text: "Materials"
            onClicked: shell.openMaterials()
            Menu {
                id: materialsMenu
                width: 200
                entries: backend.materials.concat([{ value: "+material", label: "New material" }])
                onPicked: (v) => v === "+material" ? backend.adder.add("material") : backend.select(v)
            }
        },
        RenderButton { anchors.verticalCenter: parent.verticalCenter }
    ]
    rail: Rail3D { id: rail; height: parent ? parent.height : 0 }
    centre: [
        Viewport { anchors.fill: parent },
        RenderView { anchors.fill: parent }
    ]
    right: Inspector { anchors.fill: parent; bridge: backend; keyMarks: true }
    bottom: SceneList { anchors.fill: parent }
}
