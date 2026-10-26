@echo off
REM Run the proof (GPU: through the lock):
REM   pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "priyam: pview run" gpu cmd.exe /c <this folder>\run.bat --mode sculpt --brush medium --out <folder>
setlocal
set RT=%USERPROFILE%\.rostrum\libs\3d\5.2.2-cycles-a456b76-r3\runtime
if "%QT_DIR%"=="" set QT_DIR=%USERPROFILE%\.rostrum\libs\qt\6.12.0-msvc2022_64
set PATH=%QT_DIR%\bin;%RT%\bin;%RT%\usd\lib;%PATH%
set QT_PLUGIN_PATH=%QT_DIR%\plugins
set QML_IMPORT_PATH=%QT_DIR%\qml
set QML2_IMPORT_PATH=%QT_DIR%\qml
"%~dp0.build\r3d_viewport_proof.exe" %*
