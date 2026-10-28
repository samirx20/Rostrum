@echo off
REM Configure + build + install the Rostrum Stylized Hydra delegate (hdRostrum) into .build\install
REM (hdRostrum.dll, plugInfo.json, hdRostrum\resources\{plugInfo.json,shaders}); about a minute.
REM Run it through the lock, from PowerShell (a cmd started from Git Bash through pwsh builds nothing):
REM   pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "<team>: hdRostrum build" build cmd.exe /c <worktree>\apps\3d\stylized\build.bat
REM Needs: the 3D library folder (its sdk\: usd, tbb, epoxy, python\313), VS 2022 Build Tools, cmake + ninja.
REM The library folder's sdk is %USERPROFILE%\.rostrum\libs\3d\5.2.2-cycles-a456b76-r4\sdk; set ROSTRUM3D_SDK to use another.
REM Shaders are read at run time from the install (or %ROSTRUM_SHADERS%): a shader-only change needs only the install step.
setlocal
set HERE=%~dp0
if "%ROSTRUM3D_SDK%"=="" (set SDK=%USERPROFILE%\.rostrum\libs\3d\5.2.2-cycles-a456b76-r4\sdk) else (set SDK=%ROSTRUM3D_SDK%)
if not exist "%SDK%\usd\include\pxr\pxr.h" (echo build.bat: no OpenUSD in "%SDK%" ^(set ROSTRUM3D_SDK^) & exit /b 1)
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cmake -S "%HERE%." -B "%HERE%.build\obj" -G Ninja -DCMAKE_BUILD_TYPE=Release -DSDK="%SDK%" -DCMAKE_INSTALL_PREFIX="%HERE%.build\install" || exit /b 1
cmake --build "%HERE%.build\obj" -j 4 || exit /b 1
cmake --install "%HERE%.build\obj" || exit /b 1
