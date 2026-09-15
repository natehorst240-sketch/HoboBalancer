"""Regroup BalancerREF into routable blocks.

Findings from looking at the placed-but-unrouted board:

  * USB D+/D- has to run from J1 (bottom centre) to U1 pads 23/24, which are on the
    module's BOTTOM edge at x 125-126. The straight channel between them was blocked
    by LED1/R10 and by the buck-boost cluster (U6, L1, C4-C7) at x 129-137.
  * The power path zig-zagged: J1 (bottom) -> U5 (top right) -> SW1 (bottom LEFT)
    -> U6 (centre) -> 3V3. SYS and SYS_SW are the 0.5 mm nets and crossed everything.
  * U5's support parts were scattered: R11/R12 (SUPPLY_SENSE) at the top, C12 by U5,
    D3 on the back under U5 while VBUS arrived from the bottom.

Moves, in order:
  1. Anchors to explicit spots: SW1 to the right edge between J2 and J4; U5 down
     beside J2; U6 just below U5 so the chain is J1 > U5 > J2/SW1 > U6 in one corner;
     LED1 out of the USB channel to beside SW2; TP4/TP11/TP12 beside J1 where the nets
     they probe actually are; TP13 beside U1's EN pad.
  2. Every passive re-clustered to the pin it serves, using the same courtyard-aware
     placer as fix_critical_placement.py. Each is aimed at the IC pad that shares its
     most specific net (ISET, ILIM, TS, RC_TIMING ...), falling back to a named pad.

Run with KiCad's python:  "C:/Program Files/KiCad/10.0/bin/python.exe" -u scripts/regroup_blocks.py [--apply]
Dry run by default.
"""
import sys, os, math
import pcbnew

APPLY = '--apply' in sys.argv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, 'BalancerREF.kicad_pcb')

X0, Y0, X1, Y1 = 100.0, 100.0, 150.0, 150.0
EDGE, GAP = 0.85, 0.30
GENERIC = {'GND', '/+3V3', ''}

# ref -> (x, y, rotation_deg, layer)
ANCHORS = {
    'SW1':  (147.6, 127.5, 90, 'F'),    # right edge, between J2 (y118) and J4 (y135-145)
    'U5':   (140.0, 121.5, 0, 'F'),     # charger beside the battery connector
    'U6':   (139.5, 131.5, 0, 'F'),     # buck-boost right below it, out of the USB channel
    'LED1': (105.5, 138.4, 0, 'F'),     # left edge by the tach test points, out of the USB channel
    'TP4':  (140.0, 143.5, 0, 'F'),     # VBUS, beside the USB receptacle
    'TP11': (134.0, 143.5, 0, 'F'),     # USB D+, beside J1/U7 instead of the far left
    'TP12': (137.0, 143.5, 0, 'F'),     # USB D-
    'TP13': (135.0, 112.5, 0, 'F'),     # EN, off U1's lower-right corner below SW3
}

# (ref, owning IC, fallback pad, layer, why).  Earlier entries get first pick.
JOBS = [
    # --- buck-boost loop (TPS63031: 1 VOUT, 2 L2, 4 L1, 5 VIN, 8 VINA)
    ('L1',  'U6', '4',  'F', 'switching node'),
    ('C5',  'U6', '8',  'F', '100n at VINA'),
    ('C4',  'U6', '5',  'F', '10u at VIN'),
    ('C6',  'U6', '1',  'F', '22u at VOUT'),
    ('C7',  'U6', '1',  'F', '22u at VOUT'),
    # --- charger (BQ24075: 13 IN, 2 BAT, 11 OUT)
    ('D3',  'U5', '13', 'F', 'VBUS clamp at IN, on the front where VBUS arrives'),
    ('C1',  'U5', '13', 'F', '100n at IN'),
    ('C2',  'U5', '13', 'F', '10u at IN'),
    ('C3',  'U5', '2',  'F', 'BAT cap'),
    ('C30', 'U5', '11', 'F', 'OUT cap'),
    ('R3',  'U5', None, 'B', 'ISET'),
    ('R35', 'U5', None, 'B', 'ILIM'),
    ('R36', 'U5', None, 'B', 'TS'),
    ('R37', 'U5', None, 'B', 'PGOOD pull-up'),
    ('R38', 'U5', None, 'B', 'CHG_STAT pull-up'),
    ('Q4',  'U5', '2',  'B', 'battery FET stays by BAT/J2'),
    # --- supply sense divider belongs at the ADC pin it feeds, not at the charger
    ('R11', 'U1', '16', 'B', 'SUPPLY_SENSE top, under U1 pad 16'),
    ('R12', 'U1', '16', 'B', 'SUPPLY_SENSE bottom'),
    ('C12', 'U1', '16', 'B', 'SUPPLY_SENSE filter'),
    # --- U1 decoupling and EN
    ('C8',  'U1', '3',  'B', '3V3 under pad 3'),
    ('C9',  'U1', '3',  'B', '3V3 under pad 3'),
    ('C10', 'U1', '45', 'B', 'EN delay cap'),
    ('R4',  'U1', '45', 'B', 'EN pull-up'),
    # --- LM1815 timing network under the chip
    ('C18', 'U3', None, 'B', 'RC_TIMING'),
    ('R16', 'U3', None, 'B', 'RC_TIMING'),
    ('C19', 'U3', None, 'B', 'PEAK_DET'),
    ('R17', 'U3', None, 'B', 'PEAK_DET'),
    ('R15', 'U3', None, 'B', 'MAG_TACH pull-up'),
    ('C16', 'U3', '8',  'B', 'LM1815 decoupling at VCC'),
    ('C17', 'U3', '8',  'B', 'LM1815 decoupling at VCC'),
    # --- status LED resistor follows the LED
    ('R10', 'LED1', None, 'B', 'LED series resistor'),
    # --- USB: series resistors and CC pull-downs stay in the J1/U7 corner
    ('R6',  'U7', None, 'B', 'USB D- series'),
    ('R7',  'U7', None, 'B', 'USB D+ series'),
    ('R1',  'J1', None, 'B', 'CC1 5.1k'),
    ('R2',  'J1', None, 'B', 'CC2 5.1k'),
]

board = pcbnew.LoadBoard(PCB)
fps = {f.GetReference(): f for f in board.GetFootprints()}
movers = {r for r, _, _, _, _ in JOBS}


def padpos(ref, pad):
    f = fps[ref]
    p = next(p for p in f.Pads() if p.GetPadName() == pad)
    c = p.GetBoundingBox().GetCenter()
    return pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)


def shared_pad(ref, ic):
    """The IC pad on the most specific net this part shares with it, if any."""
    mine = {p.GetNetname() for p in fps[ref].Pads()} - GENERIC
    for p in fps[ic].Pads():
        if p.GetNetname() in mine:
            c = p.GetBoundingBox().GetCenter()
            return p.GetPadName(), (pcbnew.ToMM(c.x), pcbnew.ToMM(c.y))
    return None, None


def measure(fp):
    lay = pcbnew.F_Cu if fp.GetLayer() == pcbnew.F_Cu else pcbnew.B_Cu
    poly = fp.GetCourtyard(lay)
    px, py = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
    bb = poly.BBox()
    l, t = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
    r, b = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
    return {'dx0': l - px, 'dy0': t - py, 'w': r - l, 'h': b - t}


def hits(a, b):
    return (a[0] < b[1] - 1e-9 and b[0] < a[1] - 1e-9
            and a[2] < b[3] - 1e-9 and b[2] < a[3] - 1e-9)


# U1's courtyard polygon includes the antenna keep-out and spans 102..148 x 81..116,
# which would block the whole top half of the front. Use the module body instead
# (15.4 x 15.5 mm, antenna end at the top edge).
U1_BODY = (117.3, 132.7, 98.0, 113.4)


def courtyard_box(f):
    if f.GetReference() == 'U1':
        return U1_BODY
    poly = f.GetCourtyard(f.GetLayer())
    if not poly.OutlineCount():
        return None
    bb = poly.BBox()
    return (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight()),
            pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom()))


def obstacles(layer_tag):
    want = pcbnew.F_Cu if layer_tag == 'F' else pcbnew.B_Cu
    out = []
    for f in board.GetFootprints():
        if f.GetReference() in movers:
            continue
        if f.GetLayer() == want:
            box = courtyard_box(f)
            if box:
                out.append((box[0] - GAP, box[1] + GAP, box[2] - GAP, box[3] + GAP))
        for p in f.Pads():
            if p.HasHole():
                bb = p.GetBoundingBox()
                out.append((pcbnew.ToMM(bb.GetLeft()) - 0.35, pcbnew.ToMM(bb.GetRight()) + 0.35,
                            pcbnew.ToMM(bb.GetTop()) - 0.35, pcbnew.ToMM(bb.GetBottom()) + 0.35))
    return out


def find_spot(m, target, occ, step=0.2, maxr=12.0):
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


# ---- 1. anchors
print('ANCHORS')
for ref, (x, y, rot, layer) in ANCHORS.items():
    fp = fps[ref]
    cur = 'F' if fp.GetLayer() == pcbnew.F_Cu else 'B'
    if cur != layer:
        fp.Flip(fp.GetPosition(), False)
    was = (pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y))
    fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
    fp.SetOrientationDegrees(rot)
    print('  %-5s (%.1f,%.1f) -> (%.1f,%.1f) rot %d' % (ref, was[0], was[1], x, y, rot))

# anchors overlapping each other or fixed parts is a placement error, not a job for the packer
for ref in ANCHORS:
    m = measure(fps[ref]); fp = fps[ref]
    px, py = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
    box = (px + m['dx0'], px + m['dx0'] + m['w'], py + m['dy0'], py + m['dy0'] + m['h'])
    lay = 'F' if fp.GetLayer() == pcbnew.F_Cu else 'B'
    for other in board.GetFootprints():
        o = other.GetReference()
        if o == ref or o in movers:
            continue
        if other.GetLayer() != fp.GetLayer() and not any(p.HasHole() for p in other.Pads()):
            continue
        ob = courtyard_box(other)
        if ob and hits(box, ob):
            print('  !! anchor %s overlaps %s' % (ref, o))

# ---- 2. clusters
occ = {'F': obstacles('F'), 'B': obstacles('B')}
print('\nCLUSTERS  (%d front / %d back obstacles)' % (len(occ['F']), len(occ['B'])))
print('%-5s %-6s %-13s %-13s %s' % ('REF', 'LAYER', 'FROM', 'TO', 'DISTANCE TO ITS PAD'))
worst = []
for ref, ic, pad, want_layer, why in JOBS:
    fp = fps[ref]
    was = fp.GetLayerName()
    ox, oy = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
    padname, target = shared_pad(ref, ic)
    if target is None:
        if pad is None:
            print('%-5s !! shares no specific net with %s and no fallback pad' % (ref, ic))
            continue
        padname, target = pad, padpos(ic, pad)
    cur = 'F' if fp.GetLayer() == pcbnew.F_Cu else 'B'
    if cur != want_layer:
        fp.Flip(fp.GetPosition(), False)
    m = measure(fp)
    spot = find_spot(m, target, occ[want_layer])
    if spot is None:
        print('%-5s !! no legal spot within 12 mm of %s.%s - left where it was' % (ref, ic, padname))
        continue
    fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(spot[0] - m['dx0']),
                                   pcbnew.FromMM(spot[1] - m['dy0'])))
    occ[want_layer].append((spot[0] - GAP, spot[0] + m['w'] + GAP,
                            spot[1] - GAP, spot[1] + m['h'] + GAP))
    cx, cy = spot[0] + m['w'] / 2, spot[1] + m['h'] / 2
    d = math.hypot(cx - target[0], cy - target[1])
    worst.append((d, ref))
    print('%-5s %-6s (%5.1f,%5.1f) (%5.1f,%5.1f)  %5.2f mm to %s.%-3s %s'
          % (ref, was + '>' + fp.GetLayerName()[0], ox, oy, cx, cy, d, ic, padname, why))

if worst:
    d, ref = max(worst)
    print('\nfurthest from its pad: %s at %.2f mm' % (ref, d))

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)
board.Save(PCB)
print('Saved.')
