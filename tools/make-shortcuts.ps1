<#
.SYNOPSIS
  Puts three shortcuts on the desktop: Rostrum2D, RostrumSound, Rostrum3D. Each opens its app on its sample project
  through tools\rostrum.ps1 (problems show in a message box). Running it again replaces them.

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

foreach ($s in @(@("Rostrum2D", "2d"), @("RostrumSound", "sound"), @("Rostrum3D", "3d"))) {
    $lnk = $shell.CreateShortcut((Join-Path $desktop "$($s[0]).lnk"))
    $lnk.TargetPath = $ps
    $lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`" $($s[1]) -FromShortcut"
    $lnk.WorkingDirectory = $Repo
    $lnk.WindowStyle = 7                                   # the helper window starts minimised; the app opens on top
    $lnk.Description = "Open $($s[0]) on its sample project"
    $lnk.Save()
    Write-Host "Made $(Join-Path $desktop "$($s[0]).lnk")"
}
