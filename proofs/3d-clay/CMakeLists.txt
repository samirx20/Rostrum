# P-Clay proof (throwaway): the clay core on OpenVDB, shown through Storm, rendered with Cycles.
# Built against the 3D library folder's sdk (OpenUSD, TBB, epoxy, OpenImageIO) plus OpenVDB 13.0's headers and
# import library from the same Blender lib-windows_x64 bundle (tag v5.2.2, commit 60d6e96) whose openvdb.dll is
# already in the library folder's runtime\bin (byte-identical). Nothing big is built from source.
cmake_minimum_required(VERSION 3.20)
project(clay_proof CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(BUNDLE "$ENV{USERPROFILE}/.rostrum/libs/3d/5.2.2-cycles-a456b76-r3/sdk" CACHE PATH "the 3D library folder's sdk")
set(OPENVDB "$ENV{USERPROFILE}/.rostrum/downloads/blender-lib-v5.2.2-openvdb/repo/openvdb" CACHE PATH
    "Blender lib-windows_x64 v5.2.2's openvdb folder (include, lib)")
if(NOT EXISTS "${BUNDLE}/usd/include/pxr/pxr.h")
  message(FATAL_ERROR "no usd/include/pxr/pxr.h in BUNDLE '${BUNDLE}'")
endif()
if(NOT EXISTS "${OPENVDB}/include/openvdb/openvdb.h")
  message(FATAL_ERROR "no include/openvdb/openvdb.h in OPENVDB '${OPENVDB}'")
endif()

set(CORE ${CMAKE_CURRENT_SOURCE_DIR}/../../apps/3d/core/src)
add_executable(clay_proof src/main.cpp src/clay.cpp src/mesh.cpp src/view.cpp ${CORE}/gl_context.cpp)
target_include_directories(clay_proof PRIVATE src ${CORE})
target_include_directories(clay_proof SYSTEM PRIVATE ${OPENVDB}/include
  ${BUNDLE}/usd/include ${BUNDLE}/tbb/include ${BUNDLE}/epoxy/include ${BUNDLE}/python/313/include
  ${BUNDLE}/OpenImageIO/include ${BUNDLE}/imath/include ${BUNDLE}/imath/include/Imath ${BUNDLE}/openexr/include
  ${BUNDLE}/fmt/include)
target_compile_definitions(clay_proof PRIVATE NOMINMAX _USE_MATH_DEFINES WIN32_LEAN_AND_MEAN OPENVDB_DLL
  __TBB_show_deprecation_message_atomic_H __TBB_show_deprecation_message_task_H)
target_compile_options(clay_proof PRIVATE /EHsc /bigobj /Zc:inline- /utf-8 /W3 /wd4244 /wd4267 /wd4305 /wd4251)
target_link_directories(clay_proof PRIVATE ${BUNDLE}/python/313/libs ${BUNDLE}/tbb/lib)
target_link_libraries(clay_proof PRIVATE ${OPENVDB}/lib/openvdb.lib
  ${BUNDLE}/usd/lib/usd_ms.lib ${BUNDLE}/tbb/lib/tbb.lib ${BUNDLE}/epoxy/lib/epoxy.lib
  ${BUNDLE}/OpenImageIO/lib/OpenImageIO.lib ${BUNDLE}/OpenImageIO/lib/OpenImageIO_Util.lib opengl32 psapi)
