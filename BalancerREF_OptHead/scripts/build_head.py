"""Generate BalancerREF_OptHead - pivoting optical tach head board.

Split out of BalancerREF Rev C on 2026-09-11. D1/PD1 must sit at 90 degrees to the
main PCB, on the second leg of the aluminium L-bracket, on a single pivot bolt so the
emitter can be aimed. Neither part has leads to form: XPEBRD-L1 is a ceramic SMD LED
and BPW34S is Vishay's surface-mount BPW34, so they must sit on their own copper.

Reference designators are deliberately NOT renumbered. DATASHEET-VERIFICATION.md,
PhotoTach-BOM.csv and README.md are all keyed to U8/U4/PD1/Q1/R18-R28 by name, and
renumbering would silently invalidate every recorded pin audit.

The circuit is cut AFTER the comparator, so the cable carries only DC rails and
digital edges. Cutting at the photodiode would put the 10k TIA summing junction
(PD1.2/U8.2/R21.2/C21.1) on a flying lead beside a wire switching 500 mA at 20 kHz.
C20 stays on this board so the fast emitter edges circulate locally and the cable
sees only the ~50 mA average.

Connectivity is the deliverable here, not draughtsmanship; hand layout follows in
KiCad exactly as it did for the main sheet's Rev C.
"""
import sys as _sys
if '--overwrite-hand-layout' not in _sys.argv:
    raise SystemExit(
        'BalancerREF_OptHead.kicad_sch is hand-wired in KiCad (Rev A, A3 sheet): the '
        'generated block labels were replaced with real wires. This generator would '
        'throw that away. Re-run with --overwrite-hand-layout only on purpose.\n'
        'To re-check connectivity after hand edits, do NOT run this - instead export '
        'the netlist and run verify_head.py:\n'
        '  kicad-cli sch export netlist --format kicadsexpr -o review/OptHead.net '
        'BalancerREF_OptHead.kicad_sch\n'
        '  python scripts/verify_head.py')

import sys, math, collections, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'BalancerREF' / 'scripts'))
from sexp_helpers import *          # NOTE: exports its own ROOT (= BalancerREF)
import sexpdata as sx

# Rebind AFTER the star-import, which would otherwise clobber these with the
# parent project's paths and write this board's output into BalancerREF/.
ROOT = HERE.parent
PARENT = ROOT.parent / 'BalancerREF'
assert ROOT.name == 'BalancerREF_OptHead', 'refusing to write outside this project: %s' % ROOT

PROJ = 'BalancerREF_OptHead'
sheetid = '3f2a91c4-5d6e-4b8a-9c17-2e4d8a6b0f35'

used = {}; custom = {}; instances = []; pins = {}; dirs = {}
metadata = {}; wires = []; labels = []; ncs = []; art = []

def rnd(v): return round(v, 4)
def pt(q): return tuple(rnd(v) for v in q)
def getprop(s, k): return next((a[2] for a in children(s, 'property') if a[1] == k), '')

# TS3021 comes from the parent project's verified local library rather than being
# redefined here, so both boards share exactly one pin mapping.
for a in sx.loads((PARENT / 'BalancerREF.kicad_sym').read_text(encoding='utf8')):
    if tagged(a, 'symbol') and a[1] == 'TS3021IYLT':
        custom['TS3021IYLT'] = deepcopy(a)
assert 'TS3021IYLT' in custom, 'TS3021IYLT not found in parent BalancerREF.kicad_sym'


def place(ref, lib, x, y, angle=0, value=None, fp=None, field=None, unit=1):
    if isinstance(lib, str):
        sym = deepcopy(custom[lib]); libid = PROJ + ':' + lib
    else:
        sym = standard(*lib); libid = ':'.join(lib)
    used[libid] = deepcopy(sym)
    inst = node('symbol', node('lib_id', libid), node('at', x, y, angle), node('unit', unit),
                node('in_bom', S('no' if ref.startswith('#') else 'yes')),
                node('on_board', S('no' if ref.startswith('#') else 'yes')),
                node('dnp', S('no')), node('uuid', uid()))
    t = math.radians(angle); c = math.cos(t); s = math.sin(t)
    ys = []

    def unit_of(name):
        parts = name.rsplit('_', 2)
        return int(parts[1]) if len(parts) == 3 and parts[1].isdigit() else 0

    mine = [sub for sub in children(sym, 'symbol') if unit_of(sub[1]) in (0, unit)]
    for sub in children(sym, 'symbol'):
        for pin in children(sub, 'pin'):
            at = one(pin, 'at'); num = one(pin, 'number')[1]
            if sub in mine:
                pos = pt((x + c * at[1] - s * at[2], y - s * at[1] - c * at[2]))
                pins[ref, num] = pos
                a = math.radians(at[3] + angle)
                dirs[ref, num] = pt((-math.cos(a), math.sin(a)))
                ys.append(pos[1])
            inst.append(node('pin', num, node('uuid', uid())))
    for k, v in [('Reference', ref),
                 ('Value', value if value is not None else getprop(sym, 'Value')),
                 ('Footprint', fp if fp is not None else getprop(sym, 'Footprint')),
                 ('Datasheet', getprop(sym, 'Datasheet')),
                 ('MPN', value or getprop(sym, 'Value'))]:
        ispass = ref.startswith(('R', 'C')) and not ref.startswith('LED')
        if field: fx, fy = field
        elif ispass and angle == 0: fx, fy = x + 3.81, y - 1.27
        else: fx, fy = x, min(ys or [y]) - 5.08
        pr = prop(k, v, fx, fy + (2.54 if k == 'Value' else 0),
                  k not in ('Reference', 'Value') or ref.startswith('#'))
        if ispass and angle == 0 and not field and k in ('Reference', 'Value'):
            one(pr, 'effects').append(node('justify', S('left')))
        if angle in [90, 270]: one(pr, 'at')[3] = 90
        inst.append(pr)
    inst.append(node('instances', node('project', PROJ,
                node('path', '/' + sheetid, node('reference', ref), node('unit', unit)))))
    instances.append(inst)
    metadata[ref] = {'lib_id': libid, 'value': value or getprop(sym, 'Value'),
                     'footprint': fp or getprop(sym, 'Footprint')}
    return ref


def p(r, n): return pins[r, str(n)]


def wire(*points):
    for a, b in zip(points, points[1:]):
        a, b = pt(a), pt(b)
        if a == b: continue
        assert a[0] == b[0] or a[1] == b[1], ('non-orthogonal', a, b)
        wires.append((a, b))


# Every connection below is expressed between REAL pin coordinates. Nothing routes
# to a guessed waypoint, which is what silently left pins floating on the first pass.
def star(target, *pinrefs):
    """Join each named pin to a common point by a vertical-then-horizontal dogleg."""
    target = pt(target)
    for r, n in pinrefs:
        a = p(r, n)
        wire(a, (a[0], target[1]), target)


def joinv(r1, n1, r2, n2):
    """Two pins sharing a column, or joined by a horizontal jog at the midpoint."""
    a, b = p(r1, n1), p(r2, n2)
    if a[0] == b[0] or a[1] == b[1]:
        wire(a, b)
    else:
        wire(a, (a[0], b[1]), b)


def label(net, x, y, angle=0):
    labels.append(node('label', net, node('at', x, y, angle),
                  node('effects', node('font', node('size', 1.27, 1.27)),
                       node('justify', S('left'), S('bottom'))), node('uuid', uid())))


def port(r, n, net, length=7.62):
    a = p(r, n); d = dirs[r, str(n)]
    b = pt((a[0] + d[0] * length, a[1] + d[1] * length))
    wire(a, b); label(net, *b, 0 if d[0] >= 0 else 180); return b


def text(t, x, y, size=1.5):
    art.append(node('text', t, node('at', x, y, 0),
               node('effects', node('font', node('size', size, size)),
                    node('justify', S('left'), S('top'))), node('uuid', uid())))


def box(title, x, y, w, h):
    art.append(node('rectangle', node('start', x, y), node('end', x + w, y + h),
               node('stroke', node('width', 0.254), node('type', S('default'))),
               node('fill', node('type', S('none'))), node('uuid', uid())))
    text(title, x + 3.81, y + 3.81, 2.1)


gcount = [0]; fcount = [0]


def gnd_at(x, y):
    gcount[0] += 1
    place('#PWR' + str(gcount[0]).zfill(3), ('power', 'GND'), x, y)


def to_gnd(r, n, y):
    a = p(r, n); wire(a, (a[0], y)); gnd_at(a[0], y)


def flagnet(netname, x, y):
    """PWR_FLAG so ERC knows this rail is externally driven through the cable."""
    fcount[0] += 1
    place('#FLG' + str(fcount[0]).zfill(3), ('power', 'PWR_FLAG'), x, y)
    wire((x, y), (x, y + 10.16)); label(netname, x, y + 10.16)


def flagnd(x, y):
    """GND is driven from the main board through the cable, same as the rails."""
    fcount[0] += 1
    place('#FLG' + str(fcount[0]).zfill(3), ('power', 'PWR_FLAG'), x, y)
    wire((x, y), (x, y + 10.16)); gnd_at(x, y + 10.16)


def net(name, *pinrefs):
    """Tie pins by label. Each stub leaves along its own pin direction, so it can
    never cross the symbol body and short a two-terminal part against itself -
    which a column-routed dogleg silently does (R32 through R28's pins)."""
    for r, n in pinrefs:
        port(r, n, name)


def R(val, x, y, ref, fp='Resistor_SMD:R_0603_1608Metric'):
    return place(ref, ('Device', 'R'), x, y, 0, val, fp)


def C(val, x, y, ref, fp='Capacitor_SMD:C_0805_2012Metric'):
    return place(ref, ('Device', 'C'), x, y, 0, val, fp)


# ---------------------------------------------------------------- blocks
box('PULSED EMITTER - 20 kHz / 5 us / ~500 mA', 10.16, 20.32, 121.92, 116.84)
box('TRANSIMPEDANCE + x12 AC GAIN', 142.24, 20.32, 152.4, 116.84)
box('1.65 V REFERENCE', 142.24, 154.94, 152.4, 76.2)
box('THRESHOLD COMPARATOR + HYSTERESIS', 304.8, 20.32, 106.68, 116.84)
box('CABLE TO MAIN BOARD', 304.8, 154.94, 106.68, 76.2)

# --- Emitter. C20 is the local reservoir: the 500 mA edges must circulate here,
# not down the cable, or they land on the shared return beside OPT_COMP.
C('100u / 6.3V', 33.02, 60.96, 'C20', 'Capacitor_SMD:C_1210_3225Metric')
R('3R0 1206 0.5W', 60.96, 55.88, 'R18', 'Resistor_SMD:R_1206_3216Metric')
net('SYS_SW', ('C20', 1), ('R18', 1))
to_gnd('C20', 2, 93.98)

place('D1', ('Device', 'LED'), 60.96, 83.82, 90, 'XPEBRD-L1 625nm', 'LED_SMD:LED_Cree-XP',
      field=(66.04, 76.2))
joinv('R18', 2, 'D1', 2)
place('Q1', ('Transistor_FET', 'AO3400A'), 76.2, 109.22, 0, 'AO3400A',
      'Package_TO_SOT_SMD:SOT-23', field=(83.82, 99.06))
joinv('D1', 1, 'Q1', 3)
to_gnd('Q1', 2, 127)
R('100R', 38.1, 109.22, 'R19')
R('100k', 55.88, 121.92, 'R20')
net('MOS_GATE', ('Q1', 1), ('R19', 1), ('R20', 1))
port('R19', 2, 'OPT_LED_EN')
to_gnd('R20', 2, 134.62)
text('Emitter loop is local: C20 supplies the 5 us / 500 mA pulse so the cable carries\n'
     'only the ~50 mA average. R19 damps the gate edge; R20 holds Q1 off while the main\n'
     'board is unpowered or the cable is unplugged.', 13.97, 124.46, 1.1)

# --- Photodiode and TIA. PD1 is reverse-biased; U8A holds its anode at OPT_VREF,
# so the photocurrent is forced through R21 rather than developing across PD1.
place('PD1', ('Sensor_Optical', 'BPW34'), 165.1, 45.72, 0, 'BPW34S',
      'OptoDevice:Osram_BPW34S-SMD', field=(170.18, 38.1))
place('U8', ('Amplifier_Operational', 'TLV9062xD'), 205.74, 78.74, 0, 'TLV9062IDR',
      'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm', field=(200.66, 93.98), unit=1)
R('10k', 187.96, 55.88, 'R21')
C('10p C0G', 175.26, 55.88, 'C21')
port('PD1', 1, '+3V3')
# PD_TIA_IN: the summing junction - PD1 anode, U8A inverting input, both feedback returns.
net('PD_TIA_IN', ('PD1', 2), ('U8', 2), ('R21', 2), ('C21', 1))
C('10n', 237.49, 60.96, 'C22')
net('TIA_OUT', ('U8', 1), ('R21', 1), ('C21', 2), ('C22', 1))
port('U8', 3, 'OPT_VREF')

# --- x12 inverting AC stage. R22 pin 2 sits on the coupling cap and pin 1 on the
# summing node, per the Rev C spec groups; reversing it would divide against R23.
R('10k', 237.49, 93.98, 'R22')
R('120k', 260.35, 55.88, 'R23')
place('U8', ('Amplifier_Operational', 'TLV9062xD'), 274.32, 78.74, 0, 'TLV9062IDR',
      'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm', field=(269.24, 93.98), unit=2)
net('AC_COUPLED', ('C22', 2), ('R22', 2))
net('AMP_INV', ('R22', 1), ('R23', 2), ('U8', 6))
net('OPT_AMP', ('U8', 7), ('R23', 1))
port('U8', 5, 'OPT_VREF')

# --- U8 power unit and its local decoupling.
place('U8', ('Amplifier_Operational', 'TLV9062xD'), 165.1, 190.5, 0, 'TLV9062IDR',
      'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm', field=(160.02, 205.74), unit=3)
port('U8', 8, '+3V3')
to_gnd('U8', 4, 215.9)
C('100n', 187.96, 190.5, 'C24')
port('C24', 1, '+3V3')
to_gnd('C24', 2, 215.9)

# --- 1.65 V reference: a divider, not a regulator. Both U8 halves sit on it.
R('10k', 226.06, 177.8, 'R24')
R('10k', 226.06, 205.74, 'R25')
C('100n', 248.92, 205.74, 'C23')
port('R24', 1, '+3V3')
net('OPT_VREF', ('R24', 2), ('R25', 1), ('C23', 1))
to_gnd('R25', 2, 220.98)
to_gnd('C23', 2, 220.98)

# --- Comparator. R28 sits on U4's own output, upstream of R32, so the hysteresis
# senses the real output rather than the far side of the series damping.
place('U4', 'TS3021IYLT', 344.17, 66.04, 0, 'TS3021IYLT',
      'Package_TO_SOT_SMD:SOT-23-5', field=(339.09, 83.82))
R('22k', 316.23, 38.1, 'R26')
R('10k', 316.23, 71.12, 'R27')
R('470k', 367.03, 38.1, 'R28')
R('33R', 367.03, 104.14, 'R32')
C('100n', 400.05, 71.12, 'C25')
port('U4', 4, 'OPT_AMP')
port('U4', 5, '+3V3')
to_gnd('U4', 2, 96.52)
port('R26', 1, '+3V3')
net('CMP_THRESHOLD', ('R26', 2), ('R27', 1), ('U4', 3), ('R28', 2))
to_gnd('R27', 2, 88.9)
# R28 stays on U4's own output, upstream of R32, so hysteresis senses the real
# output rather than the far side of the series damping.
net('CMP_OUT', ('U4', 1), ('R28', 1), ('R32', 1))
port('R32', 2, 'OPT_COMP')
port('C25', 1, '+3V3')
to_gnd('C25', 2, 88.9)

# --- Cable connector. Grounds are interleaved between the two digital lines:
# OPT_LED_EN crosstalk onto OPT_COMP arrives inside the synchronous gating window
# by definition, so U9 on the main board structurally cannot reject it.
place('J5', ('Connector_Generic', 'Conn_01x07'), 360.68, 194.31, 180,
      'TO MAIN BOARD',
      'Connector_JST:JST_GH_SM07B-GHS-TB_1x07-1MP_P1.25mm_Horizontal',
      field=(350.52, 165.1))
for n, net in [(1, 'SYS_SW'), (3, 'OPT_LED_EN'), (5, 'OPT_COMP'), (7, '+3V3')]:
    port('J5', n, net)
for n in (2, 4, 6):
    a = p('J5', n)
    wire(a, (a[0] + 10.16, a[1]))
    gnd_at(a[0] + 10.16, a[1])

# Everything arrives through the cable; without flags ERC sees undriven power inputs.
flagnet('+3V3', 316.23, 215.9)
flagnet('SYS_SW', 334.01, 215.9)
flagnd(351.79, 215.9)

text('Ground sits between OPT_LED_EN and OPT_COMP. Emitter-pulse crosstalk onto\n'
     'OPT_COMP lands inside the synchronous gating window and would be accepted as a\n'
     'genuine hit, so it must be stopped here, not filtered downstream. Use a latching,\n'
     'gold-plated JST series with secondary retention: tin friction contacts fret under\n'
     'sustained vibration and fail intermittently rather than cleanly.',
     306.07, 232.41, 1.1)

text('BalancerREF_OptHead - optical tach head, at 90 degrees to the main PCB on the\n'
     'aluminium L-bracket. One pivot bolt aims the emitter; add a second fastener (arc\n'
     'slot or serrated lock nut) or it drifts under vibration and loses RPM lock. The\n'
     'baffle between D1 and PD1 and the red acrylic window belong to this board.\n'
     'Designators match BalancerREF Rev C so the existing pin audits stay valid.',
     13.97, 243.84, 1.4)

# ---------------------------------------------------------------- assemble
points = set(pins.values()) | {q for seg in wires for q in seg}


def on(q, a, b):
    return ((a[0] == b[0] == q[0] and min(a[1], b[1]) <= q[1] <= max(a[1], b[1])) or
            (a[1] == b[1] == q[1] and min(a[0], b[0]) <= q[0] <= max(a[0], b[0])))


segments = set()
for a, b in wires:
    split = sorted([q for q in points if on(q, a, b)])
    for q, r in zip(split, split[1:]):
        segments.add(tuple(sorted((q, r))))
degree = collections.Counter(q for seg in segments for q in seg)
wire_nodes = [node('wire', node('pts', node('xy', *a), node('xy', *b)),
              node('stroke', node('width', 0), node('type', S('default'))),
              node('uuid', uid())) for a, b in sorted(segments)]
junc = [node('junction', node('at', *q), node('diameter', 0), node('color', 0, 0, 0, 0),
        node('uuid', uid())) for q, d in degree.items() if d >= 3]
embedded = []
for libid, sym in used.items():
    ss = deepcopy(sym); ss[1] = libid; embedded.append(ss)

sch = node('kicad_sch', node('version', 20250114), node('generator', 'eeschema'),
           node('generator_version', '10.0'),
           node('uuid', sheetid), node('paper', 'A3'),
           node('title_block',
                node('title', 'BalancerREF_OptHead - pivoting optical tach head'),
                node('date', '2026-09-11'), node('rev', 'A'),
                node('company', 'Split from BalancerREF Rev C - human review required'),
                node('comment', 1, 'Cable carries DC rails and digital edges only')),
           node('lib_symbols', *embedded), *junc, *ncs, *wire_nodes, *labels, *art,
           *instances,
           # Without this the per-symbol instance paths have no root sheet to
           # resolve against and kicad-cli reports annotation errors.
           node('sheet_instances', node('path', '/', node('page', '1'))),
           node('embedded_fonts', S('no')))

(ROOT / (PROJ + '.kicad_sch')).write_text(dump(sch) + '\n', encoding='utf8')
(ROOT / (PROJ + '.kicad_sym')).write_text(
    dump(node('kicad_symbol_lib', node('version', 20241209),
              node('generator', 'kicad_symbol_editor'), *custom.values())) + '\n',
    encoding='utf8')
(ROOT / 'sym-lib-table').write_text(
    '(sym_lib_table (version 7) (lib (name "%s")(type "KiCad")'
    '(uri "${KIPRJMOD}/%s.kicad_sym")(options "")(descr "Shared with BalancerREF")))\n'
    % (PROJ, PROJ))
(ROOT / 'review' / 'component-manifest.json').write_text(json.dumps(metadata, indent=2))
print('Wrote %d symbols, %d wires, %d junctions' % (len(instances), len(segments), len(junc)))
