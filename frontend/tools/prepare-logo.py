"""Wrap the official PNG in an SVG alpha mask; never resample or redraw artwork.
Only near-white pixels connected to the exterior are masked. Enclosed whites
in the badge, eyes, teeth and shirt remain intact. Tagline counters are exterior.
Uses only the standard library; source PNG remains byte-for-byte embedded.
"""
import base64
from collections import deque
from pathlib import Path
import struct
import zlib

root = Path(__file__).resolve().parents[1]
source = (root / 'public/brand/logo_12kool.png').read_bytes()
w, h, depth, color, _, _, interlace = struct.unpack('>IIBBBBB', source[16:29])
assert (depth, color, interlace) == (8, 6, 0)
data = bytearray()
offset = 8
while offset < len(source):
    size = struct.unpack('>I', source[offset:offset + 4])[0]
    if source[offset + 4:offset + 8] == b'IDAT':
        data.extend(source[offset + 8:offset + 8 + size])
    offset += size + 12
raw = zlib.decompress(data)
rows = []
stride = w * 4
for y in range(h):
    start = y * (stride + 1)
    kind = raw[start]
    row = bytearray(raw[start + 1:start + 1 + stride])
    prev = rows[-1] if rows else bytearray(stride)
    for i in range(stride):
        a = row[i - 4] if i >= 4 else 0
        b = prev[i]
        c = prev[i - 4] if i >= 4 else 0
        p = a + b - c
        distances = (abs(p - a), abs(p - b), abs(p - c))
        paeth = (a, b, c)[distances.index(min(distances))]
        prediction = (0, a, b, (a + b) // 2, paeth)[kind]
        row[i] = (row[i] + prediction) & 255
    rows.append(row)

def background(x, y):
    return min(rows[y][x * 4:x * 4 + 3]) >= 225

outside = set()
queue = deque([(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] +
              [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)])
# White holes in the separate tagline are not part of the illustrated badge.
queue.extend((x, y) for y in range(419, h) for x in range(w) if background(x, y))
while queue:
    x, y = queue.popleft()
    if not (0 <= x < w and 0 <= y < h) or (x, y) in outside or not background(x, y):
        continue
    outside.add((x, y))
    queue.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
segments = []
for y in range(h):
    x = 0
    while x < w:
        if (x, y) not in outside:
            x += 1
            continue
        start = x
        while x < w and (x, y) in outside:
            x += 1
        segments.append(f'M{start} {y}h{x-start}v1h{start-x}z')
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="32 44 420 411">
<!-- Official source pixels, with exterior-only transparency. -->
<defs><mask id="exterior" maskUnits="userSpaceOnUse" x="0" y="0" width="500" height="500"><rect width="500" height="500" fill="white"/><path fill="black" d="{''.join(segments)}"/></mask></defs>
<image width="500" height="500" mask="url(#exterior)" href="data:image/png;base64,{base64.b64encode(source).decode()}"/>
</svg>'''
(root / 'public/brand/logo_12kool-transparent.svg').write_text(svg)
print(f'Official pixels preserved; {len(outside)} exterior pixels masked.')
