"""Generate BalancerMain.kicad_sch: the HoboBalancer v2 main unit.

A carrier for off-the-shelf boards (decided 2026-10-25): an ESP32-S3 Feather on female
headers (Unexpected Maker FeatherS3 or Adafruit ESP32-S3 Feather; signals use Feather
positions that are plain GPIO on both), a SparkFun KX134 Qwiic accelerometer on a cable,
and an MT3608 boost module wired to pads. The board carries the LM1815 magnetic-pickup
input, the Banner tach input, the switch that powers the boost module from the cell, the
acquire button and the status LED. Hand assembly: SOIC/SOT-23 only, every passive 1206.

Standard symbols are harvested from the carrier and BalancerREF schematics in this repo
(no KiCad library is needed to run this), so the pin geometry is exactly KiCad's own.
Connectivity is made with short stubs ending in labels or power symbols, never with long
wires or T junctions, so verify_main.py can rebuild the netlist from the file.

Pass --apply to write; dry run otherwise.
"""
import sys, re
from copy import deepcopy
from pathlib import Path
import sexpdata as sx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # BalancerV2/BalancerMain
REPO = ROOT.parent.parent               # HoboBalancer
APPLY = '--apply' in sys.argv
PROJECT = 'BalancerMain'
SHEET = '6f1e2d3c-4b5a-4e8f-9a0b-1c2d3e4f5a6b'
S = sx.Symbol
import uuid


def node(k, *v): return [S(k), *v]
def tagged(x, k): return isinstance(x, list) and x and str(x[0]) == k
def children(x, k): return [a for a in x if tagged(a, k)]
def one(x, k): return next((a for a in x if tagged(a, k)), None)
def uid(): return str(uuid.uuid4())
def rnd(v): return round(float(v), 4)


def prop(k, v, x=0, y=0, hide=True):
    e = node('effects', node('font', node('size', 1.27, 1.27)))
    if hide: e.append(node('hide', S('yes')))
    return node('property', k, v, node('at', x, y, 0), e)


# ---------------------------------------------------------------- harvest library symbols
_harvest = {}
for f in (REPO / 'BalancerCarrier' / 'BalancerCarrier.kicad_sch',
          REPO / 'BalancerREF' / 'BalancerREF.kicad_sch',
          REPO / 'BalancerREF_OptHead' / 'BalancerREF_OptHead.kicad_sch'):
    doc = sx.loads(f.read_text(encoding='utf8'))
    for s in children(one(doc, 'lib_symbols'), 'symbol'):
        _harvest.setdefault(str(s[1]), s)

HARVEST = {   # our lib_id -> source lib_id
    'Device:R': 'Device:R', 'Device:C': 'Device:C', 'Device:LED': 'Device:LED', 'Device:L': 'Device:L',
    'Switch:SW_Push': 'Switch:SW_Push', 'Transistor_FET:AO3401A': 'Transistor_FET:AO3401A',
    'Transistor_FET:AO3400A': 'Transistor_FET:AO3400A',
    'Connector_Generic:Conn_01x02': 'Connector_Generic:Conn_01x02',
    'Connector_Generic:Conn_01x05': 'Connector_Generic:Conn_01x05',
    'Mechanical:MountingHole': 'Mechanical:MountingHole',
    'power:GND': 'power:GND', 'power:+3V3': 'power:+3V3', 'power:PWR_FLAG': 'power:PWR_FLAG',
    'BalancerMain:LM1815MX_NOPB': 'BalancerCarrier:LM1815MX_NOPB',
}
libsyms = {}


def rename(sym, name):
    old = str(sym[1]); sym[1] = name
    for a in children(sym, 'symbol'):
        a[1] = name.split(':')[-1] + str(a[1])[len(old.split(':')[-1]):]
    return sym


for ours, src in HARVEST.items():
    s = deepcopy(_harvest[src])
    if ours != src: rename(s, ours)
    libsyms[ours] = s

# Feather symbol: the carrier's FeatherS3 symbol (pin numbers = footprint pads, header
# order checked against the FeatherS3 pinout card), with each pin renamed to its Feather
# position so the same board takes the Adafruit ESP32-S3 Feather.
FEATHER_POS = {'1': 'BAT', '2': 'EN', '3': 'USB', '4': 'D13', '5': 'D12', '6': 'D11', '7': 'D10', '8': 'D9',
               '9': 'D6', '10': 'D5', '11': 'SCL', '12': 'SDA', '13': 'P16', '14': 'TX', '15': 'RX', '16': 'MI',
               '17': 'MO', '18': 'SCK', '19': 'A5', '20': 'A4', '21': 'A3', '22': 'A2', '23': 'A1', '24': 'A0',
               '25': 'GND', '26': 'AREF', '27': '3V', '28': 'RST'}
_fs = rename(deepcopy(_harvest['BalancerCarrier:FeatherS3']), 'BalancerMain:Feather')
for sub in children(_fs, 'symbol'):
    for pin in children(sub, 'pin'):
        one(pin, 'name')[1] = FEATHER_POS[str(one(pin, 'number')[1])]
for pr in children(_fs, 'property'):
    if pr[1] == 'Value': pr[2] = 'Feather ESP32-S3'
libsyms['BalancerMain:Feather'] = _fs


def power_clone(name):
    """A power symbol like +3V3 but for another rail: the pin name is the net name."""
    s = deepcopy(libsyms['power:+3V3']); rename(s, 'BalancerMain:' + name)   # project lib, so ERC does not compare it with KiCad's power lib
    for p in children(s, 'property'):
        if p[1] == 'Value': p[2] = name
    for sub in children(s, 'symbol'):
        for pin in children(sub, 'pin'):
            one(pin, 'name')[1] = name
    libsyms['BalancerMain:' + name] = s


for rail in ('+12V', 'VBAT'):
    power_clone(rail)


def custom_ic(name, w, h, plist, fp, url, ref='U'):
    s = node('symbol', 'BalancerMain:' + name, node('pin_names', node('offset', 0.8)),
             node('in_bom', S('yes')), node('on_board', S('yes')),
             prop('Reference', ref), prop('Value', name), prop('Footprint', fp), prop('Datasheet', url))
    g = node('symbol', name + '_0_1',
             node('rectangle', node('start', -w, h), node('end', w, -h),
                  node('stroke', node('width', 0.254), node('type', S('default'))),
                  node('fill', node('type', S('background')))))
    pp = node('symbol', name + '_1_1')
    for num, nam, typ, x, y, a in plist:
        pp.append(node('pin', S(typ), S('line'), node('at', x, y, a), node('length', 5.08),
                       node('name', nam, node('effects', node('font', node('size', 1.016, 1.016)))),
                       node('number', str(num), node('effects', node('font', node('size', 1.016, 1.016))))))
    s.extend([g, pp]); libsyms['BalancerMain:' + name] = s


custom_ic('Conn_01x03', 5.08, 5.08, [
    (1, '1', 'passive', -10.16, 2.54, 0), (2, '2', 'passive', -10.16, 0, 0), (3, '3', 'passive', -10.16, -2.54, 0)],
    'BalancerMain:SolderWire_1x03', '', ref='J')


def lib_pins(lib):
    out = []
    for sub in children(libsyms[lib], 'symbol'):
        for p in children(sub, 'pin'):
            at = one(p, 'at')
            out.append({'num': str(one(p, 'number')[1]), 'name': str(one(p, 'name')[1]),
                        'x': float(at[1]), 'y': float(at[2]), 'a': float(at[3]), 'type': str(p[1])})
    return out


# ---------------------------------------------------------------- placement
instances, wires, labels, ncs, juncs = [], [], [], [], []
used = set()
_pwr = [0]


def xform(px, py, X, Y, rot):
    """Library pin coordinate (y up) to sheet coordinate (y down) for a symbol at X,Y rotated rot."""
    if rot == 0: return X + px, Y - py
    if rot == 90: return X - py, Y - px
    if rot == 180: return X - px, Y + py
    if rot == 270: return X + py, Y + px
    raise ValueError(rot)


def outward(a, rot):
    """Unit vector pointing away from the body for a pin of library angle a, symbol rotated rot."""
    base = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[int(a) % 360]   # sheet coords at rot 0
    dx, dy = base
    for _ in range(int(rot) // 90):      # rotate CCW on screen (y down): (dx,dy) -> (dy,-dx)
        dx, dy = dy, -dx
    return dx, dy


def place(ref, lib, value, x, y, rot=0, fp=None):
    used.add(lib)
    sym = node('symbol', node('lib_id', lib), node('at', rnd(x), rnd(y), rot), node('unit', 1),
               node('exclude_from_sim', S('no')), node('in_bom', S('yes')), node('on_board', S('yes')),
               node('dnp', S('no')), node('uuid', uid()))
    sym.append(prop('Reference', ref, x + 5.08, y - 1.27, hide=ref.startswith('#')))
    sym.append(prop('Value', value, x + 5.08, y + 1.27, hide=ref.startswith('#')))
    sym.append(prop('Footprint', fp or '', x, y))
    sym.append(prop('Datasheet', '', x, y))
    sym.append(node('instances', node('project', PROJECT, node('path', '/' + SHEET, node('reference', ref), node('unit', 1)))))
    instances.append(sym)
    return {p['num']: (xform(p['x'], p['y'], x, y, rot), outward(p['a'], rot), p) for p in lib_pins(lib)}


def wire(a, b):
    a, b = (rnd(a[0]), rnd(a[1])), (rnd(b[0]), rnd(b[1]))
    assert a[0] == b[0] or a[1] == b[1], ('not orthogonal', a, b)
    if a != b:
        wires.append(node('wire', node('pts', node('xy', *a), node('xy', *b)),
                          node('stroke', node('width', 0), node('type', S('default'))), node('uuid', uid())))


def label(net, x, y, dx, dy):
    ang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[(dx, dy)]
    labels.append(node('label', net, node('at', rnd(x), rnd(y), ang),
                       node('effects', node('font', node('size', 1.27, 1.27)), node('justify', S('left'), S('bottom'))),
                       node('uuid', uid())))


def pwr(net, x, y):
    _pwr[0] += 1
    lib = {'GND': 'power:GND', '+3V3': 'power:+3V3', '+12V': 'BalancerMain:+12V', 'VBAT': 'BalancerMain:VBAT'}[net]
    place('#PWR%03d' % _pwr[0], lib, net, x, y)


def flag(x, y):
    _pwr[0] += 1
    place('#FLG%03d' % _pwr[0], 'power:PWR_FLAG', 'PWR_FLAG', x, y)


def nc(x, y):
    ncs.append(node('no_connect', node('at', rnd(x), rnd(y)), node('uuid', uid())))


POWER = ('GND', '+3V3', '+12V', 'VBAT')


def connect(pins, mapping, stub=7.62):
    """For each pin number: a net name (label or power rail), 'NC', or None (left open)."""
    for num, net in mapping.items():
        (x, y), (dx, dy), p = pins[num]
        if net == 'NC':
            nc(x, y); continue
        if net is None:
            continue
        ex, ey = x + dx * stub, y + dy * stub
        wire((x, y), (ex, ey))
        if net in POWER:
            # always a power symbol at the stub end: a local label named GND would make
            # net "/GND" on the root sheet, not the power net (the carrier PCB shows this)
            pwr(net, ex, ey)
        else:
            label(net, ex, ey, dx, dy)


def two(ref, lib, value, x, y, rot, fp, n1, n2, stub=5.08):
    """Two-terminal part: pin 1 to n1, pin 2 to n2."""
    pins = place(ref, lib, value, x, y, rot, fp)
    connect(pins, {'1': n1, '2': n2}, stub)
    return pins


R, C, L = 'Device:R', 'Device:C', 'Device:L'
FP_R, FP_C = 'Resistor_SMD:R_1206_3216Metric', 'Capacitor_SMD:C_1206_3216Metric'
FP_SOT23 = 'Package_TO_SOT_SMD:SOT-23'
FP_PADS2 = 'BalancerMain:SolderWire_1x02'

# ================================================================ Feather
# Signals by Feather position. GPIO on the two boards (FeatherS3 pinout card; Adafruit
# arduino-esp32 variant adafruit_feather_esp32s3):
#   A0 MAG_TACH   FeatherS3 IO17, Adafruit GPIO18   (RTC GPIO on both: can wake the chip)
#   A1 OPT_TACH   IO18 / GPIO17                     A2 ACQUIRE_BUTTON IO14 / GPIO16 (RTC)
#   A3 STATUS_LED IO12 / GPIO15                     A4 BOOST_EN       IO6  / GPIO14
#   A5 ACCEL_INT  IO5  / GPIO8                      SDA/SCL           IO8/IO9 / GPIO3/GPIO4
# AREF (FeatherS3 IO0, a strapping pin) and the 16th pin (FeatherS3 LDO2 output) stay open.
GPIO = {'A0': 'MAG_TACH', 'A1': 'OPT_TACH', 'A2': 'ACQUIRE_BUTTON', 'A3': 'STATUS_LED', 'A4': 'BOOST_EN',
        'A5': 'ACCEL_INT', 'SDA': 'ACCEL_SDA', 'SCL': 'ACCEL_SCL'}
FX, FY = 254.0, 101.6
fb = place('U1', 'BalancerMain:Feather', 'Feather ESP32-S3', FX, FY, 0, 'BalancerMain:Feather_Socket')
m = {}
for num, ((x, y), d, p) in fb.items():
    nam = p['name']
    if nam in GPIO: m[num] = GPIO[nam]
    elif nam == 'BAT': m[num] = 'VBAT'
    elif nam == 'GND': m[num] = 'GND'
    elif nam == '3V': m[num] = '+3V3'
    else: m[num] = 'NC'
connect(fb, m, 10.16)

# ================================================================ KX134 header
# SparkFun KX134 Qwiic: either the Qwiic cable to the Feather's STEMMA QT plus one wire to
# INT here, or all five wires here. Same I2C bus either way.
j4 = place('J4', 'Connector_Generic:Conn_01x05', 'KX134 3V3/GND/SDA/SCL/INT', 393.7, 101.6, 0,
           'Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical')
connect(j4, {'1': '+3V3', '2': 'GND', '3': 'ACCEL_SDA', '4': 'ACCEL_SCL', '5': 'ACCEL_INT'})

# ================================================================ boost module power switch
# The MT3608 module has no enable pin, so the board switches its input: Q2 P-FET high side
# from the cell, Q1 N-FET pulls Q2's gate down when the GPIO is high. R18 holds it off at boot.
q1 = place('Q1', 'Transistor_FET:AO3400A', 'AO3400A', 76.2, 160.02, 0, FP_SOT23)
connect(q1, {'1': 'BOOST_G', '2': 'GND', '3': 'BOOST_PG'})
two('R16', R, '1k', 50.8, 160.02, 90, FP_R, 'BOOST_EN', 'BOOST_G')
two('R18', R, '100k', 50.8, 182.88, 0, FP_R, 'BOOST_G', 'GND')
two('R17', R, '100k', 101.6, 139.7, 0, FP_R, 'VBAT', 'BOOST_PG')
q2 = place('Q2', 'Transistor_FET:AO3401A', 'AO3401A', 129.54, 139.7, 0, FP_SOT23)
connect(q2, {'1': 'BOOST_PG', '2': 'VBAT', '3': 'BOOST_VIN'})
j5 = place('J5', 'Connector_Generic:Conn_01x02', 'BOOST IN+ / IN-', 170.18, 139.7, 0, FP_PADS2)
connect(j5, {'1': 'BOOST_VIN', '2': 'GND'})
j6 = place('J6', 'Connector_Generic:Conn_01x02', 'BOOST OUT+ / OUT- (set 12 V)', 170.18, 177.8, 0, FP_PADS2)
connect(j6, {'1': '+12V', '2': 'GND'})
flag(203.2, 129.54); wire((203.2, 129.54), (203.2, 134.62)); pwr('VBAT', 203.2, 134.62)
flag(203.2, 167.64); wire((203.2, 167.64), (203.2, 172.72)); pwr('+12V', 203.2, 172.72)

# ================================================================ magnetic pickup, LM1815 (carrier block)
MX, MY = 76.2, 266.7
lm = place('U4', 'BalancerMain:LM1815MX_NOPB', 'LM1815MX/NOPB', MX, MY, 0, 'Package_SO:SOIC-14_3.9x8.7mm_P1.27mm')
connect(lm, {'8': '+3V3', '2': 'GND', '3': 'VR_IN', '9': 'GND', '11': 'GND', '12': 'MAG_TACH',
             '14': 'MAG_TIMING', '7': 'MAG_PEAK', '1': 'NC', '4': 'NC', '6': 'NC', '13': 'NC', '5': 'NC', '10': 'NC'})
j3 = place('J3', 'Connector_Generic:Conn_01x02', 'MPU + / -', 25.4, 246.38, 0, FP_PADS2)
connect(j3, {'1': 'MAG_IN', '2': 'GND'})
# two 10k 1206 in series: the pulse withstand that takes +/-60 V peaks is a body-size property
two('R9', R, '10k', 25.4, 271.78, 90, FP_R, 'MAG_IN', 'MAG_MID')
two('R10', R, '10k', 25.4, 284.48, 90, FP_R, 'MAG_MID', 'VR_IN')   # stacked, so no stub touches the LM1815's
# one shot on pin 14: 0.673 x 100k x 1n = 67 us (was 150k on the carrier; 100k keeps the value set)
two('R11', R, '100k', 134.62, 254.0, 0, FP_R, '+3V3', 'MAG_TIMING')
two('C8', C, '1n C0G', 134.62, 276.86, 0, FP_C, 'MAG_TIMING', 'GND')
two('R12', R, '1.6M', 152.4, 276.86, 0, FP_R, 'MAG_PEAK', 'GND')
two('C9', C, '330n', 165.1, 276.86, 0, FP_C, 'MAG_PEAK', 'GND')
two('R13', R, '10k', 152.4, 254.0, 0, FP_R, '+3V3', 'MAG_TACH')      # open-collector pull-up
two('C10', C, '100n', 182.88, 266.7, 0, FP_C, '+3V3', 'GND')         # LM1815 decoupling

# ================================================================ Banner photo-tach
# M12: pin 1 brown +12 V, pin 3 blue 0 V, pin 2 white NPN output. White pulls OPT_RAW low.
j2 = place('J2', 'BalancerMain:Conn_01x03', 'BANNER bn/bu/wh', 25.4, 322.58, 0, 'BalancerMain:SolderWire_1x03')
connect(j2, {'1': '+12V', '2': 'GND', '3': 'OPT_RAW'})
two('R14', R, '10k', 63.5, 309.88, 0, FP_R, '+3V3', 'OPT_RAW')
two('R15', R, '1k', 81.28, 322.58, 90, FP_R, 'OPT_RAW', 'OPT_TACH')

# ================================================================ UI, holes
sw = place('SW1', 'Switch:SW_Push', 'ACQUIRE', 254.0, 309.88, 0, 'Button_Switch_THT:SW_PUSH_6mm')
connect(sw, {'1': 'ACQUIRE_BUTTON', '2': 'GND'})
two('R19', R, '10k', 228.6, 284.48, 0, FP_R, '+3V3', 'ACQUIRE_BUTTON')
two('C11', C, '100n', 241.3, 330.2, 0, FP_C, 'ACQUIRE_BUTTON', 'GND')
two('R20', R, '1k', 353.06, 342.9, 90, FP_R, 'STATUS_LED', 'LED_A')
led = place('LED1', 'Device:LED', 'STATUS GREEN', 373.38, 342.9, 0, 'LED_SMD:LED_0603_1608Metric')
connect(led, {'1': 'GND', '2': 'LED_A'}, 5.08)
for i, (hx, hy) in enumerate(((381.0, 350.52), (393.7, 350.52), (406.4, 350.52), (419.1, 350.52)), 1):
    place('H%d' % i, 'Mechanical:MountingHole', 'M3', hx, hy, 0, 'MountingHole:MountingHole_3.2mm_M3')
# PWR_FLAGs for the rails that only passives drive, and ground
for net, fx, fy in (('GND', 436.88, 60.96), ('+3V3', 436.88, 81.28)):
    flag(fx, fy); wire((fx, fy), (fx, fy + 5.08))
    if net in POWER: pwr(net, fx, fy + 5.08)
    else: label(net, fx, fy + 5.08, 0, 1)

# ---------------------------------------------------------------- emit
doc = node('kicad_sch', node('version', 20260306), node('generator', 'build_main'), node('generator_version', '10.0'),
           node('uuid', SHEET), node('paper', 'A3'),
           node('title_block', node('title', 'HoboBalancer v2 main unit'), node('date', '2026-10-25'), node('rev', 'B'),
                node('comment', 1, 'Carrier: ESP32-S3 Feather, KX134 header, MT3608 module pads, LM1815 MPU input, Banner tach')))
libs = node('lib_symbols')
for lib in sorted(used):
    libs.append(deepcopy(libsyms[lib]))
doc.append(libs)
doc.extend(wires); doc.extend(juncs); doc.extend(ncs); doc.extend(labels); doc.extend(instances)
doc.append(node('sheet_instances', node('path', '/', node('page', '1'))))
doc.append(node('embedded_fonts', S('no')))
print('BalancerMain: %d symbols, %d wires, %d labels, %d no-connects' % (len(instances), len(wires), len(labels), len(ncs)))
if not APPLY:
    print('dry run; pass --apply'); sys.exit(0)
def pretty(x, depth=0):
    if not isinstance(x, list): return sx.dumps(x)
    if not any(isinstance(a, list) for a in x): return '(' + ' '.join(sx.dumps(a) for a in x) + ')'
    head = [a for a in x if not isinstance(a, list)]
    body = [a for a in x if isinstance(a, list)]
    ind = '\t' * (depth + 1)
    return '(' + ' '.join(sx.dumps(a) for a in head) + '\n' + '\n'.join(ind + pretty(b, depth + 1) for b in body) + '\n' + '\t' * depth + ')'
(ROOT / 'BalancerMain.kicad_sch').write_text(pretty(doc) + '\n', encoding='utf8')
lib = node('kicad_symbol_lib', node('version', 20241209), node('generator', 'build_main'))
for name, s in libsyms.items():
    if name.startswith('BalancerMain:') and name in used:
        c = deepcopy(s); c[1] = name.split(':')[1]; lib.append(c)
(ROOT / 'BalancerMain.kicad_sym').write_text(pretty(lib) + '\n', encoding='utf8')
(ROOT / 'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "BalancerMain")(type "KiCad")(uri "${KIPRJMOD}/BalancerMain.kicad_sym")(options "")(descr "Generated main-unit symbols")))\n', encoding='utf8')
print('wrote BalancerMain.kicad_sch and BalancerMain.kicad_sym')
