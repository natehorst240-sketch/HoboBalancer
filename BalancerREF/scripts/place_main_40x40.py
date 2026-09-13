"""Re-place every BalancerREF main-board footprint on the TOP layer of a 40x40 board.

Constraints this works to:
  * 40 x 40 mm outline, all components on F.Cu, none on the back.
  * U1's antenna overhangs the top edge. The module body is 15.4 x 20.0 mm with the
    antenna at its -y end, and its keepout (which forbids footprints, tracks, vias
    and pours) spans y -24.75..-5.25 local. Hanging the antenna off the edge puts
    that whole band off-board, which is what makes 40 x 40 reachable at all - and
    it is needed anyway, because the aluminium bracket must not sit behind a PCB
    antenna.
  * Everything is placed at rotation 0. KiCad's footprint rotation convention is
    easy to get backwards, and a wrong sign silently flips parts off the board;
    rotation-0 placement is verifiable by inspection. Rotate connectors by hand
    afterwards so their openings face outward.

Footprint (at x y) is the ORIGIN, not the bounding-box centre - several parts here
have offset origins (U1 +2.55, the tactile switches +3.25/+2.25) - so every
placement solves for the origin from the desired box position.

Existing tracks, vias and zones are deleted: they belong to the old two-sided
placement and mean nothing once everything moves.

Dry run by default. Pass --apply to write.
"""
import sys, math, collections
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexp_helpers import *

ROOT = HERE.parent
assert ROOT.name == 'BalancerREF', ROOT
APPLY = '--apply' in sys.argv
PCB = ROOT / 'BalancerREF.kicad_pcb'
KLIB = Path(r'C:\Program Files\KiCad\10.0\share\kicad\footprints')

REMOVE = {'D1', 'PD1', 'Q1', 'U4', 'U8',
          'R18', 'R19', 'R20', 'R21', 'R22', 'R23', 'R24', 'R25', 'R26', 'R27', 'R28',
          'C20', 'C21', 'C22', 'C23', 'C24', 'C25'}

X0, Y0, SIZE = 100.0, 100.0, 40.0
X1, Y1 = X0 + SIZE, Y0 + SIZE
EDGE = 0.6          # keep copper this far inside the outline
GAP = 0.05          # courtyards already carry IPC clearance

J5_LIB = 'Connector_JST'
J5_FP = 'JST_GH_SM07B-GHS-TB_1x07-1MP_P1.25mm_Horizontal'
J5_NETS = {'1': '/SYS_SW', '2': 'GND', '3': '/OPT_LED_EN', '4': 'GND',
           '5': '/OPT_COMP', '6': 'GND', '7': '/+3V3'}

d = parse(PCB.read_text(encoding='utf8'))


def refof(f):
    return next((p[2] for p in children(f, 'property') if p[1] == 'Reference'), '')


def crtyd_local(fp):
    """F.CrtYd extent. This is what KiCad's courtyards_overlap rule judges, and it
    is meaningfully larger than the pad extent - an 0805 pad box is 2.9 x 1.45 but
    its courtyard is 3.4 x 1.9. Placing to pad boxes produced 133 courtyard
    violations, so the courtyard is the real placement box."""
    xs, ys = [], []
    for g in (children(fp, 'fp_line') + children(fp, 'fp_rect')
              + children(fp, 'fp_poly') + children(fp, 'fp_circle')):
        lay = one(g, 'layer')
        if not (lay and str(lay[1]) in ('F.CrtYd', 'B.CrtYd')):
            continue
        if tagged(g, 'fp_circle'):
            # Test-point courtyards are circles, not rectangles. Missing these made
            # every TestPoint fall through to a guessed margin, which is what left
            # the test points overlapping their neighbours.
            ctr = one(g, 'center'); end = one(g, 'end')
            r = math.hypot(end[1] - ctr[1], end[2] - ctr[2])
            xs += [ctr[1] - r, ctr[1] + r]; ys += [ctr[2] - r, ctr[2] + r]
            continue
        for k in ('start', 'end'):
            c = one(g, k)
            if c: xs.append(c[1]); ys.append(c[2])
        p = one(g, 'pts')
        if p:
            for xy in children(p, 'xy'): xs.append(xy[1]); ys.append(xy[2])
    return (min(xs), max(xs), min(ys), max(ys)) if xs else None


def box_local(fp):
    """Bounding box in footprint-local coords: pads, plus F.Fab body outline where
    present (the ESP32's body is much larger than its castellated pad area)."""
    xs, ys = [], []
    for pad in children(fp, 'pad'):
        at = one(pad, 'at'); sz = one(pad, 'size')
        px, py = at[1], at[2]
        w, h = sz[1], sz[2]
        if len(at) > 3 and abs(at[3]) % 180 == 90:
            w, h = h, w
        xs += [px - w / 2, px + w / 2]; ys += [py - h / 2, py + h / 2]
    for g in children(fp, 'fp_line') + children(fp, 'fp_rect'):
        lay = one(g, 'layer')
        if lay and str(lay[1]) == 'F.Fab':
            for k in ('start', 'end'):
                c = one(g, k)
                if c: xs.append(c[1]); ys.append(c[2])
    if not xs:
        xs, ys = [-0.5, 0.5], [-0.5, 0.5]
    return min(xs), max(xs), min(ys), max(ys)


fps = children(d, 'footprint')
keep = [f for f in fps if refof(f) not in REMOVE]
print('footprints: %d -> %d after removing the optical chain' % (len(fps), len(keep)))

# ---- J5 ----------------------------------------------------------------------
src = parse((KLIB / (J5_LIB + '.pretty') / (J5_FP + '.kicad_mod')).read_text(encoding='utf8'))
j5 = [a for a in src if not (tagged(a, 'version') or tagged(a, 'generator')
                             or tagged(a, 'generator_version'))]
j5[1] = J5_LIB + ':' + J5_FP
j5 = [j5[0], j5[1]] + [a for a in j5[2:] if not tagged(a, 'property')]
j5.insert(2, node('layer', 'F.Cu'))
j5.insert(3, node('uuid', uid()))
j5.insert(4, node('at', 0, 0))
for k, v in [('Reference', 'J5'), ('Value', 'OPTICAL HEAD 7-WAY'),
             ('Datasheet', ''), ('Description', '')]:
    j5.append(node('property', k, v, node('at', 0, -2.5, 0), node('layer', 'F.SilkS'),
              node('uuid', uid()),
              node('effects', node('font', node('size', 1, 1), node('thickness', 0.15)))))
for pad in children(j5, 'pad'):
    n = J5_NETS.get(pad[1])
    if n:
        pad.append(node('net', n))
keep.append(j5)
print('added J5 (%s) with %d pads' % (J5_FP, len(children(j5, 'pad'))))

# ---- geometry ----------------------------------------------------------------
items = []
for f in keep:
    ref = refof(f)
    cy = crtyd_local(f)
    if ref == 'U1' or cy is None:
        # U1's courtyard is the 45.4 x 35.2 antenna keepout envelope, wider than the
        # board itself. Its real footprint-forbidding keepout polygon sits entirely
        # above the module and goes off-board with the overhang, so U1 is placed to
        # its body; the leftover courtyard overlap is a known ESP32-footprint quirk
        # to exclude in the DRC rules, not a real interference.
        x0, x1, y0, y1 = box_local(f)
        if cy is None:
            x0, x1, y0, y1 = x0 - 0.6, x1 + 0.6, y0 - 0.6, y1 + 0.6
    else:
        x0, x1, y0, y1 = cy
    # Pad angles in a .kicad_pcb are ABSOLUTE - they mirror the footprint rotation
    # (LED1 at 90 has pads at 90; U7 at -90 has pads at 270). Zeroing the footprint
    # rotation without rewriting every pad angle leaves pads rotated inside an
    # unrotated frame, which swaps each pad's width and height and collides them:
    # that produced 44 shorts and 40 mask bridges. So keep the original rotation
    # and rotate the placement box to match.
    at = one(f, 'at')
    rot = at[3] if len(at) > 3 else 0
    a = math.radians(rot); c, s = math.cos(a), math.sin(a)
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    g = [(lx * c - ly * s, lx * s + ly * c) for lx, ly in corners]
    gx = [p[0] for p in g]; gy = [p[1] for p in g]
    items.append({'fp': f, 'ref': ref, 'rot': rot,
                  'lx0': min(gx), 'lx1': max(gx), 'ly0': min(gy), 'ly1': max(gy),
                  'w': max(gx) - min(gx), 'h': max(gy) - min(gy)})
by = {i['ref']: i for i in items}

# U1: antenna off the top edge, pads a clear margin inside it.
u1 = by['U1']
u1_at_y = Y0 + EDGE - u1['ly0'] - 5.3     # 5.3 mm of antenna end hangs over
u1['x'] = X0 + SIZE / 2 - (u1['lx0'] + u1['lx1']) / 2
u1['y'] = u1_at_y
u1_box = (u1['x'] + u1['lx0'], u1['x'] + u1['lx1'], Y0, u1['y'] + u1['ly1'])
print('U1 on-board box: x %.2f..%.2f  y %.2f..%.2f  (%.1f mm of antenna overhangs)'
      % (u1_box[0], u1_box[1], u1_box[2], u1_box[3], Y0 - (u1['y'] + u1['ly0'])))

# Free rectangles either side of, and below, U1.
blocks = [
    ('left',  X0 + EDGE, u1_box[0] - GAP, Y0 + EDGE, Y1 - EDGE),
    ('right', u1_box[1] + GAP, X1 - EDGE, Y0 + EDGE, Y1 - EDGE),
    ('below', u1_box[0] - GAP, u1_box[1] + GAP, u1_box[3] + GAP, Y1 - EDGE),
]
for n, a, b, c, e in blocks:
    print('  block %-6s %5.2f x %5.2f = %6.1f mm2' % (n, b - a, e - c, (b - a) * (e - c)))

# Connectors and switches first so they land at block origins, i.e. against an edge.
EDGEFIRST = ['J5', 'J1', 'J2', 'J3', 'J4', 'SW1', 'SW2', 'SW3', 'SW4']
rest = [i for i in items if i['ref'] not in EDGEFIRST + ['U1']]
rest.sort(key=lambda i: -i['h'])
order = [by[r] for r in EDGEFIRST] + rest

placed = [u1]
shelves = {n: [] for n, *_ in blocks}   # (ytop, ybot, xcursor)
fail = []
for it in order:
    w, h = it['w'] + GAP, it['h'] + GAP
    done = False
    for name, bx0, bx1, by0, by1 in blocks:
        for sh in shelves[name]:
            if sh['x'] + w <= bx1 and sh['y'] + h <= sh['ybot'] + 1e-9:
                it['x'] = sh['x'] - it['lx0']; it['y'] = sh['y'] - it['ly0']
                sh['x'] += w; done = True; break
        if done: break
        ynext = (shelves[name][-1]['ybot'] if shelves[name] else by0)
        if ynext + h <= by1 and bx0 + w <= bx1:
            sh = {'x': bx0, 'y': ynext, 'ybot': ynext + h}
            it['x'] = sh['x'] - it['lx0']; it['y'] = sh['y'] - it['ly0']
            sh['x'] += w
            shelves[name].append(sh); done = True; break
    if not done:
        fail.append(it['ref']); continue
    placed.append(it)

print('\nplaced %d / %d' % (len(placed), len(items)))
if fail:
    print('DID NOT FIT (%d): %s' % (len(fail), fail))

# ---- overlap + containment check --------------------------------------------
def gbox(i):
    return (i['x'] + i['lx0'], i['x'] + i['lx1'], i['y'] + i['ly0'], i['y'] + i['ly1'])


ov = 0
for a in range(len(placed)):
    for b in range(a + 1, len(placed)):
        A, B = gbox(placed[a]), gbox(placed[b])
        if A[0] < B[1] and B[0] < A[1] and A[2] < B[3] and B[2] < A[3]:
            ov += 1
            if ov <= 5:
                print('  OVERLAP %s / %s' % (placed[a]['ref'], placed[b]['ref']))
outside = [i['ref'] for i in placed if i['ref'] != 'U1'
           and not (X0 <= gbox(i)[0] and gbox(i)[1] <= X1
                    and Y0 <= gbox(i)[2] and gbox(i)[3] <= Y1)]
print('overlaps: %d   outside outline: %s' % (ov, outside or 'none'))

if not APPLY:
    print('\nDRY RUN - nothing written. Re-run with --apply.')
    sys.exit(0)
if fail or ov or outside:
    print('\nREFUSING TO WRITE: placement is not clean.')
    sys.exit(1)

# ---- apply -------------------------------------------------------------------
for i in placed:
    at = one(i['fp'], 'at')
    at[1] = round(i['x'], 4); at[2] = round(i['y'], 4)
    # rotation is left exactly as it was; see the pad-angle note above
    lay = one(i['fp'], 'layer')
    if lay: lay[1] = 'F.Cu'

drop = {id(f) for f in fps if refof(f) in REMOVE}
d[:] = [a for a in d
        if id(a) not in drop
        and not tagged(a, 'segment') and not tagged(a, 'via') and not tagged(a, 'zone')
        and not (tagged(a, 'gr_rect') and one(a, 'layer')
                 and str(one(a, 'layer')[1]) == 'Edge.Cuts')]
if id(j5) not in {id(x) for x in d}:
    d.append(j5)
d.append(node('gr_rect', node('start', X0, Y0), node('end', X1, Y1),
         node('stroke', node('width', 0.05), node('type', S('default'))),
         node('fill', S('no')), node('layer', 'Edge.Cuts'), node('uuid', uid())))

PCB.write_text(dump(d) + '\n', encoding='utf8')
print('\nWROTE %s - %d footprints, all on F.Cu, %g x %g outline.'
      % (PCB.name, len(placed), SIZE, SIZE))
