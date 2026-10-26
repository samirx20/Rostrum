@echo off
REM Build the proof into .build\ (through the lock):
REM   pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "priyam: pview build" build cmd.exe /c <this folder>\build.bat
setlocal
set HERE=%~dp0
if "%ROSTRUM3D_SDK%"=="" set ROSTRUM3D_SDK=%USERPROFILE%\.rostrum\libs\3d\5.2.2-cycles-a456b76-r3\sdk
if "%QT_DIR%"=="" set QT_DIR=%USERPROFILE%\.rostrum\libs\qt\6.12.0-msvc2022_64
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cmake -S "%HERE%." -B "%HERE%.build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUNDLE="%ROSTRUM3D_SDK%" -DCMAKE_PREFIX_PATH="%QT_DIR%" || exit /b 1
cmake --build "%HERE%.build" -j 4 || exit /b 1
