"""Connection-aware placement for BalancerREF: 50 x 50, 4 layers, two sides.

Replaces the earlier first-fit packer. That one scanned from the top-left corner, so
it crammed every part into the top band and left the middle of the board empty - a
placement that passed DRC and containment while being useless as a layout.

Here each IC gets a target zone chosen for what it connects to, and every passive is
drawn to its owning IC. Ownership comes from two sources:
  * shared non-global nets (R13 -> J3, L1 -> U6, R6/R7 -> U7, ...)
  * for decoupling caps, which touch only GND and a rail and so share nothing
    distinctive, the nearest IC in the ORIGINAL hand-influenced board. That geometry
    encodes the designer's intent and is worth recovering rather than discarding.

Passives sit on the BOTTOM directly beneath their IC wherever possible - which is the
entire point of a two-sided 4-layer board: a decoupling cap lands under its IC's power
pins with a via straight through.

Dry run by default. Pass --apply to write.
"""
import sys, math, collections
import pcbnew

APPLY = '--apply' in sys.argv
PCB = r'C:\Users\nateh\hgs-linux\Balancer\BalancerREF\BalancerREF.kicad_pcb'
ORIG = r'C:\Users\nateh\AppData\Local\Temp\claude\BalancerREF-prePlace.kicad_pcb'
MOUNT_LIB = r'C:\Program Files\KiCad\10.0\share\kicad\footprints\MountingHole.pretty'
MOUNT_FP = 'MountingHole_2.7mm_M2.5'

X0, Y0, SIZE = 100.0, 100.0, 50.0
X1, Y1 = X0 + SIZE, Y0 + SIZE
EDGE = 0.85
GAP = 0.30
MOUNT_INSET = 3.3
U2_LOCAL_CLEARANCE = 0.15

EDGE_ROT = {'bottom': 0, 'right': 90, 'top': 180, 'left': 270}
ANCHORS = [('J1', 'bottom', 125.0), ('SW1', 'bottom', 113.0),
           ('J5', 'left', 118.0), ('J3', 'left', 136.0),
           ('J2', 'right', 118.0), ('J4', 'right', 135.0)]

# Target zones, chosen by what each part talks to rather than by packing order.
# U1 owns the top band; the interior below it is divided between the analog chain on
# the left (nearest J5/J3) and the power chain on the right (nearest J2).
IC_TARGETS = {
    'U9':  (113.0, 121.0),   # optical gate, near J5
    'U10': (113.0, 128.0),   # optical monostable, below U9
    'U3':  (113.5, 136.5),   # LM1815 mag tach, near J3
    'U2':  (124.0, 126.0),   # accelerometer, central
    'U6':  (136.0, 129.0),   # TPS63031 buck-boost
    'U5':  (138.5, 121.0),   # MCP73831 charger, near J2 battery
    'U7':  (127.5, 140.5),   # USB ESD, near J1
}
SW_TARGETS = {'SW2': (110.5, 108.0), 'SW3': (138.0, 108.0)}
GLOBAL_NETS = {'GND', '/+3V3', '/SYS_SW', '/SYS', '/BAT', '/USB_VBUS', ''}

board = pcbnew.LoadBoard(PCB)
board.SetCopperLayerCount(4)

# ---- outline -----------------------------------------------------------------
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

# ---- mounting holes ----------------------------------------------------------
CORNERS = {'H1': (X0 + MOUNT_INSET, Y1 - MOUNT_INSET),
           'H2': (X1 - MOUNT_INSET, Y1 - MOUNT_INSET),
           'H3': (X0 + MOUNT_INSET, Y0 + MOUNT_INSET),
           'H4': (X1 - MOUNT_INSET, Y0 + MOUNT_INSET)}
have = {f.GetReference(): f for f in board.GetFootprints()}
for ref, (cx, cy) in CORNERS.items():
    h = have.get(ref)
    if h is None:
        h = pcbnew.FootprintLoad(MOUNT_LIB, MOUNT_FP)
        h.SetReference(ref); h.SetValue('M2.5 MOUNT'); board.Add(h)
    h.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(cx), pcbnew.FromMM(cy)))


def refof(f): return f.GetReference()


def is_top(ref):
    if ref.startswith('H'): return None
    if ref == 'LED1': return True
    return ref.startswith(('U', 'J', 'SW', 'TP'))


fps = list(board.GetFootprints())
holes = [f for f in fps if is_top(refof(f)) is None]
top = [f for f in fps if is_top(refof(f)) is True]
bot = [f for f in fps if is_top(refof(f)) is False]
for f in bot:
    if f.GetLayer() != pcbnew.B_Cu: f.Flip(f.GetPosition(), False)
for f in top + holes:
    if f.GetLayer() != pcbnew.F_Cu: f.Flip(f.GetPosition(), False)

byref = {refof(f): f for f in fps}
byref['U2'].SetLocalClearance(pcbnew.FromMM(U2_LOCAL_CLEARANCE))


def measure(f):
    lay = pcbnew.F_Cu if f.GetLayer() == pcbnew.F_Cu else pcbnew.B_Cu
    poly = f.GetCourtyard(lay)
    px = pcbnew.ToMM(f.GetPosition().x); py = pcbnew.ToMM(f.GetPosition().y)
    if poly.OutlineCount():
        bb = poly.BBox()
        l, t = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
        r, b = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
    else:
        xs, ys = [], []
        for q in f.Pads():
            bb = q.GetBoundingBox()
            xs += [pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight())]
            ys += [pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())]
        l, r, t, b = min(xs) - 0.25, max(xs) + 0.25, min(ys) - 0.25, max(ys) + 0.25
    return {'fp': f, 'ref': refof(f), 'dx0': l - px, 'dx1': r - px,
            'dy0': t - py, 'dy1': b - py, 'w': r - l, 'h': b - t}


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


def padbox(f):
    xs, ys = [], []
    for q in f.Pads():
        bb = q.GetBoundingBox()
        xs += [pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight())]
        ys += [pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())]
    return min(xs), max(xs), min(ys), max(ys)


def setbox(m, bx, by):
    m['fp'].SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(bx - m['dx0']),
                                        pcbnew.FromMM(by - m['dy0'])))
    m['x'], m['y'] = bx, by


def hits(a, b):
    return (a[0] < b[1] - 1e-9 and b[0] < a[1] - 1e-9
            and a[2] < b[3] - 1e-9 and b[2] < a[3] - 1e-9)


def box_of(m): return (m['x'], m['x'] + m['w'], m['y'], m['y'] + m['h'])


def find_spot(m, target, occ, step=0.4, maxr=30.0):
    """Nearest free position to a target, searched outward. This is what stops the
    result piling into one corner: every part is drawn toward where it belongs and
    only pushed away by actual collisions."""
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


# ---- ownership ---------------------------------------------------------------
netof = collections.defaultdict(set)
for f in fps:
    for p in f.Pads():
        if p.GetNetname(): netof[refof(f)].add(p.GetNetname())
anchors_for_own = [r for r in netof if r.startswith(('U', 'J')) and r != 'U1']
orig = pcbnew.LoadBoard(ORIG)
opos = {refof(f): (pcbnew.ToMM(f.GetPosition().x), pcbnew.ToMM(f.GetPosition().y))
        for f in orig.GetFootprints()}
owner = {}
for f in bot:
    r = refof(f)
    best, bn = None, 0
    for a in anchors_for_own:
        share = len((netof[r] & netof[a]) - GLOBAL_NETS)
        if share > bn: bn, best = share, a
    if best is None and r in opos:
        cand = sorted((math.dist(opos[r], opos[i]), i)
                      for i in anchors_for_own + ['U1'] if i in opos)
        best = cand[0][1] if cand else 'U1'
    owner[r] = best or 'U1'
print('ownership groups:')
for k, v in sorted(collections.Counter(owner.values()).items()):
    print('   %-5s %2d parts' % (k, v))

# ---- fixed anchors -----------------------------------------------------------
items = {refof(f): measure(f) for f in fps}
occ_top, occ_bot = [], []

u1 = items['U1']; u1f = u1['fp']
fx0, fx1, fy0, fy1 = fab_offsets(u1f)
u1['dx0'], u1['dx1'], u1['dy0'], u1['dy1'] = fx0, fx1, fy0, fy1
u1['w'], u1['h'] = fx1 - fx0, fy1 - fy0
padtop_off = padbox(u1f)[2] - pcbnew.ToMM(u1f.GetPosition().y)
u1f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(X0 + SIZE / 2 - (fx0 + fx1) / 2),
                                pcbnew.FromMM(Y0 + EDGE - padtop_off)))
u1['x'] = pcbnew.ToMM(u1f.GetPosition().x) + fx0
u1['y'] = pcbnew.ToMM(u1f.GetPosition().y) + fy0
occ_top.append((u1['x'] - GAP, u1['x'] + u1['w'] + GAP, Y0, u1['y'] + u1['h'] + GAP))
print('U1 body x %.1f..%.1f, on-board to y %.1f'
      % (u1['x'], u1['x'] + u1['w'], u1['y'] + u1['h']))

mount_occ = []
for f in holes:
    m = measure(f)
    px = pcbnew.ToMM(f.GetPosition().x); py = pcbnew.ToMM(f.GetPosition().y)
    mount_occ.append((px + m['dx0'] - GAP, px + m['dx1'] + GAP,
                      py + m['dy0'] - GAP, py + m['dy1'] + GAP))
occ_top += mount_occ
occ_bot += mount_occ

bad = []
for ref, edge, along in ANCHORS:
    f = items[ref]['fp']; f.SetOrientationDegrees(EDGE_ROT[edge])
    dx0, dx1, dy0, dy1 = fab_offsets(f)
    if edge == 'bottom':  px, py = along, Y1 - dy1
    elif edge == 'top':   px, py = along, Y0 - dy0
    elif edge == 'left':  px, py = X0 - dx0, along
    else:                 px, py = X1 - dx1, along
    f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(px), pcbnew.FromMM(py)))
    pl, pr, pt0, pb = padbox(f)
    sh = 0.0
    if edge == 'left' and pl < X0 + EDGE: sh = (X0 + EDGE) - pl
    elif edge == 'right' and pr > X1 - EDGE: sh = (X1 - EDGE) - pr
    elif edge == 'bottom' and pb > Y1 - EDGE: sh = (Y1 - EDGE) - pb
    elif edge == 'top' and pt0 < Y0 + EDGE: sh = (Y0 + EDGE) - pt0
    if sh:
        if edge in ('left', 'right'): px += sh
        else: py += sh
        f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(px), pcbnew.FromMM(py)))
    m = measure(f)
    m['x'] = pcbnew.ToMM(f.GetPosition().x) + m['dx0']
    m['y'] = pcbnew.ToMM(f.GetPosition().y) + m['dy0']
    items[ref] = m
    bx = (m['x'] - GAP, m['x'] + m['w'] + GAP, m['y'] - GAP, m['y'] + m['h'] + GAP)
    if any(hits(bx, o) for o in mount_occ): bad.append(ref)
    occ_top.append(bx); occ_bot.append(bx)
print('edge connectors anchored: %s%s'
      % (' '.join(r for r, _, _ in ANCHORS), '  CLASH:%s' % bad if bad else ''))

# ---- top side ----------------------------------------------------------------
placed_top = [u1] + [items[r] for r, _, _ in ANCHORS]
fail = []
print('IC zones:')
for ref, tgt in list(IC_TARGETS.items()) + list(SW_TARGETS.items()):
    m = items[ref]
    s = find_spot(m, tgt, occ_top)
    if s is None: fail.append(ref); continue
    setbox(m, *s)
    occ_top.append((m['x'] - GAP, m['x'] + m['w'] + GAP,
                    m['y'] - GAP, m['y'] + m['h'] + GAP))
    placed_top.append(m)
    print('   %-4s -> (%5.1f,%5.1f)  %.1f mm off target'
          % (ref, m['x'] + m['w'] / 2, m['y'] + m['h'] / 2,
             math.dist((m['x'] + m['w'] / 2, m['y'] + m['h'] / 2), tgt)))

done = {m['ref'] for m in placed_top}
cx, cy = X0 + SIZE / 2, Y0 + SIZE / 2 + 4
rest_top = [items[refof(f)] for f in top if refof(f) not in done]
for m in sorted(rest_top, key=lambda m: -(m['w'] * m['h'])):
    tgt = IC_TARGETS.get(owner.get(m['ref'], ''), (cx, cy))
    s = find_spot(m, tgt, occ_top)
    if s is None: fail.append(m['ref']); continue
    setbox(m, *s)
    occ_top.append((m['x'] - GAP, m['x'] + m['w'] + GAP,
                    m['y'] - GAP, m['y'] + m['h'] + GAP))
    placed_top.append(m)

# ---- bottom side -------------------------------------------------------------
for f in top:
    for p in f.Pads():
        if p.HasHole():
            bb = p.GetBoundingBox()
            occ_bot.append((pcbnew.ToMM(bb.GetLeft()) - 0.35,
                            pcbnew.ToMM(bb.GetRight()) + 0.35,
                            pcbnew.ToMM(bb.GetTop()) - 0.35,
                            pcbnew.ToMM(bb.GetBottom()) + 0.35))
placed_bot = []
for f in sorted(bot, key=lambda f: -(items[refof(f)]['w'] * items[refof(f)]['h'])):
    m = items[refof(f)]
    om = items.get(owner.get(m['ref'], 'U1'))
    tgt = (om['x'] + om['w'] / 2, om['y'] + om['h'] / 2) if om and 'x' in om else (cx, cy)
    s = find_spot(m, tgt, occ_bot)
    if s is None: fail.append(m['ref']); continue
    setbox(m, *s)
    occ_bot.append((m['x'] - GAP, m['x'] + m['w'] + GAP,
                    m['y'] - GAP, m['y'] + m['h'] + GAP))
    placed_bot.append(m)

print('TOP placed %d, BOTTOM placed %d%s'
      % (len(placed_top), len(placed_bot), '  FAILED:%s' % fail if fail else ''))


def quadrants(ms, label):
    q = collections.Counter()
    for m in ms:
        mx, my = m['x'] + m['w'] / 2, m['y'] + m['h'] / 2
        q['%s%s' % ('T' if my < Y0 + SIZE / 2 else 'B',
                    'L' if mx < X0 + SIZE / 2 else 'R')] += 1
    print('  %s spread  TL=%2d TR=%2d BL=%2d BR=%2d'
          % (label, q['TL'], q['TR'], q['BL'], q['BR']))


quadrants(placed_top, 'top   ')
quadrants(placed_bot, 'bottom')
ov = 0
for grp in (placed_top, placed_bot):
    for i in range(len(grp)):
        for j in range(i + 1, len(grp)):
            if hits(box_of(grp[i]), box_of(grp[j])):
                ov += 1
                if ov <= 4: print('  OVERLAP %s/%s' % (grp[i]['ref'], grp[j]['ref']))
print('same-side overlaps:', ov)

if not APPLY:
    print('\nDRY RUN - nothing written.'); sys.exit(0)
if fail or ov or bad:
    print('\nREFUSING TO WRITE.'); sys.exit(1)
eb = board.GetBoardEdgesBoundingBox()
bw, bh = pcbnew.ToMM(eb.GetWidth()), pcbnew.ToMM(eb.GetHeight())
assert abs(bw - SIZE) < 0.1 and abs(bh - SIZE) < 0.1, 'outline %.2f x %.2f' % (bw, bh)
el, et = pcbnew.ToMM(eb.GetLeft()), pcbnew.ToMM(eb.GetTop())
er, ebm = pcbnew.ToMM(eb.GetRight()), pcbnew.ToMM(eb.GetBottom())
stray = []
for f in board.GetFootprints():
    if not list(f.Pads()): continue
    pl, pr, pt0, pb = padbox(f)
    if pl < el or pr > er or pt0 < et or pb > ebm:
        stray.append(refof(f))
assert not stray, 'pads outside outline: %s' % sorted(set(stray))
print('verified against actual %.1f x %.1f outline: no pads outside' % (bw, bh))
board.Save(PCB)
print('Saved.')
