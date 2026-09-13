"""Add pick-and-place fiducials to a board.

Three per populated face. They are placed at THREE of the four corners, never four:
a symmetric set gives the placement machine no way to tell a 180-degree-rotated panel
from a correct one. Missing the fourth corner is what makes the pattern unambiguous.

1 mm copper dot with a 2 mm mask opening - the common standard. The dot carries no
net, so a ground pour flows around it under mask and the exposed ring still gives the
camera its contrast.

Main board has parts on both faces, so it gets both sets. The optical head is
single-sided, so its back needs none - nothing is placed there.

Dry run by default. Pass --apply to write.
"""
import sys, os, math
import pcbnew

APPLY = '--apply' in sys.argv
WHICH = 'head' if '--head' in sys.argv else 'main'
FPLIB = r'C:\Program Files\KiCad\10.0\share\kicad\footprints\Fiducial.pretty'
FPNAME = 'Fiducial_1mm_Mask2mm'
CLEAR = 2.2          # keep this clear of any part, mm

if WHICH == 'main':
    PCB = r'C:\Users\nateh\hgs-linux\Balancer\BalancerREF\BalancerREF.kicad_pcb'
    X0, Y0, X1, Y1 = 100.0, 100.0, 150.0, 150.0
    ALL_FACES = [(pcbnew.F_Cu, 'F'), (pcbnew.B_Cu, 'B')]
else:
    PCB = r'C:\Users\nateh\hgs-linux\Balancer\BalancerREF_OptHead\BalancerREF_OptHead.kicad_pcb'
    X0, Y0, X1, Y1 = 100.0, 100.0, 125.0, 150.0
    ALL_FACES = [(pcbnew.F_Cu, 'F')]

# One face per invocation. Doing both in a single process segfaults somewhere in
# pcbnew's state after the first face's footprints are added - loading, flipping and
# the obstacle scan were each proved fine in isolation, so rather than keep guessing
# at the interaction, each face gets a clean process. --face selects; SEQ0 keeps the
# reference numbering continuous across the two runs.
_face = 'F'
if '--face' in sys.argv:
    _face = sys.argv[sys.argv.index('--face') + 1]
SEQ0 = int(sys.argv[sys.argv.index('--seq') + 1]) if '--seq' in sys.argv else 0
FACES = [(l, t) for l, t in ALL_FACES if t == _face]
assert FACES, 'no such face: %s' % _face

INSET = 5.0
board = pcbnew.LoadBoard(PCB)
# Do NOT call board.Remove() - it segfaults under standalone pcbnew, and it was the
# real cause of the crash when this script handled both faces in one process: the
# second pass tried to clear the first pass's fiducials. Existing ones are skipped
# instead, so the script is idempotent per face. To reposition, delete them in pcbnew.
existing = [f for f in board.GetFootprints() if f.GetReference().startswith('FID')]
on_this_face = [f for f in existing if f.GetLayer() == FACES[0][0]]
if on_this_face:
    print('%s.Cu already has %d fiducial(s) (%s) - nothing to do'
          % (_face, len(on_this_face), ' '.join(f.GetReference() for f in on_this_face)))
    sys.exit(0)
if existing:
    print('keeping %d fiducial(s) already on the other face' % len(existing))


def obstacles(layer):
    """Parts on this face, plus any through-hole pad from either face - a hole
    blocks both sides."""
    out = []
    for f in board.GetFootprints():
        same = f.GetLayer() == layer
        holes = [p for p in f.Pads() if p.HasHole()]
        if same:
            bb = f.GetBoundingBox(False, False)
            out.append((pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight()),
                        pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())))
        for p in holes:
            bb = p.GetBoundingBox()
            out.append((pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight()),
                        pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())))
    return out


def clear(o, x, y, r=CLEAR):
    if not (X0 + 3 <= x <= X1 - 3 and Y0 + 3 <= y <= Y1 - 3):
        return False
    return not any(x - r < a[1] and a[0] < x + r and y - r < a[3] and a[2] < y + r
                   for a in o)


def nearest_clear(o, tx, ty):
    best, bd = None, 1e9
    step = 0.5
    n = int(max(X1 - X0, Y1 - Y0) / step)
    for i in range(n * 2):
        rad = i * step
        k = max(8, int(2 * math.pi * rad / step)) if rad else 1
        for j in range(k):
            a = 2 * math.pi * j / k
            x, y = tx + rad * math.cos(a), ty + rad * math.sin(a)
            if clear(o, x, y):
                d = math.hypot(x - tx, y - ty)
                if d < bd:
                    best, bd = (round(x, 2), round(y, 2)), d
        if best:
            return best
    return None


def pick_three(o):
    """Three clear spots chosen to maximise the smallest gap between them, from a
    grid biased toward the board edge. Fixed corner targets do not work here - U1's
    band owns the whole top of the main board's front face, so a corner target just
    wanders 18 mm inboard and lands somewhere useless."""
    grid = []
    x = X0 + 3.5
    while x <= X1 - 3.5:
        y = Y0 + 3.5
        while y <= Y1 - 3.5:
            edge = min(x - X0, X1 - x, y - Y0, Y1 - y)
            if edge <= 9.0 and clear(o, x, y):
                grid.append((x, y))
            y += 0.5
        x += 0.5
    if len(grid) < 3:
        return None
    best, bestscore = None, -1
    corners = [(X0, Y1), (X1, Y1), (X0, Y0), (X1, Y0)]
    for drop in range(4):        # leave one corner empty - that is the asymmetry
        keep = [c for i, c in enumerate(corners) if i != drop]
        pts = []
        for cx, cy in keep:
            cand = min(grid, key=lambda p: math.hypot(p[0] - cx, p[1] - cy))
            pts.append(cand)
        if len({(round(p[0], 2), round(p[1], 2)) for p in pts}) < 3:
            continue
        score = min(math.hypot(a[0] - b[0], a[1] - b[1])
                    for i, a in enumerate(pts) for b in pts[i + 1:])
        if score > bestscore:
            best, bestscore = pts, score
    return best


# Obstacles for every face are computed BEFORE anything is added. Re-querying the
# board after adding footprints segfaults under standalone pcbnew.
obs = {tag: obstacles(layer) for layer, tag in FACES}

seq = SEQ0
added = []
for layer, tag in FACES:
    spots = pick_three(obs[tag])
    if spots is None:
        print('  !! not enough clear area on %s' % tag)
        continue
    for spot in spots:
        seq += 1
        fp = pcbnew.FootprintLoad(FPLIB, FPNAME)
        fp.SetReference('FID%d' % seq)
        fp.SetValue('FIDUCIAL')
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(spot[0]), pcbnew.FromMM(spot[1])))
        # Add BEFORE flipping. Flip on a footprint with no parent board is an access
        # violation inside pcbnew - it needs the board to remap its layers.
        board.Add(fp)
        if layer == pcbnew.B_Cu:
            ctr = pcbnew.VECTOR2I(pcbnew.FromMM(spot[0]), pcbnew.FromMM(spot[1]))
            fp.Flip(ctr, False)
        added.append((fp.GetReference(), tag, spot))
        print('  %-5s %s.Cu  (%.2f, %.2f)' % (fp.GetReference(), tag, spot[0], spot[1]))
    sep = min(math.hypot(a[0] - b[0], a[1] - b[1])
              for i, a in enumerate(spots) for b in spots[i + 1:])
    print('        closest pair on %s: %.1f mm apart' % (tag, sep))

print('%d fiducials on %s board' % (len(added), WHICH))
if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)
board.Save(PCB)
print('Saved %s' % os.path.basename(PCB))
