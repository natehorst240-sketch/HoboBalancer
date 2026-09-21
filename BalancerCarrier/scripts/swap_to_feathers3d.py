"""Swap the module from FireBeetle 2 ESP32-S3 to Unexpected Maker FeatherS3[D].

PATCHES the existing schematic. Does not regenerate it.

WHY
    The DFR0975 this board was designed around is pre-order only, and the documents
    supplied for it were internally inconsistent (2D CAD showing an ESP-WROOM-32
    silkscreen against an S3 schematic). The FeatherS3[D] is a Feather-format board,
    so it uses a maintained footprint instead of one built from that CAD, and any
    other Feather drops into the same footprint later.

PINOUT SOURCE
    github.com/unexpectedmaker/esp32s3 - kicad/symbols/FeatherS3.kicad_sym, checked
    pin-for-pin against series_d/schematics/schematic-feathers3d-p1.pdf headers J1
    (16 pins) and JP3 (12 pins). Both agree exactly. Symbol pins 13-28 are J1,
    pins 1-12 are JP3.

PIN CHOICES, against the ESP32-S3 datasheet
    SUPPLY_SENSE   -> IO1   ADC1 is GPIO1-10; ADC2 is unusable while Wi-Fi is up.
    ACQUIRE_BUTTON -> IO5   RTC GPIO (0-21), required to wake deep sleep on EXT1.
    left alone     IO0  carries the board's own boot button
                   IO3  strapping pin (JTAG source select)
                   RX/TX  UART0 console
                   LDO2_OUT  is 3V3_2 off U3 NCP167BMX330TBG, whose input is VBUS -
                             USB only, dead on battery, so it cannot power anything.
    spare          IO7, IO8 - both ADC1-capable

    IO35/36/37 are used. They are free on this board because its 8 MB PSRAM is QSPI,
    not octal; an octal-PSRAM S3 module would consume them. Worth a sanity check at
    bring-up if any of those three misbehave.

ALSO
    J5 pin 1 and the sense divider move from VCC_SYS to VBAT. On the FireBeetle, VCC
    was the merged system rail and reached ~5 V on USB, pushing the optical emitter to
    718 mA against a 500 mA design point. VBAT is the cell, capped at 4.2 V, so the
    emitter peaks at 513 mA instead.
"""
import sys, re, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexp_helpers import *
import sexpdata
from sexpdata import Symbol as S

ROOT = HERE.parent
SCH = ROOT / 'BalancerCarrier.kicad_sch'
SHEET = 'b1c0a5d2-0e41-4a7f-9d3c-1f2e3a4b5c6d'
APPLY = '--apply' in sys.argv
UM = Path(sys.argv[sys.argv.index('--um') + 1]) if '--um' in sys.argv else None
FP = 'BalancerCarrier:FeatherS3'

# the block being torn out
BOX = (259.08 - 1, 95.25 - 1, 345.44 + 1, 146.05 + 1)

# symbol pin -> (silkscreen label, net or None for no-connect)
PINS = {
    28: ('RST', None),       27: ('3V3', '+3V3'),      26: ('IO0', None),
    25: ('GND', 'GND'),      24: ('IO17', 'ACCEL_CS'), 23: ('IO18', 'ACCEL_DRDY'),
    22: ('IO14', 'ACCEL_MISO'), 21: ('IO12', 'ACCEL_SCK'), 20: ('IO6', 'GPS_PPS'),
    19: ('IO5', 'ACQUIRE_BUTTON'), 18: ('IO36', 'OPT_LED_EN'), 17: ('IO35', 'OPT_TACH'),
    16: ('IO37', 'STATUS_LED'), 15: ('RX', None), 14: ('TX', None),
    13: ('LDO2_OUT', None),
    1: ('VBAT', 'VBAT'),     2: ('EN', None),          3: ('5V', None),
    4: ('IO11', 'ACCEL_MOSI'), 5: ('IO10', 'GPS_UART_TX'), 6: ('IO7', None),
    7: ('IO3', None),        8: ('IO1', 'SUPPLY_SENSE'), 9: ('IO38', 'GPS_EN_N'),
    10: ('IO33', 'MAG_TACH'), 11: ('IO9', 'GPS_UART_RX'), 12: ('IO8', None),
}
_g = {net: lbl for lbl, net in PINS.values() if net and lbl.startswith('IO')}
assert 1 <= int(_g['SUPPLY_SENSE'][2:]) <= 10, 'SUPPLY_SENSE not on ADC1'
assert 0 <= int(_g['ACQUIRE_BUTTON'][2:]) <= 21, 'ACQUIRE_BUTTON not an RTC GPIO'

UX, UY = 299.72, 120.65


def pin_xy(num):
    """Sheet position of FeatherS3 symbol pin `num`."""
    if num >= 13:                       # J1, left side
        return UX - 15.24, UY + 22.86 - (num - 13) * 2.54
    return UX + 15.24, UY - 5.08 + (num - 1) * 2.54


root = parse(SCH.read_text(encoding='utf8'))
pwr_ns = [int(m) for m in re.findall(r'"#PWR(\d+)"', SCH.read_text(encoding='utf8'))]
_n = [max(pwr_ns) if pwr_ns else 0]
added = []


def _at(x, y, ang=None):
    return node('at', round(x, 4), round(y, 4), ang) if ang is not None else node('at', round(x, 4), round(y, 4))


def place(ref, lib, value, x, y, fp=None):
    sym = node('symbol', node('lib_id', lib), _at(x, y, 0), node('unit', 1),
               node('exclude_from_sim', S('no')), node('in_bom', S('yes')),
               node('on_board', S('yes')), node('dnp', S('no')), node('uuid', uid()),
               prop('Reference', ref, x + 5.08, y - 1.27, hide=False),
               prop('Value', value, x + 5.08, y + 1.27, hide=False))
    if fp:
        sym.append(prop('Footprint', fp, x, y))
    sym.append(prop('Datasheet', '', x, y))
    sym.append(node('instances', node('project', 'BalancerCarrier',
                                      node('path', '/' + SHEET,
                                           node('reference', ref), node('unit', 1)))))
    added.append(sym)


def pwr(lib, val, x, y):
    _n[0] += 1
    place('#PWR%03d' % _n[0], lib, val, x, y)


def wire(a, b):
    assert a[0] == b[0] or a[1] == b[1], ('not orthogonal', a, b)
    added.append(node('wire', node('pts', node('xy', round(a[0], 4), round(a[1], 4)),
                                   node('xy', round(b[0], 4), round(b[1], 4))),
                      node('stroke', node('width', 0), node('type', S('default'))),
                      node('uuid', uid())))


def label(net, x, y, ang=0):
    added.append(node('label', net, _at(x, y, ang),
                      node('effects', node('font', node('size', 1.27, 1.27)),
                           node('justify', S('left'), S('bottom'))), node('uuid', uid())))


def nc(x, y):
    added.append(node('no_connect', _at(x, y), node('uuid', uid())))


# ---------------------------------------------------------------- 1. tear out
def pts_of(n):
    a = one(n, 'at')
    if a and (tagged(n, 'symbol') or tagged(n, 'label') or tagged(n, 'junction')
              or tagged(n, 'no_connect')):
        return [(float(a[1]), float(a[2]))]
    if tagged(n, 'wire'):
        return [(float(xy[1]), float(xy[2])) for xy in children(one(n, 'pts'), 'xy')]
    return []


x0, y0, x1, y1 = BOX
kept, removed = [], 0
for n in root:
    p = pts_of(n)
    if p and all(x0 <= x <= x1 and y0 <= y <= y1 for x, y in p):
        removed += 1
        continue
    kept.append(n)
root[:] = kept
print('  removed %d elements of the old FireBeetle block' % removed)
if removed != 54:
    sys.exit('expected 54 elements, removed %d - aborting' % removed)

# ---------------------------------------------------------------- 2. libraries
libs = one(root, 'lib_symbols')
libs[:] = [s for s in libs if not (tagged(s, 'symbol')
                                   and 'FireBeetle2_ESP32S3' in str(s[1]))]
if UM:
    src = parse(UM.read_text(encoding='utf8'))
    fs = next((s for s in children(src, 'symbol')), None)
    if fs is None:
        sys.exit('no symbol found in %s' % UM)
    fs = list(fs)
    fs[1] = 'BalancerCarrier:FeatherS3'
    libs.append(fs)
    print('  installed symbol BalancerCarrier:FeatherS3 from', UM.name)

# ---------------------------------------------------------------- 3. the module
place('U1', 'BalancerCarrier:FeatherS3', 'FeatherS3[D]', UX, UY, FP)
for num, (lbl, net) in sorted(PINS.items()):
    px, py = pin_xy(num)
    left = num >= 13
    out, ang = (-10.16, 180) if left else (10.16, 0)
    if net == '+3V3':
        wire((px, py), (px + out * 0.75, py)); pwr('power:+3V3', '+3V3', px + out * 0.75, py)
    elif net == 'GND':
        wire((px, py), (px + out * 0.75, py)); pwr('power:GND', 'GND', px + out * 0.75, py)
    elif net:
        wire((px, py), (px + out, py)); label(net, px + out, py, ang)
    else:
        nc(px, py)

# ---------------------------------------------------------------- 4. VCC_SYS -> VBAT
renamed = 0
for n in root:
    if tagged(n, 'label') and str(n[1]) == 'VCC_SYS':
        n[1] = 'VBAT'; renamed += 1
print('  renamed %d VCC_SYS label(s) to VBAT' % renamed)
if renamed != 2:
    sys.exit('expected 2 VCC_SYS labels (J5.1 and the sense divider), found %d' % renamed)

root.extend(added)
print('  placed U1 FeatherS3[D]: %d signals, %d no-connects'
      % (sum(1 for l, nt in PINS.values() if nt and nt not in ('+3V3', 'GND')),
         sum(1 for l, nt in PINS.values() if nt is None)))

if not APPLY:
    print('\ndry run - pass --apply to write')
else:
    KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
    SCH.write_text(dump(root) + '\n', encoding='utf8')
    subprocess.run([KC, 'sch', 'upgrade', '--force', str(SCH)], capture_output=True, check=True)
    txt = SCH.read_text(encoding='utf8')
    if '\n\t(embedded_fonts' not in txt:
        SCH.write_text(txt[:-2] + '\n\t(embedded_fonts no)\n)\n', encoding='utf8')
    print('\nwrote', SCH.name)
