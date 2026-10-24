# rostrum3d-core: the Rostrum3D engine program (ENGINE_CONTRACT.md). Built against Blender's prebuilt
# Windows library bundle (OpenUSD with Hydra, OpenImageIO, OpenColorIO, TBB, epoxy): no big source builds.
# The headers and .lib files come from the library folder's sdk\ (apps/3d/libs/lay_out.py); the DLLs are found at run time
# through PATH set by rostrum3d/runtime.py.
cmake_minimum_required(VERSION 3.20)
project(rostrum3d_core CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(BUNDLE "" CACHE PATH "the sdk folder of the library folder (apps/3d/libs/lay_out.py), same layout as Blender's lib/windows_x64")
if(NOT EXISTS "${BUNDLE}/usd/include/pxr/pxr.h")
  message(FATAL_ERROR "BUNDLE must point at the library folder's sdk (no usd/include/pxr/pxr.h in '${BUNDLE}'); run apps/3d/libs/lay_out.py")
endif()

# Manifold (third_party/manifold, Apache-2.0, unmodified): mesh booleans for `combine` items. Serial build:
# MANIFOLD_PAR=-1, so no TBB, Clipper2 or Tracy. Kept outside src/ so the core's own glob doesn't pick it up.
file(GLOB MANIFOLD_SRC CONFIGURE_DEPENDS third_party/manifold/src/*.cpp)
add_library(manifold STATIC ${MANIFOLD_SRC})
target_compile_definitions(manifold PUBLIC MANIFOLD_PAR=-1 PRIVATE NOMINMAX _USE_MATH_DEFINES)
target_include_directories(manifold PUBLIC third_party/manifold/include PRIVATE third_party/manifold/src)
target_compile_options(manifold PRIVATE /EHsc /utf-8 /bigobj /W0)

# OpenSubdiv 3.7.0 (third_party/opensubdiv, Tomorrow Open Source Technology License 1.0 = Apache-2.0 with a
# trademark clause, unmodified): only Sdc, Vtr and Far's topology refiner, for an editable mesh's Smooth surface.
# USD has its own copy inside usd_ms.dll, but doesn't export it.
file(GLOB OSD_SRC CONFIGURE_DEPENDS third_party/opensubdiv/opensubdiv/sdc/*.cpp third_party/opensubdiv/opensubdiv/vtr/*.cpp)
add_library(opensubdiv_far STATIC ${OSD_SRC} third_party/opensubdiv/opensubdiv/far/error.cpp
  third_party/opensubdiv/opensubdiv/far/topologyDescriptor.cpp third_party/opensubdiv/opensubdiv/far/topologyRefiner.cpp
  third_party/opensubdiv/opensubdiv/far/topologyRefinerFactory.cpp)
target_compile_definitions(opensubdiv_far PRIVATE NOMINMAX _USE_MATH_DEFINES)
target_include_directories(opensubdiv_far PUBLIC third_party/opensubdiv)
target_compile_options(opensubdiv_far PRIVATE /EHsc /utf-8 /W0)

# xatlas (third_party/xatlas, MIT, jpcy/xatlas @ f700c77, unmodified: xatlas.cpp, xatlas.h, LICENSE): automatic
# unfolding of a mesh for painting (src/unfold.cpp, the `unfold` request).
add_library(xatlas STATIC third_party/xatlas/xatlas.cpp)
target_compile_definitions(xatlas PRIVATE NOMINMAX _USE_MATH_DEFINES)
target_include_directories(xatlas PUBLIC third_party/xatlas)
target_compile_options(xatlas PRIVATE /EHsc /utf-8 /bigobj /W0)

file(GLOB SRC CONFIGURE_DEPENDS src/*.cpp src/*.h)
add_executable(rostrum3d-core ${SRC})
target_include_directories(rostrum3d-core SYSTEM PRIVATE
  ${BUNDLE}/usd/include ${BUNDLE}/tbb/include ${BUNDLE}/epoxy/include ${BUNDLE}/python/313/include
  ${BUNDLE}/OpenImageIO/include ${BUNDLE}/imath/include ${BUNDLE}/imath/include/Imath
  ${BUNDLE}/openexr/include ${BUNDLE}/fmt/include ${BUNDLE}/opencolorio/include)
target_compile_definitions(rostrum3d-core PRIVATE NOMINMAX _USE_MATH_DEFINES WIN32_LEAN_AND_MEAN
  __TBB_show_deprecation_message_atomic_H __TBB_show_deprecation_message_task_H)
target_compile_options(rostrum3d-core PRIVATE /EHsc /bigobj /Zc:inline- /utf-8 /W3 /wd4244 /wd4267 /wd4305)
target_link_directories(rostrum3d-core PRIVATE ${BUNDLE}/python/313/libs ${BUNDLE}/tbb/lib)
target_link_libraries(rostrum3d-core PRIVATE
  ${BUNDLE}/usd/lib/usd_ms.lib ${BUNDLE}/tbb/lib/tbb.lib ${BUNDLE}/epoxy/lib/epoxy.lib
  ${BUNDLE}/OpenImageIO/lib/OpenImageIO.lib ${BUNDLE}/OpenImageIO/lib/OpenImageIO_Util.lib ${BUNDLE}/opencolorio/lib/OpenColorIO.lib
  manifold opensubdiv_far xatlas opengl32 dxgi psapi)

install(TARGETS rostrum3d-core RUNTIME DESTINATION .)
