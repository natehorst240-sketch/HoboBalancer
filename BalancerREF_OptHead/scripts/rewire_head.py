"""Re-draw BalancerREF_OptHead.kicad_sch with real wires in signal-chain order.

The generated sheet (build_head.py) and the hand pass after it tied most nets with
labelled 7.62 mm stubs. This script keeps every component symbol - same UUIDs, values,
footprints and hidden fields, so the PCB stays linked - and lays them out left to right
along the signal path, then draws point-to-point wires between the pins:

    SYS_SW > C20/R18 > D1 > Q1                     (emitter, gated by OPT_LED_EN)
    PD1 > U8A TIA (R21||C21) > C22 > R22 > U8B x12 (R23) > U4 comparator (R26/R27/R28)
        > R32 > J5

One net label stays on each wired net so the net names the PCB already carries
(/PD_TIA_IN, /TIA_OUT, ...) do not change. Labels are still used for the rails that
fan out across the sheet (+3V3, SYS_SW, GND via power symbols) and for OPT_LED_EN,
which starts at the connector and has to reach the far left of the sheet.

Only power symbols (#PWR/#FLG) are recreated; they have no pads.

Verify afterwards exactly as build_head.py says:
    kicad-cli sch export netlist --format kicadsexpr -o review/OptHead.net BalancerREF_OptHead.kicad_sch
    python scripts/verify_head.py
"""
import sys, math, collections, shutil, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'BalancerREF' / 'scripts'))
from sexp_helpers import *

ROOT = HERE.parent
assert ROOT.name == 'BalancerREF_OptHead', ROOT
SCH = ROOT / 'BalancerREF_OptHead.kicad_sch'

d = parse(SCH.read_text(encoding='utf8'))


def rnd(v): return round(float(v), 4)
def pt(q): return tuple(rnd(v) for v in q)
def refof(s): return next(p[2] for p in children(s, 'property') if p[1] == 'Reference')
def unitof(s): return int(one(s, 'unit')[1])


# ------------------------------------------------------------------ library pins
libpins = {}          # lib_id -> [(unit, number, ax, ay)]
for sym in children(one(d, 'lib_symbols'), 'symbol'):
    out = []
    for sub in children(sym, 'symbol'):
        parts = sub[1].rsplit('_', 2)
        unit = int(parts[1]) if len(parts) == 3 and parts[1].isdigit() else 0
        for pin in children(sub, 'pin'):
            at = one(pin, 'at')
            out.append((unit, str(one(pin, 'number')[1]), float(at[1]), float(at[2])))
    libpins[str(sym[1])] = out


def transform(x, y, angle, mirror, ax, ay):
    if mirror == 'x':
        ay = -ay
    t = math.radians(angle); c = math.cos(t); s = math.sin(t)
    return pt((x + c * ax - s * ay, y - s * ax - c * ay))


# ------------------------------------------------------------------ placement
# ref/unit -> (x, y, angle, mirror, (ref_x, ref_y, justify))
# Passives with angle 0 read pin1 top / pin2 bottom; angle 270 reads pin2 LEFT /
# pin1 RIGHT; angle 90 reads pin1 LEFT / pin2 RIGHT.  Op-amps are mirrored about X so
# the inverting input sits on the signal line at the top and the reference feed below.
L = 'left'; C_ = None; R_ = 'right'
PLACE = {
    # emitter
    ('C20', 1): (55.88, 73.66, 0, None, (58.42, 72.39, L)),
    ('R18', 1): (76.20, 78.74, 0, None, (78.74, 77.47, L)),
    ('D1', 1):  (76.20, 91.44, 90, None, (80.01, 90.17, R_)),
    ('Q1', 1):  (73.66, 109.22, 0, None, (80.01, 107.95, L)),
    ('R19', 1): (55.88, 109.22, 270, None, (55.88, 106.68, C_)),
    ('R20', 1): (63.50, 116.84, 0, None, (66.04, 115.57, L)),
    # detector + TIA
    ('PD1', 1): (127.00, 99.06, 270, None, (131.45, 97.79, L)),
    ('U8', 1):  (165.10, 91.44, 0, 'x', (165.10, 83.82, C_)),
    ('R21', 1): (165.10, 76.20, 270, None, (165.10, 73.66, C_)),
    ('C21', 1): (165.10, 66.04, 90, None, (165.10, 63.50, C_)),
    # AC gain
    ('C22', 1): (203.20, 91.44, 90, None, (203.20, 88.90, C_)),
    ('R22', 1): (228.60, 91.44, 270, None, (228.60, 88.90, C_)),
    ('U8', 2):  (248.92, 93.98, 0, 'x', (248.92, 86.36, C_)),
    ('R23', 1): (248.92, 78.74, 270, None, (248.92, 76.20, C_)),
    # 1.65 V reference, hung under the two amplifiers on the OPT_VREF rail
    ('R25', 1): (223.52, 114.30, 0, None, (226.06, 113.03, L)),
    ('C23', 1): (233.68, 114.30, 0, None, (236.22, 113.03, L)),
    ('R24', 1): (243.84, 106.68, 270, None, (243.84, 104.14, C_)),
    # comparator
    ('R26', 1): (287.02, 55.88, 0, None, (289.56, 54.61, L)),
    ('R27', 1): (279.40, 71.12, 0, None, (276.86, 69.85, R_)),
    ('R28', 1): (303.53, 71.12, 270, None, (303.53, 68.58, C_)),
    ('U4', 1):  (304.80, 93.98, 0, None, (309.88, 101.60, L)),
    ('R32', 1): (327.66, 93.98, 90, None, (327.66, 91.44, C_)),
    # cable
    ('C25', 1): (350.52, 106.68, 0, None, (353.06, 105.41, L)),
    ('J5', 1):  (365.76, 91.44, 0, None, (365.76, 76.20, C_)),
    # supply
    ('U8', 3):  (76.20, 165.10, 0, None, (81.28, 163.83, L)),
    ('C24', 1): (101.60, 165.10, 0, None, (104.14, 163.83, L)),
}

pins = {}
comps = [s for s in children(d, 'symbol') if not refof(s).startswith('#')]
seen = set()
for s in comps:
    key = (refof(s), unitof(s))
    assert key in PLACE, 'no placement for %s' % (key,)
    seen.add(key)
    x, y, angle, mirror, (fx, fy, just) = PLACE[key]
    at = one(s, 'at'); at[1], at[2], at[3] = x, y, angle
    # (mirror x) sits right after (at ...)
    s[:] = [a for a in s if not tagged(a, 'mirror')]
    if mirror:
        s.insert(s.index(at) + 1, node('mirror', S(mirror)))
    # KiCad adds the symbol rotation to a field's stored angle, so fields on a
    # 90/270 part need 90 stored to render horizontally.
    ta = 90 if angle in (90, 270) else 0
    for p in children(s, 'property'):
        pa = one(p, 'at')
        if p[1] == 'Reference':
            pa[1], pa[2], pa[3] = fx, fy, ta
        elif p[1] == 'Value':
            # a horizontal passive has its reference above the body, so the value
            # goes the same distance below it
            gap = (y - fy) * 2 if (ta and just is None) else 2.54
            pa[1], pa[2], pa[3] = fx, fy + gap, ta
        elif p[1] == 'Description':
            pa[1], pa[2], pa[3] = x, y, ta
        else:
            pa[1], pa[2], pa[3] = fx, fy, ta
        if p[1] in ('Reference', 'Value'):
            eff = one(p, 'effects')
            eff[:] = [a for a in eff if not tagged(a, 'justify')]
            if just:
                eff.append(node('justify', S(just)))
    libid = str(one(s, 'lib_id')[1])
    for unit, num, ax, ay in libpins[libid]:
        if unit in (0, unitof(s)):
            pins[key[0], num] = transform(x, y, angle, mirror, ax, ay)
assert seen == set(PLACE), 'placements without a symbol: %s' % (set(PLACE) - seen)


def p(r, n): return pins[r, str(n)]


# ------------------------------------------------------------------ drawing
wires = []; labels = []; art = []; power = []


def wire(*points):
    for a, b in zip(points, points[1:]):
        a, b = pt(a), pt(b)
        if a == b: continue
        assert a[0] == b[0] or a[1] == b[1], ('non-orthogonal', a, b)
        wires.append((a, b))


def label(net, x, y, angle=0):
    labels.append(node('label', net, node('at', rnd(x), rnd(y), angle),
                  node('effects', node('font', node('size', 1.27, 1.27)),
                       node('justify', S('left'), S('bottom'))), node('uuid', uid())))


def text(t, x, y, size=1.5):
    art.append(node('text', t, node('at', x, y, 0),
               node('effects', node('font', node('size', size, size)),
                    node('justify', S('left'), S('top'))), node('uuid', uid())))


templates = {}
for s in children(d, 'symbol'):
    if refof(s).startswith('#'):
        templates.setdefault(str(one(s, 'lib_id')[1]), deepcopy(s))
count = collections.Counter()


def powersym(libid, prefix, x, y, angle=0):
    count[prefix] += 1
    ref = '%s%03d' % (prefix, count[prefix])
    s = deepcopy(templates[libid])
    at = one(s, 'at'); at[1], at[2], at[3] = rnd(x), rnd(y), angle
    one(s, 'uuid')[1] = uid()
    for pin in children(s, 'pin'):
        one(pin, 'uuid')[1] = uid()
    for pr in children(s, 'property'):
        pa = one(pr, 'at')
        if pr[1] == 'Reference':
            pr[2] = ref; pa[1], pa[2] = rnd(x), rnd(y - 5.08)
        elif pr[1] == 'Value':
            pa[1], pa[2] = rnd(x), rnd(y - 2.54)
        else:
            pa[1], pa[2] = rnd(x), rnd(y)
        pa[3] = 0
    one(one(one(one(s, 'instances'), 'project'), 'path'), 'reference')[1] = ref
    power.append(s)
    pins[ref, '1'] = pt((x, y))


def gnd(x, y, angle=0): powersym('power:GND', '#PWR', x, y, angle)
def flag(x, y): powersym('power:PWR_FLAG', '#FLG', x, y)


def to_gnd(r, n, y):
    a = p(r, n); wire(a, (a[0], y)); gnd(a[0], y)


# ---- emitter: SYS_SW > R18 > D1 > Q1 drain, C20 as the local reservoir
wire(p('R18', 1), (76.20, 60.96)); label('SYS_SW', 76.20, 60.96)
wire((76.20, 66.04), (55.88, 66.04), p('C20', 1))
to_gnd('C20', 2, 86.36)
wire(p('R18', 2), p('D1', 2))                    # anode
wire(p('D1', 1), p('Q1', 3))                     # cathode > drain
to_gnd('Q1', 2, 127.00)
wire(p('R19', 1), p('Q1', 1))                    # gate
label('MOS_GATE', 60.96, 109.22, 90)
wire((63.50, 109.22), p('R20', 1))
to_gnd('R20', 2, 127.00)
wire(p('R19', 2), (43.18, 109.22)); label('OPT_LED_EN', 43.18, 109.22, 180)

# ---- detector > TIA. Cathode on the summing node, anode to ground (Rev B).
wire(p('PD1', 1), (127.00, 88.90), p('U8', 2))
label('PD_TIA_IN', 129.54, 88.90)
to_gnd('PD1', 2, 109.22)
XL, XR = 144.78, 185.42                          # feedback risers
wire((XL, 88.90), (XL, 66.04), p('C21', 1))
wire((XL, 76.20), p('R21', 2))
wire(p('U8', 1), (XR, 91.44), (XR, 66.04), p('C21', 2))
wire((XR, 76.20), p('R21', 1))
# OPT_VREF rail under the amplifiers: U8A+, U8B+, and the divider tap
wire(p('U8', 3), (151.13, 93.98), (151.13, 106.68), p('R24', 2))
label('OPT_VREF', 172.72, 106.68)

# ---- AC coupling > x12 inverting stage
wire((XR, 91.44), p('C22', 1)); label('TIA_OUT', 187.96, 91.44)
wire(p('C22', 2), p('R22', 2)); label('AC_COUPLED', 209.55, 91.44)
XL2, XR2 = 236.22, 262.89
wire(p('R22', 1), p('U8', 6)); label('AMP_INV', XL2, 86.36, 90)
wire((XL2, 91.44), (XL2, 78.74), p('R23', 2))
wire(p('U8', 7), (XR2, 93.98), (XR2, 78.74), p('R23', 1))
wire(p('U8', 5), (238.76, 96.52), (238.76, 106.68))

# ---- 1.65 V reference divider hangs off the rail
wire((223.52, 106.68), p('R25', 1)); to_gnd('R25', 2, 124.46)
wire((233.68, 106.68), p('C23', 1)); to_gnd('C23', 2, 124.46)
wire(p('R24', 1), (252.73, 106.68)); label('+3V3', 252.73, 106.68)

# ---- comparator: OPT_AMP on IN-, divider + hysteresis on IN+
wire((XR2, 93.98), (292.10, 93.98), (292.10, 96.52), p('U4', 4))
label('OPT_AMP', 267.97, 93.98)
wire(p('R26', 1), (287.02, 48.26)); label('+3V3', 287.02, 48.26)
wire(p('R26', 2), (287.02, 91.44), p('U4', 3))
label('CMP_THRESHOLD', 287.02, 83.82, 90)
wire((287.02, 63.50), (279.40, 63.50), p('R27', 1)); to_gnd('R27', 2, 81.28)
wire((287.02, 71.12), p('R28', 2))
XO = 320.04
wire(p('R28', 1), (XO, 71.12), (XO, 93.98))
wire(p('U4', 1), (XO, 93.98), p('R32', 1)); label('CMP_OUT', XO, 86.36, 90)
wire(p('U4', 5), (302.26, 81.28)); label('+3V3', 302.26, 81.28)
to_gnd('U4', 2, 109.22)

# ---- cable. GND interleaved between the two digital lines.
wire(p('R32', 2), p('J5', 5)); label('OPT_COMP', 340.36, 93.98)
wire(p('J5', 1), (345.44, 83.82)); label('SYS_SW', 345.44, 83.82, 180)
wire(p('J5', 3), (345.44, 88.90)); label('OPT_LED_EN', 345.44, 88.90, 180)
wire(p('J5', 7), (345.44, 99.06)); label('+3V3', 345.44, 99.06, 180)
for n in (2, 4, 6):
    a = p('J5', n); gnd(a[0], a[1], 270)         # lies along the pin, pointing left
wire(p('C25', 1), (350.52, 99.06)); to_gnd('C25', 2, 116.84)

# ---- supply unit + ERC flags for the rails that arrive through the cable
wire(p('U8', 8), (76.20, 152.40), (101.60, 152.40), p('C24', 1))
label('+3V3', 86.36, 152.40)
to_gnd('U8', 4, 180.34); to_gnd('C24', 2, 180.34)
for x, net in [(127.00, '+3V3'), (147.32, 'SYS_SW'), (167.64, None)]:
    flag(x, 160.02); wire((x, 160.02), (x, 170.18))
    if net: label(net, x, 170.18)
    else: gnd(x, 170.18)

# ---- annotation
text('PULSED EMITTER - 20 kHz / 5 us / ~500 mA', 30.48, 45.72, 2.1)
text('DETECTOR > TRANSIMPEDANCE > x12 AC GAIN', 118.11, 45.72, 2.1)
text('THRESHOLD COMPARATOR + HYSTERESIS', 269.24, 38.10, 2.1)
text('CABLE TO MAIN BOARD', 340.36, 66.04, 2.1)
text('1.65 V REFERENCE', 215.90, 130.81, 2.1)
text('SUPPLY + ERC FLAGS', 30.48, 147.32, 2.1)
text('Signal flows left to right: emitter, detector, gain, comparator, cable.', 30.48, 52.07, 1.3)
text('Emitter loop is local: C20 supplies the 5 us / 500 mA pulse so the cable carries\n'
     'only the ~50 mA average. R19 damps the gate edge; R20 holds Q1 off while the main\n'
     'board is unpowered or the cable is unplugged.', 30.48, 132.08, 1.1)
text('PD1 cathode on the summing node, anode to GND (Rev B): photocurrent is pulled OUT\n'
     'of the node, so TIA_OUT rises, OPT_AMP falls and the comparator can cross 1.016 V.\n'
     'Reversed, U4 never trips.', 118.11, 116.84, 1.1)
text('R28 senses U4\'s own output, upstream of the R32 series damping.', 269.24, 116.84, 1.1)
text('Ground sits between OPT_LED_EN and OPT_COMP. Emitter-pulse crosstalk onto\n'
     'OPT_COMP lands inside the synchronous gating window and would be accepted as a\n'
     'genuine hit, so it must be stopped here, not filtered downstream. Use a latching,\n'
     'gold-plated JST series with secondary retention: tin friction contacts fret under\n'
     'sustained vibration and fail intermittently rather than cleanly.',
     269.24, 127.00, 1.1)
text('BalancerREF_OptHead - optical tach head, at 90 degrees to the main PCB on the\n'
     'aluminium L-bracket. One pivot bolt aims the emitter; add a second fastener (arc\n'
     'slot or serrated lock nut) or it drifts under vibration and loses RPM lock. The\n'
     'baffle between D1 and PD1 and the red acrylic window belong to this board.\n'
     'Designators match BalancerREF Rev C so the existing pin audits stay valid.',
     30.48, 205.74, 1.4)

# ------------------------------------------------------------------ segments + junctions
points = set(pins.values()) | {q for seg in wires for q in seg}


def on(q, a, b):
    return ((a[0] == b[0] == q[0] and min(a[1], b[1]) <= q[1] <= max(a[1], b[1])) or
            (a[1] == b[1] == q[1] and min(a[0], b[0]) <= q[0] <= max(a[0], b[0])))


segments = set()
for a, b in wires:
    split = sorted(q for q in points if on(q, a, b))
    for q, r in zip(split, split[1:]):
        segments.add(tuple(sorted((q, r))))
degree = collections.Counter(q for seg in segments for q in seg)
for net_label in labels:
    at = one(net_label, 'at'); q = (rnd(at[1]), rnd(at[2]))
    assert any(on(q, a, b) for a, b in segments), 'label %s off-wire at %s' % (net_label[1], q)
# every component pin must have a wire on it
powered = {q for (r, n), q in pins.items() if r.startswith('#')}
for (r, n), q in pins.items():
    if not r.startswith('#'):
        assert degree[q] >= 1 or q in powered, 'pin %s.%s at %s is floating' % (r, n, q)
wire_nodes = [node('wire', node('pts', node('xy', *a), node('xy', *b)),
              node('stroke', node('width', 0), node('type', S('default'))),
              node('uuid', uid())) for a, b in sorted(segments)]
junc = [node('junction', node('at', *q), node('diameter', 0), node('color', 0, 0, 0, 0),
        node('uuid', uid())) for q, deg in degree.items() if deg >= 3]

# ------------------------------------------------------------------ assemble
DROP = {'junction', 'no_connect', 'wire', 'label', 'global_label', 'text', 'rectangle'}
keep = []
for a in d:
    if tagged(a, 'symbol') and refof(a).startswith('#'):
        continue
    if isinstance(a, list) and str(a[0]) in DROP:
        continue
    keep.append(a)
tail = [a for a in keep if tagged(a, 'sheet_instances') or tagged(a, 'embedded_fonts')]
head = [a for a in keep if a not in tail and not tagged(a, 'symbol')]
syms = [a for a in keep if tagged(a, 'symbol')]
d[:] = head + junc + wire_nodes + labels + art + syms + power + tail

stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
backup = ROOT / 'BalancerREF_OptHead-backups' / ('BalancerREF_OptHead-%s-pre-rewire.kicad_sch' % stamp)
backup.parent.mkdir(exist_ok=True)
shutil.copy2(SCH, backup)
SCH.write_text(dump(d) + '\n', encoding='utf8')
print('backup: %s' % backup)
print('wrote %d symbols (+%d power), %d wires, %d junctions, %d labels'
      % (len(syms), len(power), len(segments), len(junc), len(labels)))
