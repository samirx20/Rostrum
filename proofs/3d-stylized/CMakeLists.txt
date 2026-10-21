# P-3D-3: the Rostrum Stylized Hydra render delegate, built against the OpenUSD in Blender's
# Windows library bundle (the same one H1's Cycles build uses). See build.bat.
cmake_minimum_required(VERSION 3.20)
project(hdRostrum CXX)
set(CMAKE_CXX_STANDARD 17)
set(BUNDLE "" CACHE PATH "Blender lib-windows_x64 folder")
if(NOT EXISTS "${BUNDLE}/usd/include/pxr/pxr.h")
  message(FATAL_ERROR "BUNDLE must point at lib\windows_x64 (no usd/include/pxr/pxr.h in '${BUNDLE}')")
endif()

file(GLOB SRC src/*.cpp src/*.h)
add_library(hdRostrum SHARED ${SRC})
target_include_directories(hdRostrum SYSTEM PRIVATE
  ${BUNDLE}/usd/include ${BUNDLE}/tbb/include ${BUNDLE}/epoxy/include ${BUNDLE}/python/313/include)
target_compile_definitions(hdRostrum PRIVATE NOMINMAX _USE_MATH_DEFINES WIN32_LEAN_AND_MEAN
  __TBB_show_deprecation_message_atomic_H __TBB_show_deprecation_message_task_H)
target_compile_options(hdRostrum PRIVATE /EHsc /bigobj /Zc:inline- /W3 /wd4244 /wd4267 /wd4305)
target_link_directories(hdRostrum PRIVATE ${BUNDLE}/python/313/libs ${BUNDLE}/tbb/lib)
target_link_libraries(hdRostrum PRIVATE ${BUNDLE}/usd/lib/usd_ms.lib ${BUNDLE}/tbb/lib/tbb.lib
  ${BUNDLE}/epoxy/lib/epoxy.lib opengl32)

# install layout:  <prefix>/plugInfo.json, <prefix>/hdRostrum.dll, <prefix>/hdRostrum/resources/...
install(TARGETS hdRostrum RUNTIME DESTINATION .)
install(FILES resources/plugInfo.json DESTINATION hdRostrum/resources)
install(FILES plugInfo.root.json DESTINATION . RENAME plugInfo.json)
install(DIRECTORY resources/shaders DESTINATION hdRostrum/resources)
