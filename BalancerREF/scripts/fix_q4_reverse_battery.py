"""Replace Q4's single-FET reverse protection with a back-to-back bidirectional switch.

THE DEFECT
    Q4 is one AO3401A with its GATE TIED TO GND, source on /BAT, drain on the cell
    terminal at J2.1. A MOSFET channel conducts in BOTH directions once enhanced, and
    an enhanced channel shorts out its own body diode - so the only thing blocking a
    reversed cell was that diode, and whether the channel is enhanced is decided by
    whatever holds /BAT up. Plug in USB and the BQ24075 holds /BAT near 4.2 V:

        Vgs = V(gate) - V(source) = 0 - 4.2 = -4.2 V

    against an AO3401A threshold of -0.5 to -1.3 V (sources/AO3401A.txt). The channel
    is hard on and current flows into the reversed cell. Protection works with the
    cell on the bench and fails with a charger attached, which is backwards.

    It matters because BQ24075 Absolute Maximum Ratings (sources/BQ24075.pdf) give

        BAT (with respect to VSS)    -0.3 ... +5 V

    and a reversed 1S LiPo puts -3.7 to -4.2 V there - about 4 V past the minimum.
    So the protection is not optional; a backwards pack destroys the charger.

THE FIX
    TI SLVA948 Figure 12, "BPS Discrete Implementation Using Back-to-Back Connected
    P-MOSFETs". Two P-FETs source-to-source so their body diodes oppose, with the
    gates pulled TO THE COMMON SOURCE rather than to ground:

        BAT_CELL --|Q4 D..S|--+--|S..D Q5|-- BAT
                              |
                        BPS_SRC node
                              |
                    R41 1M  +  C31 10n      R41 holds Vgs = 0 -> default OFF
                              |              C31 slews the turn-on, both directions
                         BPS_GATE
                              |
                           R42 100k
                              |
              BAT_CELL --R43-- G  Q6 (AO3400A)   polarity sense
                              |  S -> GND
                           R44 1M

    Q6 is the ON/OFF element from the app note's figure, and its gate is driven from
    the cell's own + terminal, so the thing is self-deciding with no MCU involved and
    no chicken-and-egg with the supply:

        cell correct   J2.1 = +3.7 V -> Q6 gate = 3.7 x 1M/1.1M = 3.36 V -> Q6 on
                       -> BPS_GATE pulled toward 0 -> Vgs(P) = -3.82 V -> both on
        cell reversed  J2.1 = -3.7 V -> Q6 gate goes negative -> Q6 off
                       -> R41 holds Vgs = 0 -> both P-FETs off, body diodes oppose
        no cell        R44 holds Q6 off -> path open, which is correct

    Q6's gate sees at worst -3.36 V, inside the AO3400A's +/-12 V Vgs rating.

WHAT IT COSTS
    Two AO3401A in series is about 120 mohm (< 60 mohm each at Vgs = -4.5 V). At the
    249 mA fast-charge R3 programs that is 30 mV, against a V(BAT_REG) window of
    4.16-4.23 V. But charge current tapers, and by termination (~25 mA) the drop is
    ~3 mV, so the cell still reaches about 4.197 V. Negligible.

    SLVA948 notes this configuration has no thermal protection and says to oversize
    the FET. A 4 A part on a 250 mA path already is.

PLACEMENT
    The power pair goes in clear space at x 276-304, y 102-136 and the control network
    at x 276-312, y 162-198, joined to the rest of the sheet by labels the way this
    project already carries signals between blocks. It is laid out for correctness,
    not beauty - expect to drag things around in eeschema.

Dry run by default.  Pass --apply to write.
"""
import sys, subprocess, tempfile
from pathlib import Path
from copy import deepcopy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexp_helpers import *
from rollback import Rollback

ROOT = HERE.parent
assert ROOT.name == 'BalancerREF', ROOT
APPLY = '--apply' in sys.argv
SCH = ROOT / 'BalancerREF.kicad_sch'
KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'

# ---- existing geometry this patch detaches from ----------------------------
Q4_OLD = (328.93, 115.57)
J2_PIN1 = (337.82, 104.14)
OLD_D_WIRES = [((331.47, 104.14), (337.82, 104.14)),      # J2.1 across to Q4.D
               ((331.47, 110.49), (331.47, 104.14))]      # and down into it
OLD_S_WIRE = ((331.47, 120.65), (331.47, 127.0))          # Q4.S down to the BAT rail
OLD_G_WIRES = [((323.85, 115.57), (321.31, 115.57)),      # Q4.G across to the GND stub
               ((321.31, 115.57), (321.31, 118.745)),     # down to #PWR06
               ((321.31, 106.68), (321.31, 115.57))]      # up to J2.2
J2_GND_WIRE = ((337.82, 106.68), (321.31, 106.68))        # J2.2 -> the same GND stub
PWR06 = (321.31, 118.745)

# ---- the new block ---------------------------------------------------------
Q4_NEW, Q5_AT = (288.29, 111.76), (293.37, 127.0)         # rot 0 and rot 180
Q4_G, Q4_D, Q4_S = (283.21, 111.76), (290.83, 106.68), (290.83, 116.84)
Q5_G, Q5_S, Q5_D = (298.45, 127.0), (290.83, 121.92), (290.83, 132.08)
SRC_TAP, SRC_LBL = (290.83, 119.38), (281.94, 119.38)
CELL_LBL, BAT_LBL = (290.83, 102.87), (290.83, 135.89)
G4_LBL, G5_LBL = (278.13, 111.76), (303.53, 127.0)

R41_AT, R41_HI, R41_LO = (281.94, 165.10), (281.94, 161.29), (281.94, 168.91)
C31_AT, C31_HI, C31_LO = (289.56, 165.10), (289.56, 161.29), (289.56, 168.91)
SRC_BUS = [(281.94, 158.75), (289.56, 158.75)]            # BPS_SRC across the top
GATE_BUS = [(276.86, 170.18), (297.18, 170.18)]           # BPS_GATE along the bottom
R42_AT, R42_HI, R42_LO = (297.18, 173.99), (297.18, 170.18), (297.18, 177.80)
Q6_AT, Q6_G, Q6_D, Q6_S = (294.64, 182.88), (289.56, 182.88), (297.18, 177.80), (297.18, 187.96)
Q6_GND = (297.18, 190.50)
R43_AT, R43_L, R43_R = (283.21, 182.88), (279.40, 182.88), (287.02, 182.88)
R43_LBL = (276.86, 182.88)
R44_AT, R44_HI, R44_LO = (289.56, 189.23), (289.56, 185.42), (289.56, 193.04)
R44_GND = (289.56, 195.58)

# Designator/value text. The FET symbol's body sits to the RIGHT of its origin, so
# the donor's +3.81 offset lands the text on top of it; the horizontal R43 wants its
# text above and below instead of beside.
TEXT_AT = {'Q4': (Q4_NEW[0] + 8.89, Q4_NEW[1]), 'Q5': (Q5_AT[0] + 8.89, Q5_AT[1]),
           'Q6': (Q6_AT[0] + 8.89, Q6_AT[1]),
           'R43': (R43_AT[0], R43_AT[1] - 2.54, R43_AT[1] + 2.54)}


def place_text(sym, ref):
    spec = TEXT_AT.get(ref)
    if spec is None:
        return
    # A property's angle is RELATIVE to its symbol, not absolute - R29 on this sheet
    # sits at rotation 270 with its designator at 90, which is how it reads level. So
    # cancel the symbol's rotation to keep the text horizontal.
    sym_ang = one(sym, 'at')[3] if len(one(sym, 'at')) > 3 else 0
    flat = int((360 - float(sym_ang)) % 360)
    x = spec[0]
    ys = (spec[1] - 1.27, spec[1] + 1.27) if len(spec) == 2 else (spec[1], spec[2])
    for pr in children(sym, 'property'):
        a_ = one(pr, 'at')
        if pr[1] == 'Reference':
            a_[1], a_[2] = rnd(x), rnd(ys[0])
        elif pr[1] == 'Value':
            a_[1], a_[2] = rnd(x), rnd(ys[1])
        else:
            continue
        # the donor's property may carry no angle element at all, in which case the
        # text inherits the symbol's rotation - R43 is horizontal, its text must not be
        while len(a_) < 4:
            a_.append(0)
        a_[3] = flat


NEW_PINS = {'Q5.1', 'Q5.2', 'Q5.3', 'Q6.1', 'Q6.2', 'Q6.3',
            'R41.1', 'R41.2', 'C31.1', 'C31.2', 'R42.1', 'R42.2',
            'R43.1', 'R43.2', 'R44.1', 'R44.2'}


def rnd(v):
    return round(float(v), 4)


def refof(s):
    return next((p[2] for p in children(s, 'property') if p[1] == 'Reference'), '')


def setprop(sym, key, val):
    for p in children(sym, 'property'):
        if p[1] == key:
            p[2] = val
            return


def clone(src, ref, value, x, y, angle=0, text_x=None):
    c = deepcopy(src)
    a = one(c, 'at')
    a[1], a[2] = rnd(x), rnd(y)
    while len(a) < 4:
        a.append(0)
    a[3] = angle
    one(c, 'uuid')[1] = uid()
    for p in children(c, 'pin'):
        one(p, 'uuid')[1] = uid()
    setprop(c, 'Reference', ref)
    setprop(c, 'Value', value)
    setprop(c, 'MPN', value)
    inst = one(c, 'instances')
    if inst:
        prj = one(inst, 'project')
        if prj:
            pth = one(prj, 'path')
            if pth:
                one(pth, 'reference')[1] = ref
    for p in children(c, 'property'):
        at_ = one(p, 'at')
        tx = x + 3.81 if text_x is None else text_x
        if p[1] == 'Reference':
            at_[1], at_[2] = rnd(tx), rnd(y - 1.27)
        elif p[1] == 'Value':
            at_[1], at_[2] = rnd(tx), rnd(y + 1.27)
        else:
            at_[1], at_[2] = rnd(x), rnd(y)
        if len(at_) > 3:
            at_[3] = 0
        if p[1] in ('Reference', 'Value'):
            eff = one(p, 'effects')
            if eff is not None:
                eff[:] = [z for z in eff if not tagged(z, 'justify')]
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


def junction(x, y):
    return node('junction', node('at', rnd(x), rnd(y)), node('diameter', 0),
                node('color', 0, 0, 0, 0), node('uuid', uid()))


def export(out):
    r = subprocess.run([KC, 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
                        '-o', str(out), str(SCH)], capture_output=True, text=True)
    assert Path(out).exists(), r.stdout + r.stderr
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


tmp = Path(tempfile.mkdtemp())
before = partition(export(tmp / 'b.net'))
print('baseline: %d pin endpoints' % len(before))

d = parse(SCH.read_text(encoding='utf8'))
syms = children(d, 'symbol')

q4 = next(s for s in syms if refof(s) == 'Q4')
a = one(q4, 'at')
assert (rnd(a[1]), rnd(a[2])) == Q4_OLD, 'Q4 has moved: %s' % a
assert one(q4, 'lib_id')[1] == 'Transistor_FET:AO3401A', one(q4, 'lib_id')[1]
src_r = next(s for s in syms if refof(s) == 'R30')
src_c = next(s for s in syms if refof(s) == 'C27')
src_gnd = next(s for s in syms if refof(s) == '#PWR034')

# ---- the N-channel symbol is not on this sheet yet --------------------------
libs = one(d, 'lib_symbols')
if not any(str(s[1]) == 'Transistor_FET:AO3400A' for s in children(libs, 'symbol')):
    proto = standard('Transistor_FET', 'AO3400A')
    proto[1] = 'Transistor_FET:AO3400A'
    units = [str(z[1]) for z in children(proto, 'symbol')]
    assert all(u.startswith('AO3400A_') for u in units), units
    libs.append(proto)
    print('added Transistor_FET:AO3400A to the sheet lib_symbols cache')

# ---- detach Q4 and move it into the new block ------------------------------
dead = []
for w in children(d, 'wire'):
    pp = [(rnd(z[1]), rnd(z[2])) for z in children(one(w, 'pts'), 'xy')]
    for target in OLD_D_WIRES + OLD_G_WIRES + [OLD_S_WIRE]:
        if set(pp) == set(target):
            dead.append(w)
d[:] = [z for z in d if id(z) not in {id(x) for x in dead}]
print('detached Q4: removed %d wire(s) around its old position' % len(dead))

a[1], a[2] = rnd(Q4_NEW[0]), rnd(Q4_NEW[1])
for p in children(q4, 'property'):
    pa = one(p, 'at')
    pa[1], pa[2] = rnd(Q4_NEW[0] + 3.81), rnd(Q4_NEW[1] + (-1.27 if p[1] == 'Reference' else 1.27))
print('Q4 moved (%.2f, %.2f) -> (%.2f, %.2f)' % (*Q4_OLD, *Q4_NEW))

# J2 pin 1 keeps a stub and gains the label the new block reaches it by
add_w = [wire((331.47, 104.14), J2_PIN1), wire((331.47, 104.14), (325.12, 104.14))]
add_l = [label('BAT_CELL', 325.12, 104.14, 180)]
# J2 pin 2's ground stub lost its far end when Q4's gate wires went
add_w.append(wire(J2_GND_WIRE[0], (321.31, 106.68)))
add_w.append(wire((321.31, 106.68), PWR06))

# ---- the power pair --------------------------------------------------------
add_s = [clone(src_r, 'Q5', 'AO3401A', *Q5_AT, angle=180)]
add_s[0] = deepcopy(q4)                      # clone Q4 itself: right lib_id and pins
one(add_s[0], 'uuid')[1] = uid()
for p in children(add_s[0], 'pin'):
    one(p, 'uuid')[1] = uid()
setprop(add_s[0], 'Reference', 'Q5')
ai = one(add_s[0], 'at')
ai[1], ai[2], ai[3] = rnd(Q5_AT[0]), rnd(Q5_AT[1]), 180
for p in children(add_s[0], 'property'):
    pa = one(p, 'at')
    pa[1], pa[2] = rnd(Q5_AT[0] + 3.81), rnd(Q5_AT[1] + (-1.27 if p[1] == 'Reference' else 1.27))
    if len(pa) > 3:
        pa[3] = 0
inst = one(add_s[0], 'instances')
one(one(one(inst, 'project'), 'path'), 'reference')[1] = 'Q5'

add_w += [wire(Q4_S, Q5_S), wire(SRC_TAP, SRC_LBL),
          wire(Q4_D, CELL_LBL), wire(Q5_D, BAT_LBL),
          wire(Q4_G, G4_LBL), wire(Q5_G, G5_LBL)]
add_l += [label('BPS_SRC', *SRC_LBL, 180), label('BAT_CELL', *CELL_LBL, 90),
          label('BAT', *BAT_LBL, 270), label('BPS_GATE', *G4_LBL, 180),
          label('BPS_GATE', *G5_LBL)]
add_j = [junction(*SRC_TAP)]

# ---- the control network ---------------------------------------------------
add_s += [
    clone(src_r, 'R41', '1M', *R41_AT),
    clone(src_c, 'C31', '10n', *C31_AT),
    clone(src_r, 'R42', '100k', *R42_AT),
    clone(src_r, 'R43', '100k', *R43_AT, angle=90),
    clone(src_r, 'R44', '1M', *R44_AT),
    clone(src_gnd, '#PWR805', 'GND', *Q6_GND),
    clone(src_gnd, '#PWR806', 'GND', *R44_GND),
]
q6 = deepcopy(q4)
one(q6, 'uuid')[1] = uid()
for p in children(q6, 'pin'):
    one(p, 'uuid')[1] = uid()
one(q6, 'lib_id')[1] = 'Transistor_FET:AO3400A'
setprop(q6, 'Reference', 'Q6')
setprop(q6, 'Value', 'AO3400A')
setprop(q6, 'MPN', 'AO3400A')
a6 = one(q6, 'at')
a6[1], a6[2], a6[3] = rnd(Q6_AT[0]), rnd(Q6_AT[1]), 0
for p in children(q6, 'property'):
    pa = one(p, 'at')
    pa[1], pa[2] = rnd(Q6_AT[0] + 3.81), rnd(Q6_AT[1] + (-1.27 if p[1] == 'Reference' else 1.27))
    if len(pa) > 3:
        pa[3] = 0
one(one(one(one(q6, 'instances'), 'project'), 'path'), 'reference')[1] = 'Q6'
add_s.append(q6)

add_w += [
    wire(R41_HI, SRC_BUS[0]), wire(*SRC_BUS), wire(SRC_BUS[1], C31_HI),
    wire(R41_LO, (281.94, 170.18)), wire(*GATE_BUS), wire(C31_LO, (289.56, 170.18)),
    wire(Q6_G, R44_HI), wire(R44_LO, R44_GND),
    wire(R43_R, Q6_G), wire(R43_L, R43_LBL),
    wire(Q6_S, Q6_GND),
]
add_l += [label('BPS_SRC', *SRC_BUS[0], 180), label('BPS_GATE', *GATE_BUS[0], 180),
          label('BAT_CELL', *R43_LBL, 180)]
add_j += [junction(281.94, 170.18), junction(289.56, 170.18), junction(*Q6_G)]

for s in add_s + [q4]:
    place_text(s, refof(s))

d.extend(add_w); d.extend(add_l); d.extend(add_j); d.extend(add_s)
print('added Q5/Q6 + R41 1M, C31 10n, R42 100k, R43 100k, R44 1M, 2 GND')
print('        %d wires, %d labels, %d junctions' % (len(add_w), len(add_l), len(add_j)))

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)

with Rollback(SCH) as guard:
    SCH.write_text(dump(d) + '\n', encoding='utf8')
    subprocess.run([KC, 'sch', 'upgrade', '--force', str(SCH)],
                   capture_output=True, text=True, check=True)
    txt = SCH.read_text(encoding='utf8').rstrip('\n')
    if '\n\t(embedded_fonts' not in txt:
        SCH.write_text(txt[:-2] + '\n\t(embedded_fonts no)\n)\n', encoding='utf8')

    after = partition(export(tmp / 'a.net'))
    moved = {k: (before.get(k), v) for k, v in after.items() if before.get(k) != v}
    print('\nendpoints that changed net:')
    for k, (b, x) in sorted(moved.items()):
        print('   %-8s %-28s -> %s' % (k, b, x))

    guard.require(set(after) == set(before) | NEW_PINS,
                  'pin set wrong: lost %s gained %s'
                  % (sorted(set(before) - set(after)),
                     sorted(set(after) - set(before) - NEW_PINS)))
    # The two P-FETs must share a source node that reaches nothing else but R41/C31.
    guard.require(after['Q4.2'] == after['Q5.2'] == after['R41.1'] == after['C31.1'],
                  'the common source node is not shared: Q4.2=%s Q5.2=%s R41.1=%s C31.1=%s'
                  % (after['Q4.2'], after['Q5.2'], after['R41.1'], after['C31.1']))
    # ... and a gate node tying both gates to R41/C31/R42, NOT to ground.
    guard.require(after['Q4.1'] == after['Q5.1'] == after['R41.2'] == after['C31.2'] == after['R42.1'],
                  'the common gate node is not shared')
    guard.require(after['Q4.1'] != 'GND', 'the P-FET gates are still on GND - the whole defect')
    # the cell terminal reaches Q4's drain and the sense resistor, and nothing else
    guard.require(after['Q4.3'] == after['J2.1'] == after['R43.1'],
                  'BAT_CELL does not tie J2.1, Q4.3 and R43.1')
    guard.require(after['Q5.3'] == '/BAT', 'Q5 drain is on %r, expected /BAT' % after['Q5.3'])
    guard.require(after['R42.2'] == after['Q6.3'], 'R42 does not reach Q6 drain')
    guard.require(after['Q6.2'] == 'GND', 'Q6 source is on %r' % after['Q6.2'])
    guard.require(after['Q6.1'] == after['R43.2'] == after['R44.1'], 'Q6 gate network wrong')
    guard.require(after['R44.2'] == 'GND', 'R44 low side is on %r' % after['R44.2'])
    # nothing outside this corner may move
    allowed = NEW_PINS | {'Q4.1', 'Q4.2', 'Q4.3', 'J2.1'}
    stray = set(moved) - allowed
    guard.require(not stray, 'unexpected endpoints changed net: %s' % sorted(stray))
    print('\nVERIFIED: back-to-back pair with the gates on their own source node, '
          'polarity sensed from the cell, nothing else on the sheet moved.')
