"""Split the optical tach front end out of BalancerREF Rev C onto its own board.

D1/PD1 must sit at 90 degrees to the main PCB on the aluminium L-bracket's second
leg, on a pivot bolt, so the optical chain moves to BalancerREF_OptHead. The cut is
after the comparator, so the cable carries only DC rails and digital edges.

This removes the 22 optical parts from the HAND-LAID-OUT Rev C sheet and adds J5,
the 7-way cable connector. It deliberately leaves every wire in place.

That is the whole trick. Connectivity on a hand layout is geometric, and two wires
that met at a removed part's pin still meet each other at that coordinate once the
part is gone - so leaving the wires alone preserves every surviving net by
construction. Pruning them does not: SYS_SW reached C4 and U6 VIN through wires
routed via R18/C20's pins, and pruning silently killed both, along with U1 pin 13.
A repair pass that stubbed labels onto the affected pins made it worse rather than
converging. So: no pruning. The orphaned stubs left where the optical block used to
be are cosmetic, and get deleted by hand during layout cleanup.

J5 is parked in empty space at the bottom-left (56.9 mm clear of anything) to be
dragged into the optical block during that cleanup.

Dry run by default. Pass --apply to write.
"""
import sys, math, collections, subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexp_helpers import *

ROOT = HERE.parent
assert ROOT.name == 'BalancerREF', 'refusing to run outside BalancerREF: %s' % ROOT
APPLY = '--apply' in sys.argv
SCH = ROOT / 'BalancerREF.kicad_sch'
KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'

REMOVE = {'D1', 'PD1', 'Q1', 'U4', 'U8',
          'R18', 'R19', 'R20', 'R21', 'R22', 'R23', 'R24', 'R25', 'R26', 'R27', 'R28',
          'C20', 'C21', 'C22', 'C23', 'C24', 'C25'}

# Ground interleaved between the two digital lines: OPT_LED_EN crosstalk onto
# OPT_COMP lands inside U9's gating window and would pass as a genuine tape hit.
J5_PINOUT = {1: 'SYS_SW', 2: 'GND', 3: 'OPT_LED_EN', 4: 'GND',
             5: 'OPT_COMP', 6: 'GND', 7: '+3V3'}
J5_AT = (60.96, 386.08)        # on the 1.27 mm connection grid; 56 mm clear of content
J5_FP = 'Connector_JST:JST_GH_SM07B-GHS-TB_1x07-1MP_P1.25mm_Horizontal'


def rnd(v): return round(v, 4)
def unit_of(n):
    p = n.rsplit('_', 2)
    return int(p[1]) if len(p) == 3 and p[1].isdigit() else 0
def refof(s):
    return next((p[2] for p in children(s, 'property') if p[1] == 'Reference'), '')


def export_net(schpath, out):
    subprocess.run([KC, 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
                    '-o', str(out), str(schpath)], capture_output=True, text=True)
    if not Path(out).exists():
        raise SystemExit('netlist export failed')
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
base = partition(export_net(SCH, tmp / 'base.net'), drop=REMOVE)
groups = collections.defaultdict(set)
for pin, nm in base.items():
    groups[nm].add(pin)
cmp_out = next(n for n, g in groups.items() if 'U9.1' in g)
print('baseline: %d kept pins across %d nets' % (len(base), len(groups)))
print('U9.1 sits on %r -> becomes OPT_COMP via J5.5' % cmp_out)

d = parse(SCH.read_text(encoding='utf8'))
libs = {s[1]: s for s in children(one(d, 'lib_symbols'), 'symbol')}


def pininfo(sym):
    at = one(sym, 'at'); x, y = at[1], at[2]; ang = at[3] if len(at) > 3 else 0
    u = one(sym, 'unit')[1]; lib = libs[one(sym, 'lib_id')[1]]
    t = math.radians(ang); c, s = math.cos(t), math.sin(t)
    o = {}
    for sub in children(lib, 'symbol'):
        if unit_of(sub[1]) not in (0, u): continue
        for pin in children(sub, 'pin'):
            a = one(pin, 'at')
            o[one(pin, 'number')[1]] = (rnd(x + c * a[1] - s * a[2]),
                                        rnd(y - s * a[1] - c * a[2]))
    return o


symbols = children(d, 'symbol')
removed = [s for s in symbols if refof(s) in REMOVE]
assert not (REMOVE - {refof(s) for s in removed}), 'missing refs'
u9 = next(s for s in symbols if refof(s) == 'U9')
u9p1 = pininfo(u9)['1']
print('symbols: %d -> removing %d instances (%d refs); keeping all %d wires'
      % (len(symbols), len(removed), len(REMOVE), len(children(d, 'wire'))))

if not APPLY:
    print('\nDRY RUN - nothing written. Re-run with --apply.')
    sys.exit(0)

doomed = {id(s) for s in removed}
d[:] = [a for a in d if id(a) not in doomed]

# ---- J5 ----------------------------------------------------------------------
sheetid = one(d, 'uuid')[1]
conn = standard('Connector_Generic', 'Conn_01x07')
lnode = one(d, 'lib_symbols')
if not any(s[1] == 'Connector_Generic:Conn_01x07' for s in children(lnode, 'symbol')):
    c = deepcopy(conn); c[1] = 'Connector_Generic:Conn_01x07'; lnode.append(c)
x0, y0 = J5_AT
inst = node('symbol', node('lib_id', 'Connector_Generic:Conn_01x07'),
            node('at', x0, y0, 180), node('unit', 1), node('in_bom', S('yes')),
            node('on_board', S('yes')), node('dnp', S('no')), node('uuid', uid()))
t = math.radians(180); c_, s_ = math.cos(t), math.sin(t)
jp = {}
for sub in children(conn, 'symbol'):
    for pin in children(sub, 'pin'):
        a = one(pin, 'at'); num = one(pin, 'number')[1]
        jp[num] = (rnd(x0 + c_ * a[1] - s_ * a[2]), rnd(y0 - s_ * a[1] - c_ * a[2]))
        inst.append(node('pin', num, node('uuid', uid())))
for k, v in [('Reference', 'J5'), ('Value', 'OPTICAL HEAD 7-WAY'),
             ('Footprint', J5_FP), ('Datasheet', ''), ('MPN', 'SM07B-GHS-TB')]:
    inst.append(prop(k, v, x0, y0 - 25.4 + (2.54 if k == 'Value' else 0),
                     k not in ('Reference', 'Value')))
inst.append(node('instances', node('project', 'BalancerREF',
            node('path', '/' + sheetid, node('reference', 'J5'), node('unit', 1)))))
d.append(inst)

gseq = [700]


def stub(pos, netname, length=10.16):
    bx, by = rnd(pos[0] - length), rnd(pos[1])
    d.append(node('wire', node('pts', node('xy', *pos), node('xy', bx, by)),
             node('stroke', node('width', 0), node('type', S('default'))),
             node('uuid', uid())))
    if netname == 'GND':
        gseq[0] += 1; ref = '#PWR%03d' % gseq[0]
        gi = node('symbol', node('lib_id', 'power:GND'), node('at', bx, by, 270),
                  node('unit', 1), node('in_bom', S('no')), node('on_board', S('no')),
                  node('dnp', S('no')), node('uuid', uid()),
                  node('pin', '1', node('uuid', uid())))
        for k, v in [('Reference', ref), ('Value', 'GND'), ('Footprint', ''),
                     ('Datasheet', '')]:
            gi.append(prop(k, v, bx, by, True))
        gi.append(node('instances', node('project', 'BalancerREF',
                  node('path', '/' + sheetid, node('reference', ref), node('unit', 1)))))
        d.append(gi)
    else:
        d.append(node('label', netname, node('at', bx, by, 180),
                 node('effects', node('font', node('size', 1.27, 1.27)),
                      node('justify', S('left'), S('bottom'))), node('uuid', uid())))


for num, netname in sorted(J5_PINOUT.items()):
    stub(jp[str(num)], netname)

# U9 pin 1 lost the comparator that named its net; label it so J5.5 can find it.
d.append(node('label', 'OPT_COMP', node('at', u9p1[0], u9p1[1], 0),
         node('effects', node('font', node('size', 1.27, 1.27)),
              node('justify', S('left'), S('bottom'))), node('uuid', uid())))

# ---- sweep fully-orphaned islands -------------------------------------------
# Safe where the earlier prune was not: an island of wires touching NO surviving
# pin is disconnected from every net by definition, so deleting it cannot change
# connectivity. Anything still touching a real pin is left strictly alone.
libs = {s[1]: s for s in children(one(d, 'lib_symbols'), 'symbol')}  # J5's lib now present
kept_syms = [s for s in children(d, 'symbol') if not refof(s).startswith('#')]
solid_pins = {p for s in kept_syms for p in pininfo(s).values()}
pwr_syms = [s for s in children(d, 'symbol') if refof(s).startswith('#')]

wires_now = list(children(d, 'wire'))
segs = {}
for w in wires_now:
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
for pts_ in bypoint.values():
    for k in pts_[1:]:
        union(pts_[0], k)
for k, (a, b) in segs.items():
    for q in (a, b):
        for j, sg in segs.items():
            if j != k and interior(q, *sg): union(k, j)

comp = collections.defaultdict(set)
for k in segs:
    comp[find(k)].add(k)
# A PWR_FLAG anchors its island even with no component pin on it: its whole job is
# to declare a rail externally driven. Sweeping the SYS_SW flag leaves U6 VIN
# reading as undriven power.
flag_pins = {p for s in pwr_syms if one(s, 'lib_id')[1] == 'power:PWR_FLAG'
             for p in pininfo(s).values()}
anchors = solid_pins | flag_pins
orphan_segs = set()
for root, members in comp.items():
    pts_ = {q for k in members for q in segs[k]}
    if not (pts_ & anchors):
        orphan_segs |= members
orphan_pts = {q for k in orphan_segs for q in segs[k]}

dead_w = [w for w in wires_now if id(w) in orphan_segs]
dead_l = [l for l in children(d, 'label')
          if (rnd(one(l, 'at')[1]), rnd(one(l, 'at')[2])) in orphan_pts
          or any(interior((rnd(one(l, 'at')[1]), rnd(one(l, 'at')[2])), *segs[k])
                 for k in orphan_segs)]
live_pts = {q for k in segs if k not in orphan_segs for q in segs[k]}
dead_p = [s for s in pwr_syms
          if one(s, 'lib_id')[1] != 'power:PWR_FLAG'
          and list(pininfo(s).values())[0] not in live_pts
          and list(pininfo(s).values())[0] not in solid_pins]
dead_j = [j for j in children(d, 'junction')
          if (rnd(one(j, 'at')[1]), rnd(one(j, 'at')[2])) in orphan_pts]
print('sweeping orphan islands: %d wires, %d labels, %d power symbols, %d junctions'
      % (len(dead_w), len(dead_l), len(dead_p), len(dead_j)))
swept = {id(x) for x in dead_w + dead_l + dead_p + dead_j}
d[:] = [a for a in d if id(a) not in swept]

SCH.write_text(dump(d) + '\n', encoding='utf8')

# ---- verify every surviving net is unchanged ---------------------------------
cur = partition(export_net(SCH, tmp / 'after.net'))
curg = collections.defaultdict(set)
for pin, nm in cur.items():
    curg[nm].add(pin)
expect = {nm: set(g) for nm, g in groups.items()}
for num, netname in J5_PINOUT.items():
    tgt = {'SYS_SW': '/SYS_SW', 'OPT_LED_EN': '/OPT_LED_EN', '+3V3': '/+3V3',
           'GND': 'GND', 'OPT_COMP': cmp_out}[netname]
    expect[tgt].add('J5.%d' % num)

bad = []
for nm, want in expect.items():
    homes = {cur.get(p) for p in want}
    if None in homes or len(homes) > 1 or curg[list(homes)[0]] != want:
        bad.append((nm, sorted(want), sorted(h for h in homes if h)))
if bad:
    print('\nFAIL - %d net(s) changed:' % len(bad))
    for nm, want, homes in bad[:10]:
        print('  %-18s want=%s now on=%s' % (nm, want, homes))
    sys.exit(1)
print('\nPASS: all %d surviving nets identical to baseline, J5 joined to 5 of them.'
      % len(expect))
print('J5 at %s - drag it into the optical block; orphaned stubs there are cosmetic.'
      % (J5_AT,))
