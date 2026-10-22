<#
.SYNOPSIS
  Opens one app from an installed (or staged) Rostrum as a brand-new Windows user would have it, and saves a picture:
  PATH holds only Windows itself, no PYTHON* variables, and the home / AppData folders are a fresh scratch folder
  (so no C:\Users\Sam\.rostrum\venv, no uv, no Rust, no dev checkout can be found).

  pwsh -File tools\release\check.ps1 -Install <folder> -App 2d|sound -Shot <file.png> -UserHome <empty folder> [-Lnk <x.lnk>] [-Extra <args>]

  -Lnk: start exactly what this shortcut starts (its target and arguments) instead of the install's
        pythonw.exe + runtime\rostrum.pyw <app>. -Extra: more arguments (e.g. a .mtn file, as a double-click passes).
  Exits non-zero, printing the app's log, when the app fails or no picture is saved.
#>
param(
    [Parameter(Mandatory)][string]$Install,
    [Parameter(Mandatory)][ValidateSet("2d", "sound")][string]$App,
    [Parameter(Mandatory)][string]$Shot,
    [Parameter(Mandatory)][string]$UserHome,
    [string]$Lnk,
    [string[]]$Extra = @()
)
$ErrorActionPreference = "Stop"
$pyw = Join-Path $Install "runtime\python\pythonw.exe"
$launcher = Join-Path $Install "runtime\rostrum.pyw"
foreach ($f in @($pyw, $launcher)) { if (-not (Test-Path $f)) { Write-Host "FAIL: $f is missing"; exit 1 } }

New-Item -ItemType Directory -Force (Join-Path $UserHome "AppData\Local"), (Join-Path $UserHome "AppData\Roaming"), (Join-Path $UserHome "Documents") | Out-Null
$start = @($launcher, $App)
if ($Lnk) {
    $l = (New-Object -ComObject WScript.Shell).CreateShortcut($Lnk)
    if ($l.Arguments -notmatch '^"([^"]+)"\s+(\S+)$') { Write-Host "FAIL: $Lnk has unexpected arguments: $($l.Arguments)"; exit 1 }
    $pyw, $start = $l.TargetPath, @($Matches[1], $Matches[2])
    if ($Matches[2] -ne $App) { Write-Host "FAIL: $Lnk opens '$($Matches[2])', not $App"; exit 1 }
    Write-Host "shortcut $Lnk -> $pyw $($l.Arguments)"
}
$psi = [System.Diagnostics.ProcessStartInfo]::new($pyw)
foreach ($a in $start + $Extra + @("--shot", $Shot)) { $psi.ArgumentList.Add($a) }
$psi.UseShellExecute = $false
$keep = @("SystemRoot", "windir", "SystemDrive", "COMPUTERNAME", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "OS", "TEMP", "TMP")
$psi.Environment.Clear()
foreach ($k in $keep) { $v = [Environment]::GetEnvironmentVariable($k); if ($v) { $psi.Environment[$k] = $v } }
$psi.Environment["PATH"] = "$env:SystemRoot\System32;$env:SystemRoot"
$psi.Environment["USERPROFILE"] = $UserHome
$psi.Environment["HOMEDRIVE"] = $UserHome.Substring(0, 2)
$psi.Environment["HOMEPATH"] = $UserHome.Substring(2)
$psi.Environment["LOCALAPPDATA"] = Join-Path $UserHome "AppData\Local"
$psi.Environment["APPDATA"] = Join-Path $UserHome "AppData\Roaming"
$psi.Environment["ROSTRUM_NO_MESSAGE_BOX"] = "1"          # this check reads the log instead of waiting on a box
# 2D asks Windows for the Documents folder (not USERPROFILE), which would be the real user's: keep its projects in the
# scratch home's Documents, where a new user's own would be.
$psi.Environment["ROSTRUM2D_PROJECTS"] = Join-Path $UserHome "Documents\Rostrum2D"
# Qt's threaded drawing doesn't run a dialog's fade-in before a scripted picture is taken (the picture showed only the
# dimmed screen); drawing on the app's own thread does. A person's window is not affected.
$psi.Environment["QSG_RENDER_LOOP"] = "basic"
$p =[System.Diagnostics.Process]::Start($psi)
if (-not $p.WaitForExit(120000)) { $p.Kill(); Write-Host "FAIL: $App did not finish in 2 minutes (PID $($p.Id) ended)"; exit 1 }
$log = Get-ChildItem (Join-Path $UserHome "AppData\Local\Rostrum\logs") -Filter "$App-*.log" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime | Select-Object -Last 1
if ($p.ExitCode -ne 0 -or -not (Test-Path $Shot)) {
    Write-Host "FAIL: $App exit code $($p.ExitCode); picture saved: $(Test-Path $Shot). Its log ($($log.FullName)):"
    if ($log) { Get-Content $log.FullName -Tail 40 }
    exit 1
}
Write-Host "OK: $App opened from $Install as a fresh user; picture $Shot; log $($log.FullName)"
Get-Content $log.FullName | Select-Object -Last 3
exit 0
