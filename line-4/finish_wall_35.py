#!/usr/bin/env python3
"""Keep only Pepe 35's editor pigment patch and create the required wall files."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import zlib

ROOT = Path.cwd().resolve()
ANCESTOR = ROOT / 'artifacts/line-4/wall.png'
EDITED = ROOT / 'artifacts/line-4/wall-v15.png'
PATCH = (120, 810, 205, 900)
FEATHER = 7


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def write_png(width, height, rows):
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b''.join(b'\0' + bytes(row) for row in rows), 9))
            + chunk(b'IEND', b''))


def weight(x, y):
    left, top, right, bottom = PATCH
    if not (left <= x < right and top <= y < bottom):
        return 0.0
    edge = min(x - left + 1, right - x, y - top + 1, bottom - y)
    return min(1.0, edge / FEATHER)


def main():
    before = ANCESTOR.read_bytes()
    ancestor_hash = hashlib.sha256(before).hexdigest()
    spec = importlib.util.spec_from_file_location(
        'thumbnail35', ROOT / 'line-4/tools/call-rehearsal/thumbnail.py')
    codec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(codec)
    width, height, old = codec.png_rgb(ANCESTOR)
    edited_width, edited_height, new = codec.png_rgb(EDITED)
    assert (width, height) == (edited_width, edited_height) == (1254, 1254)
    rows, inside, outside = [bytearray(row) for row in old], 0, 0
    for y in range(height):
        for x in range(width):
            alpha = weight(x, y)
            if alpha:
                offset = x * 3
                for channel in range(3):
                    rows[y][offset + channel] = round(
                        old[y][offset + channel] * (1 - alpha) + new[y][offset + channel] * alpha)
            offset = x * 3
            if rows[y][offset:offset + 3] != old[y][offset:offset + 3]:
                if alpha:
                    inside += 1
                else:
                    outside += 1
    assert inside > 0 and outside == 0
    finished = write_png(width, height, rows)
    ANCESTOR.write_bytes(finished)
    EDITED.write_bytes(finished)
    jpeg = codec.jpeg(codec.resize(width, height, rows, 512))
    assert len(jpeg) < 100_000
    thumbnail = ROOT / 'dist/line-4/35.jpg'
    with thumbnail.open('xb') as handle:
        handle.write(jpeg)
    report = {
        'ancestor_sha256': ancestor_hash,
        'wall_sha256': hashlib.sha256(finished).hexdigest(),
        'wall': {'format': 'PNG', 'width': width, 'height': height, 'mode': 'RGB', 'bytes': len(finished)},
        'thumbnail': {'format': 'JPEG', 'width': 512, 'height': 512, 'bytes': len(jpeg),
                      'sha256': hashlib.sha256(jpeg).hexdigest()},
        'addition_rectangle': {'left': PATCH[0], 'top': PATCH[1], 'right': PATCH[2], 'bottom': PATCH[3]},
        'feather_pixels': FEATHER,
        'changed_pixels_inside': inside,
        'changed_pixels_outside': outside,
        'named_wall_identical': ANCESTOR.read_bytes() == EDITED.read_bytes(),
        'unmet_visual_requirements': [
            'Inherited small three-pronged trail marks cannot be certified as five-digit handprints; they were preserved unchanged.'
        ]
    }
    (ROOT / 'line-4/delivery-checks-35.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
