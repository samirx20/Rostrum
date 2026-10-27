@echo off
REM P-3D-3: configure + build + install the Rostrum Stylized Hydra delegate (about a minute).
REM Run through the lock:  pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: hdRostrum build" build cmd.exe /c C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-stylized\build.bat
REM Needs: H1's library bundle (proofs\3d-product\.build\cycles\lib\windows_x64), VS 2022 Build Tools, cmake + ninja.
setlocal
set HERE=%~dp0
set BUNDLE=%HERE%..\3d-product\.build\cycles\lib\windows_x64
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cmake -S "%HERE%." -B "%HERE%.build\obj" -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUNDLE="%BUNDLE%" -DCMAKE_INSTALL_PREFIX="%HERE%.build\install" || exit /b 1
cmake --build "%HERE%.build\obj" -j 4 || exit /b 1
cmake --install "%HERE%.build\obj" || exit /b 1
