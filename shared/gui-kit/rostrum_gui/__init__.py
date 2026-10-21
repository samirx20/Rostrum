"""rostrum_gui: the Python side of the shared GUI kit (document bridge, inspector rows, command bar, app start).
The QML side is the RostrumKit module in ../qml/RostrumKit."""
from .bridge import DocBridge
from .app import KIT_QML, start

__all__ = ["DocBridge", "KIT_QML", "start"]
