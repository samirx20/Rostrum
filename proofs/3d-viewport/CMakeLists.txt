# P-3D-viewport proof (throwaway): Storm drawing inside the Qt Quick window's own process. Two parts that never share
# a source file: `pview_draw` (USD/Hydra/epoxy + the clay core's own files from apps/3d/core/src, unchanged, with the
# core's compiler flags) and `pview` (Qt 6.12, Qt's flags). Built against the 3D library folder's sdk (like the core)
# and the Qt SDK in QT_DIR.
cmake_minimum_required(VERSION 3.21)
project(pview CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(BUNDLE "" CACHE PATH "the 3D library folder's sdk")
set(CORE "${CMAKE_CURRENT_SOURCE_DIR}/../../apps/3d/core/src")

add_library(pview_draw STATIC src/draw.cpp src/head.cpp
  ${CORE}/clay_volume.cpp ${CORE}/clay_volume_io.cpp ${CORE}/clay_band.cpp ${CORE}/clay_coarse.cpp ${CORE}/clay_mesh.cpp
  ${CORE}/clay_stroke.cpp ${CORE}/clay_usd.cpp ${CORE}/clay_dabs.cpp)
target_include_directories(pview_draw PUBLIC src PRIVATE ${CORE})
target_include_directories(pview_draw SYSTEM PRIVATE
  ${BUNDLE}/usd/include ${BUNDLE}/tbb/include ${BUNDLE}/epoxy/include ${BUNDLE}/python/313/include
  ${BUNDLE}/imath/include ${BUNDLE}/imath/include/Imath ${BUNDLE}/openexr/include ${BUNDLE}/openvdb/include)
target_compile_definitions(pview_draw PRIVATE NOMINMAX _USE_MATH_DEFINES WIN32_LEAN_AND_MEAN OPENVDB_DLL
  __TBB_show_deprecation_message_atomic_H __TBB_show_deprecation_message_task_H)
target_compile_options(pview_draw PRIVATE /EHsc /bigobj /Zc:inline- /utf-8 /W3 /wd4244 /wd4267 /wd4305 /wd4251)
target_link_directories(pview_draw PUBLIC ${BUNDLE}/python/313/libs ${BUNDLE}/tbb/lib)
target_link_libraries(pview_draw PUBLIC ${BUNDLE}/usd/lib/usd_ms.lib ${BUNDLE}/tbb/lib/tbb.lib
  ${BUNDLE}/epoxy/lib/epoxy.lib ${BUNDLE}/openvdb/lib/openvdb.lib opengl32)

find_package(Qt6 REQUIRED COMPONENTS Gui GuiPrivate Qml Quick Test)
set(CMAKE_AUTOMOC ON)
# not "pview.exe": the NVIDIA driver has a profile for that name that caps OpenGL at 1.2 (found the hard way)
add_executable(r3d_viewport_proof src/main.cpp src/view.cpp src/view.h)
target_compile_definitions(r3d_viewport_proof PRIVATE NOMINMAX QT_NO_KEYWORDS)
target_compile_options(r3d_viewport_proof PRIVATE /utf-8)
target_link_libraries(r3d_viewport_proof PRIVATE pview_draw Qt6::Gui Qt6::GuiPrivate Qt6::Qml Qt6::Quick Qt6::Test psapi)
