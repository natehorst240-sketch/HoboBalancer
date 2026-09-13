"""Put the switching loop and the decoupling where they electrically belong.

Three findings from the repo review, all of them a consequence of the blanket rule
"ICs on the front, passives on the back":

  * U6 (TPS63031) is on the front while L1 and C4-C7 are on the back, so the L1/L2
    switching node and BOTH the input and output capacitors reach their IC through
    vias. At 2.4 MHz that loop inductance is not a detail - it is the dominant term in
    output ripple and radiated noise. These five parts move to the front, tight to the
    pins they serve.
  * The BQ24075's C2/C3/C30 have the same problem, less critically, and move too.
  * C8/C9 decouple U1 but sit under the middle of the module near x 125-127, while the
    3V3 pad is on the module's left edge at x 118. They stay on the back - U1's body
    owns that area of the front - but move directly beneath pad 3.

Each part is aimed at the specific pad it serves rather than at the package centre:
L1 at the L1/L2 pins, C4/C5 at the SYS_SW inputs, C6/C7 at the +3V3 outputs, and so on.

pcbnew hazards worked around here, all found the hard way on this board:
  * board.Remove() segfaults - parts are repositioned, never removed
  * Flip() on a footprint with no parent board segfaults - these all have one
  * through-hole pads block BOTH faces, so they are obstacles regardless of layer
  * stdout is buffered and lost on a segfault - run with python -u

Dry run by default. Pass --apply to write.
"""
import sys, os, math
import pcbnew

APPLY = '--apply' in sys.argv
ROOT = r'C:\Users\nateh\hgs-linux\Balancer\BalancerREF'
PCB = os.path.join(ROOT, 'BalancerREF.kicad_pcb')

X0, Y0, X1, Y1 = 100.0, 100.0, 150.0, 150.0
EDGE, GAP = 0.85, 0.30

# ref -> (target IC, target pad, destination layer, why)
JOBS = [
    ('L1',  'U6', '4',  'F', 'switching node - shortest possible loop to L1/L2'),
    ('C4',  'U6', '7',  'F', 'SYS_SW input cap'),
    ('C5',  'U6', '6',  'F', 'SYS_SW input cap'),
    ('C6',  'U6', '10', 'F', '+3V3 output cap'),
    ('C7',  'U6', '1',  'F', '+3V3 output cap'),
    ('C3',  'U5', '2',  'F', 'BAT cap, 4.7-47uF per SLUS810N'),
    ('C2',  'U5', '13', 'F', 'IN cap'),
    ('C30', 'U5', '11', 'F', 'OUT cap'),
    ('C8',  'U1', '3',  'B', 'U1 3V3 decoupling - stays on the back, under pad 3'),
    ('C9',  'U1', '3',  'B', 'U1 3V3 decoupling - stays on the back, under pad 3'),
]

board = pcbnew.LoadBoard(PCB)
fps = {f.GetReference(): f for f in board.GetFootprints()}
movers = {r for r, _, _, _, _ in JOBS}
print('board has %d footprints; moving %d' % (len(fps), len(movers)))


def padpos(ref, pad):
    f = fps[ref]
    p = next(p for p in f.Pads() if p.GetPadName() == pad)
    c = p.GetBoundingBox().GetCenter()
    return pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)


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


def obstacles(layer_tag):
    """Courtyards on this face, plus every through-hole pad from either face."""
    want = pcbnew.F_Cu if layer_tag == 'F' else pcbnew.B_Cu
    out = []
    for f in board.GetFootprints():
        if f.GetReference() in movers:
            continue
        if f.GetLayer() == want:
            poly = f.GetCourtyard(f.GetLayer())
            if poly.OutlineCount():
                bb = poly.BBox()
                out.append((pcbnew.ToMM(bb.GetLeft()) - GAP, pcbnew.ToMM(bb.GetRight()) + GAP,
                            pcbnew.ToMM(bb.GetTop()) - GAP, pcbnew.ToMM(bb.GetBottom()) + GAP))
        for p in f.Pads():
            if p.HasHole():
                bb = p.GetBoundingBox()
                out.append((pcbnew.ToMM(bb.GetLeft()) - 0.35, pcbnew.ToMM(bb.GetRight()) + 0.35,
                            pcbnew.ToMM(bb.GetTop()) - 0.35, pcbnew.ToMM(bb.GetBottom()) + 0.35))
    return out


def find_spot(m, target, occ, step=0.2, maxr=14.0):
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


occ = {'F': obstacles('F'), 'B': obstacles('B')}
print('obstacles: front %d, back %d' % (len(occ['F']), len(occ['B'])))
print()
print('%-5s %-6s %-9s %-9s %s' % ('REF', 'LAYER', 'FROM', 'TO', 'DISTANCE TO ITS PAD'))

results = []
for ref, ic, pad, want_layer, why in JOBS:
    fp = fps[ref]
    was = fp.GetLayerName()
    ox, oy = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
    target = padpos(ic, pad)

    cur = 'F' if fp.GetLayer() == pcbnew.F_Cu else 'B'
    if cur != want_layer:
        ctr = fp.GetPosition()
        fp.Flip(ctr, False)

    m = measure(fp)
    spot = find_spot(m, target, occ[want_layer])
    if spot is None:
        print('%-5s !! no legal spot within 14 mm of %s.%s - left where it was'
              % (ref, ic, pad))
        continue
    fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(spot[0] - m['dx0']),
                                   pcbnew.FromMM(spot[1] - m['dy0'])))
    occ[want_layer].append((spot[0] - GAP, spot[0] + m['w'] + GAP,
                            spot[1] - GAP, spot[1] + m['h'] + GAP))
    cx, cy = spot[0] + m['w'] / 2, spot[1] + m['h'] / 2
    d = math.hypot(cx - target[0], cy - target[1])
    results.append((ref, d, ic, pad, why))
    print('%-5s %-6s (%.1f,%.1f) (%.1f,%.1f)  %.2f mm to %s.%s   %s'
          % (ref, was + '->' + fp.GetLayerName(), ox, oy, cx, cy, d, ic, pad, why))

print()
worst = max(results, key=lambda r: r[1]) if results else None
if worst:
    print('furthest from its pad: %s at %.2f mm (%s)' % (worst[0], worst[1], worst[4]))

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)
board.Save(PCB)
print('Saved.')
