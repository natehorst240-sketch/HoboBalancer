"""Put R33 / R34 / C31 (the BAT sense divider) onto the main board.

They go on the BACK, like every other passive, and are drawn toward U1 - the divider
output lands on U1 pin 8 (GPIO4) and the node is high impedance at 500k, so the run
from the divider to the ADC pin wants to be short. C31 sits closest to U1 of the
three: it is the part that actually supplies the ADC's sampling charge.

Known pcbnew hazards this script works around, all found the hard way:
  * board.Remove() segfaults - existing parts are repositioned, never removed
  * Flip() on a footprint with no parent board segfaults - Add() first
  * stdout is buffered and lost on a segfault - run with python -u

Dry run by default. Pass --apply to write.
"""
import sys, os, math
import pcbnew

APPLY = '--apply' in sys.argv
ROOT = r'C:\Users\nateh\hgs-linux\Balancer\BalancerREF'
PCB = os.path.join(ROOT, 'BalancerREF.kicad_pcb')
FPDIR = r'C:\Program Files\KiCad\10.0\share\kicad\footprints'

X0, Y0, X1, Y1 = 100.0, 100.0, 150.0, 150.0
EDGE, GAP = 0.85, 0.30

NEW = [
    ('R33', '1M',   'Resistor_SMD:R_0603_1608Metric',
     {'1': '/BAT', '2': '/BAT_SENSE'}),
    ('R34', '1M',   'Resistor_SMD:R_0603_1608Metric',
     {'1': '/BAT_SENSE', '2': 'GND'}),
    ('C31', '100n', 'Capacitor_SMD:C_0805_2012Metric',
     {'1': '/BAT_SENSE', '2': 'GND'}),
]

board = pcbnew.LoadBoard(PCB)
have = {f.GetReference(): f for f in board.GetFootprints()}
print('board has %d footprints' % len(have))

nets = {}
for f in board.GetFootprints():
    for p in f.Pads():
        if p.GetNetname():
            nets[p.GetNetname()] = p.GetNet()
# /BAT_SENSE is new in the schematic and has no NETINFO_ITEM on the board yet, so it
# has to be created before any pad can be assigned to it.
missing = {n for _, _, _, m in NEW for n in m.values() if n not in nets}
for n in sorted(missing):
    ni = pcbnew.NETINFO_ITEM(board, n)
    board.Add(ni)
    nets[n] = ni
    print('created new net %s' % n)
if not missing:
    print('all required nets already present')


def measure(fp):
    lay = pcbnew.F_Cu if fp.GetLayer() == pcbnew.F_Cu else pcbnew.B_Cu
    poly = fp.GetCourtyard(lay)
    px = pcbnew.ToMM(fp.GetPosition().x); py = pcbnew.ToMM(fp.GetPosition().y)
    bb = poly.BBox()
    l, t = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
    r, b = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
    return {'fp': fp, 'dx0': l - px, 'dy0': t - py, 'w': r - l, 'h': b - t}


def hits(a, b):
    return (a[0] < b[1] - 1e-9 and b[0] < a[1] - 1e-9
            and a[2] < b[3] - 1e-9 and b[2] < a[3] - 1e-9)


occ = []
for f in board.GetFootprints():
    back = f.GetLayer() == pcbnew.B_Cu
    holes = [p for p in f.Pads() if p.HasHole()]
    if back:
        bb = f.GetBoundingBox(False, False)
        occ.append((pcbnew.ToMM(bb.GetLeft()) - GAP, pcbnew.ToMM(bb.GetRight()) + GAP,
                    pcbnew.ToMM(bb.GetTop()) - GAP, pcbnew.ToMM(bb.GetBottom()) + GAP))
    for p in holes:
        bb = p.GetBoundingBox()
        occ.append((pcbnew.ToMM(bb.GetLeft()) - 0.35, pcbnew.ToMM(bb.GetRight()) + 0.35,
                    pcbnew.ToMM(bb.GetTop()) - 0.35, pcbnew.ToMM(bb.GetBottom()) + 0.35))
print('back-side obstacles: %d' % len(occ))

u1 = have['U1']
p8 = next((p for p in u1.Pads() if p.GetPadName() == '8'), None)
tgt = (pcbnew.ToMM(p8.GetBoundingBox().GetCenter().x),
       pcbnew.ToMM(p8.GetBoundingBox().GetCenter().y)) if p8 else (125.0, 112.0)
print('U1 pin 8 (GPIO4) at (%.2f, %.2f) - divider is drawn here' % tgt)


def find_spot(m, target, step=0.4, maxr=28.0):
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


added = []
for ref, val, fpid, padnets in NEW:
    if ref in have:
        print('  %s already on the board - skipping' % ref)
        continue
    lib, name = fpid.split(':', 1)
    fp = pcbnew.FootprintLoad(os.path.join(FPDIR, lib + '.pretty'), name)
    assert fp is not None, 'could not load %s' % fpid
    fp.SetReference(ref)
    fp.SetValue(val)
    board.Add(fp)                      # Add before Flip - Flip needs a parent board
    ctr = pcbnew.VECTOR2I(pcbnew.FromMM(125.0), pcbnew.FromMM(125.0))
    fp.SetPosition(ctr)
    fp.Flip(ctr, False)                # passives live on the back
    for p in fp.Pads():
        n = padnets.get(p.GetPadName())
        if n:
            p.SetNet(nets[n])
    m = measure(fp)
    spot = find_spot(m, tgt)
    assert spot, 'no room for %s' % ref
    fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(spot[0] - m['dx0']),
                                   pcbnew.FromMM(spot[1] - m['dy0'])))
    occ.append((spot[0] - GAP, spot[0] + m['w'] + GAP,
                spot[1] - GAP, spot[1] + m['h'] + GAP))
    cx, cy = spot[0] + m['w'] / 2, spot[1] + m['h'] / 2
    added.append(ref)
    print('  %-4s %-6s %s  at (%.2f, %.2f)  %.1f mm from U1.8   nets %s'
          % (ref, val, fp.GetLayerName(), cx, cy, math.hypot(cx - tgt[0], cy - tgt[1]),
             ' '.join(sorted(set(padnets.values())))))

print('added %d footprints' % len(added))
if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)
board.Save(PCB)
print('Saved. Board now has %d footprints'
      % len(pcbnew.LoadBoard(PCB).GetFootprints()))
