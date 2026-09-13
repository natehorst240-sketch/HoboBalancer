"""Replace MCP73831 + D2 + Q3 + R31 with a BQ24075 integrated charger/power path.

The old arrangement was a charger plus a discrete OR: USB reached SYS through D2 (a
Schottky, costing ~0.45 V) while Q3 disconnected the battery whenever VBUS pulled its
gate high. The BQ24075 does all of that internally with DPPM - the system runs from a
regulated OUT, and the battery supplements only when the load exceeds the input limit.

Consequences worth knowing:
  * D2's drop is gone, so SYS no longer sags toward the battery voltage on a weak USB
    port. The old worst case put SYS at ~4.30 V against a full cell at 4.20 V.
  * PGOOD reports a valid input directly, which is what Rev D's BAT_SENSE differential
    comparison existed to infer. BAT_SENSE stays useful as a battery gauge.
  * Package is VQFN-16 3x3 with a thermal pad - not hand-solderable with an iron.

Pinout taken from SLUS810N Rev N Table 7-1 / Figure 7-3. Note pin 15 is SYSOFF on the
'75 but ITERM on the '74 - the wrong variant silently disconnects the battery.

Dry run by default. Pass --apply to write.
"""
import sys, json, math, subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexp_helpers import *

ROOT = HERE.parent
assert ROOT.name == 'BalancerREF', ROOT
APPLY = '--apply' in sys.argv
SCH = ROOT / 'BalancerREF.kicad_sch'
KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'

DROP = {'U5', 'R3', 'D2', 'Q3', 'R31'}
U5_AT = (534.67, 95.25)          # verified clear against wire SEGMENTS, not just endpoints
RES_X, RES_X2 = 39.37, 39.37
GPIO = {  # U1 pad -> (net, stub direction sign)
    '9':  ('CHG_EN1',  -1),   # GPIO5
    '22': ('CHG_EN2',  -1),   # GPIO18
    '25': ('PGOOD_N',  +1),   # GPIO21
    '34': ('CHG_STAT', +1),   # GPIO38
}
U1_PINPOS = {'9': (421.64, 289.56), '22': (421.64, 322.58),
             '25': (452.12, 284.48), '34': (452.12, 302.26)}


def rnd(v): return round(v, 4)
def refof(s): return next((p[2] for p in children(s, 'property') if p[1] == 'Reference'), '')
def unit_of(n):
    p = n.rsplit('_', 2)
    return int(p[1]) if len(p) == 3 and p[1].isdigit() else 0


def setprop(sym, key, val):
    for p in children(sym, 'property'):
        if p[1] == key:
            p[2] = val
            return


def wire(a, b):
    a, b = (rnd(a[0]), rnd(a[1])), (rnd(b[0]), rnd(b[1]))
    assert a[0] == b[0] or a[1] == b[1], (a, b)
    return node('wire', node('pts', node('xy', *a), node('xy', *b)),
                node('stroke', node('width', 0), node('type', S('default'))),
                node('uuid', uid()))


def label(net, x, y, ang=0):
    return node('label', net, node('at', rnd(x), rnd(y), ang),
                node('effects', node('font', node('size', 1.27, 1.27)),
                     node('justify', S('left'), S('bottom'))), node('uuid', uid()))


d = parse(SCH.read_text(encoding='utf8'))
libs = {s[1]: s for s in children(one(d, 'lib_symbols'), 'symbol')}
syms = children(d, 'symbol')
src_r = next(s for s in syms if refof(s) == 'R11')

tmp = Path(tempfile.mkdtemp())
def export(o):
    subprocess.run([KC, 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
                    '-o', str(o), str(SCH)], capture_output=True, text=True)
    return parse(Path(o).read_text(encoding='utf8'))
def partition(doc):
    r = {}
    for n in children(one(doc, 'nets'), 'net'):
        nm = one(n, 'name')[1]
        for p in children(n, 'node'):
            q = one(p, 'ref')[1]
            if not q.startswith('#'): r[q + '.' + one(p, 'pin')[1]] = nm
    return r

before = partition(export(tmp / 'b.net'))
print('baseline: %d pin endpoints' % len(before))
gone = [s for s in syms if refof(s) in DROP]
print('removing: %s' % sorted(refof(s) for s in gone))
assert {refof(s) for s in gone} == DROP, 'missing one of %s' % DROP

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)

d[:] = [a for a in d if id(a) not in {id(s) for s in gone}]

# --- embed the BQ24075 symbol into the sheet's lib_symbols --------------------
proj_lib = parse((ROOT / 'BalancerREF.kicad_sym').read_text(encoding='utf8'))
bq = deepcopy(next(a for a in proj_lib if tagged(a, 'symbol') and a[1] == 'BQ24075RGT'))
bq[1] = 'BalancerREF:BQ24075RGT'
lnode = one(d, 'lib_symbols')
lnode[:] = [a for a in lnode if not (tagged(a, 'symbol') and a[1] == 'BalancerREF:BQ24075RGT')]
lnode.append(bq)

sheetid = one(d, 'uuid')[1]
PINS = [(13, 'IN', -22.86, 12.7, 0), (1, 'TS', -22.86, 5.08, 0),
        (4, 'CE', -22.86, 0.0, 0), (6, 'EN1', -22.86, -5.08, 0),
        (5, 'EN2', -22.86, -10.16, 0), (15, 'SYSOFF', -22.86, -15.24, 0),
        (12, 'ILIM', 22.86, -15.24, 180), (16, 'ISET', 22.86, -10.16, 180),
        (14, 'TMR', 22.86, -5.08, 180), (10, 'OUT', 22.86, 12.7, 180),
        (11, 'OUT', 22.86, 10.16, 180), (2, 'BAT', 22.86, 5.08, 180),
        (3, 'BAT', 22.86, 2.54, 180), (7, 'PGOOD', 22.86, -2.54, 180),
        (9, 'CHG', 22.86, -7.62, 180), (8, 'VSS', -2.54, -22.86, 90),
        (17, 'EP', 2.54, -22.86, 90)]
NETS = {13: 'USB_VBUS', 1: 'TS', 4: 'GND', 6: 'CHG_EN1', 5: 'CHG_EN2',
        15: 'GND', 12: 'ILIM', 16: 'ISET', 10: 'SYS', 11: 'SYS',
        2: 'BAT', 3: 'BAT', 7: 'PGOOD_N', 9: 'CHG_STAT', 8: 'GND', 17: 'GND'}

ux, uy = U5_AT
inst = node('symbol', node('lib_id', 'BalancerREF:BQ24075RGT'), node('at', ux, uy, 0),
            node('unit', 1), node('in_bom', S('yes')), node('on_board', S('yes')),
            node('dnp', S('no')), node('uuid', uid()))
for num, nm, px, py, ang in PINS:
    inst.append(node('pin', str(num), node('uuid', uid())))
for k, v in [('Reference', 'U5'), ('Value', 'BQ24075RGT'),
             ('Footprint', 'Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.675x1.675mm'),
             ('Datasheet', 'https://www.ti.com/lit/ds/symlink/bq24075.pdf'),
             ('MPN', 'BQ24075RGTR')]:
    inst.append(prop(k, v, ux, uy - 26.67, k not in ('Reference', 'Value')))
inst.append(node('instances', node('project', 'BalancerREF',
            node('path', '/' + sheetid, node('reference', 'U5'), node('unit', 1)))))
d.append(inst)

# stub + label on every pin; TMR is left open on purpose (default safety timers)
for num, nm, px, py, ang in PINS:
    gx, gy = ux + px, uy - py
    a = math.radians(ang)
    dx, dy = -math.cos(a), math.sin(a)
    bx, by = rnd(gx + dx * 7.62), rnd(gy + dy * 7.62)
    if num == 14:
        d.append(node('no_connect', node('at', gx, gy), node('uuid', uid())))
        continue
    d.append(wire((gx, gy), (bx, by)))
    d.append(label(NETS[num], bx, by, 180 if dx < 0 else 0))

# --- support resistors --------------------------------------------------------
def clone_r(ref, val, x, y):
    c = deepcopy(src_r)
    at = one(c, 'at'); at[1], at[2] = x, y
    while len(at) < 4: at.append(0)
    at[3] = 0
    one(c, 'uuid')[1] = uid()
    for p in children(c, 'pin'): one(p, 'uuid')[1] = uid()
    setprop(c, 'Reference', ref); setprop(c, 'Value', val)
    ins = one(c, 'instances')
    one(one(ins, 'project'), 'path')
    one(one(one(ins, 'project'), 'path'), 'reference')[1] = ref
    for p in children(c, 'property'):
        a2 = one(p, 'at')
        if p[1] == 'Reference': a2[1], a2[2] = x + 3.81, y - 1.27
        elif p[1] == 'Value':   a2[1], a2[2] = x + 3.81, y + 1.27
        else:                   a2[1], a2[2] = x, y
    return c

# Column in the verified-clear left band, 10.16 mm pitch. Labels carry the
# connections; nothing here relies on being physically near U5.
# 20.32 mm pitch, NOT 10.16. At 10.16 with labels 5.08 either side of centre, each
# resistor's lower label lands exactly on the next one's upper label and the two nets
# merge - that is how +3V3 got shorted to GND on the first attempt.
RES = [('R3',  '3.57k 1%', RES_X,  71.12,  'ISET',  'GND'),
       ('R35', '1.6k',     RES_X,  91.44,  'ILIM',  'GND'),
       ('R36', '10k',      RES_X, 111.76,  'TS',    'GND'),
       ('R37', '100k',     RES_X, 132.08,  '+3V3',  'PGOOD_N'),
       ('R38', '100k',     RES_X, 152.40,  '+3V3',  'CHG_STAT')]

# Pins that reached /SYS only through D2 or Q3: those wires now dead-end where the
# removed pins were, so the survivors need the net name stated explicitly.
RELABEL = [('SW1', '1', 'SYS'), ('C30', '1', 'SYS')]
for ref, val, x, y, top, bot in RES:
    d.append(clone_r(ref, val, x, y))
    d.append(wire((x, y - 3.81), (x, y - 5.08))); d.append(label(top, x, y - 5.08))
    d.append(wire((x, y + 3.81), (x, y + 5.08))); d.append(label(bot, x, y + 5.08))

# --- re-attach the SYS pins orphaned by D2/Q3 ---------------------------------
def pinpos(sym, num):
    at = one(sym, 'at'); x, y = at[1], at[2]; ang = at[3] if len(at) > 3 else 0
    t = math.radians(ang); c, si = math.cos(t), math.sin(t)
    for sub in children(libs[one(sym, 'lib_id')[1]], 'symbol'):
        if unit_of(sub[1]) not in (0, one(sym, 'unit')[1]): continue
        for p in children(sub, 'pin'):
            if one(p, 'number')[1] == num:
                a = one(p, 'at')
                ar = math.radians(a[3] + ang)
                return ((rnd(x + c * a[1] - si * a[2]), rnd(y - si * a[1] - c * a[2])),
                        (rnd(-math.cos(ar)), rnd(math.sin(ar))))
    raise KeyError(num)

for ref, num, net in RELABEL:
    sym = next(s2 for s2 in children(d, 'symbol') if refof(s2) == ref)
    (px, py), (dx, dy) = pinpos(sym, num)
    bx, by = rnd(px + dx * 5.08), rnd(py + dy * 5.08)
    d.append(wire((px, py), (bx, by)))
    d.append(label(net, bx, by, 180 if dx < 0 else 0))
    print('re-labelled %s.%s -> %s at (%.2f, %.2f)' % (ref, num, net, bx, by))

# --- four GPIOs: clear their no-connects and label them ------------------------
for pad, (net, sgn) in GPIO.items():
    px, py = U1_PINPOS[pad]
    d[:] = [a for a in d if not (tagged(a, 'no_connect')
            and (rnd(one(a, 'at')[1]), rnd(one(a, 'at')[2])) == (px, py))]
    bx = rnd(px + sgn * 10.16)
    d.append(wire((px, py), (bx, py)))
    d.append(label(net, bx, py, 0 if sgn > 0 else 180))

SCH.write_text(dump(d) + '\n', encoding='utf8')

up = ROOT / 'review' / 'unused-pins.json'
nc = json.loads(up.read_text())
for pad in GPIO:
    nc.pop('U1.' + pad, None)
nc['U5.14'] = 'TMR left open: sets the default pre-charge and fast-charge safety timers (SLUS810N Table 7-1)'
up.write_text(json.dumps(nc, indent=2))
print('unused-pins.json: dropped 4 U1 GPIOs, added U5.14 (TMR); %d entries' % len(nc))

after = partition(export(tmp / 'a.net'))
print('\nchanged endpoints:')
for k in sorted(set(after) | set(before)):
    b, a = before.get(k), after.get(k)
    if b != a: print('   %-9s %-26s -> %s' % (k, b, a))
for n in ('/SYS', '/BAT', '/USB_VBUS', '/CHG_EN1', '/CHG_EN2', '/PGOOD_N', '/CHG_STAT',
          '/ISET', '/ILIM', '/TS'):
    g = sorted(k for k, v in after.items() if v == n)
    print('%-11s %s' % (n, ' '.join(g) if g else '(absent)'))
