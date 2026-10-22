<#
.SYNOPSIS
  Installs a RostrumSetup-*.exe into a scratch folder (silently, the apps in -Apps, desktop shortcuts) and walks each
  installed app as a brand-new user (check.ps1: only Windows on the PATH, a fresh home folder):
    plain start from the Start menu and the desktop (must open a new empty file, never the sample) · New → add one
    thing → Save · plain start again (must reopen that file) · the saved file double-clicked · export (2D: MP4 and WebM;
    Sound: WAV and FLAC), each file read back · 2D: the Lull sample's MP4 with the project's sound (Sound's engine part
    comes with 2D alone too) · Help › About and licences · Sound's clean-up library loads
  checks that an app not picked left nothing of its own (shortcuts, file type, folders, agent server), then uninstalls
  and checks that nothing is left but the person's own files. Pictures go to -Results.

  pwsh -File tools\release\try-installer.ps1 -Setup <RostrumSetup.exe> -Scratch <empty folder> -Results <folder> [-Apps 2d,sound]

  The test shortcuts use the real desktop and Start menu (same names as the dev launchers' shortcuts), so any existing
  Rostrum2D / RostrumSound desktop shortcuts are copied aside first and put back at the end, whatever happens.
#>
param(
    [Parameter(Mandatory)][string]$Setup,
    [Parameter(Mandatory)][string]$Scratch,
    [Parameter(Mandatory)][string]$Results,
    [ValidateSet("2d", "sound")][string[]]$Apps = @("2d", "sound")
)
$ErrorActionPreference = "Stop"
$check = Join-Path $PSScriptRoot "check.ps1"
$dir = Join-Path $Scratch "install dir"                  # a space in the path, on purpose
$desk = [Environment]::GetFolderPath("Desktop")
$menu = Join-Path ([Environment]::GetFolderPath("Programs")) "Rostrum"
$names = @("Rostrum2D", "RostrumSound")
$component = @{ "2d" = "app2d"; "sound" = "appsound" }; $desktopTask = @{ "2d" = "desktop2d"; "sound" = "desktopsound" }
$saved = Join-Path $Scratch "desktop-shortcuts-before"
$problems = [System.Collections.Generic.List[string]]::new()
function Problem([string]$m) { $problems.Add($m); Write-Host "PROBLEM: $m" -ForegroundColor Red }

# Each app's walk: its steps (the same calls the screen's buttons make), and the files a New → Save and an export leave.
$walk = @{
    "2d"    = @{ name = "Rostrum2D"; ext = ".mtn"; docs = "Documents\Rostrum2D"
                 save = @("--step", "new Fresh test", "--step", "add text")      # 2D saves every change itself
                 export = @(@("mp4", @("--step", "export mp4")), @("webm", @("--step", "export webm")))
                 own = @("apps\2d", "rostrum-2d-mcp.cmd") }
    "sound" = @{ name = "RostrumSound"; ext = ".trk"; docs = "Documents\Rostrum Sound"
                 save = @("--step", "new Fresh_song", "--step", "add-track piano", "--step", "add-note 0 60")   # saves itself
                 export = @(@("wav", @("--step", "export-as wav24", "--step", "export")), @("flac", @("--step", "export-as flac", "--step", "export")))
                 own = @("apps\sound\screen", "apps\sound\site-packages", "rostrum-sound-mcp.cmd") }
}

function Open-App($app, $shotName, $userHome, [string[]]$extra = @(), [string]$lnk = "", [int]$wait = 120) {
    $shot = Join-Path $Results "installed-$app-$shotName.png"
    $a = @{ Install = $dir; App = $app; Shot = $shot; UserHome = $userHome; Extra = $extra; Wait = $wait }
    if ($lnk) { $a.Lnk = $lnk }
    & $check @a | Out-Host
    if ($LASTEXITCODE) { Problem "$app $shotName failed (lines above)" }
    $log = Get-ChildItem (Join-Path $userHome "AppData\Local\Rostrum\logs") -Filter "$app-*.log" | Sort-Object LastWriteTime | Select-Object -Last 1
    return (Get-Content $log.FullName -Raw)
}

# The real user's agent settings files: hashed now and again at the end (the walk must leave them untouched).
$userVars = @("USERPROFILE", "HOME", "APPDATA", "LOCALAPPDATA", "CODEX_HOME", "ROSTRUM2D_PROJECTS"); $envBefore = $null
$devPy = Join-Path $HOME ".rostrum\venv\Scripts\python.exe"
# Per file: its servers (must not change) and its bytes (a change is only a note: an agent that is running, like the
# Claude Code driving this walk, rewrites its own file).
$agentState = { & $devPy -I -c "import sys; sys.path.insert(0, sys.argv[1]); from rostrum_connect import agents, connect
for a in agents.AGENTS:
    try: print(agents.user_file(a), '|', sorted(connect.entries(a.id).items()))
    except Exception as e: print(agents.user_file(a), '| unreadable', e)" (Join-Path $PSScriptRoot "..\..\shared\mcp") }
$realAgentFiles = @(& $agentState)
$realHashes = @{}; foreach ($f in $realAgentFiles) { $p = ($f -split " \| ")[0]; $realHashes[$p] = if (Test-Path $p) { (Get-FileHash $p).Hash } else { "absent" } }
New-Item -ItemType Directory -Force $saved, $Results | Out-Null
# Aside, then off the desktop, so a not-picked app's dev shortcut isn't taken for the installer's (put back at the end).
foreach ($n in $names) { $l = Join-Path $desk "$n.lnk"; if (Test-Path $l) { Copy-Item $l $saved; Remove-Item $l } }
try {
    $p = Start-Process $Setup -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=`"$dir`"",
        "/COMPONENTS=$(($Apps | ForEach-Object { $component[$_] }) -join ',')", "/TASKS=$(($Apps | ForEach-Object { $desktopTask[$_] }) -join ',')", "/LOG=`"$Scratch\install.log`"" -Wait -PassThru
    if ($p.ExitCode) { throw "the installer exited with $($p.ExitCode) (log: $Scratch\install.log)" }
    $mb = (Get-ChildItem $dir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
    Write-Host ("installed into {0} ({1:N0} MB): {2}" -f $dir, $mb, ($Apps -join " + "))

    # An app not picked leaves nothing of its own; Sound's engine part comes with either app (rostrum.iss).
    foreach ($app in @($walk.Keys | Where-Object { $_ -notin $Apps })) {
        $w = $walk[$app]
        foreach ($f in $w.own) { if (Test-Path (Join-Path $dir $f)) { Problem "$($w.name) was not picked, but $dir\$f is installed" } }
        foreach ($l in @((Join-Path $menu "$($w.name).lnk"), (Join-Path $desk "$($w.name).lnk"))) { if (Test-Path $l) { Problem "$($w.name) was not picked, but $l exists" } }
        if (Test-Path "HKCU:\Software\Classes\$($w.ext)") { Problem "$($w.name) was not picked, but $($w.ext) is registered" }
    }
    foreach ($f in @("apps\sound\engine\target\agent\rostrum-sound.exe", "apps\sound\python\rostrum_sound\__init__.py")) {
        if (-not (Test-Path (Join-Path $dir $f))) { Problem "Sound's engine part is missing: $dir\$f" }
    }

    foreach ($app in $Apps) {
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
            $out = Get-ChildItem $doc.Directory.Parent.FullName -Recurse -Filter "*.$($e[0])" | Where-Object { $_.LastWriteTime -ge $before } | Sort-Object Length | Select-Object -Last 1   # the mix, not a stem
            if (-not $out) { Problem "$($w.name): no .$($e[0]) file after the export"; continue }
            Copy-Item $out.FullName (Join-Path $Results "installed-$app-export.$($e[0])")
            $ffprobe = (Get-Command ffprobe -ErrorAction SilentlyContinue).Source       # a different program reads it back
            $info = if ($ffprobe) { & $ffprobe -v error -show_entries "stream=codec_name,width,height,sample_rate,channels:format=duration" -of compact $out.FullName } else { "(no ffprobe here)" }
            Write-Host ("exported {0} ({1:N1} MB): {2}" -f $out.FullName, ($out.Length / 1MB), ($info -join " | "))
            if ($ffprobe -and $LASTEXITCODE) { Problem "$($out.FullName) can't be read back" }
        }
        Open-App $app "licences" $userHome @("--step", "about") | Out-Null
    }
    if ("2d" -in $Apps) {
        # The Lull sample's MP4 with the project's sound: mixed by Sound's engine, which a 2D-only install has too.
        # The step prints where the MP4 went (Documents\Rostrum\Samples\Lull\renders\…). The range (drop → logo lands,
        # 3.4 s) keeps the run inside 2D's 30 s limit for scripted runs.
        $userHome = Join-Path $Scratch "user-2d"
        $log = Open-App "2d" "export-mp4-with-sound" $userHome @("--open-sample", "--step", "export mp4 range=drop→logo_lands")
        $out = if ($log -match "export mp4: (.+?\.mp4) \[") { Get-Item $Matches[1] -ErrorAction SilentlyContinue }
        if (-not $out) { Problem "Rostrum2D: the Lull sample's MP4 export named no file that exists (log above)" }
        else {
            Copy-Item $out.FullName (Join-Path $Results "installed-2d-lull-with-sound.mp4")
            $ffprobe = (Get-Command ffprobe -ErrorAction SilentlyContinue).Source
            $audio = if ($ffprobe) { & $ffprobe -v error -select_streams a -show_entries "stream=codec_name,sample_rate,channels" -of compact $out.FullName } else { "(no ffprobe here)" }
            Write-Host ("exported {0} ({1:N1} MB), sound: {2}" -f $out.FullName, ($out.Length / 1MB), ($audio -join " | "))
            if ($ffprobe -and -not ($audio -match "codec_name=aac")) { Problem "the Lull MP4 has no sound stream: $audio" }
        }
    }
    $py = Join-Path $dir "runtime\python\python.exe"
    if ("sound" -in $Apps) {
        $ort = & $py -c "import onnxruntime as o; print(o.__version__, o.get_available_providers())" 2>&1
        if ($LASTEXITCODE) { Problem "onnxruntime (Make cleaned take) doesn't load in the installed Python: $ort" } else { Write-Host "onnxruntime loads: $ort" }
    }
    $agentApp = $Apps[0]                                 # the agent walk uses the first installed app

    # Connect an AI agent, as a new user: Codex in a scratch home (CODEX_HOME), so no real agent settings are touched.
    # From here to the uninstall, this script and what it starts (the uninstaller too) see the scratch user's folders.
    $agentUser = Join-Path $Scratch "user-agents"; $codexHome = Join-Path $agentUser ".codex"
    New-Item -ItemType Directory -Force $codexHome, (Join-Path $agentUser "AppData\Local"), (Join-Path $agentUser "AppData\Roaming") | Out-Null
    $toml = Join-Path $codexHome "config.toml"
    [IO.File]::WriteAllBytes($toml, [Text.Encoding]::ASCII.GetBytes("# my Codex settings`r`nmodel = `"gpt-5`"`r`n`r`n[mcp_servers.other]`r`ncommand = `"other.exe`"`r`n"))
    $seed = Get-FileHash $toml
    $envBefore = @{}; foreach ($k in $userVars) { $envBefore[$k] = [Environment]::GetEnvironmentVariable($k) }
    $env:USERPROFILE = $agentUser; $env:HOME = $agentUser; $env:CODEX_HOME = $codexHome
    $env:APPDATA = Join-Path $agentUser "AppData\Roaming"; $env:LOCALAPPDATA = Join-Path $agentUser "AppData\Local"
    $env:ROSTRUM2D_PROJECTS = Join-Path $agentUser "Documents\Rostrum2D"
    $hand = (& $py -m rostrum_connect hand --agent codex --app $agentApp) -join "`n"
    $hand | Set-Content (Join-Path $Results "installed-codex-by-hand.txt") -Encoding utf8
    if ($hand -notmatch [regex]::Escape("$dir\runtime\python\python.exe") -or $hand -match "PYTHONPATH|\.rostrum\\venv") {
        Problem "the by-hand text doesn't use the installed Python, or names PYTHONPATH / the dev venv:`n$hand" }
    Open-App $agentApp "connect-codex-by-hand" $agentUser @("--step", "agents codex") | Out-Null
    $list = Join-Path $PSScriptRoot "list_tools.py"
    foreach ($app in $Apps) {
        $out = & $py $list (Join-Path $dir "rostrum-$app-mcp.cmd") 2>&1
        Write-Host "rostrum-$app-mcp.cmd: $($out -join ' | ')"
        if ($LASTEXITCODE) { Problem "rostrum-$app-mcp.cmd didn't start a server that lists its tools: $out" }
    }
    $add = & $py -m rostrum_connect add --agent codex --app $agentApp --yes 2>&1
    Write-Host "add: $add"
    if ($LASTEXITCODE) { Problem "adding $($walk[$agentApp].name) to Codex failed: $add" }
    Copy-Item $toml (Join-Path $Results "installed-codex-config-after-add.toml")
    $out = & $py $list --codex $toml "rostrum-$agentApp" 2>&1
    Write-Host "Codex's entry: $($out -join ' | ')"
    if ($LASTEXITCODE) { Problem "the server Codex's entry starts didn't list its tools: $out" }
    Open-App $agentApp "connect-codex-added" $agentUser @("--step", "agents") | Out-Null

    $p = Start-Process (Join-Path $dir "unins000.exe") -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait -PassThru
    if ($p.ExitCode) { Problem "the uninstaller exited with $($p.ExitCode)" }
    for ($i = 0; $i -lt 30 -and (Test-Path $dir); $i++) { Start-Sleep -Milliseconds 500 }   # it finishes in a copy of itself
    foreach ($k in $userVars) { [Environment]::SetEnvironmentVariable($k, $envBefore[$k]) }
    $envBefore = $null
    if ((Get-FileHash $toml).Hash -ne $seed.Hash) { Problem "after uninstall, Codex's config.toml isn't byte-for-byte what it was: $(Get-Content $toml -Raw)" }
    else { Write-Host "uninstall took Rostrum out of Codex: config.toml byte-for-byte as before" }
    for ($i = 0; $i -lt 30 -and (Test-Path $dir); $i++) { Start-Sleep -Milliseconds 500 }   # it finishes in a copy of itself
    $left = @()
    if (Test-Path $dir) { $left += "the install folder: $((Get-ChildItem $dir -Recurse -Force | Select-Object -First 5).FullName -join ', ')" }
    if (Test-Path $menu) { $left += "the Start-menu folder $menu" }
    foreach ($n in $names) { if (Test-Path (Join-Path $desk "$n.lnk")) { $left += "desktop shortcut $n" } }
    foreach ($k in @(".mtn", ".trk", "Rostrum.Document2D", "Rostrum.DocumentSound")) {
        if (Test-Path "HKCU:\Software\Classes\$k") { $left += "registry HKCU\Software\Classes\$k" }
    }
    if ($left) { Problem "left behind after uninstall: $($left -join '; ')" } else { Write-Host "uninstall left nothing behind" }
    foreach ($app in $Apps) {
        if (-not (Get-ChildItem (Join-Path $Scratch "user-$app\$($walk[$app].docs)") -Recurse -Filter "*$($walk[$app].ext)" -ErrorAction SilentlyContinue)) {
            Problem "the person's own $($walk[$app].name) files are gone after uninstall" }
    }
} catch {
    Problem "$_"
} finally {
    if ($envBefore) { foreach ($k in $userVars) { [Environment]::SetEnvironmentVariable($k, $envBefore[$k]) } }
    $after = @(& $agentState)
    if (($after -join "`n") -ne ($realAgentFiles -join "`n")) { Problem "the real user's agent servers changed during the walk:`n$($after -join "`n")" }
    else { Write-Host "the real user's $($after.Count) agent settings files list the same servers as before the walk" }
    foreach ($p in $realHashes.Keys) {
        $now = if (Test-Path $p) { (Get-FileHash $p).Hash } else { "absent" }
        Write-Host ("  {0}: {1}" -f $p, $(if ($now -eq $realHashes[$p]) { "byte-for-byte the same" } else { "bytes changed (same servers; the agent's own writes)" }))
    }
    foreach ($f in Get-ChildItem $saved -Filter *.lnk) { Copy-Item $f.FullName $desk -Force }
    Write-Host "desktop shortcuts put back: $((Get-ChildItem $saved -Filter *.lnk).Name -join ', ')"
}
if ($problems.Count) { Write-Host "FAIL: $($problems.Count) problem(s)" -ForegroundColor Red; exit 1 }
Write-Host "OK: installed $($Apps -join ' + '), walked as a new user (plain start, New → Save → reopen, double-click, export, licences), uninstalled clean" -ForegroundColor Green
