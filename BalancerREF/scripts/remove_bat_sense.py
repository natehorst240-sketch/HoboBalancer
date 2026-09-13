"""Remove the BAT_SENSE divider - the BQ24075's PGOOD pin makes it redundant.

BAT_SENSE (R33/R34/C31 on GPIO4) existed in Rev D so firmware could compare SYS_SW
against BAT and infer whether USB was present, because SUPPLY_SENSE alone could not
separate the two. The BQ24075 reports a valid input directly on PGOOD, so the
inference is no longer needed.

SUPPLY_SENSE still gauges the cell: with no input the BQ24075's OUT follows BAT, so
SYS_SW/2 is the battery voltage whenever the puck is actually running on battery. What
is lost is battery voltage *while charging* - CHG reports that state instead.

Dry run by default. Pass --apply to write.
"""
import sys, json, math, collections, subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexp_helpers import *
from rollback import Rollback

ROOT = HERE.parent
assert ROOT.name == 'BalancerREF', ROOT
APPLY = '--apply' in sys.argv
SCH = ROOT / 'BalancerREF.kicad_sch'
KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
DROP = {'R33', 'R34', 'C31'}
U1_PIN8 = (421.64, 287.02)
STUB_END = (411.48, 287.02)


def rnd(v): return round(v, 4)
def refof(s): return next((p[2] for p in children(s, 'property') if p[1] == 'Reference'), '')
def unit_of(n):
    p = n.rsplit('_', 2)
    return int(p[1]) if len(p) == 3 and p[1].isdigit() else 0


def export(o):
    subprocess.run([KC, 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
                    '-o', str(o), str(SCH)], capture_output=True, text=True)
    return parse(Path(o).read_text(encoding='utf8'))


def partition(doc, drop=()):
    r = {}
    for n in children(one(doc, 'nets'), 'net'):
        nm = one(n, 'name')[1]
        for p in children(n, 'node'):
            q = one(p, 'ref')[1]
            if not q.startswith('#') and q not in drop:
                r[q + '.' + one(p, 'pin')[1]] = nm
    return r


tmp = Path(tempfile.mkdtemp())
base = partition(export(tmp / 'b.net'), drop=DROP | {'U1'})
print('baseline (excluding %s and U1): %d pins' % (','.join(sorted(DROP)), len(base)))

d = parse(SCH.read_text(encoding='utf8'))
libs = {s[1]: s for s in children(one(d, 'lib_symbols'), 'symbol')}
gone = [s for s in children(d, 'symbol') if refof(s) in DROP]
assert {refof(s) for s in gone} == DROP, 'missing %s' % (DROP - {refof(s) for s in gone})
print('removing symbols: %s' % sorted(refof(s) for s in gone))

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)

dead = {id(s) for s in gone}
# the stub and label that carried BAT_SENSE to U1 pin 8
for w in children(d, 'wire'):
    xs = children(one(w, 'pts'), 'xy')
    e = ((rnd(xs[0][1]), rnd(xs[0][2])), (rnd(xs[1][1]), rnd(xs[1][2])))
    if set(e) == {U1_PIN8, STUB_END}:
        dead.add(id(w))
for l in children(d, 'label'):
    if l[1] == 'BAT_SENSE' and (rnd(one(l, 'at')[1]), rnd(one(l, 'at')[2])) == STUB_END:
        dead.add(id(l))
d[:] = [a for a in d if id(a) not in dead]
d.append(node('no_connect', node('at', *U1_PIN8), node('uuid', uid())))
print('removed the U1.8 stub and label; no_connect restored on GPIO4')

# sweep wire islands that no longer touch a pin
def pinpts(s):
    at = one(s, 'at'); x, y = at[1], at[2]; ang = at[3] if len(at) > 3 else 0
    t = math.radians(ang); c, si = math.cos(t), math.sin(t); o = []
    for sub in children(libs[one(s, 'lib_id')[1]], 'symbol'):
        if unit_of(sub[1]) not in (0, one(s, 'unit')[1]): continue
        for p in children(sub, 'pin'):
            a = one(p, 'at')
            o.append((rnd(x + c * a[1] - si * a[2]), rnd(y - si * a[1] - c * a[2])))
    return o


anchors = set()
for s in children(d, 'symbol'):
    if not refof(s).startswith('#') or one(s, 'lib_id')[1] == 'power:PWR_FLAG':
        anchors.update(pinpts(s))
wires = list(children(d, 'wire')); segs = {}
for w in wires:
    xs = children(one(w, 'pts'), 'xy')
    segs[id(w)] = ((rnd(xs[0][1]), rnd(xs[0][2])), (rnd(xs[1][1]), rnd(xs[1][2])))
par = {k: k for k in segs}
def find(k):
    while par[k] != k: par[k] = par[par[k]]; k = par[k]
    return k
def uni(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: par[ra] = rb
bp = collections.defaultdict(list)
for k, (a, b) in segs.items(): bp[a].append(k); bp[b].append(k)
for v in bp.values():
    for k in v[1:]: uni(v[0], k)
comp = collections.defaultdict(set)
for k in segs: comp[find(k)].add(k)
orph = set()
for mem in comp.values():
    if not ({q for k in mem for q in segs[k]} & anchors): orph |= mem
opts = {q for k in orph for q in segs[k]}
dw = [w for w in wires if id(w) in orph]
dl = [l for l in children(d, 'label') if (rnd(one(l, 'at')[1]), rnd(one(l, 'at')[2])) in opts]
live = {q for k in segs if k not in orph for q in segs[k]}
dp = [s for s in children(d, 'symbol') if refof(s).startswith('#')
      and one(s, 'lib_id')[1] != 'power:PWR_FLAG'
      and pinpts(s) and pinpts(s)[0] not in live and pinpts(s)[0] not in anchors]
print('sweeping orphans: %d wires, %d labels, %d power symbols' % (len(dw), len(dl), len(dp)))
d[:] = [a for a in d if id(a) not in {id(x) for x in dw + dl + dp}]

up = ROOT / 'review' / 'unused-pins.json'
# The orphan sweep is the risky step - it decides which wire islands no longer reach a
# pin, and getting that wrong silently splits a net. So both files are snapshotted and
# the netlist comparison below is a gate, not a report: if any surviving net moved, the
# schematic and unused-pins.json go back exactly as they were and the run fails.
with Rollback(SCH, up) as guard:
    SCH.write_text(dump(d) + '\n', encoding='utf8')

    nc = json.loads(up.read_text())
    nc['U1.8'] = 'Unused GPIO; BAT_SENSE removed once the BQ24075 PGOOD pin made it redundant'
    up.write_text(json.dumps(nc, indent=2))
    print('unused-pins.json: U1.8 restored, %d entries' % len(nc))

    cur = partition(export(tmp / 'a.net'), drop={'U1'})
    moved = {k: (base[k], cur.get(k)) for k in base if base[k] != cur.get(k)}
    guard.require(not moved, 'surviving nets changed: %s' % moved)
    print('\nsurviving nets: NONE changed - every other net identical')

    still = sorted(k for k, v in cur.items() if v == '/BAT_SENSE')
    guard.require(not still, 'BAT_SENSE survived on %s' % still)
    print('BAT_SENSE present: False')
