# Imports of glTF / GLB, OBJ, FBX and Alembic (src/convert*.cpp, convert.h). Included from CMakeLists.txt after
# r3d_core is defined:  include(convert.cmake)
#
# - cgltf v1.15 (third_party/cgltf, MIT, unmodified cgltf.h + LICENSE) and tinyobjloader v2.0.0rc13
#   (third_party/tinyobjloader, MIT, unmodified tiny_obj_loader.h + LICENSE): single headers, their implementations
#   compiled once in src/convert_gltf.cpp and src/convert_obj.cpp.
# - ufbx v0.23.1 (third_party/ufbx, MIT or public domain, unmodified ufbx.c, ufbx.h + LICENSE): ufbx.c is C, so the
#   project must have C enabled. `project(... CXX)` doesn't; this turns it on (allowed after project()).
# - Alembic 1.8.3 (BSD-3), the static Alembic.lib of Blender's lib/windows_x64 bundle, laid into ${BUNDLE}/alembic
#   (include/Alembic/..., lib/Alembic.lib). Built static: ALEMBIC_DLL must stay undefined. Its headers include
#   Imath's (already on r3d_core's include path: ${BUNDLE}/imath/include and .../Imath) and it links Imath.lib.

enable_language(C)

add_library(ufbx STATIC third_party/ufbx/ufbx.c)
target_include_directories(ufbx PUBLIC third_party/ufbx)
target_compile_options(ufbx PRIVATE /utf-8 /W0)

if(NOT EXISTS "${BUNDLE}/alembic/include/Alembic/Abc/All.h")
  message(FATAL_ERROR "no alembic/include/Alembic/Abc/All.h in BUNDLE '${BUNDLE}'; run apps/3d/libs/lay_out.py again")
endif()

target_include_directories(r3d_core SYSTEM PRIVATE third_party/cgltf third_party/tinyobjloader
  ${BUNDLE}/alembic/include ${BUNDLE}/imath/include ${BUNDLE}/imath/include/Imath)
target_link_libraries(r3d_core PUBLIC ufbx ${BUNDLE}/alembic/lib/Alembic.lib ${BUNDLE}/imath/lib/Imath.lib)
