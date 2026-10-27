import QtQuick
import "."

// Every shortcut of the apps and the kit (a plain Shortcut is refused by tests/test_background_keys.py). A window opened
// behind the person's work (app.background(), `backgroundWindow`) is never the active window, and Qt fires a window
// shortcut only in the active window, so there each shortcut answers application-wide: a real key press (QTest on the
// window) reaches it without the window being activated. Set when the shortcut is made, so a key never searches the
// window for shortcuts made since (that cost 35-400 ms a key on a full song). Firing tells the window's typed-word
// guard that this key was a command, not a word's first letter (rostrum_gui/typed_word.py), so the next key runs too.
Shortcut {
    context: typeof backgroundWindow !== "undefined" && backgroundWindow ? Qt.ApplicationShortcut : Qt.WindowShortcut
    // (A command closes the popups left open: OpenPopups.closeForCommand; this runs before the instance's own handler.)
    onActivated: {
        OpenPopups.closeForCommand(sequences.length ? sequences : [sequence])
        if (typeof typedWord !== "undefined" && typedWord) typedWord.ran()
    }
}
