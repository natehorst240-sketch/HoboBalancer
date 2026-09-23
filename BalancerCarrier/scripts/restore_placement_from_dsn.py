"""Put the placement from temp-freerouting.dsn back onto a freshly-imported board.

WHY THIS EXISTS
    A Freerouting crash on 2026-09-21 lost the carrier's .kicad_pcb. What survived was
    temp-freerouting.dsn, written at 21:56 from the in-memory board, which carries every
    footprint's position, rotation and side. The only .kicad_pcb left was a 22:02 backup
    holding the post-crash "Update PCB from Schematic" auto-arrangement - all 36 parts in
    tidy 3.01 mm columns, which is not a layout.

    So: take the footprints from the fresh board, take the positions from the DSN.

COORDINATES
    Specctra DSN is micrometres with the Y axis negated relative to KiCad:
        kicad_x =  dsn_x / 1000
        kicad_y = -dsn_y / 1000
    A sign error here mirrors the board, so the checks below compare the resulting
    bounding box against the DSN's own boundary before anything is written.

WHAT IT DOES NOT RESTORE
    Only placement and, optionally, the board outline. The DSN carries what Freerouting
    needs - footprints, nets, outline, copper - so silkscreen edits, text, courtyard
    tweaks and any non-copper work are simply not in it. The 13 routed wires the DSN
    holds are also skipped: at that count re-routing is faster than trusting an import.

USAGE
    python restore_placement_from_dsn.py                 # dry run, prints the moves
    python restore_placement_from_dsn.py --apply         # writes BalancerCarrier.kicad_pcb
    python restore_placement_from_dsn.py --apply --outline   # also redraw Edge.Cuts
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DSN = ROOT / 'temp-freerouting.dsn'
SRC = ROOT / 'BalancerCarrier-backups' / 'BalancerCarrier-2026-09-21_213713' / 'BalancerCarrier.kicad_pcb'
OUT = ROOT / 'BalancerCarrier.kicad_pcb'
APPLY = '--apply' in sys.argv
OUTLINE = '--outline' in sys.argv


def die(m):
    sys.exit('ABORT: ' + m)


if not DSN.exists():
    die(f'{DSN.name} not found')
if not SRC.exists():
    die(f'{SRC} not found')

dsn = DSN.read_text(encoding='utf8', errors='replace')

# ---- placements out of the DSN --------------------------------------------
place = {}
for ref, x, y, side, rot in re.findall(
        r'\(place\s+(\S+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(\w+)\s+(-?[\d.]+)', dsn):
    place[ref] = (float(x) / 1000.0, -float(y) / 1000.0, side.lower(), float(rot) % 360)
if not place:
    die('no (place ...) records in the DSN')

# ---- the DSN's own outline, used to sanity-check the transform -------------
b = re.search(r'\(boundary\s*\(path\s+\S+\s+\S+((?:\s+-?[\d.]+)+)\)', dsn)
bound = None
if b:
    n = [float(v) for v in b.group(1).split()]
    bx = [v / 1000.0 for v in n[0::2]]
    by = [-v / 1000.0 for v in n[1::2]]
    bound = (min(bx), min(by), max(bx), max(by))

px = [p[0] for p in place.values()]
py = [p[1] for p in place.values()]
print(f'DSN: {len(place)} placements, bbox x {min(px):.2f}..{max(px):.2f}  y {min(py):.2f}..{max(py):.2f}')
if bound:
    print(f'DSN outline: x {bound[0]:.2f}..{bound[2]:.2f}  y {bound[1]:.2f}..{bound[3]:.2f} '
          f'({bound[2]-bound[0]:.1f} x {bound[3]-bound[1]:.1f} mm)')
    pad = 2.0
    if not (bound[0] - pad <= min(px) and max(px) <= bound[2] + pad
            and bound[1] - pad <= min(py) and max(py) <= bound[3] + pad):
        die('placements fall outside the DSN outline - the Y-axis transform is wrong')
    print('  check: every placement sits inside the outline, so the transform is right')

# ---- rewrite each footprint's position -------------------------------------
text = SRC.read_text(encoding='utf8', errors='replace')
parts = re.split(r'(\n\t\(footprint )', text)
out, moved, missing, i = [parts[0]], [], [], 1
while i < len(parts):
    sep, body = parts[i], parts[i + 1]
    m = re.search(r'\(property "Reference" "([^"]+)"', body)
    ref = m.group(1) if m else None
    if ref in place:
        x, y, side, rot = place[ref]
        at = re.search(r'\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', body)
        old = (float(at.group(1)), float(at.group(2)), float(at.group(3) or 0)) if at else None
        body = body[:at.start()] + f'(at {x:.4f} {y:.4f}{"" if rot == 0 else f" {rot:g}"})' + body[at.end():] \
            if at else body
        moved.append((ref, old, (x, y, rot), side))
    elif ref:
        missing.append(ref)
    out.append(sep)
    out.append(body)
    i += 2
text = ''.join(out)

print(f'\n{len(moved)} footprints repositioned; {len(missing)} not in the DSN: {missing or "none"}')
for ref, old, new, side in sorted(moved)[:10]:
    o = f'({old[0]:.1f},{old[1]:.1f})' if old else '(?)'
    print(f'   {ref:5s} {o:>18s} -> ({new[0]:.2f}, {new[1]:.2f}) rot {new[2]:g} {side}')
if len(moved) > 10:
    print(f'   ... +{len(moved)-10} more')

back = [r for r, _, _, s in moved if s != 'front']
if back:
    print(f'\nNOTE: on the back side in the DSN, layer NOT changed by this script: {back}')

# ---- optional: redraw the outline ------------------------------------------
if OUTLINE and bound:
    text = re.sub(r'\n\t\(gr_line[^\n]*Edge\.Cuts[^\n]*\)', '', text)
    x0, y0, x1, y1 = bound
    seg = ''.join(
        f'\n\t(gr_line (start {a:.3f} {b:.3f}) (end {c:.3f} {d:.3f})'
        f' (stroke (width 0.1) (type solid)) (layer "Edge.Cuts"))'
        for a, b, c, d in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)))
    text = text[:text.rfind(')')] + seg + '\n)\n'
    print(f'\noutline redrawn as a rectangle {x1-x0:.1f} x {y1-y0:.1f} mm')

if not APPLY:
    print(f'\ndry run. --apply writes {OUT.name}' + ('' if OUTLINE else '   (add --outline to redraw Edge.Cuts)'))
else:
    if OUT.exists():
        die(f'{OUT.name} already exists - move it aside first, this will not overwrite')
    OUT.write_text(text, encoding='utf8')
    print(f'\nwrote {OUT.name}')
