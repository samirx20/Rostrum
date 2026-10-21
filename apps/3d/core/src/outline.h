// The selection outline in the live viewport: a ring a few pixels wide just outside the selected items' mask,
// in the GUI kit's accent colour, drawn over the displayed 8-bit picture.
#pragma once
#include "image_out.h"

namespace r3d {

void draw_outline(const Picture& p, unsigned char* rgba8, int radius = 2);

}  // namespace r3d
