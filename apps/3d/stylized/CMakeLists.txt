# The Rostrum Stylized Hydra render delegate (hdRostrum), built against the OpenUSD of the 3D
# library folder's sdk\ (the same OpenUSD the core and Cycles use). See build.bat.
cmake_minimum_required(VERSION 3.20)
project(hdRostrum CXX)
set(CMAKE_CXX_STANDARD 17)
set(SDK "" CACHE PATH "the library folder's sdk (usd, tbb, epoxy, python/313)")
foreach(need usd/include/pxr/pxr.h usd/lib/usd_ms.lib tbb/lib/tbb.lib epoxy/include/epoxy/gl.h epoxy/lib/epoxy.lib
        python/313/include/Python.h)
  if(NOT EXISTS "${SDK}/${need}")
    message(FATAL_ERROR "SDK must point at the library folder's sdk: no ${need} in '${SDK}'")
  endif()
endforeach()

file(GLOB SRC src/*.cpp src/*.h)
add_library(hdRostrum SHARED ${SRC})
target_include_directories(hdRostrum SYSTEM PRIVATE
  ${SDK}/usd/include ${SDK}/tbb/include ${SDK}/epoxy/include ${SDK}/python/313/include)
target_compile_definitions(hdRostrum PRIVATE NOMINMAX _USE_MATH_DEFINES WIN32_LEAN_AND_MEAN
  __TBB_show_deprecation_message_atomic_H __TBB_show_deprecation_message_task_H)
target_compile_options(hdRostrum PRIVATE /EHsc /bigobj /Zc:inline- /W3 /wd4244 /wd4267 /wd4305)
target_link_directories(hdRostrum PRIVATE ${SDK}/python/313/libs ${SDK}/tbb/lib)
target_link_libraries(hdRostrum PRIVATE ${SDK}/usd/lib/usd_ms.lib ${SDK}/tbb/lib/tbb.lib
  ${SDK}/epoxy/lib/epoxy.lib opengl32)

# install layout:  <prefix>/plugInfo.json, <prefix>/hdRostrum.dll, <prefix>/hdRostrum/resources/...
install(TARGETS hdRostrum RUNTIME DESTINATION .)
install(FILES resources/plugInfo.json DESTINATION hdRostrum/resources)
install(FILES plugInfo.root.json DESTINATION . RENAME plugInfo.json)
install(DIRECTORY resources/shaders DESTINATION hdRostrum/resources)
