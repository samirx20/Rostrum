@echo off
REM Configure + build + install rostrum3d-core into apps\3d\core\.build\install.
REM Run through the lock:  pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: 3d core build" build cmd.exe /c C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\apps\3d\core\build.bat
REM Needs: the library folder from  python -I apps\3d\libs\lay_out.py  (its sdk\ folder; override with ROSTRUM3D_SDK), VS 2022 Build Tools, cmake + ninja.
setlocal
set HERE=%~dp0
if "%ROSTRUM3D_SDK%"=="" set ROSTRUM3D_SDK=%USERPROFILE%\.rostrum\libs\3d\5.2.2-cycles-a456b76-r3\sdk
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cmake -S "%HERE%." -B "%HERE%.build\obj" -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUNDLE="%ROSTRUM3D_SDK%" -DCMAKE_INSTALL_PREFIX="%HERE%.build\install" || exit /b 1
cmake --build "%HERE%.build\obj" -j 4 || exit /b 1
cmake --install "%HERE%.build\obj" || exit /b 1
