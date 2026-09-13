"""Put the BQ24075 and its support resistors on the board.

U5 changes package entirely (SOT-23-5 -> VQFN-16 3x3 with a thermal pad), so the old
footprint is removed by scripts/swap_to_bq24075 stage 1 and a new one added here.

U5 goes on the FRONT with the other ICs; its support resistors on the back with the
rest of the passives, drawn toward U5. ISET/ILIM/TS are programming resistors whose
current sets a regulation point, so they want to be close with a short return; the two
status pull-ups are not critical.

pcbnew hazards worked around: Remove() segfaults (removal is done in the s-expression
instead), Flip() needs a parent board so Add() comes first, and stdout is buffered so
this must run under python -u.
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
    ('U5', 'BQ24075RGT', 'Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.675x1.675mm', False,
     {'1': '/TS', '2': '/BAT', '3': '/BAT', '4': 'GND', '5': '/CHG_EN2', '6': '/CHG_EN1',
      '7': '/PGOOD_N', '8': 'GND', '9': '/CHG_STAT', '10': '/SYS', '11': '/SYS',
      '12': '/ILIM', '13': '/USB_VBUS', '15': 'GND', '16': '/ISET', '17': 'GND'}),
    ('R35', '1.6k', 'Resistor_SMD:R_0603_1608Metric', True, {'1': '/ILIM', '2': 'GND'}),
    ('R36', '10k',  'Resistor_SMD:R_0603_1608Metric', True, {'1': '/TS', '2': 'GND'}),
    ('R37', '100k', 'Resistor_SMD:R_0603_1608Metric', True, {'1': '/+3V3', '2': '/PGOOD_N'}),
    ('R38', '100k', 'Resistor_SMD:R_0603_1608Metric', True, {'1': '/+3V3', '2': '/CHG_STAT'}),
]

board = pcbnew.LoadBoard(PCB)
have = {f.GetReference(): f for f in board.GetFootprints()}
print('board has %d footprints' % len(have))

nets = {}
for f in board.GetFootprints():
    for p in f.Pads():
        if p.GetNetname():
            nets[p.GetNetname()] = p.GetNet()
need = {n for _, _, _, _, m in NEW for n in m.values()}
for n in sorted(need - set(nets)):
    ni = pcbnew.NETINFO_ITEM(board, n)
    board.Add(ni); nets[n] = ni
    print('created net %s' % n)


def measure(fp):
    poly = fp.GetCourtyard(pcbnew.F_Cu if fp.GetLayer() == pcbnew.F_Cu else pcbnew.B_Cu)
    px = pcbnew.ToMM(fp.GetPosition().x); py = pcbnew.ToMM(fp.GetPosition().y)
    bb = poly.BBox()
    l, t = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
    r, b = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
    return {'dx0': l - px, 'dy0': t - py, 'w': r - l, 'h': b - t}


def hits(a, b):
    return (a[0] < b[1] - 1e-9 and b[0] < a[1] - 1e-9
            and a[2] < b[3] - 1e-9 and b[2] < a[3] - 1e-9)


def obstacles(layer):
    o = []
    for f in board.GetFootprints():
        if f.GetLayer() == layer:
            bb = f.GetBoundingBox(False, False)
            o.append((pcbnew.ToMM(bb.GetLeft()) - GAP, pcbnew.ToMM(bb.GetRight()) + GAP,
                      pcbnew.ToMM(bb.GetTop()) - GAP, pcbnew.ToMM(bb.GetBottom()) + GAP))
        for p in f.Pads():
            if p.HasHole():
                bb = p.GetBoundingBox()
                o.append((pcbnew.ToMM(bb.GetLeft()) - 0.35, pcbnew.ToMM(bb.GetRight()) + 0.35,
                          pcbnew.ToMM(bb.GetTop()) - 0.35, pcbnew.ToMM(bb.GetBottom()) + 0.35))
    return o


occ = {False: obstacles(pcbnew.F_Cu), True: obstacles(pcbnew.B_Cu)}


def find_spot(m, target, o, step=0.4, maxr=30.0):
    w, h = m['w'] + GAP, m['h'] + GAP
    tx, ty = target[0] - w / 2, target[1] - h / 2
    c = [(0.0, tx, ty)]
    r = step
    while r <= maxr:
        n = max(8, int(2 * math.pi * r / step))
        for i in range(n):
            a = 2 * math.pi * i / n
            c.append((r, tx + r * math.cos(a), ty + r * math.sin(a)))
        r += step
    for _, x, y in sorted(c):
        if x < X0 + EDGE or y < Y0 + EDGE or x + w > X1 - EDGE or y + h > Y1 - EDGE:
            continue
        if any(hits((x, x + w, y, y + h), q) for q in o):
            continue
        return x, y
    return None


# U5 near where the old charger sat, by J2 (battery) on the right edge
j2 = have['J2']
tgt = (pcbnew.ToMM(j2.GetPosition().x) - 8.0, pcbnew.ToMM(j2.GetPosition().y))
print('anchoring U5 near J2 at (%.1f, %.1f)' % tgt)

placed = {}
for ref, val, fpid, back, padnets in NEW:
    lib, name = fpid.split(':', 1)
    fp = pcbnew.FootprintLoad(os.path.join(FPDIR, lib + '.pretty'), name)
    assert fp is not None, fpid
    fp.SetReference(ref); fp.SetValue(val)
    board.Add(fp)
    ctr = pcbnew.VECTOR2I(pcbnew.FromMM(125.0), pcbnew.FromMM(125.0))
    fp.SetPosition(ctr)
    if back:
        fp.Flip(ctr, False)
    for p in fp.Pads():
        n = padnets.get(p.GetPadName())
        if n:
            p.SetNet(nets[n])
    m = measure(fp)
    aim = tgt if ref == 'U5' else placed.get('U5', tgt)
    spot = find_spot(m, aim, occ[back])
    assert spot, 'no room for %s' % ref
    fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(spot[0] - m['dx0']),
                                   pcbnew.FromMM(spot[1] - m['dy0'])))
    occ[back].append((spot[0] - GAP, spot[0] + m['w'] + GAP,
                      spot[1] - GAP, spot[1] + m['h'] + GAP))
    cx, cy = spot[0] + m['w'] / 2, spot[1] + m['h'] / 2
    placed[ref] = (cx, cy)
    print('  %-4s %-11s %s (%.2f, %.2f)  %s' %
          (ref, val, 'B.Cu' if back else 'F.Cu', cx, cy,
           '' if ref == 'U5' else '%.1f mm from U5' % math.hypot(cx - placed['U5'][0],
                                                                 cy - placed['U5'][1])))

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)
board.Save(PCB)
b2 = pcbnew.LoadBoard(PCB)
print('Saved. %d footprints' % len(b2.GetFootprints()))
