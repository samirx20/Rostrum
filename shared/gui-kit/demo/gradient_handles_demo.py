"""Look harness for GradientHandles: a linear and a radial fill with their on-canvas handles.

    python shared/gui-kit/demo/gradient_handles_demo.py [out.png]      # saves the picture, exits
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_gui import start  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = r"C:\Users\Sam\.rostrum\waves\results\kit\s45\handles-demo.png"


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else OUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    app, engine, win = start(HERE / "qml" / "GradientHandlesDemo.qml", {}, (1646, 900))
    from PySide6.QtCore import QTimer

    def grab():
        win.grabWindow().save(str(out))
        print(out)
        app.quit()
    QTimer.singleShot(800, grab)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
