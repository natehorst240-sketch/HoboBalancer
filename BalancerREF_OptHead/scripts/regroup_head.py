"""Regroup the optical head so it routes on two layers with a bare, solid-ground back.

Constraints that drive the layout:
  * D1 and PD1 stay on the board centreline where the baffle and window expect them,
    and the band between them (y 116 to 124.7) is kept clear of parts for the divider wall.
    Both are rotated 180 so that PD1's cathode (the transimpedance summing node) faces
    the amplifier side and D1's cathode faces Q1.
  * The pulse loop C20 > R18 > D1 > Q1 > GND lives in the top-left corner, the summing
    node and both amplifier stages on the right, so the 500 mA / 20 kHz edges are never
    beside the 10k summing node.
  * J5 pin 1 (SYS_SW) is on the left, so the 0.8 mm SYS_SW trace runs straight down the
    left edge from C20 to the connector. +3V3 (pin 7) is on the right where U8/U4 are.
  * The back gets a full GND zone and nothing else, so the board can sit flat on the
    aluminium bracket. The existing front GND zone stays for stitching.

Run with KiCad's python:
  "C:/Program Files/KiCad/10.0/bin/python.exe" -u scripts/regroup_head.py [--apply]
"""
import sys, os, math
import pcbnew

APPLY = '--apply' in sys.argv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, 'BalancerREF_OptHead.kicad_pcb')

X0, Y0, X1, Y1 = 100.0, 100.0, 125.0, 150.0
EDGE, GAP = 0.85, 0.30
GENERIC = {'GND', '/+3V3', ''}

# ref -> (x, y, rot).  Worked against the real pad coordinates; see the header.
ANCHORS = {
    # optical pair on the centreline, rotated so the signal pins face the right way
    'D1':  (112.50, 109.00, 180),   # anode left (111.1) toward R18, cathode right (113.9) toward Q1
    'PD1': (112.50, 127.00, 180),   # cathode = summing node right (115.55), anode-GND left
    'J5':  (112.50, 146.45, 0),     # pin1 SYS_SW 108.75 .. pin7 +3V3 116.25, must face the edge
    # pulse loop, top-left, away from PD1's summing node
    'R18': (107.50, 108.80, 0),     # pin2 (108.96) -> D1 anode, pin1 SYS_SW outboard
    'Q1':  (111.50, 113.70, 0),     # drain (112.44) up to D1 cathode; gate/source on the left
    'R20': (107.20, 112.75, 180),   # pin1 (108.03) -> Q1 gate on the same row, pin2 GND
    'R19': (107.20, 115.00, 180),   # pin1 up to R20 pin1, pin2 OPT_LED_EN outboard
    'C20': (102.00, 113.50, 270),   # vertical on the left edge, above the baffle band: SYS_SW top, GND bottom
    # detector + TIA, right of centre, pins 1/2 on the right column facing PD1
    'U8':  (116.80, 133.50, 180),
    'R21': (121.90, 134.80, 90),    # pin2 IN- on the 134.1 row, pin1 TIA_OUT on the 135.4 row
    'C21': (122.90, 131.80, 0),     # pin1 IN- tees off the PD1 drop, pin2 TIA_OUT
    'R23': (111.80, 134.00, 90),    # beside U8 pins 6/7: pin2 AMP_INV top, pin1 OPT_AMP bottom
    'C24': (111.00, 131.00, 180),   # U8 +3V3 decoupling, pin1 (111.95) toward U8 pin8
    # AC coupling row under U8
    'C22': (118.00, 138.00, 180),   # pin1 TIA_OUT (118.95) under U8 pin1, pin2 AC_COUPLED
    'R22': (114.40, 138.00, 0),     # pin2 AC_COUPLED, pin1 AMP_INV up to U8 pin6 / R23
    # 1.65 V reference, left of PD1's GND pad
    'R24': (103.00, 126.00, 0),     # pin1 +3V3 left, pin2 OPT_VREF right, above R25 pin1
    'R25': (103.00, 128.30, 180),   # pin1 OPT_VREF right, pin2 GND left
    'C23': (106.60, 128.30, 0),     # pin1 OPT_VREF, pin2 GND
    # comparator, bottom centre. rot 270: pin3 THRESH top-left, pin1 CMP_OUT top-right,
    # pin4 OPT_AMP bottom-left, pin5 +3V3 bottom-right
    'U4':  (110.00, 141.00, 270),
    'R28': (110.00, 138.00, 180),   # pin1 CMP_OUT (110.82) over U4 pin1, pin2 THRESH over pin3
    'R32': (113.50, 139.70, 0),     # pin1 CMP_OUT, pin2 OPT_COMP straight down to J5 pin5
    'R27': (106.60, 139.90, 180),   # pin1 THRESH (107.42) -> U4 pin3, pin2 GND
    'R26': (106.60, 137.90, 0),     # pin2 THRESH (107.42) above R27 pin1, pin1 +3V3
    'C25': (119.60, 141.20, 90),    # U4 / J5 +3V3 decoupling, pin1 at the bottom by J5 pin7
}
JOBS = []

board = pcbnew.LoadBoard(PCB)
fps = {f.GetReference(): f for f in board.GetFootprints()}
movers = {r for r, _, _, _ in JOBS}
mm = pcbnew.ToMM


def padpos(ref, pad):
    p = next(p for p in fps[ref].Pads() if p.GetPadName() == pad)
    c = p.GetBoundingBox().GetCenter()
    return mm(c.x), mm(c.y)


def shared_pad(ref, ic):
    mine = {p.GetNetname() for p in fps[ref].Pads()} - GENERIC
    for p in fps[ic].Pads():
        if p.GetNetname() in mine:
            c = p.GetBoundingBox().GetCenter()
            return p.GetPadName(), (mm(c.x), mm(c.y))
    return None, None


def box(f):
    poly = f.GetCourtyard(f.GetLayer())
    if not poly.OutlineCount():
        return None
    bb = poly.BBox()
    return (mm(bb.GetLeft()), mm(bb.GetRight()), mm(bb.GetTop()), mm(bb.GetBottom()))


def measure(fp):
    b = box(fp); px, py = mm(fp.GetPosition().x), mm(fp.GetPosition().y)
    return {'dx0': b[0] - px, 'dy0': b[2] - py, 'w': b[1] - b[0], 'h': b[3] - b[2]}


def hits(a, b):
    return (a[0] < b[1] - 1e-9 and b[0] < a[1] - 1e-9
            and a[2] < b[3] - 1e-9 and b[2] < a[3] - 1e-9)


def obstacles():
    out = []
    for f in board.GetFootprints():
        if f.GetReference() in movers:
            continue
        b = box(f)
        if b:
            out.append((b[0] - GAP, b[1] + GAP, b[2] - GAP, b[3] + GAP))
    return out


def find_spot(m, target, occ, step=0.2, maxr=10.0):
    w, h = m['w'] + GAP, m['h'] + GAP
    tx, ty = target[0] - w / 2, target[1] - h / 2
    cands = [(0.0, tx, ty)]
    r = step
    while r <= maxr:
        n = max(8, int(2 * math.pi * r / step))
        for i in range(n):
            a = 2 * math.pi * i / n
            cands.append((r, tx + r * math.cos(a), ty + r * math.sin(a)))
        r += step
    for _, x, y in sorted(cands):
        if x < X0 + EDGE or y < Y0 + EDGE or x + w > X1 - EDGE or y + h > Y1 - EDGE:
            continue
        if any(hits((x, x + w, y, y + h), o) for o in occ):
            continue
        return x, y
    return None


print('ANCHORS')
for ref, (x, y, rot) in ANCHORS.items():
    fp = fps[ref]
    fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
    fp.SetOrientationDegrees(rot)
    print('  %-4s (%.2f, %.2f) rot %d' % (ref, x, y, rot))
allrefs = sorted(fps)
for i, a in enumerate(allrefs):
    for b_ in allrefs[i + 1:]:
        A, B = box(fps[a]), box(fps[b_])
        if A and B and hits(A, B):
            print('  !! %s overlaps %s' % (a, b_))
for r in allrefs:
    for p in fps[r].Pads():
        bb = p.GetBoundingBox()
        if (mm(bb.GetLeft()) < X0 + 0.5 or mm(bb.GetRight()) > X1 - 0.5
                or mm(bb.GetTop()) < Y0 + 0.5 or mm(bb.GetBottom()) > Y1 - 0.5):
            print('  !! %s pad %s within 0.5 mm of the edge' % (r, p.GetPadName()))
if '--pads' in sys.argv:
    for r in ANCHORS:
        print('  %-4s' % r, [(p.GetPadName(), p.GetNetname().replace('/', ''),
                              round(mm(p.GetPosition().x), 2), round(mm(p.GetPosition().y), 2))
                             for p in fps[r].Pads() if p.GetPadName() and p.GetNetname()])

occ = obstacles()
print('\nCLUSTERS')
for ref, owner, pad, why in JOBS:
    fp = fps[ref]
    padname, target = shared_pad(ref, owner)
    if target is None:
        padname, target = pad, padpos(owner, pad)
    m = measure(fp)
    spot = find_spot(m, target, occ)
    if spot is None:
        print('  %-4s !! no spot near %s.%s' % (ref, owner, padname)); continue
    fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(spot[0] - m['dx0']),
                                   pcbnew.FromMM(spot[1] - m['dy0'])))
    occ.append((spot[0] - GAP, spot[0] + m['w'] + GAP, spot[1] - GAP, spot[1] + m['h'] + GAP))
    cx, cy = spot[0] + m['w'] / 2, spot[1] + m['h'] / 2
    print('  %-4s (%.2f, %.2f)  %.2f mm to %s.%-2s %s'
          % (ref, cx, cy, math.hypot(cx - target[0], cy - target[1]), owner, padname, why))

# ---- ratsnest length as a crude quality metric
nets = {}
for f in board.GetFootprints():
    for p in f.Pads():
        n = p.GetNetname()
        if n and n != 'GND':
            nets.setdefault(n, []).append((mm(p.GetPosition().x), mm(p.GetPosition().y)))
total = 0.0
for n, pts in nets.items():
    # minimum spanning tree length
    left = pts[1:]; tree = [pts[0]]; L = 0.0
    while left:
        d, q = min((min(math.hypot(a[0] - t[0], a[1] - t[1]) for t in tree), a) for a in left)
        L += d; tree.append(q); left.remove(q)
    total += L
print('\nsum of net spanning lengths: %.1f mm' % total)

# ---- back-side ground pour
have_back = any(z.GetLayer() == pcbnew.B_Cu for z in board.Zones())
if not have_back:
    gnd = board.FindNet('GND')
    z = pcbnew.ZONE(board)
    z.SetLayer(pcbnew.B_Cu)
    z.SetNet(gnd)
    z.SetZoneName('GND_back')
    pts = [(X0 + 0.3, Y0 + 0.3), (X1 - 0.3, Y0 + 0.3), (X1 - 0.3, Y1 - 0.3), (X0 + 0.3, Y1 - 0.3)]
    outline = z.Outline()
    outline.NewOutline()
    for x, y in pts:
        outline.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    z.SetLocalClearance(pcbnew.FromMM(0.3))
    z.SetMinThickness(pcbnew.FromMM(0.25))
    z.SetThermalReliefGap(pcbnew.FromMM(0.3))
    z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.4))
    board.Add(z)
    print('added B.Cu GND zone')

# ---- baffle band between D1 and PD1: keep-out for footprints, silk marks for the print
BAFFLE_Y0, BAFFLE_Y1 = 116.5, 124.2
if not any(z.GetIsRuleArea() and z.GetZoneName() == 'BAFFLE' for z in board.Zones()):
    k = pcbnew.ZONE(board)
    k.SetIsRuleArea(True)
    k.SetZoneName('BAFFLE')
    ls = pcbnew.LSET(); ls.addLayer(pcbnew.F_Cu); ls.addLayer(pcbnew.B_Cu)
    k.SetLayerSet(ls)
    k.SetDoNotAllowFootprints(True)
    k.SetDoNotAllowTracks(False); k.SetDoNotAllowVias(False)
    k.SetDoNotAllowZoneFills(False); k.SetDoNotAllowPads(False)
    o = k.Outline(); o.NewOutline()
    for x, y in [(X0, BAFFLE_Y0), (X1, BAFFLE_Y0), (X1, BAFFLE_Y1), (X0, BAFFLE_Y1)]:
        o.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    board.Add(k)
    for y in (BAFFLE_Y0, BAFFLE_Y1):
        seg = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        seg.SetLayer(pcbnew.F_SilkS)
        seg.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(X0 + 0.5), pcbnew.FromMM(y)))
        seg.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(X1 - 0.5), pcbnew.FromMM(y)))
        seg.SetWidth(pcbnew.FromMM(0.15))
        board.Add(seg)
    txt = pcbnew.PCB_TEXT(board)
    txt.SetLayer(pcbnew.F_SilkS)
    txt.SetText('BAFFLE')
    txt.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(103.5), pcbnew.FromMM((BAFFLE_Y0 + BAFFLE_Y1) / 2)))
    txt.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.0), pcbnew.FromMM(1.0)))
    txt.SetTextThickness(pcbnew.FromMM(0.15))
    board.Add(txt)
    print('added BAFFLE keep-out (footprints only) y %.1f..%.1f with silk marks' % (BAFFLE_Y0, BAFFLE_Y1))

if not APPLY:
    print('\nDRY RUN - nothing written.'); sys.exit(0)
board.Save(PCB)
print('Saved.')
