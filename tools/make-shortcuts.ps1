<#
.SYNOPSIS
  Puts three shortcuts on the desktop: Rostrum2D, RostrumSound, Rostrum3D. Each opens its app (2D / Sound: your last file,
  else a new one; 3D: its sample project) through tools\rostrum.ps1 (problems show in a message box). Running it again replaces them.

  pwsh -File tools\make-shortcuts.ps1
#>
param([string]$Repo = (Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference = "Stop"

$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
$ps = (Get-Command pwsh -ErrorAction SilentlyContinue)
$ps = if ($ps) { $ps.Source } else { (Get-Command powershell).Source }
$launcher = Join-Path $Repo "tools\rostrum.ps1"
if (-not (Test-Path $launcher)) { Write-Host "Note: $launcher isn't there yet; the shortcuts work once it is." -ForegroundColor Yellow }

# The apps' own icons (the installer's, drawn by tools\release\icons.py) instead of PowerShell's
$icons = Join-Path $env:LOCALAPPDATA "Rostrum\icons"
$py = Join-Path $HOME ".rostrum\venv\Scripts\python.exe"
if (Test-Path $py) { & $py (Join-Path $Repo "tools\release\icons.py") $icons }

foreach ($s in @(@("Rostrum2D", "2d", "rostrum2d"), @("RostrumSound", "sound", "rostrumsound"), @("Rostrum3D", "3d", ""))) {
    $lnk = $shell.CreateShortcut((Join-Path $desktop "$($s[0]).lnk"))
    $lnk.TargetPath = $ps
    $ico = Join-Path $icons "$($s[2]).ico"
    if ($s[2] -and (Test-Path $ico)) { $lnk.IconLocation = "$ico,0" }
    $lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`" $($s[1]) -FromShortcut"
    $lnk.WorkingDirectory = $Repo
    $lnk.WindowStyle = 7                                   # the helper window starts minimised; the app opens on top
    $lnk.Description = "Open $($s[0]) on its sample project"
    $lnk.Save()
    Write-Host "Made $(Join-Path $desktop "$($s[0]).lnk")"
}
