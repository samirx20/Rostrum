@echo off
REM P-3D-1: configure + build standalone Cycles (Hydra delegate, USD reader, CUDA/OptiX for sm_86).
REM Run through the lock:  pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: cycles build" build cmd.exe /c C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-product\build.bat
REM Needs: .build\cycles with lib\windows_x64 (make_update.py), VS 2022 Build Tools, CUDA 12.9 redist and OptiX headers in C:\Users\Sam\.rostrum\tools.
setlocal
set HERE=%~dp0
set SRC=%HERE%.build\cycles
set CUDA=C:/Users/Sam/.rostrum/tools/cuda-12.9
set OPTIX=C:/Users/Sam/.rostrum/tools/optix-9.1
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set CUDA_PATH=%CUDA%
set PATH=%CUDA%\bin;%PATH%
cmake -S "%SRC%" -B "%SRC%\build" -G Ninja -DCMAKE_BUILD_TYPE=Release ^
  -DCUDA_TOOLKIT_ROOT_DIR="%CUDA%" -DWITH_CYCLES_CUDA_BINARIES=ON -DCYCLES_CUDA_BINARIES_ARCH=sm_86 ^
  -DWITH_CYCLES_DEVICE_OPTIX=ON -DOPTIX_ROOT_DIR="%OPTIX%" ^
  -DWITH_CYCLES_DEVICE_HIP=OFF -DWITH_CYCLES_DEVICE_ONEAPI=OFF ^
  -DWITH_CYCLES_OSL=OFF -DWITH_CYCLES_ALEMBIC=OFF -DWITH_CYCLES_OPENVDB=OFF -DWITH_CYCLES_NANOVDB=OFF ^
  -DWITH_CYCLES_USD=ON -DWITH_CYCLES_HYDRA_RENDER_DELEGATE=ON -DWITH_STRICT_BUILD_OPTIONS=ON || exit /b 1
cmake --build "%SRC%\build" -j 4 --target install || exit /b 1
