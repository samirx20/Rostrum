import QtQuick

// Sound's editing and timeline keys (INTERACTION.md Part 2, §1.7; apps/sound/DESIGN.md §6), instanced once in
// Main.qml. Actions go through the one action list (backend.keyAction: done when valid, else the message line says
// why); none fire while typing in a field. Arrows nudge the selection (Shift: a bar; Alt: fine), ↑ ↓ notes a half step
// (Shift: an octave) or clips to the track above / below; Ctrl+← → move the playhead (Ctrl+Shift: ten steps);
// `,` / `.` previous / next thing that happens. Nudges under 1 s apart are one undo step (the core merges them).
// Space, Home, Delete / Backspace, E, X, Ctrl+L and R live in Main.qml (the workspace's keys): a key bound twice
// fires neither. Not yet: Shift+K (click on its own, outside recording), K (key on automation lanes),
// Ctrl+↑ / ↓ (pitch by a scale step).
Item {
    id: keys
    readonly property bool typing: {
        const f = Window.activeFocusItem
        return !!f && f.cursorPosition !== undefined && f.selectByMouse !== undefined      // a text field has the keys
    }
    function act(key) { return backend.keyAction(key) }

    // nudge in time: a grid step, a bar (Shift), fine (Alt)
    Shortcut { enabled: !keys.typing; sequence: "Right"; onActivated: backend.nudge("grid", 1) }
    Shortcut { enabled: !keys.typing; sequence: "Left"; onActivated: backend.nudge("grid", -1) }
    Shortcut { enabled: !keys.typing; sequence: "Shift+Right"; onActivated: backend.nudge("bar", 1) }
    Shortcut { enabled: !keys.typing; sequence: "Shift+Left"; onActivated: backend.nudge("bar", -1) }
    Shortcut { enabled: !keys.typing; sequence: "Alt+Right"; onActivated: backend.nudge("fine", 1) }
    Shortcut { enabled: !keys.typing; sequence: "Alt+Left"; onActivated: backend.nudge("fine", -1) }
    // notes: a half step, an octave (Shift); clips: the track above / below
    Shortcut { enabled: !keys.typing; sequence: "Up"; onActivated: backend.pitchStep(1) }
    Shortcut { enabled: !keys.typing; sequence: "Down"; onActivated: backend.pitchStep(-1) }
    Shortcut { enabled: !keys.typing; sequence: "Shift+Up"; onActivated: backend.pitchStep(12) }
    Shortcut { enabled: !keys.typing; sequence: "Shift+Down"; onActivated: backend.pitchStep(-12) }
    // the playhead (never a change)
    Shortcut { enabled: !keys.typing; sequence: "Ctrl+Right"; onActivated: backend.playheadStep(1) }
    Shortcut { enabled: !keys.typing; sequence: "Ctrl+Left"; onActivated: backend.playheadStep(-1) }
    Shortcut { enabled: !keys.typing; sequence: "Ctrl+Shift+Right"; onActivated: backend.playheadStep(10) }
    Shortcut { enabled: !keys.typing; sequence: "Ctrl+Shift+Left"; onActivated: backend.playheadStep(-10) }
    Shortcut { enabled: !keys.typing; sequence: ","; onActivated: backend.jump(-1) }
    Shortcut { enabled: !keys.typing; sequence: "."; onActivated: backend.jump(1) }
    // the time range and the loop
    Shortcut { enabled: !keys.typing; sequence: "Shift+I"; autoRepeat: false; onActivated: backend.rangeEdge("in") }
    Shortcut { enabled: !keys.typing; sequence: "Shift+O"; autoRepeat: false; onActivated: backend.rangeEdge("out") }
    Shortcut { enabled: !keys.typing; sequence: "Shift+L"; autoRepeat: false; onActivated: backend.toggleLoop() }
    Shortcut { enabled: !keys.typing; sequence: "F"; autoRepeat: false; onActivated: backend.fitSelection() }
    // the edit block
    Shortcut { enabled: !keys.typing; sequence: StandardKey.Copy; autoRepeat: false; onActivated: keys.act("sel:copy") }
    Shortcut { enabled: !keys.typing; sequence: StandardKey.Cut; autoRepeat: false; onActivated: keys.act("sel:cut") }
    Shortcut { enabled: !keys.typing; sequence: StandardKey.Paste; autoRepeat: false; onActivated: keys.act("sel:paste") }
    Shortcut { enabled: !keys.typing; sequence: "Ctrl+D"; autoRepeat: false
               onActivated: keys.act(backend.selectedIds.length ? "sel:duplicate" : "sel:range_duplicate") }
    Shortcut { enabled: !keys.typing; sequence: "Shift+Del"; autoRepeat: false; onActivated: keys.act("sel:cut_range") }
    Shortcut { enabled: !keys.typing; sequence: "F2"; autoRepeat: false; onActivated: keys.act("sel:rename") }
    Shortcut { enabled: !keys.typing; sequence: StandardKey.SelectAll; autoRepeat: false; onActivated: backend.selectAll() }
    Shortcut { enabled: !keys.typing; sequence: "Esc"; autoRepeat: false; onActivated: backend.clearSelection() }
    // per-action keys
    Shortcut { enabled: !keys.typing; sequence: "Q"; autoRepeat: false; onActivated: keys.act("sel:quantize") }
    Shortcut { enabled: !keys.typing; sequence: "Ctrl+T"; autoRepeat: false; onActivated: keys.act("sel:split") }
    Shortcut { enabled: !keys.typing; sequence: "Ctrl+J"; autoRepeat: false; onActivated: keys.act("sel:join") }
    Shortcut { enabled: !keys.typing; sequence: "Ctrl+G"; autoRepeat: false
               onActivated: keys.act(backend.applies("sel:layer") ? "sel:layer" : "sel:group") }
    Shortcut { enabled: !keys.typing; sequence: "Ctrl+]"; onActivated: keys.act("sel:move_down") }
    Shortcut { enabled: !keys.typing; sequence: "Ctrl+["; onActivated: keys.act("sel:move_up") }
    Shortcut { enabled: !keys.typing; sequence: "Ctrl+Shift+L"; autoRepeat: false
               onActivated: keys.act(backend.applies("sel:lock") ? "sel:lock" : "sel:unlock") }
    Shortcut { enabled: !keys.typing; sequence: "Shift+M"; autoRepeat: false; onActivated: keys.act("sel:mute") }
    Shortcut { enabled: !keys.typing; sequence: "Shift+S"; autoRepeat: false; onActivated: keys.act("sel:solo") }
    Shortcut { enabled: !keys.typing; sequence: "M"; autoRepeat: false; onActivated: backend.markerAt(backend.time) }
}
