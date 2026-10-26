@echo off
REM Configure + build the P-Clay proof into proofs\3d-clay\.build. Run through the lock:
REM   pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "priyam: clay proof build" build cmd.exe /c <this folder>\build.bat
setlocal
set HERE=%~dp0
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cmake -S "%HERE%." -B "%HERE%.build" -G Ninja -DCMAKE_BUILD_TYPE=Release || exit /b 1
cmake --build "%HERE%.build" -j 4 || exit /b 1
