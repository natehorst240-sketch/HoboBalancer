"""Re-place BalancerREF as a 4-layer, two-sided 40 x 40 board.

Split requested: ICs, connectors, switches and test points on the TOP layer;
everything else (passives, diodes, FETs, the inductor) on the BOTTOM.

LED1 is treated as a top-side part despite being a passive-looking 0603: it is the
status indicator and has to be visible from the same face as the switches.

All through-hole parts (J1-J4, SW1-SW4) are in the top group by construction, which
is required - they insert from the top.

Uses KiCad's own pcbnew API rather than editing the s-expression. Flipping a
footprint is not a coordinate negation: it mirrors geometry AND remaps every F.*
layer to B.* across pads, graphics, courtyard and silkscreen. Hand-rolling that is
how you get pads that look right and are silently wrong - the earlier pass already
proved that by zeroing rotations without rewriting absolute pad angles, which
produced 44 phantom shorts.

BOX2I values are read out into plain floats immediately; the SWIG wrappers return
temporaries that must not be held.

Dry run by default. Pass --apply to write.
"""
import sys
import pcbnew

APPLY = '--apply' in sys.argv
PCB = r'C:\Users\nateh\hgs-linux\Balancer\BalancerREF\BalancerREF.kicad_pcb'

X0, Y0, SIZE = 100.0, 100.0, 50.0
X1, Y1 = X0 + SIZE, Y0 + SIZE
EDGE = 0.85         # rule is 0.5; leave real margin, not zero
GAP = 0.30          # roomier on 50x50; helps routability, not just DRC

TOP_EXTRA = {'LED1'}
BOTTOM_EXTRA = set()

# M2.5 unplated, one per corner. The courtyard is 5.99 mm across, so the centre sits
# 3.3 mm in from both edges. Unplated deliberately: a plated hole would bond board
# ground to the aluminium bracket, and J3's magnetic pickup front end is specified as
# a passive ISOLATED input - chassis-bonding it turns an isolated pickup into a
# grounded one. Ask for plated + GND only if you actually want that bond.
MOUNT_LIB = r'C:\Program Files\KiCad\10.0\share\kicad\footprints\MountingHole.pretty'
MOUNT_FP = 'MountingHole_2.7mm_M2.5'
MOUNT_INSET = 3.3
# The board mounts vertically, so the accelerometer no longer needs anchoring to a
# specific bolt - it packs with everything else.
ACCEL_CORNER = None

# J1 is a TopMnt_Horizontal USB-C: its mouth faces local +y and the footprint carries
# a Dwgs.User line at local y = +3.67 marking where the PCB edge must fall. Aligning
# that line to the board edge is what makes the receptacle actually usable; anywhere
# else and the plug cannot reach it. Rotation 0 puts the mouth at the BOTTOM edge.
# Verified empirically against this KiCad build: a footprint's local +y maps to
# global +y at rot 0, +x at 90, -y at 180, -x at 270. Both horizontal-entry
# connectors here (J1 USB-C, J5 JST-GH) have their mouth on local +y, so the edge
# a connector faces determines its rotation outright.
EDGE_ROT = {'bottom': 0, 'right': 90, 'top': 180, 'left': 270}

# ref -> (edge, position along that edge). The body's outward face is set flush to
# the outline. J5 goes left because the optical head sits on that side; J1 bottom so
# the USB port is reachable without disturbing the antenna edge.
ANCHORS = [('J1', 'bottom', 125.0), ('SW1', 'bottom', 113.0),
           ('J5', 'left', 118.0), ('J3', 'left', 136.0),
           ('J2', 'right', 118.0), ('J4', 'right', 135.0)]

# U2's IIS3DWB LGA-14 has 0.175 mm between adjacent pads - a property of the package,
# not of placement. Scope the relaxation to this one footprint rather than dropping
# the whole board's clearance below 0.2 mm.
U2_LOCAL_CLEARANCE = 0.15


def is_top(ref):
    if ref.startswith('H'): return None          # mounting holes: fixed, not packed
    if ref in TOP_EXTRA: return True
    if ref in BOTTOM_EXTRA: return False
    return ref.startswith(('U', 'J', 'SW', 'TP'))


board = pcbnew.LoadBoard(PCB)
board.SetCopperLayerCount(4)
print('copper layers -> %d  (F.Cu, In1.Cu, In2.Cu, B.Cu)' % board.GetCopperLayerCount())

# Set the outline HERE. This script previously only moved footprints, placing them
# against the constant X1/Y1 while Edge.Cuts still held the old 40x40 rectangle - so
# parts sat outside the real board and the containment check passed anyway, because
# it compared against the constant instead of the artifact.
for d in list(board.GetDrawings()):
    if d.GetLayer() == pcbnew.Edge_Cuts:
        board.Remove(d)
rect = pcbnew.PCB_SHAPE(board)
rect.SetShape(pcbnew.SHAPE_T_RECT)
rect.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(X0), pcbnew.FromMM(Y0)))
rect.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(X1), pcbnew.FromMM(Y1)))
rect.SetLayer(pcbnew.Edge_Cuts)
rect.SetWidth(pcbnew.FromMM(0.05))
board.Add(rect)
eb = board.GetBoardEdgesBoundingBox()
print('outline set to %.1f x %.1f mm'
      % (pcbnew.ToMM(eb.GetWidth()), pcbnew.ToMM(eb.GetHeight())))

# ---- corner mounting holes ---------------------------------------------------
CORNERS = {'top-left': (X0 + MOUNT_INSET, Y0 + MOUNT_INSET),
           'top-right': (X1 - MOUNT_INSET, Y0 + MOUNT_INSET),
           'bot-left': (X0 + MOUNT_INSET, Y1 - MOUNT_INSET),
           'bot-right': (X1 - MOUNT_INSET, Y1 - MOUNT_INSET)}
existing = {f.GetReference() for f in board.GetFootprints()}
for i, (name, (cx, cy)) in enumerate(sorted(CORNERS.items()), start=1):
    ref = 'H%d' % i
    if ref in existing:
        # Reposition, never skip. Skipping left the holes at the 40x40 corners when
        # the board grew to 50x50, and J3/J4 were then anchored straight onto them.
        h = next(f for f in board.GetFootprints() if f.GetReference() == ref)
        h.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(cx), pcbnew.FromMM(cy)))
        print('moved %s to (%.2f, %.2f)  [%s]' % (ref, cx, cy, name))
        continue
    h = pcbnew.FootprintLoad(MOUNT_LIB, MOUNT_FP)
    h.SetReference(ref)
    h.SetValue('M2.5 MOUNT')
    h.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(cx), pcbnew.FromMM(cy)))
    board.Add(h)
    print('added %s at (%.2f, %.2f)  [%s]' % (ref, cx, cy, name))

fps = list(board.GetFootprints())
holes = [f for f in fps if is_top(f.GetReference()) is None]
top = [f for f in fps if is_top(f.GetReference()) is True]
bot = [f for f in fps if is_top(f.GetReference()) is False]
print('top group   : %2d  %s' % (len(top), ' '.join(sorted(f.GetReference() for f in top))))
print('bottom group: %2d  %s' % (len(bot), ' '.join(sorted(f.GetReference() for f in bot))))

# Flip the bottom group first, then measure - a flipped courtyard is not the mirror
# of the front one for asymmetric parts.
for f in bot:
    if f.GetLayer() != pcbnew.B_Cu:
        f.Flip(f.GetPosition(), False)
for f in top:
    if f.GetLayer() != pcbnew.F_Cu:
        f.Flip(f.GetPosition(), False)
print('flipped: %d now on B.Cu, %d on F.Cu'
      % (sum(1 for f in fps if f.GetLayer() == pcbnew.B_Cu),
         sum(1 for f in fps if f.GetLayer() == pcbnew.F_Cu)))


def measure(f):
    """Courtyard box as offsets from the footprint position, in mm."""
    lay = pcbnew.F_Cu if f.GetLayer() == pcbnew.F_Cu else pcbnew.B_Cu
    poly = f.GetCourtyard(lay)
    px = pcbnew.ToMM(f.GetPosition().x); py = pcbnew.ToMM(f.GetPosition().y)
    if poly.OutlineCount():
        bb = poly.BBox()
        l, t = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
        r, b = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
    else:
        l = t = r = b = None
        for p in f.Pads():
            bb = p.GetBoundingBox()
            pl, pt = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
            pr, pb = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
            l = pl if l is None else min(l, pl); t = pt if t is None else min(t, pt)
            r = pr if r is None else max(r, pr); b = pb if b is None else max(b, pb)
        l -= 0.25; t -= 0.25; r += 0.25; b += 0.25
    return {'fp': f, 'ref': f.GetReference(),
            'dx0': l - px, 'dx1': r - px, 'dy0': t - py, 'dy1': b - py,
            'w': r - l, 'h': b - t}


def body_box(f):
    """F.Fab/B.Fab body outline offsets - U1's real extent, not its keepout."""
    lay = 'F.Fab' if f.GetLayer() == pcbnew.F_Cu else 'B.Fab'
    lid = board.GetLayerID(lay)
    xs, ys = [], []
    for g in f.GraphicalItems():
        if g.GetLayer() == lid:
            bb = g.GetBoundingBox()
            xs += [pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight())]
            ys += [pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())]
    if not xs: return None
    px = pcbnew.ToMM(f.GetPosition().x); py = pcbnew.ToMM(f.GetPosition().y)
    return {'dx0': min(xs) - px, 'dx1': max(xs) - px,
            'dy0': min(ys) - py, 'dy1': max(ys) - py,
            'w': max(xs) - min(xs), 'h': max(ys) - min(ys)}


items = {}
for f in fps:
    m = measure(f)
    if f.GetReference() == 'U1':
        # U1's courtyard is the 45.4 x 35.2 antenna-keepout envelope, wider than the
        # board. Place to the module body; the keepout itself goes off-board with the
        # antenna overhang.
        bb = body_box(f)
        if bb: m.update(bb)
    items[m['ref']] = m


def place(m, bx, by):
    """Put the part's box top-left corner at (bx, by)."""
    m['fp'].SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(bx - m['dx0']),
                                        pcbnew.FromMM(by - m['dy0'])))
    m['x'], m['y'] = bx, by


def tht_obstacles(group, pad_clear=0.35):
    """Through-hole pads from the other face. A hole passes through every layer, so
    a THT pin on top forbids bottom-side copper at the same spot - J1-J4 and SW1-SW4
    are all through-hole, and ignoring them put bottom parts straight through their
    pins (26 violations on J4 alone)."""
    out = []
    for f in group:
        for p in f.Pads():
            if not p.HasHole():
                continue
            bb = p.GetBoundingBox()
            l, t = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
            r, b = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
            out.append((l - pad_clear, r + pad_clear, t - pad_clear, b + pad_clear))
    return out


def hits(a, b):
    return (a[0] < b[1] - 1e-9 and b[0] < a[1] - 1e-9
            and a[2] < b[3] - 1e-9 and b[2] < a[3] - 1e-9)


def gridpack(group, obstacles, label, step=0.4):
    """First-fit on a grid against an explicit obstacle list. Shelf packing cannot
    express 'avoid these scattered rectangles', which is what the THT pins are."""
    occ = list(obstacles)
    placed, failed = [], []
    for m in sorted(group, key=lambda m: -(m['w'] * m['h'])):
        w, h = m['w'] + GAP, m['h'] + GAP
        spot = None
        y = Y0 + EDGE
        while y + h <= Y1 - EDGE and spot is None:
            x = X0 + EDGE
            while x + w <= X1 - EDGE:
                box = (x, x + w, y, y + h)
                if not any(hits(box, o) for o in occ):
                    spot = (x, y); break
                x += step
            y += step
        if spot:
            place(m, spot[0], spot[1])
            occ.append((spot[0], spot[0] + w, spot[1], spot[1] + h))
            placed.append(m)
        else:
            failed.append(m)
    print('%-6s placed %d/%d%s' % (label, len(placed), len(group),
                                   '  FAILED: %s' % [f['ref'] for f in failed] if failed else ''))
    return placed, failed


def shelfpack(group, blocks, label):
    shelves = {n: [] for n, *_ in blocks}
    placed, failed = [], []
    for m in group:
        w, h = m['w'] + GAP, m['h'] + GAP
        done = False
        for name, bx0, bx1, by0, by1 in blocks:
            for sh in shelves[name]:
                if sh['x'] + w <= bx1 and sh['y'] + h <= sh['ybot'] + 1e-9:
                    place(m, sh['x'], sh['y']); sh['x'] += w; done = True; break
            if done: break
            ynext = shelves[name][-1]['ybot'] if shelves[name] else by0
            if ynext + h <= by1 and bx0 + w <= bx1:
                sh = {'x': bx0, 'y': ynext, 'ybot': ynext + h}
                place(m, sh['x'], sh['y']); sh['x'] += w
                shelves[name].append(sh); done = True; break
        (placed if done else failed).append(m)
    print('%-6s placed %d/%d%s' % (label, len(placed), len(group),
                                   '  FAILED: %s' % [f['ref'] for f in failed] if failed else ''))
    return placed, failed


# --- top side -----------------------------------------------------------------
# Drive U1 from its PAD row, not a hardcoded overhang. The pad-to-body offset is
# exactly 5.3 mm, so overhanging by 5.3 lands the top pad row precisely on the edge
# with zero margin - and it actually landed 0.35 mm OFF the board. Solve instead for
# the topmost pad sitting EDGE inside the outline; the antenna overhang is whatever
# falls out of that.
u1 = items['U1']
u1f = u1['fp']
padtop_off = min(pcbnew.ToMM(p.GetBoundingBox().GetTop()) for p in u1f.Pads())              - pcbnew.ToMM(u1f.GetPosition().y)
u1x = X0 + SIZE / 2 - u1['w'] / 2
u1f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(X0 + SIZE / 2 - (u1['dx0'] + u1['dx1']) / 2),
                                pcbnew.FromMM(Y0 + EDGE - padtop_off)))
u1['x'] = pcbnew.ToMM(u1f.GetPosition().x) + u1['dx0']
u1['y'] = pcbnew.ToMM(u1f.GetPosition().y) + u1['dy0']
u1box = (u1['x'], u1['x'] + u1['w'], Y0, u1['y'] + u1['h'])
print('U1 body x %.2f..%.2f  on-board to y %.2f  (%.2f mm antenna overhang, '
      'top pad row at y=%.2f)'
      % (u1box[0], u1box[1], u1box[3], Y0 - u1['y'], Y0 + EDGE))

# These must not overlap each other: the side blocks stop where the full-width
# block begins, or the packer fills the same region twice and parts land on top of
# one another while every individual block check still passes.
topblocks = [
    ('T-left',  X0 + EDGE, u1box[0] - GAP, Y0 + EDGE, u1box[3]),
    ('T-right', u1box[1] + GAP, X1 - EDGE, Y0 + EDGE, u1box[3]),
    ('T-below', X0 + EDGE, X1 - EDGE, u1box[3] + GAP, Y1 - EDGE),
]
# Sort the whole top group by height. Putting connectors first stranded U3 (9.16 mm
# tall) after the shelves had been set by shorter parts; shelf packing only works
# when the tallest items open the shelves. Connectors therefore end up wherever they
# fit rather than against an edge - fix that by hand.
tg = sorted([items[f.GetReference()] for f in top if f.GetReference() != 'U1'],
            key=lambda m: -m['h'])
mount_occ = []
for f in holes:
    m = measure(f)
    px = pcbnew.ToMM(f.GetPosition().x); py = pcbnew.ToMM(f.GetPosition().y)
    mount_occ.append((px + m['dx0'] - GAP, px + m['dx1'] + GAP,
                      py + m['dy0'] - GAP, py + m['dy1'] + GAP))
print('mounting-hole obstacles: %d (both faces - the holes are drilled through)'
      % len(mount_occ))

def fab_offsets(f):
    lid = board.GetLayerID('F.Fab' if f.GetLayer() == pcbnew.F_Cu else 'B.Fab')
    xs, ys = [], []
    for g in f.GraphicalItems():
        if g.GetLayer() == lid:
            bb = g.GetBoundingBox()
            xs += [pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight())]
            ys += [pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())]
    px = pcbnew.ToMM(f.GetPosition().x); py = pcbnew.ToMM(f.GetPosition().y)
    return min(xs) - px, max(xs) - px, min(ys) - py, max(ys) - py


def anchor_edge(ref, edge, along):
    """Rotate so the connector faces outward, then set its body's outward face flush
    with the outline. Rotation goes through SetOrientationDegrees, which rewrites the
    absolute pad angles properly."""
    f = items[ref]['fp']
    f.SetOrientationDegrees(EDGE_ROT[edge])
    dx0, dx1, dy0, dy1 = fab_offsets(f)
    if edge == 'bottom':  px, py = along, Y1 - dy1
    elif edge == 'top':   px, py = along, Y0 - dy0
    elif edge == 'left':  px, py = X0 - dx0, along
    else:                 px, py = X1 - dx1, along
    f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(px), pcbnew.FromMM(py)))
    # Flushing the BODY to the outline is not sufficient: several of these parts have
    # pads that reach further out than their body outline (J5 and J3 both ended up
    # 0.2 mm off the board). Pull back by whatever the pads overhang, plus EDGE.
    pl = min(pcbnew.ToMM(q.GetBoundingBox().GetLeft()) for q in f.Pads())
    pr = max(pcbnew.ToMM(q.GetBoundingBox().GetRight()) for q in f.Pads())
    pt0 = min(pcbnew.ToMM(q.GetBoundingBox().GetTop()) for q in f.Pads())
    pb0 = max(pcbnew.ToMM(q.GetBoundingBox().GetBottom()) for q in f.Pads())
    shift = 0.0
    if edge == 'left' and pl < X0 + EDGE:    shift = (X0 + EDGE) - pl
    elif edge == 'right' and pr > X1 - EDGE: shift = (X1 - EDGE) - pr
    elif edge == 'bottom' and pb0 > Y1 - EDGE: shift = (Y1 - EDGE) - pb0
    elif edge == 'top' and pt0 < Y0 + EDGE:  shift = (Y0 + EDGE) - pt0
    if shift:
        if edge in ('left', 'right'): px += shift
        else: py += shift
        f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(px), pcbnew.FromMM(py)))
        print('    %s pulled %+.2f mm inboard so its pads clear the edge' % (ref, shift))
    m = measure(f)
    m['x'] = pcbnew.ToMM(f.GetPosition().x) + m['dx0']
    m['y'] = pcbnew.ToMM(f.GetPosition().y) + m['dy0']
    items[ref] = m
    pl = min(pcbnew.ToMM(q.GetBoundingBox().GetLeft()) for q in f.Pads())
    pr = max(pcbnew.ToMM(q.GetBoundingBox().GetRight()) for q in f.Pads())
    pt_ = min(pcbnew.ToMM(q.GetBoundingBox().GetTop()) for q in f.Pads())
    pb = max(pcbnew.ToMM(q.GetBoundingBox().GetBottom()) for q in f.Pads())
    inside = X0 <= pl and pr <= X1 and Y0 <= pt_ and pb <= Y1
    print('  %-4s %-6s rot %3d  pads x %.2f..%.2f y %.2f..%.2f  on-board:%s'
          % (ref, edge, EDGE_ROT[edge], pl, pr, pt_, pb, inside))
    return m, inside


print('edge-anchored connectors:')
usb_occ = []
anchor_bad = []
def clash(m):
    return [i for i, o in enumerate(mount_occ)
            if hits((m['x'], m['x'] + m['w'], m['y'], m['y'] + m['h']), o)]
for ref, edge, along in ANCHORS:
    m, ok = anchor_edge(ref, edge, along)
    if not ok: anchor_bad.append(ref)
    if clash(m):
        print('    !! %s clashes with a mounting hole at this position' % ref)
        anchor_bad.append(ref)
    usb_occ.append((m['x'] - GAP, m['x'] + m['w'] + GAP,
                    m['y'] - GAP, m['y'] + m['h'] + GAP))

u2f = items['U2']['fp']
u2f.SetLocalClearance(pcbnew.FromMM(U2_LOCAL_CLEARANCE))
print('U2 local clearance override: %.3f mm (package pitch, scoped to U2 only)'
      % U2_LOCAL_CLEARANCE)

u1occ = [(u1box[0] - GAP, u1box[1] + GAP, Y0, u1box[3] + GAP)]
anchored = {r for r, _, _ in ANCHORS}
tg = [m for m in tg if m['ref'] not in anchored]
tp, tf = gridpack(tg, u1occ + mount_occ + usb_occ, 'TOP')
tp += [items[r] for r in anchored]

# --- bottom side --------------------------------------------------------------
obst = tht_obstacles(top) + mount_occ
print('through-hole obstacles from the top side: %d pads' % len(obst))
bg = [items[f.GetReference()] for f in bot]
bp, bf = gridpack(bg, obst, 'BOT')

# --- checks -------------------------------------------------------------------
def gbox(m):
    return (m['x'], m['x'] + m['w'], m['y'], m['y'] + m['h'])


ov = 0
for side, grp in (('top', [u1] + tp), ('bottom', bp)):
    for i in range(len(grp)):
        for j in range(i + 1, len(grp)):
            A, B = gbox(grp[i]), gbox(grp[j])
            if A[0] < B[1] - 1e-9 and B[0] < A[1] - 1e-9 and A[2] < B[3] - 1e-9 and B[2] < A[3] - 1e-9:
                ov += 1
                if ov <= 5: print('  OVERLAP(%s) %s / %s' % (side, grp[i]['ref'], grp[j]['ref']))
# U1 and J1 overhang the outline by design - U1's antenna clears the board, J1's
# receptacle mouth must reach the edge to be pluggable. For those two, the test is
# that their PADS are on the board, not their courtyards.
OVERHANG = {'U1', 'J1', 'J5', 'J3', 'J2', 'J4', 'SW1'}
outside = [m['ref'] for m in tp + bp
           if m['ref'] not in OVERHANG
           and not (X0 <= gbox(m)[0] and gbox(m)[1] <= X1
                    and Y0 <= gbox(m)[2] and gbox(m)[3] <= Y1)]
for ref in OVERHANG:
    f = items[ref]['fp']
    pl = min(pcbnew.ToMM(p.GetBoundingBox().GetLeft()) for p in f.Pads())
    pr = max(pcbnew.ToMM(p.GetBoundingBox().GetRight()) for p in f.Pads())
    pt_ = min(pcbnew.ToMM(p.GetBoundingBox().GetTop()) for p in f.Pads())
    pb = max(pcbnew.ToMM(p.GetBoundingBox().GetBottom()) for p in f.Pads())
    ok = X0 <= pl and pr <= X1 and Y0 <= pt_ and pb <= Y1
    print('%s pads x %.2f..%.2f y %.2f..%.2f  inside outline: %s'
          % (ref, pl, pr, pt_, pb, ok))
    if not ok:
        outside.append(ref + '(pads)')
print('same-side overlaps: %d   outside outline: %s' % (ov, outside or 'none'))

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)
if tf or bf or ov or outside or anchor_bad:
    print('\nREFUSING TO WRITE: placement not clean.')
    sys.exit(1)
# Verify against the board's OWN geometry, not the constants this script was told.
eb = board.GetBoardEdgesBoundingBox()
bw, bh = pcbnew.ToMM(eb.GetWidth()), pcbnew.ToMM(eb.GetHeight())
assert abs(bw - SIZE) < 0.1 and abs(bh - SIZE) < 0.1,     'outline is %.2f x %.2f, expected %g' % (bw, bh, SIZE)
el, et = pcbnew.ToMM(eb.GetLeft()), pcbnew.ToMM(eb.GetTop())
er, ebm = pcbnew.ToMM(eb.GetRight()), pcbnew.ToMM(eb.GetBottom())
stray = []
for f in board.GetFootprints():
    for q in f.Pads():
        pb = q.GetBoundingBox()
        if (pcbnew.ToMM(pb.GetLeft()) < el or pcbnew.ToMM(pb.GetRight()) > er
                or pcbnew.ToMM(pb.GetTop()) < et or pcbnew.ToMM(pb.GetBottom()) > ebm):
            stray.append(f.GetReference()); break
assert not stray, 'pads outside the real outline: %s' % sorted(set(stray))
print('verified against actual outline %.1f x %.1f: no pads outside' % (bw, bh))

board.Save(PCB)
print('\nSaved: 4 copper layers, %d top / %d bottom, %g x %g mm.'
      % (len(tp) + 1, len(bp), SIZE, SIZE))
