# ATTRIBUTIONS.md

Every third-party library, model, asset source and tool that ships in or is downloaded by Rostrum, with its licence. Add a row whenever you add one, including its own dependencies when they carry their own licence. The experiment's list (`experiment-final:docs/ATTRIBUTIONS.md`) is the starting point for code carried over.

- **How it's linked:** `static`, `dynamic` (required for LGPL), `separate program`, `vendored source`, `data` or `model`.
- **Ships?** `ships` (inside the installer), `on demand` (downloaded when the user asks), or `dev only` (proofs, build tools, tests; never shipped).
- **What it asks of us:** credit line, keep the notice, offer the LGPL source / allow relinking, and so on.

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| Qt for Python (PySide6, Shiboken6) with Qt 6 | 6.12.0 | LGPL-3.0 (Qt modules used: Core, Gui, Qml, Quick, Multimedia) | `proofs/gui-qt` (GUI proof) | dynamic | dev only | Keep Qt dynamically linked and replaceable; ship the LGPL notice and offer the source | https://pypi.org/project/PySide6/ |
| PyOpenGL | 3.1.10 | BSD-3-Clause | `proofs/gui-qt` (GUI proof) | Python package | dev only | Keep the notice | https://pypi.org/project/PyOpenGL/ |
| NumPy | 2.5.4 | BSD-3-Clause | `proofs/gui-qt` (GUI proof) | Python package | dev only | Keep the notice | https://pypi.org/project/numpy/ |
