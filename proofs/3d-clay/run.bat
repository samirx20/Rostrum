@echo off
REM Run the P-Clay proof (GPU: through the lock):
REM   pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "priyam: clay proof run" gpu cmd.exe /c <this folder>\run.bat <out folder> [options]
setlocal
set RT=%USERPROFILE%\.rostrum\libs\3d\5.2.2-cycles-a456b76-r3\runtime
set PATH=%RT%\bin;%RT%\usd\lib;%PATH%
set PXR_PLUGINPATH_NAME=%RT%\hydra\cycles\hydra
if "%CYCLES_DEVICE%"=="" set CYCLES_DEVICE=OPTIX
"%~dp0.build\clay_proof.exe" %*
