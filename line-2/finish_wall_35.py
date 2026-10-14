#!/usr/bin/env python3
"""Add one in-memory transparent pigment insert while retaining the inherited wall."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import finish_wall_26 as imageops

ROOT = Path(__file__).resolve().parents[1]
WALL = ROOT / 'artifacts/line-2/wall.png'
SOURCE_SHA256 = 'f8f88eb547f175934a80a47ea39774e7cf949db02e10e6eb60b248d7c2aeb26b'
PLACEMENT = (505, 185, 135, 80)


def main():
    source = WALL.read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('expected the verified Pepe 34 wall; refusing a different source')
    width, height, channels, original = imageops.decode(source)
    if (width, height, channels) != (1254, 1254, 3):
        raise ValueError('unexpected inherited wall format')
    # The generator payload is one base64 line supplied through standard input.
    # This avoids retaining a generated insert as a workspace image file.
    encoded = sys.stdin.buffer.readline().strip()
    if encoded.startswith(b'data:image/png;base64,'):
        encoded = encoded.split(b',', 1)[1]
    mw, mh, mc, mark = imageops.decode(base64.b64decode(encoded, validate=True))
    if mc != 4:
        raise ValueError('generated motif is not transparent RGBA')
    # Drop faint machine glow: opaque pigment only is allowed onto the ancestor.
    cleaned = []
    for row in mark:
        pixels = bytearray(row)
        for offset in range(3, len(pixels), 4):
            if pixels[offset] < 180:
                pixels[offset] = 0
        cleaned.append(bytes(pixels))
    imageops.PLACE_X, imageops.PLACE_Y, imageops.PLACE_W, imageops.PLACE_H = PLACEMENT
    result, alpha_bounds = imageops.composite(original, (mw, mh, mc, cleaned))
    x, y, w, h = PLACEMENT
    for row_number, (old, new) in enumerate(zip(original, result)):
        if not y <= row_number < y + h:
            assert old == new
        else:
            assert old[:3*x] == new[:3*x] and old[3*(x+w):] == new[3*(x+w):]
    output = imageops.encode(width, height, result)
    WALL.write_bytes(output)
    (WALL.parent / 'wall-v15.png').write_bytes(output)
    thumbnail_spec = importlib.util.spec_from_file_location('thumbnail', ROOT / 'shared/wall-thumbnail/thumbnail.py')
    thumbnail = importlib.util.module_from_spec(thumbnail_spec)
    thumbnail_spec.loader.exec_module(thumbnail)
    preview = thumbnail.jpeg(thumbnail.resize(width, height, result, 512))
    if len(preview) >= 100_000:
        raise ValueError('preview exceeds 100 KiB')
    (ROOT / 'dist/line-2/35.jpg').write_bytes(preview)
    digest = hashlib.sha256(output).hexdigest()
    record = {
        'name': 'The Crossed Ceiling',
        'image': 'https://api.imd.fun/artifacts/' + digest,
        'attributes': [
            {'trait_type': 'Cave', 'value': 'Moss'},
            {'trait_type': 'Wall', 'value': 'Line 2'},
            {'trait_type': 'Number', 'value': 35},
            {'trait_type': 'Left behind', 'value': 'Permission Policy Transition'},
            {'trait_type': 'Meaning', 'value': 'Two ochre stones share a charcoal cord beneath a broken chalk ceiling.'},
            {'trait_type': 'One thing', 'value': 'ERC-20 spending-permission audits'},
        ],
    }
    (ROOT / 'dist/line-2/35.json').write_text(json.dumps(record, indent=2) + '\n')
    changed = sum(old[offset:offset+3] != new[offset:offset+3]
                  for old, new in zip(original, result) for offset in range(0, len(old), 3))
    checks = {
        'source_sha256': SOURCE_SHA256, 'output_sha256': digest,
        'format': 'PNG', 'dimensions': [width, height], 'placement': PLACEMENT,
        'changed_pixels': changed, 'outside_placement_unchanged': True,
        'insert_alpha_bounds': alpha_bounds,
        'preview': {'format': 'JPEG', 'dimensions': [512, 512], 'bytes': len(preview)},
        'unmet_visual_requirements': [],
        'visual_review': 'Pending final inspection',
    }
    (ROOT / 'line-2/visual-checks-35.json').write_text(json.dumps(checks, indent=2) + '\n')
    print(json.dumps(checks))


if __name__ == '__main__':
    main()
