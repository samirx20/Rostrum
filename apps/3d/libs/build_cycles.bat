@echo off
REM Cycles' Hydra plug-in with our patch (cycles-rostrum.patch: H22's lights - a dome the camera doesn't see, panel
REM spread, light linking; 3D-11b's object motion blur - transforms sampled over the shutter; 3D-15's light passes and rostrum:castShadows; 3D leftovers' per-copy colour; PR9's light groups, Cryptomatte and motion vectors), built into install-r5\.
REM Run through the lock:
REM   pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "<team>: cycles r5 build" build cmd.exe /c <worktree>\apps\3d\libs\build_cycles.bat
REM Then: python -I apps\3d\libs\lay_out.py   (lays out the new library folder, VERSION in lay_out.py)
REM The GPU kernels don't change with the patch (it touches src\hydra only), so they are not rebuilt: they are copied
REM from the laid-out library folder (KERNELS below, or set ROSTRUM3D_KERNELS). Needs what proofs\3d-product\build.bat
REM needs. A source tree carrying an older version of the patch is reset first (src\hydra only).
setlocal
set HERE=%~dp0
set SRC=%HERE%..\..\..\proofs\3d-product\.build\cycles
set PATCH=%HERE%cycles-rostrum.patch
set CUDA=C:/Users/Sam/.rostrum/tools/cuda-12.9
set OPTIX=C:/Users/Sam/.rostrum/tools/optix-9.1
set KERNELS=%ROSTRUM3D_KERNELS%
if "%KERNELS%"=="" set KERNELS=%USERPROFILE%\.rostrum\libs\3d\5.2.2-cycles-a456b76-r2\runtime\hydra\cycles\lib
if not exist "%KERNELS%\kernel_optix.ptx.zst" (echo no GPU kernels in %KERNELS% & exit /b 1)
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set CUDA_PATH=%CUDA%
set PATH=%CUDA%\bin;%PATH%
git -C "%SRC%" apply --reverse --check "%PATCH%" 2>nul
if errorlevel 1 (
  git -C "%SRC%" checkout -- src/hydra || exit /b 1
  git -C "%SRC%" apply "%PATCH%" || (echo the patch does not apply to %SRC% & exit /b 1)
)
REM the build folder; ROSTRUM3D_CYCLES_BUILD may name an earlier one (e.g. build-r2) so only the changed files compile
set BUILD=%ROSTRUM3D_CYCLES_BUILD%
if "%BUILD%"=="" set BUILD=%SRC%\build-r5
cmake -S "%SRC%" -B "%BUILD%" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="%SRC%\install-r5" ^
  -DCUDA_TOOLKIT_ROOT_DIR="%CUDA%" -DWITH_CYCLES_CUDA_BINARIES=OFF ^
  -DWITH_CYCLES_DEVICE_OPTIX=ON -DOPTIX_ROOT_DIR="%OPTIX%" ^
  -DWITH_CYCLES_DEVICE_HIP=OFF -DWITH_CYCLES_DEVICE_ONEAPI=OFF ^
  -DWITH_CYCLES_OSL=OFF -DWITH_CYCLES_ALEMBIC=OFF -DWITH_CYCLES_OPENVDB=OFF -DWITH_CYCLES_NANOVDB=OFF ^
  -DWITH_CYCLES_USD=ON -DWITH_CYCLES_HYDRA_RENDER_DELEGATE=ON -DWITH_STRICT_BUILD_OPTIONS=ON || exit /b 1
cmake --build "%BUILD%" -j 4 --target install || exit /b 1
if not exist "%SRC%\install-r5\lib" mkdir "%SRC%\install-r5\lib"
copy /y "%KERNELS%\*.zst" "%SRC%\install-r5\lib\" >nul || (echo could not copy the GPU kernels from %KERNELS% & exit /b 1)
if not exist "%SRC%\install-r5\hydra\hdCycles.dll" (echo the build made no hydra\hdCycles.dll & exit /b 1)
echo built %SRC%\install-r5
