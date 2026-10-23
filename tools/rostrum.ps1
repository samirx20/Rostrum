<#
.SYNOPSIS
  Opens one Rostrum app:  pwsh -File tools\rostrum.ps1 2d | sound | 3d

  2d     Rostrum2D: your last project (its own Open recent list), else a new empty one
  sound  RostrumSound: your last song, else a new empty one
  3d     Rostrum3D on the product shot          (C:\Users\Sam\.rostrum\samples\product-shot, item "product")

  -Sample                2d / sound: the Lull sample instead (the film / the score), your own copy in
                         Documents\Rostrum\Samples\Lull, made once from C:\Users\Sam\.rostrum\samples\lull
  -Doc <folder> <item>   open another project
  -Shot <file.png>       save a picture of the window and close it (to check that the app opens)
  -Step "<a>; <b>"       scripted steps before the picture, as the app's own --step (e.g. -Step "page mix; time 14.9")
  -FromShortcut          problems show in a message box that stays until closed, and every run keeps its log in
                         %LOCALAPPDATA%\Rostrum\logs (tools\release\rostrum.pyw, as the installed app; the shortcuts use this)
elease
ostrum.pyw, as the installed app; the shortcuts use this)

  It uses the one Python environment (C:\Users\Sam\.rostrum\venv; made by tools\setup-python.ps1 when missing) and
  this checkout's engine (built once through the machine's job lock when missing). Anything else missing stops it
  with one plain sentence.
#>
param(
    [Parameter(Position = 0)][ValidateSet("2d", "sound", "3d")][string]$App,
    [string[]]$Doc,
    [string]$Shot,
    [string[]]$Step,
    [switch]$FromShortcut,
    [switch]$Sample,
    [string]$Repo = (Split-Path $PSScriptRoot -Parent)
)
$ErrorActionPreference = "Stop"
$Samples = Join-Path $HOME ".rostrum\samples"
$Venv = Join-Path $HOME ".rostrum\venv"
$Heavy = Join-Path $HOME ".rostrum\waves\heavy.ps1"

# One row per app: everything the launcher needs to know about it.
$Apps = @{
    "2d"    = @{ Name = "Rostrum2D"; Main = "apps\2d\screen\main.py"; EnvVar = "ROSTRUM2D_ENGINE"
                 Engines = @("apps\2d\engine\target\release\rostrum2d-render.exe", "apps\2d\engine\target\agent\rostrum2d-render.exe")
                 Build = @("cargo", "build", "--profile", "agent", "-j", "4"); BuildIn = "apps\2d\engine"
                 Script = $null }
    "sound" = @{ Name = "RostrumSound"; Main = "apps\sound\screen\main.py"; EnvVar = "ROSTRUM_SOUND_ENGINE"
                 Engines = @("apps\sound\engine\target\release\rostrum-sound.exe", "apps\sound\engine\target\agent\rostrum-sound.exe")
                 Build = @("cargo", "build", "--profile", "agent", "-j", "4"); BuildIn = "apps\sound\engine"
                 Script = $null }
    "3d"    = @{ Name = "Rostrum3D"; Main = "apps\3d\app\main.py"; EnvVar = "ROSTRUM3D_CORE"
                 Engines = @("apps\3d\core\.build\install\rostrum3d-core.exe")
                 Build = @("cmd.exe", "/c", (Join-Path $Repo "apps\3d\core\build.bat")); BuildIn = "apps\3d\core"
                 Folder = "product-shot"; Item = "product"; Script = "product-shot-script.py" }
}

function Fail([string]$msg) {
    Write-Host $msg -ForegroundColor Red
    if ($FromShortcut) {
        Add-Type -AssemblyName System.Windows.Forms
        [void][System.Windows.Forms.MessageBox]::Show($msg, "Rostrum", "OK", "Warning")
    }
    exit 1
}

if (-not $App) { Fail "Say which app to open: rostrum.ps1 2d, rostrum.ps1 sound or rostrum.ps1 3d." }
$a = $Apps[$App]

# 1. The Python environment.
$py = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "The Python environment is missing; making it now (a few minutes, once) ..."
    & (Join-Path $PSScriptRoot "setup-python.ps1") -Repo $Repo -Venv $Venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $py)) { Fail "Could not make the Python environment in $Venv. Run tools\setup-python.ps1 to see why." }
}

# 2. The engine: this checkout's build, made once when missing.
function Find-Engine { foreach ($e in $a.Engines) { $p = Join-Path $Repo $e; if (Test-Path $p) { return $p } }; return $null }
$engine = Find-Engine
if (-not $engine) {
    if ($a.Build[0] -eq "cargo" -and -not (Get-Command cargo -ErrorAction SilentlyContinue)) {
        Fail "$($a.Name)'s engine is not built yet, and Rust (cargo) is not installed to build it."
    }
    Write-Host "$($a.Name)'s engine is not built yet; building it now (first time: 5 to 20 minutes) ..."
    Push-Location (Join-Path $Repo $a.BuildIn)
    try {
        if (Test-Path $Heavy) { & pwsh -NoProfile -File $Heavy run "sam: build $($a.Name) engine for the launcher" build @($a.Build) }
        else { & $a.Build[0] @($a.Build[1..($a.Build.Count - 1)]) }
    } finally { Pop-Location }
    $engine = Find-Engine
    if (-not $engine) { Fail "Building $($a.Name)'s engine failed, so the app can't open. The lines above say why." }
}
Set-Item -Path "env:$($a.EnvVar)" -Value $engine

if ($App -eq "3d") {     # the 3D engine's libraries: one folder, named by rostrum3d.runtime (the one place)
    $libs = & $py -c "from rostrum3d.runtime import libs_root; print(libs_root())"
    if ($LASTEXITCODE -ne 0) { Fail "Rostrum3D's Python package won't load. Run tools\setup-python.ps1 again." }
    if (-not (Test-Path (Join-Path $libs "runtime"))) {
        Fail "Rostrum3D's libraries are missing ($libs). Make them once with: $py -I $Repo\apps\3d\libs\lay_out.py"
    }
}

# 3. The project.
if ($Doc) {
    if ($Doc.Count -ne 2) { Fail "-Doc needs a project folder and an item name, like: -Doc C:\my\project film" }
    $folder, $item, $script = $Doc[0], $Doc[1], $null
} elseif ($App -ne "3d" -and $Sample) {   # the person's copy of the sample (rostrum_core.samples: the one place)
    $got = & $py -c "from rostrum_core import samples; f, i = samples.open_copy('lull', '$App'); print(f); print(i)"
    if ($LASTEXITCODE -ne 0) { Fail "The Lull sample could not be copied to Documents\Rostrum\Samples (the lines above say why)." }
    $folder, $item, $script = $got[0], $got[1], $null
} elseif ($App -ne "3d") {                # no project named: the app opens its last file, else a new one
    $folder, $item, $script = $null, $null, $null
} else {
    $folder = Join-Path $Samples $a.Folder; $item = $a.Item
    $script = if ($a.Script) { Join-Path $folder $a.Script } else { $null }
    if (-not (Test-Path $folder)) { Fail "The sample project for $($a.Name) is missing: $folder" }
}
$argv = @((Join-Path $Repo $a.Main))
if ($folder) { $argv += @("--doc", $folder, $item) }
if ($script) { $argv += @("--script", $script) }      # used only the first time, to make the document
foreach ($s in ($Step -join ";") -split ";") { if ($s.Trim()) { $argv += @("--step", $s.Trim()) } }
if ($Shot) { $argv += @("--shot", $Shot) }

# 4. Open it. The window stays until you close it; this prompt waits for it.
Write-Host "Opening $($a.Name) $(if ($folder) { "on $folder ($item)" } else { "(your last file, else a new one)" }) ..."
if ($FromShortcut) {
    # The installed app's watcher, the one place for this: a log per run in %LOCALAPPDATA%\Rostrum\logs (the newest 20
    # kept), and a message box that stays until closed for a crash, an error, or a fatal line before a "fine" close.
    $env:ROSTRUM_ROOT = $Repo
    & $py (Join-Path $Repo "tools\release\rostrum.pyw") $App @($argv | Select-Object -Skip 1)
} else {
    & $py @argv
    if ($LASTEXITCODE -ne 0) { Fail "$($a.Name) stopped with a problem (the lines above say what)." }
}
