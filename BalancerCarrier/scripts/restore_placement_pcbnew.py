"""Restore placement from temp-freerouting.dsn using KiCad's own API.

Run with KiCad's python:
    "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" scripts/restore_placement_pcbnew.py [--apply]

WHY NOT THE TEXT-EDITING VERSION
    restore_placement_from_dsn.py rewrote each footprint's (at x y rot) directly and left
    everything inside the footprint alone. That is wrong: KiCad stores each pad's angle
    INCLUDING its parent footprint's, so setting the body to 270 while the pads stay at 0
    shears the part - the pads end up 90 degrees to the body and overlap each other. It
    showed up as U3's GND / SYNC_DELAY / OPT_COMP pads sitting on top of one another, and
    on U4 in the opposite direction (body 0, pads left at 270).

    SetOrientationDegrees() moves the pads, reference, value, silkscreen and courtyard
    together, which is the whole reason to go through the API rather than the file.

COORDINATES
    Specctra DSN is micrometres with Y negated relative to KiCad:
        kicad_x =  dsn_x / 1000
        kicad_y = -dsn_y / 1000
    The placements are checked against the DSN's own boundary before anything is written,
    so a sign error fails loudly instead of mirroring the board.
"""
import re
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
DSN = ROOT / 'temp-freerouting.dsn'
SRC = ROOT / 'BalancerCarrier-backups' / 'BalancerCarrier-2026-09-21_213713' / 'BalancerCarrier.kicad_pcb'
OUT = ROOT / 'BalancerCarrier.kicad_pcb'
APPLY = '--apply' in sys.argv


def die(m):
    sys.exit('ABORT: ' + m)


dsn = DSN.read_text(encoding='utf8', errors='replace')
place = {}
for ref, x, y, side, rot in re.findall(
        r'\(place\s+(\S+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(\w+)\s+(-?[\d.]+)', dsn):
    place[ref] = (float(x) / 1000.0, -float(y) / 1000.0, side.lower(), float(rot) % 360)
if not place:
    die('no (place ...) records in the DSN')

b = re.search(r'\(boundary\s*\(path\s+\S+\s+\S+((?:\s+-?[\d.]+)+)\)', dsn)
bound = None
if b:
    n = [float(v) for v in b.group(1).split()]
    bx = [v / 1000.0 for v in n[0::2]]
    by = [-v / 1000.0 for v in n[1::2]]
    bound = (min(bx), min(by), max(bx), max(by))
    px = [p[0] for p in place.values()]
    py = [p[1] for p in place.values()]
    pad = 2.0
    if not (bound[0] - pad <= min(px) and max(px) <= bound[2] + pad
            and bound[1] - pad <= min(py) and max(py) <= bound[3] + pad):
        die('placements fall outside the DSN outline - the Y transform is wrong')
    print('transform check: all %d placements sit inside the %.1f x %.1f mm outline'
          % (len(place), bound[2] - bound[0], bound[3] - bound[1]))

board = pcbnew.LoadBoard(str(SRC))
done, missing, flipped = [], [], []
for fp in board.GetFootprints():
    ref = fp.GetReference()
    if ref not in place:
        missing.append(ref)
        continue
    x, y, side, rot = place[ref]
    fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
    if side == 'back' and fp.GetLayer() != pcbnew.B_Cu:
        fp.Flip(fp.GetPosition(), False)
        flipped.append(ref)
    fp.SetOrientationDegrees(rot)      # moves pads, text and courtyard with the body
    done.append((ref, x, y, rot))

print('placed %d footprints; %d not in the DSN: %s' % (len(done), len(missing), missing or 'none'))
if flipped:
    print('flipped to the back:', flipped)

# board outline, from the DSN boundary
if bound:
    for d in list(board.GetDrawings()):
        if d.GetLayer() == pcbnew.Edge_Cuts:
            board.Remove(d)
    x0, y0, x1, y1 = bound
    for ax, ay, bx2, by2 in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(ax), pcbnew.FromMM(ay)))
        seg.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(bx2), pcbnew.FromMM(by2)))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(pcbnew.FromMM(0.1))
        board.Add(seg)
    print('outline redrawn: %.1f x %.1f mm' % (x1 - x0, y1 - y0))

# verify pad angles now track their footprints
bad = []
for fp in board.GetFootprints():
    fr = round(fp.GetOrientationDegrees()) % 360
    for p in fp.Pads():
        pr = round(p.GetOrientationDegrees()) % 360
        if (pr - fr) % 90 != 0:
            bad.append((fp.GetReference(), fr, pr))
            break
print('pad/footprint angle consistency:', 'OK' if not bad else 'PROBLEM %s' % bad[:5])

if not APPLY:
    print('\ndry run. --apply writes %s' % OUT.name)
else:
    board.Save(str(OUT))
    print('\nwrote', OUT.name)
