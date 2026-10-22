"""Generate BalancerMain.kicad_sch: the HoboBalancer v2 main unit.

Carrier architecture with an OMGS3 module soldered to pads (ESP32-S3-PICO) with the IIS3DWB replaced by sockets for
the EVAL-ADXL357Z, the LM1815 magnetic-pickup input kept, a Banner SM312 NPN tach input,
and 3S power. Hand assembly: SOIC/SOT-23 only, every passive 1206, through-hole for
connectors, switch, inductors and pads. Six resistor values, four capacitor values.

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

# OMGS3 symbol from Unexpected Maker's own library (github.com/UnexpectedMaker/esp32s3,
# kicad/symbols/OMGS3.kicad_sym), copied into this repo under BalancerMain/vendor/.
_omg = sx.loads((ROOT / 'vendor' / 'OMGS3.kicad_sym').read_text(encoding='utf8'))
_omg = next(a for a in children(_omg, 'symbol') if str(a[1]) == 'OMGS3')
libsyms['BalancerMain:OMGS3'] = rename(deepcopy(_omg), 'BalancerMain:OMGS3')


def power_clone(name):
    """A power symbol like +3V3 but for another rail: the pin name is the net name."""
    s = deepcopy(libsyms['power:+3V3']); rename(s, 'power:' + name)
    for p in children(s, 'property'):
        if p[1] == 'Value': p[2] = name
    for sub in children(s, 'symbol'):
        for pin in children(sub, 'pin'):
            one(pin, 'name')[1] = name
    libsyms['power:' + name] = s


for rail in ('+5V', '+12V', 'VBAT'):
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


FP_SOT236 = 'Package_TO_SOT_SMD:SOT-23-6'
# TPS54202DDCR, SLVSD01: 1 GND, 2 SW, 3 VIN, 4 FB, 5 EN, 6 BST
custom_ic('TPS54202DDCR', 10.16, 10.16, [
    (3, 'VIN', 'power_in', -15.24, 5.08, 0), (5, 'EN', 'input', -15.24, 0, 0), (4, 'FB', 'input', -15.24, -5.08, 0),
    (6, 'BST', 'passive', 15.24, 5.08, 180), (2, 'SW', 'power_out', 15.24, 0, 180),
    (1, 'GND', 'power_in', 0, -15.24, 90)], FP_SOT236, 'https://www.ti.com/lit/ds/symlink/tps54202.pdf')
# MT3608 (Aerosemi / XI'AN): 1 SW, 2 GND, 3 FB, 4 EN, 5 IN, 6 NC
custom_ic('MT3608', 10.16, 10.16, [
    (5, 'IN', 'power_in', -15.24, 5.08, 0), (4, 'EN', 'input', -15.24, 0, 0), (3, 'FB', 'input', -15.24, -5.08, 0),
    (1, 'SW', 'power_out', 15.24, 5.08, 180), (6, 'NC', 'no_connect', 15.24, -5.08, 180),
    (2, 'GND', 'power_in', 0, -15.24, 90)], FP_SOT236, 'https://www.olimex.com/Products/Breadboarding/BB-PWR-3608/resources/MT3608.pdf')
custom_ic('D_Schottky', 5.08, 2.54, [(1, 'K', 'passive', -7.62, 0, 0), (2, 'A', 'passive', 7.62, 0, 180)],
          'Diode_SMD:D_SMA', '', ref='D')
custom_ic('Polyfuse', 5.08, 2.54, [(1, '1', 'passive', -7.62, 0, 0), (2, '2', 'passive', 7.62, 0, 180)],
          'Fuse:Fuse_1812_4532Metric', '', ref='F')
custom_ic('Conn_02x03', 7.62, 5.08, [
    (1, '1', 'passive', -12.7, 2.54, 0), (3, '3', 'passive', -12.7, 0, 0), (5, '5', 'passive', -12.7, -2.54, 0),
    (2, '2', 'passive', 12.7, 2.54, 180), (4, '4', 'passive', 12.7, 0, 180), (6, '6', 'passive', 12.7, -2.54, 180)],
    'Connector_PinSocket_2.54mm:PinSocket_2x03_P2.54mm_Vertical', '', ref='J')
custom_ic('Conn_01x03', 5.08, 5.08, [
    (1, '1', 'passive', -10.16, 2.54, 0), (2, '2', 'passive', -10.16, 0, 0), (3, '3', 'passive', -10.16, -2.54, 0)],
    'BalancerMain:SolderWire_1x03', '', ref='J')
custom_ic('Conn_01x04', 5.08, 6.35, [
    (1, '1', 'passive', -10.16, 3.81, 0), (2, '2', 'passive', -10.16, 1.27, 0),
    (3, '3', 'passive', -10.16, -1.27, 0), (4, '4', 'passive', -10.16, -3.81, 0)],
    'Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical', '', ref='J')


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
    lib = {'GND': 'power:GND', '+3V3': 'power:+3V3', '+5V': 'power:+5V', '+12V': 'power:+12V', 'VBAT': 'power:VBAT'}[net]
    place('#PWR%03d' % _pwr[0], lib, net, x, y)


def flag(x, y):
    _pwr[0] += 1
    place('#FLG%03d' % _pwr[0], 'power:PWR_FLAG', 'PWR_FLAG', x, y)


def nc(x, y):
    ncs.append(node('no_connect', node('at', rnd(x), rnd(y)), node('uuid', uid())))


POWER = ('GND', '+3V3', '+5V', '+12V', 'VBAT')


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
FP_L = 'BalancerMain:L_Radial_D9_P5'
FP_SOT23 = 'Package_TO_SOT_SMD:SOT-23'
FP_PADS2 = 'BalancerMain:SolderWire_1x02'

# ================================================================ OMGS3
# Pad names from the OMGS3 pinout card and schematic P1 (2024-07-20): 17 GPIO on pads,
# IO0 strapping, IO3 strapping (JTAG select, inactive unless the eFuse is burned),
# IO8/IO9 shared with the module's MAX17048 fuel gauge I2C (10k pull-ups), IO33/34/35
# internal (VBUS sense, RGB LED). BAT_SENSE needs ADC1: IO1..IO9 are ADC1 channels.
GPIO = {
    'IO1': 'BAT_SENSE', 'IO2': 'DOCK_DET', 'IO3': 'BOOST_EN',
    'IO4': 'ACCEL_SCK', 'IO5': 'ACCEL_MISO', 'IO6': 'ACCEL_MOSI', 'IO7': 'ACCEL_CS', 'IO10': 'ACCEL_DRDY',
    'IO11': 'MAG_TACH', 'IO12': 'OPT_TACH', 'IO13': 'ACQUIRE_BUTTON', 'IO14': 'DOCK_EN',
    'IO8': 'STATUS_LED',                     # shares the fuel-gauge SDA pull-up; LED glows faintly until firmware drives it
    'TX0': 'GPS_UART_TX', 'RX0': 'GPS_UART_RX',
    'D-': 'USB_DM', 'D+': 'USB_DP', 'IO0': 'PROG_IO0', 'RESET': 'PROG_RST',
}
FX, FY = 254.0, 101.6
fb = place('U1', 'BalancerMain:OMGS3', 'OMGS3', FX, FY, 0, 'BalancerMain:OMGS3')
m = {}
for num, ((x, y), d, p) in fb.items():
    nam = p['name']
    if nam in GPIO: m[num] = GPIO[nam]
    elif nam == '5V': m[num] = '+5V'        # module's VBUS input: ideal diode then the 700 mA 3.3 V LDO
    elif nam == 'GND' or num == 'EXP': m[num] = 'GND'
    elif nam == '3V3': m[num] = '+3V3'
    else: m[num] = 'NC'          # BAT (no LiPo on the module), EN (3V3 LDO enable, default on), IO9
connect(fb, m, 10.16)
# programming header: wire a USB breakout here (D+/D-/GND), IO0 and RESET for manual bootloader entry
j5 = place('J5', 'Connector_Generic:Conn_01x05', 'PROG GND/D-/D+/IO0/RST', 393.7, 134.62, 0,
           'Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical')
connect(j5, {'1': 'GND', '2': 'USB_DM', '3': 'USB_DP', '4': 'PROG_IO0', '5': 'PROG_RST'})

# ================================================================ battery in, buck, boost
# J1 battery pads -> F1 polyfuse -> D3 Schottky (reverse polarity) -> VBAT
j1 = place('J1', 'Connector_Generic:Conn_01x02', 'BATT 3S +/-', 25.4, 50.8, 0, FP_PADS2)
connect(j1, {'1': 'BAT_IN', '2': 'GND'})
two('F1', 'BalancerMain:Polyfuse', '2A polyfuse 1812', 60.96, 48.26, 0, 'Fuse:Fuse_1812_4532Metric', 'BAT_IN', 'BAT_F')
two('D3', 'BalancerMain:D_Schottky', 'SS14', 91.44, 48.26, 180, 'Diode_SMD:D_SMA', 'VBAT', 'BAT_F')   # K to VBAT, A to BAT_F
flag(111.76, 40.64); wire((111.76, 40.64), (111.76, 45.72)); pwr('VBAT', 111.76, 45.72)
two('C1', C, '10u 25V', 134.62, 60.96, 0, FP_C, 'VBAT', 'GND')
two('C2', C, '10u 25V', 147.32, 60.96, 0, FP_C, 'VBAT', 'GND')
# battery monitor: 100k / 10k, 12.6 V -> 1.15 V on ADC1 (GPIO6)
two('R1', R, '100k', 165.1, 48.26, 0, FP_R, 'VBAT', 'BAT_SENSE')
two('R2', R, '10k', 165.1, 71.12, 0, FP_R, 'BAT_SENSE', 'GND')
two('C3', C, '100n', 177.8, 71.12, 0, FP_C, 'BAT_SENSE', 'GND')

# TPS54202 buck, 5 V, 2 A. Vfb 0.596 V: 75k / 10k -> 5.07 V. L 10 uH, Cout 2 x 10 uF.
BX, BY = 76.2, 121.92
bk = place('U2', 'BalancerMain:TPS54202DDCR', 'TPS54202DDCR', BX, BY, 0, FP_SOT236)
connect(bk, {'3': 'VBAT', '5': 'BUCK_EN', '4': 'BUCK_FB', '6': 'BUCK_BST', '2': 'BUCK_SW', '1': 'GND'})
two('R3', R, '100k', 40.64, 134.62, 0, FP_R, 'VBAT', 'BUCK_EN')      # EN pulled to VIN
two('C4', C, '100n', 116.84, 111.76, 90, FP_C, 'BUCK_BST', 'BUCK_SW')   # bootstrap
two('L1', L, '10uH 3A', 134.62, 121.92, 90, FP_L, 'BUCK_SW', '+5V')
two('C5', C, '10u 25V', 157.48, 134.62, 0, FP_C, '+5V', 'GND')
two('C6', C, '10u 25V', 170.18, 134.62, 0, FP_C, '+5V', 'GND')
two('R4', R, '75k', 190.5, 121.92, 0, FP_R, '+5V', 'BUCK_FB')
two('R5', R, '10k', 190.5, 144.78, 0, FP_R, 'BUCK_FB', 'GND')
flag(157.48, 106.68); wire((157.48, 106.68), (157.48, 111.76)); pwr('+5V', 157.48, 111.76)

# MT3608 boost, 12 V for the Banner sensor only. Vfb 0.6 V: 100k / 5.1k -> 12.4 V. L 22 uH.
OX, OY = 76.2, 187.96
bo = place('U3', 'BalancerMain:MT3608', 'MT3608', OX, OY, 0, FP_SOT236)
connect(bo, {'5': 'VBAT', '4': 'BOOST_EN', '3': 'BOOST_FB', '1': 'BOOST_SW', '6': 'NC', '2': 'GND'})
two('R6', R, '100k', 40.64, 200.66, 0, FP_R, 'BOOST_EN', 'GND')       # off until firmware raises IO38
two('L2', L, '22uH 1A', 116.84, 177.8, 90, FP_L, 'VBAT', 'BOOST_SW')
two('D2', 'BalancerMain:D_Schottky', 'SS14', 142.24, 177.8, 180, 'Diode_SMD:D_SMA', '+12V', 'BOOST_SW')  # K to +12V
two('C7', C, '10u 25V', 157.48, 200.66, 0, FP_C, '+12V', 'GND')
two('R7', R, '100k', 177.8, 187.96, 0, FP_R, '+12V', 'BOOST_FB')
two('R8', R, '5.1k', 177.8, 210.82, 0, FP_R, 'BOOST_FB', 'GND')
flag(157.48, 172.72); wire((157.48, 172.72), (157.48, 177.8)); pwr('+12V', 157.48, 177.8)

# ================================================================ magnetic pickup, LM1815 (carrier block)
MX, MY = 76.2, 266.7
lm = place('U4', 'BalancerMain:LM1815MX_NOPB', 'LM1815MX/NOPB', MX, MY, 0, 'Package_SO:SOIC-14_3.9x8.7mm_P1.27mm')
connect(lm, {'8': '+3V3', '2': 'GND', '3': 'VR_IN', '9': 'GND', '11': 'GND', '12': 'MAG_TACH',
             '14': 'MAG_TIMING', '7': 'MAG_PEAK', '1': 'NC', '4': 'NC', '6': 'NC', '13': 'NC', '5': 'NC', '10': 'NC'})
j3 = place('J3', 'Connector_Generic:Conn_01x02', 'MPU + / -', 25.4, 246.38, 0, FP_PADS2)
connect(j3, {'1': 'MAG_IN', '2': 'GND'})
# two 10k 1206 in series: the pulse withstand that takes +/-60 V peaks is a body-size property
two('R9', R, '10k', 25.4, 271.78, 90, FP_R, 'MAG_IN', 'MAG_MID')
two('R10', R, '10k', 43.18, 271.78, 90, FP_R, 'MAG_MID', 'VR_IN')
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

# ================================================================ ADXL357 eval board sockets (UG-1119 fig 5, 6)
j6 = place('J6', 'BalancerMain:Conn_02x03', 'ADXL357 P1', 274.32, 220.98, 0, 'Connector_PinSocket_2.54mm:PinSocket_2x03_P2.54mm_Vertical')
connect(j6, {'1': '+3V3', '3': '+3V3', '5': 'GND', '2': 'NC', '4': 'NC', '6': 'ACCEL_DRDY'})
j7 = place('J7', 'BalancerMain:Conn_02x03', 'ADXL357 P2', 274.32, 251.46, 0, 'Connector_PinSocket_2.54mm:PinSocket_2x03_P2.54mm_Vertical')
connect(j7, {'1': 'NC', '3': 'NC', '5': 'ACCEL_MISO', '2': 'ACCEL_CS', '4': 'ACCEL_SCK', '6': 'ACCEL_MOSI'})

# ================================================================ dock: 5 V switch and pogo pins
# Q1 N-FET level shifts IO36; Q2 P-FET passes +5V to the pogo pin when IO36 is high.
q1 = place('Q1', 'Transistor_FET:AO3400A', 'AO3400A', 317.5, 309.88, 0, FP_SOT23)
connect(q1, {'1': 'DOCK_EN_G', '2': 'GND', '3': 'DOCK_PG'})
two('R16', R, '1k', 297.18, 309.88, 90, FP_R, 'DOCK_EN', 'DOCK_EN_G')
two('R17', R, '100k', 317.5, 284.48, 0, FP_R, '+5V', 'DOCK_PG')
q2 = place('Q2', 'Transistor_FET:AO3401A', 'AO3401A', 347.98, 284.48, 0, FP_SOT23)
connect(q2, {'1': 'DOCK_PG', '2': '+5V', '3': 'DOCK_5V'})
j8 = place('J8', 'BalancerMain:Conn_01x03', 'DOCK pogo 5V/GND/DET', 391.16, 309.88, 0, 'BalancerMain:Pogo_1x03')
connect(j8, {'1': 'DOCK_5V', '2': 'GND', '3': 'DOCK_DET'})
two('R18', R, '10k', 403.86, 284.48, 0, FP_R, '+3V3', 'DOCK_DET')

# ================================================================ UI, GPS, holes
sw = place('SW1', 'Switch:SW_Push', 'ACQUIRE', 254.0, 309.88, 0, 'Button_Switch_THT:SW_PUSH_6mm')
connect(sw, {'1': 'ACQUIRE_BUTTON', '2': 'GND'})
two('R19', R, '10k', 228.6, 284.48, 0, FP_R, '+3V3', 'ACQUIRE_BUTTON')
two('C11', C, '100n', 241.3, 330.2, 0, FP_C, 'ACQUIRE_BUTTON', 'GND')
two('R20', R, '1k', 353.06, 342.9, 90, FP_R, 'STATUS_LED', 'LED_A')
led = place('LED1', 'Device:LED', 'STATUS GREEN', 373.38, 342.9, 0, 'LED_SMD:LED_0603_1608Metric')
connect(led, {'1': 'GND', '2': 'LED_A'}, 5.08)
j4 = place('J4', 'BalancerMain:Conn_01x04', 'GPS 3V3/GND/RX/TX', 393.7, 101.6, 0, 'Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical')
connect(j4, {'1': '+3V3', '2': 'GND', '3': 'GPS_UART_RX', '4': 'GPS_UART_TX'})
for i, (hx, hy) in enumerate(((381.0, 350.52), (393.7, 350.52), (406.4, 350.52), (419.1, 350.52)), 1):
    place('H%d' % i, 'Mechanical:MountingHole', 'M3', hx, hy, 0, 'MountingHole:MountingHole_3.2mm_M3')
# PWR_FLAGs for the rails that only passives drive, and ground
for net, fx, fy in (('GND', 436.88, 60.96), ('+3V3', 436.88, 81.28), ('BAT_IN', 436.88, 101.6)):
    flag(fx, fy); wire((fx, fy), (fx, fy + 5.08))
    if net in POWER: pwr(net, fx, fy + 5.08)
    else: label(net, fx, fy + 5.08, 0, 1)

# ---------------------------------------------------------------- emit
doc = node('kicad_sch', node('version', 20260306), node('generator', 'build_main'), node('generator_version', '10.0'),
           node('uuid', SHEET), node('paper', 'A3'),
           node('title_block', node('title', 'HoboBalancer v2 main unit'), node('date', '2026-10-22'), node('rev', 'A'),
                node('comment', 1, 'OMGS3 ESP32-S3 on pads, ADXL357 sockets, LM1815 MPU input, Banner tach, 3S power')))
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
    if name.startswith('BalancerMain:'):
        c = deepcopy(s); c[1] = name.split(':')[1]; lib.append(c)
(ROOT / 'BalancerMain.kicad_sym').write_text(pretty(lib) + '\n', encoding='utf8')
(ROOT / 'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "BalancerMain")(type "KiCad")(uri "${KIPRJMOD}/BalancerMain.kicad_sym")(options "")(descr "Generated main-unit symbols")))\n', encoding='utf8')
print('wrote BalancerMain.kicad_sch and BalancerMain.kicad_sym')
