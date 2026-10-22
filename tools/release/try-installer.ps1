<#
.SYNOPSIS
  Installs a RostrumSetup-*.exe into a scratch folder (silently, both apps, desktop shortcuts) and walks each app as a
  brand-new user (check.ps1: only Windows on the PATH, a fresh home folder):
    plain start from the Start menu and the desktop (must open a new empty file, never the sample) · New → add one
    thing → Save · plain start again (must reopen that file) · the saved file double-clicked · export (2D: MP4;
    Sound: WAV and FLAC), each file read back · Help › About and licences · Sound's clean-up library loads
  then uninstalls and checks that nothing is left but the person's own files. Pictures go to -Results.

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

# Each app's walk: its steps (the same calls the screen's buttons make), and the files a New → Save and an export leave.
$walk = @{
    "2d"    = @{ name = "Rostrum2D"; ext = ".mtn"; docs = "Documents\Rostrum2D"
                 save = @("--step", "new Fresh test", "--step", "add text", "--step", "save")
                 export = @(@("mp4", @("--step", "export mp4"))) }
    "sound" = @{ name = "RostrumSound"; ext = ".trk"; docs = "Documents\Rostrum"
                 save = @("--step", "file-new", "--step", "add-track piano", "--step", "add-note 0 60", "--step", "file-save-as {home}\Documents\Rostrum\Fresh song")
                 export = @(@("wav", @("--step", "export-as wav24", "--step", "export")), @("flac", @("--step", "export-as flac", "--step", "export"))) }
}

function Open-App($app, $shotName, $userHome, [string[]]$extra = @(), [string]$lnk = "") {
    $shot = Join-Path $Results "installed-$app-$shotName.png"
    $a = @{ Install = $dir; App = $app; Shot = $shot; UserHome = $userHome; Extra = $extra }
    if ($lnk) { $a.Lnk = $lnk }
    & $check @a | Out-Host
    if ($LASTEXITCODE) { Problem "$app $shotName failed (lines above)" }
    $log = Get-ChildItem (Join-Path $userHome "AppData\Local\Rostrum\logs") -Filter "$app-*.log" | Sort-Object LastWriteTime | Select-Object -Last 1
    return (Get-Content $log.FullName -Raw)
}

New-Item -ItemType Directory -Force $saved, $Results | Out-Null
foreach ($n in $names) { $l = Join-Path $desk "$n.lnk"; if (Test-Path $l) { Copy-Item $l $saved } }
try {
    $p = Start-Process $Setup -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=`"$dir`"",
        "/COMPONENTS=app2d,appsound", "/TASKS=desktop2d,desktopsound", "/LOG=`"$Scratch\install.log`"" -Wait -PassThru
    if ($p.ExitCode) { throw "the installer exited with $($p.ExitCode) (log: $Scratch\install.log)" }
    $mb = (Get-ChildItem $dir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
    Write-Host ("installed into {0} ({1:N0} MB)" -f $dir, $mb)

    foreach ($app in $walk.Keys) {
        $w = $walk[$app]; $userHome = Join-Path $Scratch "user-$app"
        foreach ($where in @(@("start-menu", (Join-Path $menu "$($w.name).lnk")), @("desktop", (Join-Path $desk "$($w.name).lnk")))) {
            if (-not (Test-Path $where[1])) { Problem "no $($where[0]) shortcut $($where[1])"; continue }
            $log = Open-App $app "plain-start-$($where[0])" $userHome -lnk $where[1]
            if ($log -match "Samples\\Lull") { Problem "$($w.name)'s plain start opened the sample, not a new file" }
        }
        $save = $w.save | ForEach-Object { $_.Replace("{home}", $userHome) }
        Open-App $app "new-saved" $userHome $save | Out-Null
        $doc = Get-ChildItem (Join-Path $userHome $w.docs) -Recurse -Filter "*$($w.ext)" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch "Samples" } | Sort-Object LastWriteTime | Select-Object -Last 1
        if (-not $doc) { Problem "$($w.name): New → Save left no $($w.ext) file under $userHome\$($w.docs)"; continue }
        Write-Host "saved: $($doc.FullName)"
        $log = Open-App $app "reopened-last" $userHome
        if ($log -notmatch [regex]::Escape($doc.Directory.Parent.Name) -and $log -notmatch "Fresh") { Write-Host "note: the log doesn't name the reopened file; look at the picture" }

        # A double-clicked document: exactly the command Windows has registered for the file type.
        $type = (Get-ItemProperty "HKCU:\Software\Classes\$($w.ext)" -ErrorAction SilentlyContinue).'(default)'
        $cmd = if ($type) { (Get-ItemProperty "HKCU:\Software\Classes\$type\shell\open\command").'(default)' } else { $null }
        if (-not $cmd -or $cmd -notmatch [regex]::Escape($dir)) { Problem "$($w.ext) is not registered to open with $($w.name) ($cmd)" }
        else { Open-App $app "double-click" $userHome @($doc.FullName) | Out-Null }

        foreach ($e in $w.export) {
            $before = Get-Date
            Open-App $app "export-$($e[0])" $userHome (@($doc.FullName) + $e[1]) | Out-Null
            $out = Get-ChildItem $doc.Directory.Parent.FullName -Recurse -Filter "*.$($e[0])" | Where-Object { $_.LastWriteTime -ge $before } | Select-Object -First 1
            if (-not $out) { Problem "$($w.name): no .$($e[0]) file after the export"; continue }
            Copy-Item $out.FullName (Join-Path $Results "installed-$app-export.$($e[0])")
            $ffprobe = (Get-Command ffprobe -ErrorAction SilentlyContinue).Source       # a different program reads it back
            $info = if ($ffprobe) { & $ffprobe -v error -show_entries "stream=codec_name,width,height,sample_rate,channels:format=duration" -of compact $out.FullName } else { "(no ffprobe here)" }
            Write-Host ("exported {0} ({1:N1} MB): {2}" -f $out.FullName, ($out.Length / 1MB), ($info -join " | "))
            if ($ffprobe -and $LASTEXITCODE) { Problem "$($out.FullName) can't be read back" }
        }
        Open-App $app "licences" $userHome @("--step", "about") | Out-Null
    }
    $py = Join-Path $dir "runtime\python\python.exe"
    $ort = & $py -c "import onnxruntime as o; print(o.__version__, o.get_available_providers())" 2>&1
    if ($LASTEXITCODE) { Problem "onnxruntime (Make cleaned take) doesn't load in the installed Python: $ort" } else { Write-Host "onnxruntime loads: $ort" }

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
    foreach ($app in $walk.Keys) {
        if (-not (Get-ChildItem (Join-Path $Scratch "user-$app\$($walk[$app].docs)") -Recurse -Filter "*$($walk[$app].ext)" -ErrorAction SilentlyContinue)) {
            Problem "the person's own $($walk[$app].name) files are gone after uninstall" }
    }
} catch {
    Problem "$_"
} finally {
    foreach ($f in Get-ChildItem $saved -Filter *.lnk) { Copy-Item $f.FullName $desk -Force }
    Write-Host "desktop shortcuts put back: $((Get-ChildItem $saved -Filter *.lnk).Name -join ', ')"
}
if ($problems.Count) { Write-Host "FAIL: $($problems.Count) problem(s)" -ForegroundColor Red; exit 1 }
Write-Host "OK: installed, walked both apps as a new user (plain start, New → Save → reopen, double-click, export, licences), uninstalled clean" -ForegroundColor Green
