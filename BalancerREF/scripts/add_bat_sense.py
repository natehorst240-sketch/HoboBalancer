"""Add a BAT sense divider so firmware can tell USB from battery.

SUPPLY_SENSE measures SYS_SW/2, and SYS is fed either from USB through D2 or from the
battery through Q3. Those ranges overlap: a USB port at the low end of spec minus D2's
drop lands near 4.30 V, and a full battery is 4.20 V. With divider tolerance and the
ESP32-S3's ADC error that is not separable, so SUPPLY_SENSE cannot answer "am I on
USB?" - only "what is my supply?".

This adds a second divider on /BAT and a comparison becomes possible:

    SYS_SW ~= BAT           -> running on battery
    SYS_SW  > BAT + ~0.3 V  -> USB present (D2 feeding SYS, Q3 off)

That is a differential test, so it does not depend on absolute ADC accuracy, which is
what makes it work where the single-ended reading does not.

1M/1M rather than the 100k/100k used for SUPPLY_SENSE: this divider hangs directly on
the cell and drains it whenever the puck is switched off. 1M/1M is ~2.1 uA (decades
against a 500 mAh cell) where 100k/100k would be ~21 uA (under three years). The cost
is a 500k source impedance into the ADC - C31 supplies the sampling charge, and
firmware should use a long sample time and multisample.

GPIO4 (module pad 8) is ADC1_CH3 and was unused. ADC1 is preferred over ADC2 - ADC2 is
shared with the radio - and GPIO3 was avoided because it is a strapping pin.

Dry run by default. Pass --apply to write.
"""
import sys, json, math, collections, subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexp_helpers import *

ROOT = HERE.parent
assert ROOT.name == 'BalancerREF', ROOT
APPLY = '--apply' in sys.argv
SCH = ROOT / 'BalancerREF.kicad_sch'
KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'

U1_PIN8 = (421.64, 287.02)      # GPIO4, pin body points left
# Every coordinate here is a multiple of 1.27 mm - KiCad's connection grid. Off-grid
# endpoints raise endpoint_off_grid and can fail to connect at all.
COL = 60.96                     # 48 x 1.27; free column on the sheet
NET = 'BAT_SENSE'


def rnd(v): return round(v, 4)
def refof(s):
    return next((p[2] for p in children(s, 'property') if p[1] == 'Reference'), '')


def setprop(sym, key, val, hide=None):
    for p in children(sym, 'property'):
        if p[1] == key:
            p[2] = val
            if hide is not None:
                p[:] = [a for a in p if not tagged(a, 'hide')]
                if hide:
                    p.append(node('hide', S('yes')))
            return


def clone(src, ref, value, x, y, angle=None):
    """Copy an existing instance so lib_id, pin list and instances block are right.
    The angle MUST be set explicitly: R11 (the donor) sits at rotation 90, so an
    inherited clone is horizontal and vertical wiring misses its pins entirely."""
    c = deepcopy(src)
    at = one(c, 'at')
    at[1] = x
    at[2] = y
    if angle is not None:
        while len(at) < 4:
            at.append(0)
        at[3] = angle
    u = one(c, 'uuid'); u[1] = uid()
    for p in children(c, 'pin'):
        one(p, 'uuid')[1] = uid()
    setprop(c, 'Reference', ref)
    setprop(c, 'Value', value)
    inst = one(c, 'instances')
    if inst:
        prj = one(inst, 'project')
        if prj:
            pth = one(prj, 'path')
            if pth:
                one(pth, 'reference')[1] = ref
    # keep property text next to the part
    for p in children(c, 'property'):
        a = one(p, 'at')
        if p[1] == 'Reference': a[1], a[2] = x + 3.81, y - 1.27
        elif p[1] == 'Value':   a[1], a[2] = x + 3.81, y + 1.27
        else:                   a[1], a[2] = x, y
    return c


def wire(a, b):
    a, b = (rnd(a[0]), rnd(a[1])), (rnd(b[0]), rnd(b[1]))
    assert a[0] == b[0] or a[1] == b[1], (a, b)
    return node('wire', node('pts', node('xy', *a), node('xy', *b)),
                node('stroke', node('width', 0), node('type', S('default'))),
                node('uuid', uid()))


def label(net, x, y, angle=0):
    return node('label', net, node('at', rnd(x), rnd(y), angle),
                node('effects', node('font', node('size', 1.27, 1.27)),
                     node('justify', S('left'), S('bottom'))), node('uuid', uid()))


d = parse(SCH.read_text(encoding='utf8'))
syms = children(d, 'symbol')
src_r = next(s for s in syms if refof(s) == 'R11')
src_c = next(s for s in syms if refof(s) == 'C12')
src_gnd = next(s for s in syms if one(s, 'lib_id')[1] == 'power:GND')

tmp = Path(tempfile.mkdtemp())


def export(out):
    subprocess.run([KC, 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
                    '-o', str(out), str(SCH)], capture_output=True, text=True)
    return parse(Path(out).read_text(encoding='utf8'))


def partition(doc):
    o = {}
    for n in children(one(doc, 'nets'), 'net'):
        nm = one(n, 'name')[1]
        for p in children(n, 'node'):
            r = one(p, 'ref')[1]
            if not r.startswith('#'):
                o[r + '.' + one(p, 'pin')[1]] = nm
    return o


before = partition(export(tmp / 'b.net'))
print('baseline: %d pin endpoints' % len(before))

# --- remove the no-connect on U1 pin 8 ---------------------------------------
ncs = [n for n in children(d, 'no_connect')
       if (rnd(one(n, 'at')[1]), rnd(one(n, 'at')[2])) == U1_PIN8]
print('no_connect on U1.8 (GPIO4): %s' % ('found, removing' if ncs else 'NONE FOUND'))
assert ncs, 'expected a no_connect at U1 pin 8'
d[:] = [a for a in d if id(a) not in {id(n) for n in ncs}]

# --- the divider --------------------------------------------------------------
R33_Y, R34_Y, NODE_Y = 200.66, 220.98, 212.09   # 158, 174, 167 x 1.27
CAP_X, LBL_X = 78.74, 45.72                      # 62, 36 x 1.27
TOP_Y, GND_Y = 187.96, 232.41                    # 148, 183 x 1.27
add = [
    clone(src_r, 'R33', '1M', COL, R33_Y, angle=0),
    clone(src_r, 'R34', '1M', COL, R34_Y, angle=0),
    clone(src_c, 'C31', '100n', CAP_X, R34_Y, angle=0),
    clone(src_gnd, '#PWR801', 'GND', COL, GND_Y),
    clone(src_gnd, '#PWR802', 'GND', CAP_X, GND_Y),
]
wires = [
    wire((COL, TOP_Y), (COL, R33_Y - 3.81)),           # /BAT into R33
    wire((COL, R33_Y + 3.81), (COL, NODE_Y)),          # R33 down to the node
    wire((COL, NODE_Y), (COL, R34_Y - 3.81)),          # node into R34
    wire((COL, R34_Y + 3.81), (COL, GND_Y)),           # R34 to GND
    wire((COL, NODE_Y), (CAP_X, NODE_Y)),              # node across to C31
    wire((CAP_X, NODE_Y), (CAP_X, R34_Y - 3.81)),
    wire((CAP_X, R34_Y + 3.81), (CAP_X, GND_Y)),       # C31 to GND
    wire((LBL_X, NODE_Y), (COL, NODE_Y)),               # node out to its label
    wire(U1_PIN8, (U1_PIN8[0] - 10.16, U1_PIN8[1])),   # U1 pin 8 stub
]
labels = [
    label('BAT', COL, TOP_Y),
    label(NET, LBL_X, NODE_Y),
    label(NET, U1_PIN8[0] - 10.16, U1_PIN8[1], 180),
]
d.extend(wires); d.extend(labels); d.extend(add)
print('added R33 1M, R34 1M, C31 100n, 2 GND, %d wires, %d labels'
      % (len(wires), len(labels)))

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)

SCH.write_text(dump(d) + '\n', encoding='utf8')

# --- drop U1.8 from the documented-unused list --------------------------------
up = ROOT / 'review' / 'unused-pins.json'
nc = json.loads(up.read_text())
if 'U1.8' in nc:
    del nc['U1.8']
    up.write_text(json.dumps(nc, indent=2))
    print('unused-pins.json: removed U1.8 (now BAT_SENSE), %d remain' % len(nc))

after = partition(export(tmp / 'a.net'))
changed = {k: (before.get(k), v) for k, v in after.items() if before.get(k) != v}
gone = [k for k in before if k not in after]
print('\nnets that changed:')
for k, (b, a) in sorted(changed.items()):
    print('   %-8s %s -> %s' % (k, b, a))
print('endpoints lost:', gone or 'none')
grp = sorted(k for k, v in after.items() if v == '/' + NET)
print('/%s now: %s' % (NET, ' '.join(grp)))
