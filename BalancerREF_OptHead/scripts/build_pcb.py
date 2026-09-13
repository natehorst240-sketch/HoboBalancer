"""Create and place BalancerREF_OptHead.kicad_pcb - 25 x 50 mm, 2 layers.

Layout constraints given:
  * D1 centred on the top of the board
  * PD1 directly beneath it
  * the cable connector on any edge except the top

Faces are split by function rather than to save space (24 parts in 1250 mm^2 is
roughly 22% utilisation, so area is not the constraint here):

  FRONT  = the optical face. Only D1 and PD1. The baffle between them and the red
           acrylic window both live on this face, so keeping every other part off it
           means nothing has to be worked around mechanically.
  BACK   = the electronics, plus J5 so the cable exits behind rather than across the
           optical aperture.

A lens keepout is reserved around D1. It is provisional - confirm against the actual
Ledil TINA lens holder before committing, as it drives how far PD1 can sit.

Dry run by default. Pass --apply to write.
"""
import sys, os
import pcbnew

APPLY = '--apply' in sys.argv
ROOT = r'C:\Users\nateh\hgs-linux\Balancer\BalancerREF_OptHead'
PCB = os.path.join(ROOT, 'BalancerREF_OptHead.kicad_pcb')
NET = os.path.join(ROOT, 'review', 'OptHead.net')
FPDIR = r'C:\Program Files\KiCad\10.0\share\kicad\footprints'

X0, Y0 = 100.0, 100.0
W, H = 25.0, 50.0
X1, Y1 = X0 + W, Y0 + H
EDGE = 0.85
GAP = 0.35

CX = X0 + W / 2                 # 112.5 - the optical axis
D1_Y = Y0 + 9.0                 # emitter, near the top
PD1_Y = Y0 + 27.0               # detector, directly beneath, baffle gap between
LENS_R = 8.0                    # provisional lens keepout radius around D1
PD1_APERTURE_R = 4.5            # clear ring around the detector aperture

# EVERYTHING on the front. D1/PD1 must be on the optical face, so single-sided means
# the front - which frees B.Cu as an uninterrupted ground pour. That is worth more
# here than a clean optical face: the TIA summing junction (PD1/U8/R21/C21) is the
# highest-impedance node on the board and it sits beside a wire switching 500 mA at
# 20 kHz. A solid reference plane under it is the single best defence.
# Cost: the baffle and the red acrylic window now have to clear the electronics.
FRONT = None                    # None => no part is flipped to the back

# KiCad's bundled Python has no sexpdata, and the exported netlist is pretty-printed
# multi-line rather than flat, which makes regex parsing fragile. So scripts/dump_netlist.py
# (system Python, which does have sexpdata) pre-parses it into JSON and this reads that.
import json

data = json.load(open(os.path.join(ROOT, 'review', 'netlist.json'), encoding='utf8'))
comps = {r: tuple(v) for r, v in data['comps'].items()}
nets = {tuple(k.split('|', 1)): v for k, v in data['nets'].items()}
assert len(comps) == 24, 'expected 24 components, got %d' % len(comps)
print('netlist: %d components, %d pad-net assignments' % (len(comps), len(nets)))

board = pcbnew.BOARD()
board.SetCopperLayerCount(2)

# outline
rect = pcbnew.PCB_SHAPE(board)
rect.SetShape(pcbnew.SHAPE_T_RECT)
rect.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(X0), pcbnew.FromMM(Y0)))
rect.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(X1), pcbnew.FromMM(Y1)))
rect.SetLayer(pcbnew.Edge_Cuts)
rect.SetWidth(pcbnew.FromMM(0.05))
board.Add(rect)

netinfo = {}
def netfor(name):
    if name not in netinfo:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netinfo[name] = ni
    return netinfo[name]

placed = {}
for ref, (val, fpid) in sorted(comps.items()):
    lib, name = fpid.split(':', 1)
    fp = pcbnew.FootprintLoad(os.path.join(FPDIR, lib + '.pretty'), name)
    if fp is None:
        print('  !! could not load %s for %s' % (fpid, ref)); sys.exit(1)
    fp.SetReference(ref)
    fp.SetValue(val)
    board.Add(fp)
    for pad in fp.Pads():
        nm = nets.get((ref, pad.GetPadName()))
        if nm:
            pad.SetNet(netfor(nm))
    placed[ref] = fp
print('loaded %d footprints, %d nets' % (len(placed), len(netinfo)))

if FRONT is not None:
    for ref, fp in placed.items():
        if ref not in FRONT and fp.GetLayer() != pcbnew.B_Cu:
            fp.Flip(fp.GetPosition(), False)


def measure(fp):
    lay = pcbnew.F_Cu if fp.GetLayer() == pcbnew.F_Cu else pcbnew.B_Cu
    poly = fp.GetCourtyard(lay)
    px = pcbnew.ToMM(fp.GetPosition().x); py = pcbnew.ToMM(fp.GetPosition().y)
    if poly.OutlineCount():
        bb = poly.BBox()
        l, t = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
        r, b = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
    else:
        xs, ys = [], []
        for q in fp.Pads():
            bb = q.GetBoundingBox()
            xs += [pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight())]
            ys += [pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())]
        l, r, t, b = min(xs) - 0.25, max(xs) + 0.25, min(ys) - 0.25, max(ys) + 0.25
    return {'fp': fp, 'ref': fp.GetReference(), 'dx0': l - px, 'dx1': r - px,
            'dy0': t - py, 'dy1': b - py, 'w': r - l, 'h': b - t}


def fab_offsets(fp):
    lid = board.GetLayerID('F.Fab' if fp.GetLayer() == pcbnew.F_Cu else 'B.Fab')
    xs, ys = [], []
    for g in fp.GraphicalItems():
        if g.GetLayer() == lid:
            bb = g.GetBoundingBox()
            xs += [pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight())]
            ys += [pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())]
    px = pcbnew.ToMM(fp.GetPosition().x); py = pcbnew.ToMM(fp.GetPosition().y)
    return (min(xs) - px, max(xs) - px, min(ys) - py, max(ys) - py) if xs else None


def padbox(fp):
    xs, ys = [], []
    for q in fp.Pads():
        bb = q.GetBoundingBox()
        xs += [pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight())]
        ys += [pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())]
    return min(xs), max(xs), min(ys), max(ys)


def centre_on(m, cx, cy):
    m['fp'].SetPosition(pcbnew.VECTOR2I(
        pcbnew.FromMM(cx - (m['dx0'] + m['dx1']) / 2),
        pcbnew.FromMM(cy - (m['dy0'] + m['dy1']) / 2)))
    m['x'] = cx - m['w'] / 2
    m['y'] = cy - m['h'] / 2


def hits(a, b):
    return (a[0] < b[1] - 1e-9 and b[0] < a[1] - 1e-9
            and a[2] < b[3] - 1e-9 and b[2] < a[3] - 1e-9)


items = {r: measure(f) for r, f in placed.items()}

# --- optical axis: D1 on top, PD1 directly beneath ---------------------------
d1, pd1 = items['D1'], items['PD1']
centre_on(d1, CX, D1_Y)
centre_on(pd1, CX, PD1_Y)
print('D1  centred at (%.2f, %.2f)  %.2f x %.2f' % (CX, D1_Y, d1['w'], d1['h']))
print('PD1 centred at (%.2f, %.2f)  %.2f x %.2f  -> %.1f mm below D1'
      % (CX, PD1_Y, pd1['w'], pd1['h'], PD1_Y - D1_Y))

# --- J5 on the bottom edge, mouth facing off the board -----------------------
# local +y is the mouth for this JST-GH; rot 0 puts it on the bottom edge.
j5 = items['J5']
j5['fp'].SetOrientationDegrees(0)
fo = fab_offsets(j5['fp'])
j5['fp'].SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(CX), pcbnew.FromMM(Y1 - fo[3])))
pl, pr, pt, pb = padbox(j5['fp'])
if pb > Y1 - EDGE:
    sh = (Y1 - EDGE) - pb
    j5['fp'].SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(CX),
                                         pcbnew.FromMM(Y1 - fo[3] + sh)))
j5 = measure(j5['fp'])
j5['x'] = pcbnew.ToMM(j5['fp'].GetPosition().x) + j5['dx0']
j5['y'] = pcbnew.ToMM(j5['fp'].GetPosition().y) + j5['dy0']
items['J5'] = j5
pl, pr, pt, pb = padbox(j5['fp'])
print('J5  bottom edge, rot 0, pads x %.2f..%.2f y %.2f..%.2f (board ends %.1f)'
      % (pl, pr, pt, pb, Y1))

# --- obstacles ---------------------------------------------------------------
# D1's lens keepout blocks the FRONT only; the back face is clear beneath it.
front_occ = [(CX - LENS_R, CX + LENS_R, D1_Y - LENS_R, D1_Y + LENS_R),
             (pd1['x'] - GAP, pd1['x'] + pd1['w'] + GAP,
              pd1['y'] - GAP, pd1['y'] + pd1['h'] + GAP)]
# One obstacle list now - everything shares the front face. The optical keepouts
# are real placement constraints here, not just mechanical notes.
back_occ = [(j5['x'] - GAP, j5['x'] + j5['w'] + GAP,
             j5['y'] - GAP, j5['y'] + j5['h'] + GAP),
            (CX - LENS_R, CX + LENS_R, D1_Y - LENS_R, D1_Y + LENS_R),
            (CX - PD1_APERTURE_R, CX + PD1_APERTURE_R,
             PD1_Y - PD1_APERTURE_R, PD1_Y + PD1_APERTURE_R)]
for r, f in placed.items():
    for p in f.Pads():
        if p.HasHole():
            bb = p.GetBoundingBox()
            o = (pcbnew.ToMM(bb.GetLeft()) - 0.35, pcbnew.ToMM(bb.GetRight()) + 0.35,
                 pcbnew.ToMM(bb.GetTop()) - 0.35, pcbnew.ToMM(bb.GetBottom()) + 0.35)
            front_occ.append(o); back_occ.append(o)

# --- the electronics, clustered by signal order down the board ---------------
# Roughly follows the chain: emitter loop up near D1, detector front end beside
# PD1, then gain and comparator below, connector at the bottom.
TARGETS = {
    # emitter loop, tucked either side of the lens keepout near D1
    'C20': (X0 + 3.2, Y0 + 18.5), 'R18': (X1 - 3.2, Y0 + 18.5),
    'Q1':  (X0 + 3.5, Y0 + 22.5), 'R19': (X1 - 3.5, Y0 + 22.5),
    'R20': (X1 - 3.5, Y0 + 26.0),
    # detector front end, close to PD1 but clear of its aperture
    'R21': (X0 + 3.5, Y0 + 27.0), 'C21': (X0 + 3.5, Y0 + 30.5),
    # gain stage
    'U8':  (CX - 3.0, Y0 + 34.5),
    'C22': (X1 - 3.5, Y0 + 30.5), 'R22': (X1 - 3.5, Y0 + 34.0),
    'R23': (X1 - 3.5, Y0 + 37.0), 'C24': (X1 - 7.5, Y0 + 37.5),
    # 1.65 V reference
    'R24': (X0 + 3.5, Y0 + 34.0), 'R25': (X0 + 3.5, Y0 + 37.0),
    'C23': (X0 + 7.0, Y0 + 37.5),
    # comparator and cable damping, just above J5
    'U4':  (CX, Y0 + 41.0),
    'R26': (X0 + 3.5, Y0 + 40.5), 'R27': (X0 + 3.5, Y0 + 43.0),
    'R28': (X1 - 3.5, Y0 + 40.5), 'C25': (X1 - 3.5, Y0 + 43.0),
    'R32': (CX + 4.5, Y0 + 43.5),
}



def find_spot(m, target, occ, step=0.3, maxr=26.0):
    import math
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
    for _, x, y in cands:
        if x < X0 + EDGE or y < Y0 + EDGE or x + w > X1 - EDGE or y + h > Y1 - EDGE:
            continue
        if any(hits((x, x + w, y, y + h), o) for o in occ):
            continue
        return x, y
    return None


fail = []
back_placed = [items['J5']]
for ref in sorted(TARGETS, key=lambda r: -(items[r]['w'] * items[r]['h'])):
    m = items[ref]
    s = find_spot(m, TARGETS[ref], back_occ)
    if s is None:
        fail.append(ref); continue
    m['fp'].SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(s[0] - m['dx0']),
                                        pcbnew.FromMM(s[1] - m['dy0'])))
    m['x'], m['y'] = s
    back_occ.append((s[0] - GAP, s[0] + m['w'] + GAP, s[1] - GAP, s[1] + m['h'] + GAP))
    back_placed.append(m)

print('front face placed %d/%d%s'
      % (len(back_placed) - 1, len(TARGETS), '  FAILED:%s' % fail if fail else ''))

# --- checks ------------------------------------------------------------------
def box_of(m): return (m['x'], m['x'] + m['w'], m['y'], m['y'] + m['h'])


ov = 0
for grp in ([d1, pd1], back_placed):
    for i in range(len(grp)):
        for j in range(i + 1, len(grp)):
            if hits(box_of(grp[i]), box_of(grp[j])):
                ov += 1
                print('  OVERLAP %s/%s' % (grp[i]['ref'], grp[j]['ref']))
lens_clash = [m['ref'] for m in [d1, pd1]
              if m['ref'] != 'D1'
              and hits(box_of(m), (CX - LENS_R, CX + LENS_R, D1_Y - LENS_R, D1_Y + LENS_R))]
print('same-face overlaps: %d   inside D1 lens keepout: %s'
      % (ov, lens_clash or 'none'))

stray = []
for r, f in placed.items():
    pl, pr, pt, pb = padbox(f)
    if pl < X0 or pr > X1 or pt < Y0 or pb > Y1:
        stray.append(r)
print('pads outside %g x %g outline: %s' % (W, H, stray or 'none'))
print('front face: %s' % sorted(r for r, f in placed.items() if f.GetLayer() == pcbnew.F_Cu))

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)
if fail or ov or stray:
    print('\nREFUSING TO WRITE.')
    sys.exit(1)

# --- B.Cu ground pour ---------------------------------------------------------
# The whole point of putting every part on the front: B.Cu is now an uninterrupted
# reference plane under the TIA input and under the 500 mA emitter loop, with
# nothing but signal vias breaking it.
POUR_INSET = 0.3
gnd = netinfo.get('GND')
if gnd is None:
    print('  !! no GND net found - not pouring')
else:
    z = pcbnew.ZONE(board)
    z.SetLayer(pcbnew.B_Cu)
    z.SetNetCode(gnd.GetNetCode())
    z.SetLocalClearance(pcbnew.FromMM(0.25))
    z.SetMinThickness(pcbnew.FromMM(0.20))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    o = z.Outline()
    o.NewOutline()
    for cx_, cy_ in ((X0 + POUR_INSET, Y0 + POUR_INSET), (X1 - POUR_INSET, Y0 + POUR_INSET),
                     (X1 - POUR_INSET, Y1 - POUR_INSET), (X0 + POUR_INSET, Y1 - POUR_INSET)):
        o.Append(pcbnew.FromMM(cx_), pcbnew.FromMM(cy_))
    board.Add(z)
    # Do NOT call ZONE_FILLER here: it segfaults under standalone pcbnew Python
    # (no app context). The zone is written unfilled and KiCad fills it on open, or
    # 'Edit > Fill All Zones' / B does it explicitly.
    print('B.Cu GND pour: %.1f x %.1f mm outline (%.0f mm2), unfilled - '
          'KiCad fills on open'
          % (W - 2 * POUR_INSET, H - 2 * POUR_INSET,
             (W - 2 * POUR_INSET) * (H - 2 * POUR_INSET)))

board.Save(PCB)
eb = pcbnew.LoadBoard(PCB).GetBoardEdgesBoundingBox()
print('Saved %s  (%.1f x %.1f mm, %d layers, %d footprints)'
      % (os.path.basename(PCB), pcbnew.ToMM(eb.GetWidth()), pcbnew.ToMM(eb.GetHeight()),
         pcbnew.LoadBoard(PCB).GetCopperLayerCount(),
         len(pcbnew.LoadBoard(PCB).GetFootprints())))
