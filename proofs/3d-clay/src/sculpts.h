// P-Clay proof: the comparison sculpts (member B). Throwaway proof code.
#pragma once
#include "session.h"

namespace clay {

// An agent's head through the proof's steps (pieces + world-space strokes with every brush), Y up, facing +Z,
// about 0.25 tall, centred near the origin, same scale and framing as main.cpp's head.
void sculpt_agent_head(Session& S);
// An agent's small character (whole body, about 0.25 tall, standing on y = -0.125, facing +Z).
void sculpt_agent_character(Session& S);
// A head made the way a person with a mouse would: rough forms by pieces only where a person would drop a sphere
// (at most 4), everything else by strokes along pixel paths through `cam` (stroke_screen), several views.
void sculpt_mouse_head(Session& S, int width, int height);

// cameras for side-by-side pictures (similar framing to the reference pictures)
Camera head_three_quarter();
Camera head_front();
Camera character_three_quarter();

}  // namespace clay
