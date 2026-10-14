"""One-shot assembly of Pepe 35's isolated pigment onto the verified wall.

Before running, wall.png is the SHA-verified record-34 ancestor and
wall-v15.png is the generated transparent motif. Both become final wall bytes.
No intermediate image is saved in the workspace.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('thumbnail', ROOT / 'shared/wall-thumbnail/thumbnail.py')
thumbnail = importlib.util.module_from_spec(spec)
spec.loader.exec_module(thumbnail)
wall = ROOT / 'artifacts/line-1/wall.png'
motif = ROOT / 'artifacts/line-1/wall-v15.png'
ancestor_hash = '1268dbcf3c6042534e7b53a2488fd0f57f5c809b6e0fe118cf737cffff831171'
assert hashlib.sha256(wall.read_bytes()).hexdigest() == ancestor_hash
width, height, old = thumbnail.png_rgb(wall)
assert (width, height) == (1254, 1254)


def png_rgba(data):
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    pos, compressed = 8, bytearray()
    while pos < len(data):
        length = int.from_bytes(data[pos:pos+4], 'big')
        kind = data[pos+4:pos+8]
        payload = data[pos+8:pos+8+length]
        assert zlib.crc32(kind + payload) == int.from_bytes(data[pos+8+length:pos+12+length], 'big')
        if kind == b'IHDR':
            iw, ih, depth, color, comp, filt, interlace = struct.unpack('>IIBBBBB', payload)
            assert depth == 8 and color == 6 and comp == filt == interlace == 0
        elif kind == b'IDAT':
            compressed.extend(payload)
        elif kind == b'IEND':
            break
        pos += length + 12
    stride = iw * 4
    raw = zlib.decompress(compressed)
    assert len(raw) == (stride + 1) * ih
    previous, rows = bytearray(stride), []
    for y in range(ih):
        start = y * (stride + 1)
        mode, row = raw[start], bytearray(raw[start+1:start+1+stride])
        assert mode in range(5)
        for x in range(stride):
            a = row[x-4] if x >= 4 else 0
            b = previous[x]
            c = previous[x-4] if x >= 4 else 0
            p = a + b - c
            distances = (abs(p-a), abs(p-b), abs(p-c))
            predictor = (0, a, b, (a+b)//2, (a,b,c)[distances.index(min(distances))])[mode]
            row[x] = (row[x] + predictor) & 255
        rows.append([tuple(row[x:x+4]) for x in range(0, stride, 4)])
        previous = row
    return iw, ih, rows


generated_bytes = motif.read_bytes()
iw, ih, pixels = png_rgba(generated_bytes)
paint = [(x, y) for y in range(ih) for x in range(iw) if pixels[y][x][3] > 20]
sx0, sy0 = min(x for x, y in paint), min(y for x, y in paint)
sx1, sy1 = max(x for x, y in paint)+1, max(y for x, y in paint)+1
box = (290, 755, 410, 815)
x0, y0, x1, y1 = box
rows = [bytearray(row) for row in old]
for y in range(y0, y1):
    ya = sy0 + (y-y0)*(sy1-sy0)//(y1-y0)
    yb = sy0 + (y-y0+1)*(sy1-sy0)//(y1-y0)
    for x in range(x0, x1):
        xa = sx0 + (x-x0)*(sx1-sx0)//(x1-x0)
        xb = sx0 + (x-x0+1)*(sx1-sx0)//(x1-x0)
        samples = [pixels[yy][xx] for yy in range(ya, yb) for xx in range(xa, xb)]
        total_alpha = sum(p[3] for p in samples)
        if not total_alpha:
            continue
        alpha = 0.82 * total_alpha / (255 * len(samples))
        for channel in range(3):
            color = sum(p[channel]*p[3] for p in samples) / total_alpha
            base = old[y][3*x+channel]
            rows[y][3*x+channel] = round(base*(1-alpha) + color*alpha)

changed_inside = sum(rows[y][3*x:3*x+3] != old[y][3*x:3*x+3]
                     for y in range(y0, y1) for x in range(x0, x1))
changed_outside = sum(rows[y][3*x:3*x+3] != old[y][3*x:3*x+3]
                      for y in range(height) for x in range(width)
                      if not (x0 <= x < x1 and y0 <= y < y1))
assert changed_inside > 1000 and changed_outside == 0


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
       + chunk(b'IDAT', zlib.compress(b''.join(b'\0' + row for row in rows), 9))
       + chunk(b'IEND', b''))
wall.write_bytes(png)
motif.write_bytes(png)
jpeg = thumbnail.jpeg(thumbnail.resize(width, height, rows, 512))
assert len(jpeg) < 100_000
(ROOT / 'dist/line-1/35.jpg').write_bytes(jpeg)
checks = {
    'ancestor_sha256': ancestor_hash,
    'generated_motif_sha256': hashlib.sha256(generated_bytes).hexdigest(),
    'wall_sha256': hashlib.sha256(png).hexdigest(),
    'wall': {'width': width, 'height': height, 'format': 'PNG', 'mode': 'RGB', 'bytes': len(png)},
    'jpeg': {'width': 512, 'height': 512, 'format': 'JPEG', 'bytes': len(jpeg)},
    'addition_box': list(box), 'source_pigment_bounds': [sx0, sy0, sx1, sy1],
    'changed_pixels_inside': changed_inside, 'changed_pixels_outside': changed_outside,
    'hand_review': 'The inherited large Pepe has four fingers and one thumb on each hand; no hands or prints added.',
    'unmet_visual_requirements': [],
    'visual_limitations': ['The new motif is small at 512-pixel thumbnail scale.',
                           'Pixel preservation is measured; aesthetic review is contributor observation.']
}
(ROOT / 'line-1/visual-checks-35.json').write_text(json.dumps(checks, indent=2) + '\n')
print(json.dumps(checks, indent=2))
