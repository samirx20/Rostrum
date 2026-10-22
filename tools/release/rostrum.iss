; Rostrum's one installer (Inno Setup 6). Tick Rostrum2D and / or RostrumSound; the shared runtime is installed once.
; Built by tools\release\build-installer.ps1 from the folder tools\release\bundle.py makes:
;   ISCC.exe /DStage=<bundle>\stage /DOutDir=<folder> /DVersion=0.1.0-dev rostrum.iss
; Installs for the current user only (no admin prompt) into %LOCALAPPDATA%\Programs\Rostrum.
; Uninstall removes the program, its shortcuts, file types and logs; the person's own projects
; (Documents\Rostrum and wherever they saved) are never touched.

#ifndef Stage
  #error Pass /DStage=<bundle stage folder>
#endif
#ifndef Version
  #define Version "0.1.0-dev"
#endif
#ifndef OutDir
  #define OutDir "."
#endif
#define Pyw "{app}\runtime\python\pythonw.exe"
#define Launch "{app}\runtime\rostrum.pyw"

[Setup]
AppId={{6C2E8F4A-2D1B-4E57-9A0C-52D7B3F1A9E4}
AppName=Rostrum
AppVersion={#Version}
AppPublisher=HireMyLens Media
AppPublisherURL=https://github.com/samirx20/Rostrum
DefaultDirName={localappdata}\Programs\Rostrum
DefaultGroupName=Rostrum
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile={#Stage}\LICENSE
OutputDir={#OutDir}
OutputBaseFilename=RostrumSetup-{#Version}
SetupIconFile={#Stage}\runtime\icons\rostrum2d.ico
UninstallDisplayIcon={app}\runtime\icons\rostrum2d.ico
UninstallDisplayName=Rostrum {#Version}
Compression=lzma2/max
SolidCompression=yes
LZMANumBlockThreads=4
ChangesAssociations=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Types]
Name: "full"; Description: "Rostrum2D and RostrumSound"
Name: "custom"; Description: "Choose apps"; Flags: iscustom

[Components]
Name: "runtime"; Description: "Shared parts (Python, Qt, samples)"; Types: full custom; Flags: fixed
Name: "app2d"; Description: "Rostrum2D: motion design, type, drawing, 2D characters"; Types: full
Name: "appsound"; Description: "RostrumSound: music, sound effects, voice, mixing"; Types: full

[Tasks]
Name: "desktop2d"; Description: "Rostrum2D on the desktop"; Components: app2d
Name: "desktopsound"; Description: "RostrumSound on the desktop"; Components: appsound

[Files]
Source: "{#Stage}\runtime\*"; DestDir: "{app}\runtime"; Components: runtime; Flags: recursesubdirs ignoreversion
Source: "{#Stage}\shared\*"; DestDir: "{app}\shared"; Components: runtime; Flags: recursesubdirs ignoreversion
Source: "{#Stage}\LICENSE"; DestDir: "{app}"; Components: runtime
Source: "{#Stage}\ATTRIBUTIONS.md"; DestDir: "{app}"; Components: runtime
Source: "{#Stage}\apps\2d\*"; DestDir: "{app}\apps\2d"; Components: app2d; Flags: recursesubdirs ignoreversion
Source: "{#Stage}\apps\sound\*"; DestDir: "{app}\apps\sound"; Components: appsound; Flags: recursesubdirs ignoreversion
; Each app's agent server, started by hand in a terminal (Help > Connect an AI agent shows this command).
Source: "{#Stage}\rostrum-2d-mcp.cmd"; DestDir: "{app}"; Components: app2d
Source: "{#Stage}\rostrum-sound-mcp.cmd"; DestDir: "{app}"; Components: appsound

[Icons]
Name: "{group}\Rostrum2D"; Filename: "{#Pyw}"; Parameters: """{#Launch}"" 2d"; WorkingDir: "{app}"; IconFilename: "{app}\runtime\icons\rostrum2d.ico"; Components: app2d
Name: "{group}\RostrumSound"; Filename: "{#Pyw}"; Parameters: """{#Launch}"" sound"; WorkingDir: "{app}"; IconFilename: "{app}\runtime\icons\rostrumsound.ico"; Components: appsound
Name: "{group}\Samples\Lull (Rostrum2D)"; Filename: "{#Pyw}"; Parameters: """{#Launch}"" 2d --open-sample"; WorkingDir: "{app}"; IconFilename: "{app}\runtime\icons\rostrum2d.ico"; Components: app2d
Name: "{group}\Samples\Lull (RostrumSound)"; Filename: "{#Pyw}"; Parameters: """{#Launch}"" sound --open-sample"; WorkingDir: "{app}"; IconFilename: "{app}\runtime\icons\rostrumsound.ico"; Components: appsound
Name: "{group}\Uninstall Rostrum"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Rostrum2D"; Filename: "{#Pyw}"; Parameters: """{#Launch}"" 2d"; WorkingDir: "{app}"; IconFilename: "{app}\runtime\icons\rostrum2d.ico"; Tasks: desktop2d
Name: "{userdesktop}\RostrumSound"; Filename: "{#Pyw}"; Parameters: """{#Launch}"" sound"; WorkingDir: "{app}"; IconFilename: "{app}\runtime\icons\rostrumsound.ico"; Tasks: desktopsound

[Registry]
; Double-click a .mtn (2D) or .trk (Sound) document to open it in its app (current user only).
Root: HKCU; Subkey: "Software\Classes\.mtn"; ValueType: string; ValueData: "Rostrum.Document2D"; Flags: uninsdeletevalue uninsdeletekeyifempty; Components: app2d
Root: HKCU; Subkey: "Software\Classes\Rostrum.Document2D"; ValueType: string; ValueData: "Rostrum2D document"; Flags: uninsdeletekey; Components: app2d
Root: HKCU; Subkey: "Software\Classes\Rostrum.Document2D\DefaultIcon"; ValueType: string; ValueData: "{app}\runtime\icons\document2d.ico"; Components: app2d
Root: HKCU; Subkey: "Software\Classes\Rostrum.Document2D\shell\open\command"; ValueType: string; ValueData: """{#Pyw}"" ""{#Launch}"" 2d ""%1"""; Components: app2d
Root: HKCU; Subkey: "Software\Classes\.trk"; ValueType: string; ValueData: "Rostrum.DocumentSound"; Flags: uninsdeletevalue uninsdeletekeyifempty; Components: appsound
Root: HKCU; Subkey: "Software\Classes\Rostrum.DocumentSound"; ValueType: string; ValueData: "RostrumSound document"; Flags: uninsdeletekey; Components: appsound
Root: HKCU; Subkey: "Software\Classes\Rostrum.DocumentSound\DefaultIcon"; ValueType: string; ValueData: "{app}\runtime\icons\documentsound.ico"; Components: appsound
Root: HKCU; Subkey: "Software\Classes\Rostrum.DocumentSound\shell\open\command"; ValueType: string; ValueData: """{#Pyw}"" ""{#Launch}"" sound ""%1"""; Components: appsound

[Run]
Filename: "{#Pyw}"; Parameters: """{#Launch}"" 2d"; Description: "Open Rostrum2D"; Flags: postinstall nowait skipifsilent; Components: app2d
Filename: "{#Pyw}"; Parameters: """{#Launch}"" sound"; Description: "Open RostrumSound"; Flags: postinstall nowait skipifsilent unchecked; Components: appsound

[UninstallRun]
; First, before any file goes: take Rostrum out of every coding agent it was added to (only the entries Rostrum added
; that start this install's Python; each settings file is backed up first), so no agent points at a deleted Python.
Filename: "{app}\runtime\python\python.exe"; Parameters: "-m rostrum_connect remove-all --yes --this-install"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveAgentEntries"

[UninstallDelete]
; What the apps write next to themselves (Python's compiled-code caches) and their logs.
Type: filesandordirs; Name: "{app}\runtime"
Type: filesandordirs; Name: "{app}\shared"
Type: filesandordirs; Name: "{app}\apps"
Type: filesandordirs; Name: "{localappdata}\Rostrum\logs"
Type: dirifempty; Name: "{localappdata}\Rostrum"
Type: dirifempty; Name: "{app}"
