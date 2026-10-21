# Opens the app on its sample project. Same as: rostrum.ps1 3d  (see rostrum.ps1 for -Doc, -Shot)
& (Join-Path $PSScriptRoot "rostrum.ps1") 3d @args
exit $LASTEXITCODE
