"""Remove SW4 (RESET) from BalancerREF, schematic and board.

SW1 feeds U6's VIN and EN, so the power slide already power-cycles the regulator and
therefore the MCU - a dedicated EN button is redundant. Net-(U1-EN) keeps R4 (10k
pull-up), C10 (1u) and TP13, so EN stays pulled high and is still reachable by probe.

Wires are NOT pruned. Two wires meeting at a removed part's pin still meet each other
at that coordinate once the part is gone, so leaving them preserves every surviving
net by construction; pruning fragments nets silently. Only fully-orphaned islands -
wire groups touching no surviving pin, which cannot affect connectivity - are swept.

Dry run by default. Pass --apply to write.
"""
import sys, collections, subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexp_helpers import *
import math

ROOT = HERE.parent
assert ROOT.name == 'BalancerREF', ROOT
APPLY = '--apply' in sys.argv
SCH = ROOT / 'BalancerREF.kicad_sch'
KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
DROP = {'SW4'}


def rnd(v): return round(v, 4)
def refof(s):
    return next((p[2] for p in children(s, 'property') if p[1] == 'Reference'), '')
def unit_of(n):
    p = n.rsplit('_', 2)
    return int(p[1]) if len(p) == 3 and p[1].isdigit() else 0


def export_net(path, out):
    subprocess.run([KC, 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
                    '-o', str(out), str(path)], capture_output=True, text=True)
    return parse(Path(out).read_text(encoding='utf8'))


def partition(doc, drop=()):
    out = {}
    for n in children(one(doc, 'nets'), 'net'):
        nm = one(n, 'name')[1]
        for p in children(n, 'node'):
            r = one(p, 'ref')[1]
            if r.startswith('#') or r in drop: continue
            out[r + '.' + one(p, 'pin')[1]] = nm
    return out


tmp = Path(tempfile.mkdtemp())
base = partition(export_net(SCH, tmp / 'b.net'), drop=DROP)
groups = collections.defaultdict(set)
for pin, nm in base.items():
    groups[nm].add(pin)
print('baseline (excluding %s): %d pins across %d nets'
      % (','.join(sorted(DROP)), len(base), len(groups)))

d = parse(SCH.read_text(encoding='utf8'))
libs = {s[1]: s for s in children(one(d, 'lib_symbols'), 'symbol')}
syms = children(d, 'symbol')
gone = [s for s in syms if refof(s) in DROP]
assert gone, 'SW4 not found'
print('removing %d symbol instance(s): %s' % (len(gone), [refof(s) for s in gone]))


def pinpos(sym):
    at = one(sym, 'at'); x, y = at[1], at[2]; ang = at[3] if len(at) > 3 else 0
    u = one(sym, 'unit')[1]; lib = libs[one(sym, 'lib_id')[1]]
    t = math.radians(ang); c, s = math.cos(t), math.sin(t)
    out = []
    for sub in children(lib, 'symbol'):
        if unit_of(sub[1]) not in (0, u): continue
        for pin in children(sub, 'pin'):
            a = one(pin, 'at')
            out.append((rnd(x + c * a[1] - s * a[2]), rnd(y - s * a[1] - c * a[2])))
    return out


if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)

d[:] = [a for a in d if id(a) not in {id(s) for s in gone}]

# sweep wire islands that touch no surviving pin
kept = [s for s in children(d, 'symbol') if not refof(s).startswith('#')]
solid = {p for s in kept for p in pinpos(s)}
pwr = [s for s in children(d, 'symbol') if refof(s).startswith('#')]
flagpins = {p for s in pwr if one(s, 'lib_id')[1] == 'power:PWR_FLAG' for p in pinpos(s)}
anchors = solid | flagpins

wires = list(children(d, 'wire'))
segs = {}
for w in wires:
    xs = children(one(w, 'pts'), 'xy')
    segs[id(w)] = ((rnd(xs[0][1]), rnd(xs[0][2])), (rnd(xs[1][1]), rnd(xs[1][2])))


def interior(q, a, b):
    return ((a[0] == b[0] == q[0] and min(a[1], b[1]) <= q[1] <= max(a[1], b[1])) or
            (a[1] == b[1] == q[1] and min(a[0], b[0]) <= q[0] <= max(a[0], b[0])))


parent = {k: k for k in segs}
def find(k):
    while parent[k] != k:
        parent[k] = parent[parent[k]]; k = parent[k]
    return k
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: parent[ra] = rb


bypoint = collections.defaultdict(list)
for k, (a, b) in segs.items():
    bypoint[a].append(k); bypoint[b].append(k)
for v in bypoint.values():
    for k in v[1:]: union(v[0], k)
for k, (a, b) in segs.items():
    for q in (a, b):
        for j, sg in segs.items():
            if j != k and interior(q, *sg): union(k, j)

comp = collections.defaultdict(set)
for k in segs: comp[find(k)].add(k)
orphan = set()
for members in comp.values():
    pts = {q for k in members for q in segs[k]}
    if not (pts & anchors): orphan |= members
opts = {q for k in orphan for q in segs[k]}
dead_w = [w for w in wires if id(w) in orphan]
dead_l = [l for l in children(d, 'label')
          if (rnd(one(l, 'at')[1]), rnd(one(l, 'at')[2])) in opts]
live = {q for k in segs if k not in orphan for q in segs[k]}
dead_p = [s for s in pwr
          if one(s, 'lib_id')[1] != 'power:PWR_FLAG'
          and pinpos(s)[0] not in live and pinpos(s)[0] not in solid]
dead_j = [j for j in children(d, 'junction')
          if (rnd(one(j, 'at')[1]), rnd(one(j, 'at')[2])) in opts]
print('sweeping orphan islands: %d wires, %d labels, %d power symbols, %d junctions'
      % (len(dead_w), len(dead_l), len(dead_p), len(dead_j)))
swept = {id(x) for x in dead_w + dead_l + dead_p + dead_j}
d[:] = [a for a in d if id(a) not in swept]
SCH.write_text(dump(d) + '\n', encoding='utf8')

cur = partition(export_net(SCH, tmp / 'a.net'))
curg = collections.defaultdict(set)
for pin, nm in cur.items(): curg[nm].add(pin)
bad = []
for nm, want in groups.items():
    homes = {cur.get(p) for p in want}
    if None in homes or len(homes) > 1 or curg[list(homes)[0]] != want:
        bad.append((nm, sorted(want), sorted(h for h in homes if h)))
if bad:
    print('\nFAIL - %d net(s) changed:' % len(bad))
    for nm, want, homes in bad[:8]:
        print('   %-16s want=%s now=%s' % (nm, want, homes))
    sys.exit(1)
print('PASS: all %d surviving nets identical to baseline' % len(groups))
print('  EN net is now: %s' % ' '.join(sorted(curg[cur['U1.45']])))
