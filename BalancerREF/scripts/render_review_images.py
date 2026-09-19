"""Re-render the schematic review images from the current sheet.

    python3 scripts/render_review_images.py            # needs kicad-cli on PATH and pymupdf

Writes review/BalancerREF.pdf (vector), the low-resolution review PNGs that
final_review.py used to produce (overview.png and the five block crops), and the
Reddit set in review/reddit/ at print resolution. The first Reddit post used a
5052 px wide full-sheet image, about 216 DPI on an A2 sheet, and the feedback was
that it was unreadable; the set here is rendered at the DPI values below.

Block rectangles are in sheet millimetres and match the hand layout's five blocks.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
KC = os.environ.get('KICAD_CLI', 'kicad-cli')
SCH = ROOT / 'BalancerREF.kicad_sch'
PDF = ROOT / 'review' / 'BalancerREF.pdf'
REDDIT = ROOT / 'review' / 'reddit'

FULL_DPI = 400
BLOCK_DPI = 600

BLOCKS = [
    ('power', '01-battery-usb-power', (29, 36, 568, 148)),
    ('accel', '02-accelerometer-iis3dwb', (29, 151, 275, 239)),
    ('opt', '03-optical-tach', (29, 242, 275, 370)),
    ('mag', '04-mag-tach-lm1815', (284, 151, 568, 239)),
    ('mcu', '05-mcu-esp32s3', (284, 242, 568, 370)),
]


def rev_of(sch_text):
    for line in sch_text.splitlines():
        line = line.strip()
        if line.startswith('(rev "'):
            return line.split('"')[1]
    raise SystemExit('no (rev "...") in the title block')


def mm_rect(r):
    return pymupdf.Rect(*[v * 72 / 25.4 for v in r])


rev = rev_of(SCH.read_text(encoding='utf8'))
subprocess.run([KC, 'sch', 'export', 'pdf', '-o', str(PDF), str(SCH)], check=True)
doc = pymupdf.open(PDF)
assert len(doc) == 1, 'expected a one-sheet schematic'
page = doc[0]

# the older, lighter review set
page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(ROOT / 'review' / 'overview.png')
for name, _, rect in BLOCKS:
    page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=mm_rect(rect)).save(ROOT / 'review' / f'{name}.png')
shutil.copy2(ROOT / 'review' / 'overview.png', ROOT / 'BalancerREF-Schematic.png')
shutil.copy2(PDF, ROOT / 'BalancerREF-Schematic.pdf')

# the Reddit set
REDDIT.mkdir(exist_ok=True)
for old in REDDIT.glob('HOBOVibe-Rev*-full-sheet.png'):
    old.unlink()
full = REDDIT / f'HOBOVibe-Rev{rev}-full-sheet.png'
z = FULL_DPI / 72
pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z))
pix.save(full)
print(f'{full.name}: {pix.width} x {pix.height} @ {FULL_DPI} DPI')
z = BLOCK_DPI / 72
for _, fname, rect in BLOCKS:
    out = REDDIT / f'{fname}.png'
    pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=mm_rect(rect))
    pix.save(out)
    print(f'{out.name}: {pix.width} x {pix.height} @ {BLOCK_DPI} DPI')
