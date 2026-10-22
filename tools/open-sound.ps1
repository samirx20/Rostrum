# Opens the app: your last song, else a new one (-Sample: the Lull sample). Same as: rostrum.ps1 sound  (see rostrum.ps1 for -Doc, -Step, -Shot)
$ErrorActionPreference = "Stop"          # a problem calling the launcher stops here with a non-zero exit
& (Join-Path $PSScriptRoot "rostrum.ps1") sound @args
exit $LASTEXITCODE
