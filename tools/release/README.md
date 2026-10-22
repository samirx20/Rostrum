# tools/release — the bundled runtime and the one installer

Makes `RostrumSetup-<version>.exe`: tick Rostrum2D and / or RostrumSound; the shared parts install once. Per-user
install (no admin prompt) into `%LOCALAPPDATA%\Programs\Rostrum`. The checklist it serves: `docs/RELEASE.md`.

    pwsh -File tools\release\build-installer.ps1 -Out <folder> [-Version 0.1.0-dev] [-Engines <checkout with built engines>]
    pwsh -File tools\release\check.ps1 -Install <installed or staged folder> -App 2d|sound -Shot <x.png> -UserHome <empty folder>

| File | Job |
|---|---|
| `bundle.py` | Makes the folder the installer packs (below) |
| `qt_trim.py` | Leaves out the Qt parts no app uses (web engine, 3D, charts, PDF, dev tools, translations): 494 MB saved |
| `icons.py` | Placeholder app and document icons (until real ones are designed) |
| `rostrum.pyw` | What every shortcut and double-clicked file runs: picks the app, turns `<project>\docs\<item>.mtn` into the project, with no file lets the app open its last file or a new one, with `--open-sample` (Start menu › Samples) opens the person's copy of the Lull sample in `Documents\Rostrum\Samples` (`rostrum_core.samples`), writes everything to `%LOCALAPPDATA%\Rostrum\logs`, shows a message box naming the log on a crash |
| `notices.py` | The About / Licences screen's data (`apps/<app>/notices.json`) and full texts (`NOTICES.txt`) from `ATTRIBUTIONS.md` + what the bundle really holds; refuses any GPL / AGPL item |
| `rostrum.iss` | The Inno Setup script: components, shortcuts, `.mtn` / `.trk` file types, uninstall |
| `build-installer.ps1` | Bundle + Inno Setup, inside one build slot of the job lock |
| `check.ps1` | Opens an app from an install as a brand-new user would (PATH = Windows only, fresh home / AppData, no PYTHON* variables) and saves a picture |

## How the bundle works (choice and why)

**Embedded Python + wheels**, not PyInstaller / Nuitka. python.org's embeddable Python 3.12.10 (PSF licence) goes in
`runtime\python`; third-party wheels are installed with uv from the shared cache. PyInstaller's licence is GPL with a
bootloader exception (allowed, but it brushes against our "no GPL in what ships" rule); Nuitka (Apache-2.0) compiles
for many minutes per build and its output is harder to debug. Plain files also keep Qt's DLLs separate and
replaceable, which LGPL asks for.

The install folder **mirrors the repo layout** (`shared\core\rostrum_core`, `apps\2d\python\rostrum2d`,
`apps\2d\engine\target\agent\rostrum2d-render.exe`, `apps\2d\guides` …), so every "where is my engine / guides /
fonts" lookup in the code works unchanged; the Python's `python312._pth` puts those folders on the path. Wheels are
split by who needs them: shared (Qt, MCP, numpy, Pillow …) in `runtime\python\Lib\site-packages`, one app's own in
`apps\<app>\site-packages`. Each top folder is one installer component.

## Size (0.1.0-dev, 2026-10-22)

| Part | On disk |
|---|---|
| Shared runtime (Python, trimmed Qt 6.12, MCP, numpy, Pillow, Lull sample 53 MB) | 335 MB |
| Rostrum2D (engine 30 MB, PDF / PSD / EXR / colour libraries, fonts, guides) | 68 MB |
| RostrumSound (engine 11 MB, librosa + numba/llvmlite 127 MB, OpenCV 112 MB, SciPy 102 MB, scikit-learn, matplotlib) | 414 MB |
| Both apps installed | 818 MB |
| Installer download | see `C:\Users\Sam\.rostrum\waves\results\release\s20\README.md` |

Sound's share is mostly its agent "listening" extras; see the requests to the app teams.

## Known limits

- The check runs as a simulated fresh user (empty PATH, fresh home and AppData folders), not a real second Windows
  account: making one needs admin rights.
- Engines are copied from a checkout's `target\agent` build; a release should build `--release` engines first.
- Icons are placeholders.
- Inno Setup's makers ask (not require) commercial users to buy a licence; see the S20 report.

## Attribution rows

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| Python (embeddable build for Windows) | 3.12.10 | PSF-2.0 (plus its bundled libraries: OpenSSL Apache-2.0, libffi MIT, SQLite public domain, zlib, bzip2, xz, Tcl not included) | the installed runtime of every app (`tools/release`) | separate program | ships | Keep the PSF licence and copyright notice | https://www.python.org/downloads/release/python-31210/ |
| Inno Setup | 6.7.3 | Inno Setup License (permissive, BSD-style; commercial licence requested but not required) | builds `RostrumSetup-*.exe`; its setup / uninstall program is inside the installer | separate program | ships (setup stub), build tool | Keep the copyright notice and web address; don't misrepresent the origin | https://jrsoftware.org/isinfo.php |
| uv | as installed | MIT OR Apache-2.0 | installs the wheels into the bundle (`tools/release/bundle.py`) | build tool | dev only | — | https://github.com/astral-sh/uv |
| Qt for Python (PySide6, PySide6-Essentials, PySide6-Addons, Shiboken6) with Qt 6, trimmed | 6.12.0 | LGPL-3.0 | every app's screens | dynamic | ships | Keep Qt dynamically linked and replaceable; ship the LGPL notice and offer the source (replaces the row marked "dev only") | https://pypi.org/project/PySide6/ |
| FFmpeg libraries inside the PySide6 wheel (avcodec, avformat, avutil, swscale, swresample) | as shipped in PySide6 6.12.0 | LGPL-2.1+ | QtMultimedia (Sound's playback / video) | dynamic | ships | Separate replaceable DLLs; LGPL notice; offer source (replaces the row marked "dev only") | https://doc.qt.io/qt-6/qtmultimedia-attribution-ffmpeg.html |

The 30 (2D) / 54 (Sound) Python packages that ship without their own row are listed by `notices.py` on every build
(`missing rows:`); the full list is in `C:\Users\Sam\.rostrum\waves\results\release\s20\README.md`.
