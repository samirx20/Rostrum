# Opens the app on its sample project. Same as: rostrum.ps1 3d  (see rostrum.ps1 for -Doc, -Step, -Shot)
$ErrorActionPreference = "Stop"          # a problem calling the launcher stops here with a non-zero exit
& (Join-Path $PSScriptRoot "rostrum.ps1") 3d @args
exit $LASTEXITCODE
