# Opens the app on its sample project. Same as: rostrum.ps1 sound  (see rostrum.ps1 for -Doc, -Step, -Shot)
$ErrorActionPreference = "Stop"          # a problem calling the launcher stops here with a non-zero exit
& (Join-Path $PSScriptRoot "rostrum.ps1") sound @args
exit $LASTEXITCODE
