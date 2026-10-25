"""Check BalancerMain.kicad_pcb against BalancerMain.net.json and for placement faults.

Every schematic pin must land on a pad with the same net, no two footprints' pads may
come within 0.5 mm of each other, every pad must sit inside the board outline, and no
other part may sit under the Feather's body (it rides on female headers above them).
Exit code 1 on any failure.
"""
import sys, json, math
from pathlib import Path
import sexpdata as sx

ROOT = Path(__file__).resolve().parent.parent
def tg(x, k): return isinstance(x, list) and x and str(x[0]) == k
def ch(x, k): return [a for a in x if tg(a, k)]
def one(x, k): return next((a for a in x if tg(a, k)), None)

doc = sx.loads((ROOT / 'BalancerMain.kicad_pcb').read_text(encoding='utf8'))
net = json.loads((ROOT / 'BalancerMain.net.json').read_text())
want = {(r, p): n for n, m in net['nets'].items() for r, p in m}
edge = [(float(one(g, k)[1]), float(one(g, k)[2])) for g in ch(doc, 'gr_line') if str(one(g, 'layer')[1]) == 'Edge.Cuts' for k in ('start', 'end')]
bx0, bx1 = min(p[0] for p in edge), max(p[0] for p in edge)
by0, by1 = min(p[1] for p in edge), max(p[1] for p in edge)
got, boxes, feather = {}, [], None
for fp in ch(doc, 'footprint'):
    ref = next(str(p[2]) for p in ch(fp, 'property') if str(p[1]) == 'Reference')
    at = one(fp, 'at'); X, Y = float(at[1]), float(at[2]); rot = float(at[3]) if len(at) > 3 else 0
    r = math.radians(rot); xs = []; ys = []
    for p in ch(fp, 'pad'):
        n = one(p, 'net')
        if n: got[(ref, str(p[1]))] = str(n[1]).lstrip('/')
        pa = one(p, 'at'); px, py = float(pa[1]), float(pa[2]); sz = one(p, 'size')
        x = X + px * math.cos(r) + py * math.sin(r); y = Y - px * math.sin(r) + py * math.cos(r)
        h = max(float(sz[1]), float(sz[2])) / 2
        xs += [x - h, x + h]; ys += [y - h, y + h]
    boxes.append((ref, min(xs), min(ys), max(xs), max(ys)))
    if 'Feather' in str(fp[1]):
        feather = (X - 11.59, Y - 24.33, X + 11.27, Y + 26.47)   # body outline from the footprint's F.Fab
ok = True
for k in want:
    if k not in got: print('FAIL: no pad for', k); ok = False
    elif got[k] != want[k]: print('FAIL: %s.%s has %s, schematic says %s' % (k[0], k[1], got[k], want[k])); ok = False
for i, a in enumerate(boxes):
    for b in boxes[i + 1:]:
        if a[1] < b[3] + 0.5 and b[1] < a[3] + 0.5 and a[2] < b[4] + 0.5 and b[2] < a[4] + 0.5:
            print('FAIL: pads of %s and %s within 0.5 mm' % (a[0], b[0])); ok = False
    if a[1] < bx0 + 0.3 or a[2] < by0 + 0.3 or a[3] > bx1 - 0.3 or a[4] > by1 - 0.3:
        print('FAIL: %s pads outside or on the board edge' % a[0]); ok = False
    if feather and a[0] != 'U1' and a[1] < feather[2] and feather[0] < a[3] and a[2] < feather[3] and feather[1] < a[4]:
        print('FAIL: %s under the Feather' % a[0]); ok = False
print('%d footprints, %d pins checked: %s' % (len(boxes), len(want), 'PASS' if ok else 'FAILED'))
sys.exit(0 if ok else 1)
