"""Conserve inherited pixels and retain only the image editor's new pigment."""
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
ancestor_path = ROOT / 'artifacts/line-3/wall.png'
output_path = ROOT / 'artifacts/line-3/wall-v15.png'
ancestor_bytes = ancestor_path.read_bytes()
generated_bytes = output_path.read_bytes()
assert hashlib.sha256(ancestor_bytes).hexdigest() == '3c7f76ec247884338acda9872790e33316966087a852dc1f2b1afcb4a8dba075'
w, h, ancestor = thumbnail.png_rgb(ancestor_path)
gw, gh, generated = thumbnail.png_rgb(output_path)
assert (w, h) == (gw, gh) == (1254, 1254)
rows = [bytearray(row) for row in ancestor]
box = (630, 546, 798, 645)
for y in range(box[1], box[3]):
    for x in range(box[0], box[2]):
        red, green, blue = generated[y][3*x:3*x+3]
        radius = ((x-672)/38)**2 + ((y-587)/38)**2
        chalk = .64 < radius < 1.18 and red > 175 and green > 150 and blue > 110
        stone = ((x-672)/24)**2 + ((y-586)/22)**2 < 1 and red > 110 and 55 < green < 145 and blue < 85
        dots = any(((x-cx)/rx)**2 + ((y-cy)/ry)**2 < 1
                   for cx,cy,rx,ry in ((722,606,10,10),(745,617,9,10),(766,626,9,9),(787,632,9,9)))
        charcoal = dots and red < 110 and green < 85 and blue < 65
        if chalk or stone or charcoal:
            rows[y][3*x:3*x+3] = generated[y][3*x:3*x+3]


def chunk(kind, payload):
    return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind+payload))


png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',w,h,8,2,0,0,0))
       + chunk(b'IDAT', zlib.compress(b''.join(b'\0'+row for row in rows),9)) + chunk(b'IEND',b''))
changed = outside = 0
for y in range(h):
    for x in range(w):
        if rows[y][3*x:3*x+3] != ancestor[y][3*x:3*x+3]:
            changed += 1
            if not (box[0] <= x < box[2] and box[1] <= y < box[3]): outside += 1
assert changed > 0 and outside == 0
output_path.write_bytes(png)
ancestor_path.write_bytes(png)
jpeg = thumbnail.jpeg(thumbnail.resize(w,h,rows,512))
assert len(jpeg) < 100000
(ROOT / 'dist/line-3/35.jpg').write_bytes(jpeg)
report = {'ancestor_sha256':hashlib.sha256(ancestor_bytes).hexdigest(),
          'generated_sha256':hashlib.sha256(generated_bytes).hexdigest(),
          'wall_sha256':hashlib.sha256(png).hexdigest(),
          'format':'PNG','dimensions':[w,h],'mode':'RGB',
          'addition_box':box,'changed_pixels':changed,'changed_pixels_outside_addition':outside,
          'thumbnail':{'format':'JPEG','dimensions':[512,512],'bytes':len(jpeg)},
          'manual_review_pending':True,'unmet_visual_requirements':[]}
(ROOT / 'line-3/visual-checks-35.json').write_text(json.dumps(report,indent=2)+'\n')
record = {'name':'The Chosen Stone', 'image':'https://api.imd.fun/artifacts/'+report['wall_sha256'],
          'attributes':[{'trait_type':'Cave','value':'Moss'},
                        {'trait_type':'Wall','value':'Line 3'},
                        {'trait_type':'Number','value':35},
                        {'trait_type':'Left behind','value':'Code Call Query'},
                        {'trait_type':'Meaning','value':'Pepe picks one stone from the long trail to inspect.'},
                        {'trait_type':'One thing','value':'Ethereum executable code identity'}]}
with (ROOT / 'dist/line-3/35.json').open('x') as stream:
    stream.write(json.dumps(record,indent=2)+'\n')
print(json.dumps(report,indent=2))
