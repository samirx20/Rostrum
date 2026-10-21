@echo off
REM H22: Cycles' Hydra plug-in with our lights patch (cycles-rostrum-lights.patch: a dome the camera doesn't see,
REM panel spread, light linking), built into install-r1\ next to the proof's install\ (which stays untouched).
REM Run through the lock:
REM   pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: cycles r1 build" build cmd.exe /c <worktree>\apps\3d\libs\build_cycles.bat
REM Then: python -I apps\3d\libs\lay_out.py   (lays out the new library folder, VERSION in lay_out.py)
REM The GPU kernels don't change with the patch (it touches src\hydra only), so they are not rebuilt:
REM they are copied from install\lib. Needs what proofs\3d-product\build.bat needs.
setlocal
set HERE=%~dp0
set SRC=%HERE%..\..\..\proofs\3d-product\.build\cycles
set PATCH=%HERE%cycles-rostrum-lights.patch
set CUDA=C:/Users/Sam/.rostrum/tools/cuda-12.9
set OPTIX=C:/Users/Sam/.rostrum/tools/optix-9.1
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set CUDA_PATH=%CUDA%
set PATH=%CUDA%\bin;%PATH%
git -C "%SRC%" apply --reverse --check "%PATCH%" 2>nul
if errorlevel 1 (
  git -C "%SRC%" apply "%PATCH%" || (echo the lights patch does not apply to %SRC% & exit /b 1)
)
cmake -S "%SRC%" -B "%SRC%\build-r1" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="%SRC%\install-r1" ^
  -DCUDA_TOOLKIT_ROOT_DIR="%CUDA%" -DWITH_CYCLES_CUDA_BINARIES=OFF ^
  -DWITH_CYCLES_DEVICE_OPTIX=ON -DOPTIX_ROOT_DIR="%OPTIX%" ^
  -DWITH_CYCLES_DEVICE_HIP=OFF -DWITH_CYCLES_DEVICE_ONEAPI=OFF ^
  -DWITH_CYCLES_OSL=OFF -DWITH_CYCLES_ALEMBIC=OFF -DWITH_CYCLES_OPENVDB=OFF -DWITH_CYCLES_NANOVDB=OFF ^
  -DWITH_CYCLES_USD=ON -DWITH_CYCLES_HYDRA_RENDER_DELEGATE=ON -DWITH_STRICT_BUILD_OPTIONS=ON || exit /b 1
cmake --build "%SRC%\build-r1" -j 4 --target install || exit /b 1
if not exist "%SRC%\install-r1\lib" mkdir "%SRC%\install-r1\lib"
copy /y "%SRC%\install\lib\*.zst" "%SRC%\install-r1\lib\" >nul || (echo no GPU kernels in %SRC%\install\lib & exit /b 1)
if not exist "%SRC%\install-r1\hydra\hdCycles.dll" (echo the build made no hydra\hdCycles.dll & exit /b 1)
echo built %SRC%\install-r1
