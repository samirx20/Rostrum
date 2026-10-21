# Opens the app on its sample project. Same as: rostrum.ps1 sound  (see rostrum.ps1 for -Doc, -Shot)
& (Join-Path $PSScriptRoot "rostrum.ps1") sound @args
exit $LASTEXITCODE
