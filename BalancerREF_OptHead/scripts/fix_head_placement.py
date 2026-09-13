"""Tighten the emitter loop and pull the TIA node away from it.

Two findings from the repo review:

  * The 0.9 A pulse loop spanned the whole board. R18 sat at x 121, Q1 and C20 at
    x 103, with D1 in the middle, so the loop C20 -> R18 -> D1 -> Q1 -> GND enclosed
    almost the full 25 mm width. Loop area is what radiates, and this one switches
    ~0.5 A in 5 us at 20 kHz.
  * R21 and C21 form the transimpedance summing junction - the highest-impedance node
    on the design - and sat at x 103, about 4 mm from Q1. They belong against U8 pins
    1 and 2, as far from the switcher as the board allows.

Why the parts were spread out in the first place: D1 has a provisional 8 mm lens
keepout (x 104.5-120.5, y 101-117) and PD1 has its own clear ring, which leaves only a
~7 mm band between them. The original placer pushed the emitter parts to the left and
right edges of that band. They can be clustered in the middle of it instead, which is
what this does - the ~8 mm run up to D1's pads is set by the lens keepout and cannot be
shortened without shrinking that keepout.

Dry run by default. Pass --apply to write.
"""
import sys, os, math
import pcbnew

APPLY = '--apply' in sys.argv
ROOT = r'C:\Users\nateh\hgs-linux\Balancer\BalancerREF_OptHead'
PCB = os.path.join(ROOT, 'BalancerREF_OptHead.kicad_pcb')

X0, Y0, X1, Y1 = 100.0, 100.0, 125.0, 150.0
EDGE, GAP = 0.85, 0.35
CX, D1_Y, LENS_R = 112.5, 109.0, 8.0

# ref -> (target x, y, why). Order matters: earlier entries get first pick.
JOBS = [
    ('R18', (CX,        118.4), 'series resistor, as close under D1 as the lens keepout allows'),
    ('Q1',  (CX + 3.2,  121.4), 'switch, kept beside R18 so the pulse loop stays small'),
    ('C20', (CX - 3.6,  120.2), 'reservoir - it sources the 5 us pulse, so it closes the loop'),
    ('R21', (104.2,     132.4), 'TIA feedback, against U8 pin 1'),
    ('C21', (104.2,     133.8), 'TIA feedback cap, against U8 pin 2'),
    # R24/R25 held the space beside U8 pins 1-2. They are the OPT_VREF divider -
    # a 10k/10k node with C23 across it, far less sensitive than the summing
    # junction - so they yield and move round to pin 5's side. Listed last so the
    # TIA parts get their spots first.
    ('R24', (116.0,     134.6), 'OPT_VREF divider, moved off the TIA side'),
    ('R25', (116.0,     136.8), 'OPT_VREF divider, moved off the TIA side'),
]

board = pcbnew.LoadBoard(PCB)
fps = {f.GetReference(): f for f in board.GetFootprints()}
movers = {r for r, _, _ in JOBS}
print('head board: %d footprints, moving %d' % (len(fps), len(movers)))


def measure(fp):
    poly = fp.GetCourtyard(fp.GetLayer())
    px, py = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
    bb = poly.BBox()
    l, t = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
    r, b = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
    return {'dx0': l - px, 'dy0': t - py, 'w': r - l, 'h': b - t}


def hits(a, b):
    return (a[0] < b[1] - 1e-9 and b[0] < a[1] - 1e-9
            and a[2] < b[3] - 1e-9 and b[2] < a[3] - 1e-9)


# D1's lens keepout is a hard placement constraint, not a note
occ = [(CX - LENS_R, CX + LENS_R, D1_Y - LENS_R, D1_Y + LENS_R)]
for f in board.GetFootprints():
    if f.GetReference() in movers:
        continue
    poly = f.GetCourtyard(f.GetLayer())
    if poly.OutlineCount():
        bb = poly.BBox()
        occ.append((pcbnew.ToMM(bb.GetLeft()) - GAP, pcbnew.ToMM(bb.GetRight()) + GAP,
                    pcbnew.ToMM(bb.GetTop()) - GAP, pcbnew.ToMM(bb.GetBottom()) + GAP))
    for p in f.Pads():
        if p.HasHole():
            bb = p.GetBoundingBox()
            occ.append((pcbnew.ToMM(bb.GetLeft()) - 0.35, pcbnew.ToMM(bb.GetRight()) + 0.35,
                        pcbnew.ToMM(bb.GetTop()) - 0.35, pcbnew.ToMM(bb.GetBottom()) + 0.35))
print('obstacles (incl. the D1 lens keepout): %d' % len(occ))


def find_spot(m, target, step=0.2, maxr=12.0):
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


print()
placed = {}
for ref, target, why in JOBS:
    fp = fps[ref]
    ox, oy = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
    m = measure(fp)
    spot = find_spot(m, target)
    if spot is None:
        print('%-4s !! no legal spot - left at (%.2f, %.2f)' % (ref, ox, oy))
        continue
    fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(spot[0] - m['dx0']),
                                   pcbnew.FromMM(spot[1] - m['dy0'])))
    occ.append((spot[0] - GAP, spot[0] + m['w'] + GAP,
                spot[1] - GAP, spot[1] + m['h'] + GAP))
    cx, cy = spot[0] + m['w'] / 2, spot[1] + m['h'] / 2
    placed[ref] = (cx, cy)
    print('%-4s (%6.2f,%6.2f) -> (%6.2f,%6.2f)   %s' % (ref, ox, oy, cx, cy, why))


def span(refs):
    pts = [placed.get(r) or (pcbnew.ToMM(fps[r].GetPosition().x),
                             pcbnew.ToMM(fps[r].GetPosition().y)) for r in refs]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return max(xs) - min(xs), max(ys) - min(ys)


def dist(a, b):
    pa = placed.get(a) or (pcbnew.ToMM(fps[a].GetPosition().x), pcbnew.ToMM(fps[a].GetPosition().y))
    pb = placed.get(b) or (pcbnew.ToMM(fps[b].GetPosition().x), pcbnew.ToMM(fps[b].GetPosition().y))
    return math.hypot(pa[0] - pb[0], pa[1] - pb[1])


w, h = span(['C20', 'R18', 'Q1'])
print()
print('emitter cluster C20/R18/Q1 now spans %.1f x %.1f mm (was about 18 mm wide)' % (w, h))
print('TIA parts to the switch:  R21<->Q1 %.1f mm, C21<->Q1 %.1f mm (was about 4 mm)'
      % (dist('R21', 'Q1'), dist('C21', 'Q1')))
def padpos(ref, pad):
    p = next(p for p in fps[ref].Pads() if p.GetPadName() == pad)
    c = p.GetBoundingBox().GetCenter()
    return pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)


def to_pad(ref, ic, pad):
    a = placed.get(ref) or (pcbnew.ToMM(fps[ref].GetPosition().x),
                            pcbnew.ToMM(fps[ref].GetPosition().y))
    b = padpos(ic, pad)
    return math.hypot(a[0] - b[0], a[1] - b[1])


# measure to the PIN, not the package centre - the centre flatters the number
print('TIA parts to their pins:  R21 %.1f mm to U8.1, C21 %.1f mm to U8.2'
      % (to_pad('R21', 'U8', '1'), to_pad('C21', 'U8', '2')))

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)
board.Save(PCB)
print('Saved.')
