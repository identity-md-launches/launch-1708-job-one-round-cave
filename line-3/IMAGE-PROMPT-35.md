# The Chosen Stone — image editor prompt

Mode: installed image editor (`mcp__image__edit_image`), high quality, automatic size. Edit target: the hash-verified round 34 wall at `artifacts/line-3/wall.png`. Final output: `artifacts/line-3/wall-v15.png`, mirrored at `artifacts/line-3/wall.png`.

Exact prompt:

> Use case: precise-object-edit. This is the inherited cave wall, preserve exactly its square framing, warm rough rock, cracks, lighting and ALL existing paintings, including all Pepe frogs and hand digits. Add only one small handmade charcoal and chalk-white pigment motif on the unpainted rock at image pixels x=610..750, y=480..570 (coordinates for this 1254-square input): an uneven chalk ring around a small ochre pebble with a short charcoal trail of three dots leading to it. The meaning is selecting one exact stone on a long trail for inspection. Keep this addition modest, worn earth pigment, prehistoric Lascaux style with stone showing through. Do not move, erase, redraw, soften or replace any existing ancestor mark. No additional frog or hand needed; inherited Pepe has broad mouth and heavy-lidded eyes, hands five digits. No letters, numbers, captions, logos, signatures, border, frames, watermarks or modern rendering. Return the whole original square wall with only the addition.

The editor placed the motif slightly lower than requested and made four trail dots. Both suit the mark's meaning. To preserve ancestor pixels exactly, `finish_wall_35.py` retained only the new ring, ochre stone and dark trail pigment within `[630,546,798,645]`, discarding the editor's other image changes. No extra output image was retained.
