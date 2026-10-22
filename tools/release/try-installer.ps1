<#
.SYNOPSIS
  Installs a RostrumSetup-*.exe into a scratch folder (silently, both apps, desktop shortcuts), opens each app from its
  new Start-menu and desktop shortcut and from a double-clicked document (check.ps1, as a fresh user), then
  uninstalls and checks that nothing is left. Pictures go to -Results.

  pwsh -File tools\release\try-installer.ps1 -Setup <RostrumSetup.exe> -Scratch <empty folder> -Results <folder>

  The test shortcuts use the real desktop and Start menu (same names as the dev launchers' shortcuts), so any existing
  Rostrum2D / RostrumSound desktop shortcuts are copied aside first and put back at the end, whatever happens.
#>
param(
    [Parameter(Mandatory)][string]$Setup,
    [Parameter(Mandatory)][string]$Scratch,
    [Parameter(Mandatory)][string]$Results
)
$ErrorActionPreference = "Stop"
$check = Join-Path $PSScriptRoot "check.ps1"
$dir = Join-Path $Scratch "install dir"                  # a space in the path, on purpose
$desk = [Environment]::GetFolderPath("Desktop")
$menu = Join-Path ([Environment]::GetFolderPath("Programs")) "Rostrum"
$names = @("Rostrum2D", "RostrumSound")
$saved = Join-Path $Scratch "desktop-shortcuts-before"
$problems = [System.Collections.Generic.List[string]]::new()
function Problem([string]$m) { $problems.Add($m); Write-Host "PROBLEM: $m" -ForegroundColor Red }

New-Item -ItemType Directory -Force $saved, $Results | Out-Null
foreach ($n in $names) { $l = Join-Path $desk "$n.lnk"; if (Test-Path $l) { Copy-Item $l $saved } }
try {
    $p = Start-Process $Setup -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=`"$dir`"",
        "/COMPONENTS=app2d,appsound", "/TASKS=desktop2d,desktopsound", "/LOG=`"$Scratch\install.log`"" -Wait -PassThru
    if ($p.ExitCode) { throw "the installer exited with $($p.ExitCode) (log: $Scratch\install.log)" }
    $mb = (Get-ChildItem $dir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
    Write-Host ("installed into {0} ({1:N0} MB)" -f $dir, $mb)

    $apps = @{ "2d" = @("Rostrum2D", "film.mtn"); "sound" = @("RostrumSound", "score.trk") }
    foreach ($app in $apps.Keys) {
        $name, $file = $apps[$app]
        foreach ($where in @(@("start-menu", (Join-Path $menu "$name.lnk")), @("desktop", (Join-Path $desk "$name.lnk")))) {
            if (-not (Test-Path $where[1])) { Problem "no $($where[0]) shortcut $($where[1])"; continue }
            $shot = Join-Path $Results "installed-$app-from-$($where[0]).png"
            & pwsh -NoProfile -File $check -Install $dir -App $app -Shot $shot -UserHome (Join-Path $Scratch "user-$app") -Lnk $where[1]
            if ($LASTEXITCODE) { Problem "$name did not open from its $($where[0]) shortcut" }
        }
        # A double-clicked document: exactly the command Windows has registered for the file type.
        $type = (Get-ItemProperty "HKCU:\Software\Classes\$([IO.Path]::GetExtension($file))" -ErrorAction SilentlyContinue).'(default)'
        $cmd = if ($type) { (Get-ItemProperty "HKCU:\Software\Classes\$type\shell\open\command").'(default)' } else { $null }
        if (-not $cmd -or $cmd -notmatch [regex]::Escape($dir)) { Problem "$file is not registered to open with $name ($cmd)"; continue }
        $doc = Join-Path $Scratch "user-$app\Documents\Rostrum\Samples\Lull\docs\$file"   # made by the first open
        $shot = Join-Path $Results "installed-$app-from-double-click.png"
        & pwsh -NoProfile -File $check -Install $dir -App $app -Shot $shot -UserHome (Join-Path $Scratch "user-$app") -Extra $doc
        if ($LASTEXITCODE) { Problem "$name did not open a double-clicked $file" }
    }

    $p = Start-Process (Join-Path $dir "unins000.exe") -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait -PassThru
    if ($p.ExitCode) { Problem "the uninstaller exited with $($p.ExitCode)" }
    for ($i = 0; $i -lt 30 -and (Test-Path $dir); $i++) { Start-Sleep -Milliseconds 500 }   # it finishes in a copy of itself
    $left = @()
    if (Test-Path $dir) { $left += "the install folder: $((Get-ChildItem $dir -Recurse -Force | Select-Object -First 5).FullName -join ', ')" }
    if (Test-Path $menu) { $left += "the Start-menu folder $menu" }
    foreach ($n in $names) { if (Test-Path (Join-Path $desk "$n.lnk")) { $left += "desktop shortcut $n" } }
    foreach ($k in @(".mtn", ".trk", "Rostrum.Document2D", "Rostrum.DocumentSound")) {
        if (Test-Path "HKCU:\Software\Classes\$k") { $left += "registry HKCU\Software\Classes\$k" }
    }
    if ($left) { Problem "left behind after uninstall: $($left -join '; ')" } else { Write-Host "uninstall left nothing behind" }
} catch {
    Problem "$_"
} finally {
    foreach ($f in Get-ChildItem $saved -Filter *.lnk) { Copy-Item $f.FullName $desk -Force }
    Write-Host "desktop shortcuts put back: $((Get-ChildItem $saved -Filter *.lnk).Name -join ', ')"
}
if ($problems.Count) { Write-Host "FAIL: $($problems.Count) problem(s)" -ForegroundColor Red; exit 1 }
Write-Host "OK: installed, opened both apps from both shortcuts and a double-clicked document, uninstalled clean" -ForegroundColor Green
