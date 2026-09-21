"""Delete the GPS load switch and the supply-sense divider; use the FeatherS3[D]'s own.

PATCHES the existing schematic. Does not regenerate it.

WHY
    Both blocks duplicate hardware already on the module, which only became clear after
    tracing its schematic properly:

    LDO2  U3 NCP167BMX330TBG, output 3V3_2, brought out on J1 pin 1 (symbol pin 13).
          Its input is VBUS, and VBUS is an OR of USB (through D4) and VBAT (through
          T2, a CJ3139K P-FET) - the same node that feeds U1, the main 3.3 V LDO. So
          LDO2 is live on battery, and firmware switches it through an internal GPIO
          (MTCK), costing no header pin. That is exactly what Q1/R16/R17/C13 did
          discretely, so they come out and the GPS runs from LDO2 instead.

    GAUGE U4 MAX17048G+T10 on the module's I2C bus, measuring the cell directly and
          reporting voltage and state of charge. Strictly better than R20/R21 sampling
          a rail through a divider, so the divider comes out.

    Removing both also fixes a pin budget that had reached zero spare: of 21 header
    GPIO, IO0 is the boot button, IO3 is a strapping pin, RX/TX are the console and
    IO8/IO9 are the I2C bus the gauge sits on - leaving exactly 15 for 15 signals.
    This frees IO1 and IO38.

REMOVES
    Q1 AO3401A, R16 100k, R17 10k, C13 100n   and their +3V3 symbols
    R20 100k, R21 100k, C10 100n              and their GND symbols
    the SUPPLY_SENSE and GPS_EN_N nets entirely
REWIRES
    U1 pin 13 LDO2_OUT -> GPS_3V3   (was a no-connect; now supplies J4 pin 1)
    U1 pin 8  IO1      -> no-connect (was SUPPLY_SENSE)
    U1 pin 9  IO38     -> no-connect (was GPS_EN_N)
"""
import sys, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexp_helpers import *
from sexpdata import Symbol as S

ROOT = HERE.parent
SCH = ROOT / 'BalancerCarrier.kicad_sch'
APPLY = '--apply' in sys.argv
UX, UY = 299.72, 120.65


def pin_xy(n):
    if n >= 13:
        return round(UX - 15.24, 2), round(UY + 22.86 - (n - 13) * 2.54, 2)
    return round(UX + 15.24, 2), round(UY - 5.08 + (n - 1) * 2.54, 2)


# x1 stops at 366: the accelerometer's GND symbol sits at (370.84, 198.12) and must survive
BOXES = {'load switch': (358, 56, 402, 100), 'sense divider': (344, 194, 366, 238)}
EXPECT = {'load switch': 20, 'sense divider': 15}

P13, P8, P9 = pin_xy(13), pin_xy(8), pin_xy(9)
STUB8 = (round(P8[0] + 10.16, 2), P8[1])
STUB9 = (round(P9[0] + 10.16, 2), P9[1])

root = parse(SCH.read_text(encoding='utf8'))


def pts(n):
    a = one(n, 'at')
    if a and (tagged(n, 'symbol') or tagged(n, 'label') or tagged(n, 'junction')
              or tagged(n, 'no_connect')):
        return [(round(float(a[1]), 2), round(float(a[2]), 2))]
    if tagged(n, 'wire'):
        return [(round(float(x[1]), 2), round(float(x[2]), 2)) for x in children(one(n, 'pts'), 'xy')]
    return []


kept, counts = [], {k: 0 for k in BOXES}
drop_pins = 0
for n in root:
    p = pts(n)
    hit = None
    for name, (x0, y0, x1, y1) in BOXES.items():
        if p and all(x0 <= x <= x1 and y0 <= y <= y1 for x, y in p):
            hit = name; break
    if hit:
        counts[hit] += 1
        continue
    # U1's own stubs for the two nets going away, and the LDO2_OUT no-connect
    if tagged(n, 'no_connect') and p and p[0] == P13:
        drop_pins += 1; continue
    if tagged(n, 'wire') and (P8 in p or P9 in p):
        drop_pins += 1; continue
    if tagged(n, 'label') and p and p[0] in (STUB8, STUB9):
        drop_pins += 1; continue
    kept.append(n)
root[:] = kept

for k, v in counts.items():
    print('  %-14s removed %2d elements (expected %d)' % (k, v, EXPECT[k]))
    if v != EXPECT[k]:
        sys.exit('  ABORT: %s removed %d, expected %d' % (k, v, EXPECT[k]))
print('  U1 stubs        removed %2d elements (expected 5)' % drop_pins)
if drop_pins != 5:
    sys.exit('  ABORT: expected 5 U1 stub elements, removed %d' % drop_pins)


def wire(a, b):
    root.append(node('wire', node('pts', node('xy', *a), node('xy', *b)),
                     node('stroke', node('width', 0), node('type', S('default'))),
                     node('uuid', uid())))


# LDO2_OUT now feeds the GPS; IO1 and IO38 go back to spare
wire(P13, (round(P13[0] - 10.16, 2), P13[1]))
root.append(node('label', 'GPS_3V3', node('at', round(P13[0] - 10.16, 2), P13[1], 180),
                 node('effects', node('font', node('size', 1.27, 1.27)),
                      node('justify', S('left'), S('bottom'))), node('uuid', uid())))
for p in (P8, P9):
    root.append(node('no_connect', node('at', *p), node('uuid', uid())))
print('  U1 pin 13 LDO2_OUT -> GPS_3V3; pins 8 (IO1) and 9 (IO38) freed')

if not APPLY:
    print('\ndry run - pass --apply to write')
else:
    KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
    SCH.write_text(dump(root) + '\n', encoding='utf8')
    subprocess.run([KC, 'sch', 'upgrade', '--force', str(SCH)], capture_output=True, check=True)
    t = SCH.read_text(encoding='utf8')
    if '\n\t(embedded_fonts' not in t:
        SCH.write_text(t[:-2] + '\n\t(embedded_fonts no)\n)\n', encoding='utf8')
    print('\nwrote', SCH.name)
