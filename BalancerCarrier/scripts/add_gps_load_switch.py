"""Add a high-side load switch on the GPS supply - PATCHES the existing schematic.

This does NOT regenerate BalancerCarrier.kicad_sch. It loads the file that is there,
adds four parts and rewires two nets, and writes it back. Anything hand-edited in
KiCad survives, as long as it is not one of the two things listed under REMOVES.

WHY
    J4 pin 1 was hardwired to +3V3. An ATGM336H-class GPS draws about 25 mA
    continuously, against 10.8 mA worst case for the whole rest of the 3V3 rail, so
    leaving it powered dominates battery life 2:1. This gates it from a spare GPIO.

CIRCUIT
    Q1  AO3401A P-channel, source on +3V3, drain on the new GPS_3V3 net.
        Datasheet AO3401A: VGS(th) -0.5/-0.9/-1.3 V, RDS(ON) < 85 mohm at
        VGS = -2.5 V, so at -3.3 V drive and 25 mA the drop is about 2 mV.
        Absolute max VGS is +/-12 V, so a 3.3 V gate swing is well inside it.
    R16 100k gate-to-source. Holds the switch OFF whenever the GPIO is high-Z,
        which is the state during reset and early boot. Default is GPS unpowered.
    R17 10k in series with the GPIO. Limits the pin current and, with C13, sets
        the turn-on slew.
    C13 100n gate-to-source. Soft start: the gate moves with tau = R17 x C13 = 1 ms,
        so the FET comes on over milliseconds instead of microseconds and the GPS
        module's input capacitance cannot brown out the 3V3 rail on connection.

    Sense is ACTIVE LOW - GPS_EN_N low turns the GPS on. That falls out of using a
    P-FET driven straight from the GPIO, and it is the safe polarity: a floating or
    unconfigured pin leaves the GPS off rather than on.

REMOVES
    the +3V3 power symbol on J4 pin 1  (becomes the GPS_3V3 label)
    the no-connect on U1 pin 18, IO38   (becomes the GPS_EN_N stub)
"""
import sys, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexp_helpers import *
import sexpdata
from sexpdata import Symbol as S

ROOT = HERE.parent
SCH = ROOT / 'BalancerCarrier.kicad_sch'
REF_SCH = ROOT.parent / 'BalancerREF' / 'BalancerREF.kicad_sch'
SHEET = 'b1c0a5d2-0e41-4a7f-9d3c-1f2e3a4b5c6d'
APPLY = '--apply' in sys.argv

FP_R = 'Resistor_SMD:R_0603_1608Metric'
FP_C = 'Capacitor_SMD:C_0805_2012Metric'
FP_SOT23 = 'Package_TO_SOT_SMD:SOT-23'

# ---------------------------------------------------------------- geometry
# All coordinates are multiples of 1.27; the region 350-410 x 60-100 was empty.
QX, QY = 368.30, 76.20          # Q1 placement point, rotated 180
Q_S = (365.76, 71.12)           # source, upward to +3V3
Q_D = (365.76, 81.28)           # drain, downward to GPS_3V3
Q_G = (373.38, 76.20)           # gate, to the right
GATE_Y = 76.20
R16_X, C13_X = 383.54, 396.24   # gate pull-up and soft-start cap
RAIL_Y = 60.96                  # where their +3V3 symbols sit
J4_V3 = (368.30, 40.64)         # the +3V3 symbol on J4 pin 1 that goes away
IO38 = (330.20, 106.68)         # U1 pin 18, currently a no-connect

root = parse(SCH.read_text(encoding='utf8'))
before = SCH.read_text(encoding='utf8')

# ---------------------------------------------------------------- housekeeping
pwr_ns = [int(m) for m in re.findall(r'"#PWR(\d+)"', before)]
_next = [max(pwr_ns) if pwr_ns else 0]


def newpwr():
    _next[0] += 1
    return '#PWR%03d' % _next[0]


def at_is(n, pt, tol=0.01):
    a = one(n, 'at')
    return a and abs(float(a[1]) - pt[0]) < tol and abs(float(a[2]) - pt[1]) < tol


added = []


def place(ref, lib, value, x, y, angle=0, fp=None):
    sym = node('symbol', node('lib_id', lib), node('at', x, y, angle),
               node('unit', 1), node('exclude_from_sim', S('no')),
               node('in_bom', S('yes')), node('on_board', S('yes')),
               node('dnp', S('no')), node('uuid', uid()),
               prop('Reference', ref, x + 5.08, y - 1.27, hide=False),
               prop('Value', value, x + 5.08, y + 1.27, hide=False))
    if fp:
        sym.append(prop('Footprint', fp, x, y))
    sym.append(prop('Datasheet', '', x, y))
    sym.append(node('instances', node('project', 'BalancerCarrier',
                                      node('path', '/' + SHEET,
                                           node('reference', ref), node('unit', 1)))))
    added.append(sym)
    return sym


def v3v3(x, y):
    place(newpwr(), 'power:+3V3', '+3V3', x, y)


def wire(a, b):
    assert a[0] == b[0] or a[1] == b[1], ('not orthogonal', a, b)
    added.append(node('wire', node('pts', node('xy', *a), node('xy', *b)),
                      node('stroke', node('width', 0), node('type', S('default'))),
                      node('uuid', uid())))


def label(net, x, y, angle=0):
    added.append(node('label', net, node('at', x, y, angle),
                      node('effects', node('font', node('size', 1.27, 1.27)),
                           node('justify', S('left'), S('bottom'))), node('uuid', uid())))


def junction(x, y):
    added.append(node('junction', node('at', x, y), node('diameter', 0),
                      node('color', 0, 0, 0, 0), node('uuid', uid())))


# ---------------------------------------------------------------- lib_symbol
libs = one(root, 'lib_symbols')
have = {str(one(s, 'lib_id') or s[1]) for s in children(libs, 'symbol')}
have |= {str(s[1]) for s in children(libs, 'symbol')}
if 'Transistor_FET:AO3401A' not in have:
    ref_txt = REF_SCH.read_text(encoding='utf8')
    ref_root = parse(ref_txt)
    src = next((s for s in children(one(ref_root, 'lib_symbols'), 'symbol')
                if str(s[1]) == 'Transistor_FET:AO3401A'), None)
    if src is None:
        sys.exit('could not find Transistor_FET:AO3401A in BalancerREF to copy')
    libs.append(src)
    print('  copied Transistor_FET:AO3401A from BalancerREF into lib_symbols')

# ---------------------------------------------------------------- the switch
place('Q1', 'Transistor_FET:AO3401A', 'AO3401A', QX, QY, 180, FP_SOT23)
wire(Q_S, (Q_S[0], 63.50)); v3v3(Q_S[0], 63.50)
wire(Q_D, (Q_D[0], 88.90)); label('GPS_3V3', Q_D[0], 88.90, 270)

wire(Q_G, (C13_X, GATE_Y))                     # gate bus
for x, ref, val, fp in ((R16_X, 'R16', '100k', FP_R), (C13_X, 'C13', '100n', FP_C)):
    place(ref, 'Device:R' if ref == 'R16' else 'Device:C', val, x, 68.58, 0, fp)
    wire((x, 72.39), (x, GATE_Y))              # bottom pin down onto the gate bus
    wire((x, 64.77), (x, RAIL_Y)); v3v3(x, RAIL_Y)
junction(R16_X, GATE_Y)                        # R16 lands mid-bus; C13 is the end

place('R17', 'Device:R', '10k', Q_G[0], 88.90, 0, FP_R)
wire(Q_G, (Q_G[0], 85.09))                     # gate bus down to R17
wire((Q_G[0], 92.71), (Q_G[0], 96.52)); label('GPS_EN_N', Q_G[0], 96.52, 270)
junction(*Q_G)                                 # gate pin + bus + R17 all meet here

# ---------------------------------------------------------------- rewire
kept, dropped = [], []
for n in root:
    if tagged(n, 'symbol') and at_is(n, J4_V3):
        v = next((p for p in children(n, 'property') if str(p[1]) == 'Value'), None)
        if v is not None and str(v[2]) == '+3V3':
            dropped.append('+3V3 power symbol on J4.1'); continue
    if tagged(n, 'no_connect') and at_is(n, IO38):
        dropped.append('no-connect on U1.18 (IO38)'); continue
    kept.append(n)
root[:] = kept
label('GPS_3V3', *J4_V3, 180)                  # J4.1 now runs off the switch
wire(IO38, (IO38[0] + 10.16, IO38[1]))
label('GPS_EN_N', IO38[0] + 10.16, IO38[1], 0)

for d in dropped:
    print('  removed', d)
if len(dropped) != 2:
    sys.exit('expected to remove exactly 2 items, removed %d - aborting' % len(dropped))

root.extend(added)
out = dump(root)
print('  added Q1 AO3401A, R16 100k, R17 10k, C13 100n (+%d elements)' % len(added))

if not APPLY:
    print('\ndry run - pass --apply to write')
else:
    # sexpdata emits one enormous line; kicad-cli reformats it back to the canonical
    # layout. The upgrade drops the top-level (embedded_fonts no), so put it back -
    # same dance build_carrier.py does.
    import subprocess
    KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
    SCH.write_text(out + '\n', encoding='utf8')
    subprocess.run([KC, 'sch', 'upgrade', '--force', str(SCH)],
                   capture_output=True, check=True)
    txt = SCH.read_text(encoding='utf8')
    if '\n\t(embedded_fonts' not in txt:
        SCH.write_text(txt[:-2] + '\n\t(embedded_fonts no)\n)\n', encoding='utf8')
    print('\nwrote %s (%d lines)' % (SCH.name, SCH.read_text(encoding='utf8').count('\n')))
