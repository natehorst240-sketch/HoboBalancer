"""!! NO LONGER AUTHORITATIVE - DO NOT RUN WITH --apply !!

As of 2026-09-20 BalancerCarrier.kicad_sch is the source of truth, not this script.
Running it with --apply would overwrite the file wholesale and silently drop:

    - the GPS load switch (Q1/R16/R17/C13), added by add_gps_load_switch.py
    - anything hand-edited in KiCad since

This file is kept because its comments carry the datasheet reasoning behind most of
the board. Further changes go in as patch scripts alongside add_gps_load_switch.py:
load the existing .kicad_sch, change only what is named, diff the netlist before and
after, and write it back.
"""

_ORIGINAL_HEADER = r"""Generate BalancerCarrier: the HOBOVibe instrument on a FireBeetle 2 ESP32-S3.

WHY THIS BOARD EXISTS
    BalancerREF carries its own ESP32-S3 module, BQ24075 charger, TPS63031 buck-boost,
    USB-C receptacle and ESD array. Those are 47 of its 81 parts and every QFN, WSON and
    LGA on it. Handing the MCU and charger to a proven dev board deletes all of them and
    leaves an instrument board that is entirely hand-solderable at 0603 and SOIC.

    Target is the FireBeetle 2 ESP32-S3 **N16R8** (DFR1145 family, 25.4 x 60 mm):
    dual-core Xtensa S3 so the existing firmware ports as a pin remap rather than an
    architecture change, 16 MB flash so the 4.9 MB flight-log partition fits with room
    to grow, 8 MB PSRAM, native USB, and onboard LiPo charging with a PH2.0 connector.

WHAT MOVED OFF THE BOARD
    Only the optical head, on J5. The IIS3DWB was briefly moved onto a cable on J6, to
    get the sole LGA-14 off the carrier and let the sensor bolt to the airframe rather
    than the enclosure. That was reverted on 2026-09-20: the accelerometer is soldered
    down, copying BalancerREF's U2 block whole. Re-deriving verified blocks is what put
    three bugs into this schematic, and a cabled SPI bus would have needed its own
    termination and decoupling study that no datasheet on hand could settle.

WHAT CAME WITH IT
    The reverse-polarity switch from BalancerREF Rev G. The FireBeetle's cell connector
    goes straight to its charger with no protection, and a reversed 1S pack is about 4 V
    past the absolute maximum of any charger's BAT pin. Two P-FETs source-to-source with
    the gates held at their own source, switched by an N-FET whose gate is driven from
    the cell's own positive terminal, so it is off unless the pack is the right way
    round. J1 takes the cell; J2 feeds the FireBeetle's PH2.0 by a short cable.

WHAT WAS LOST AND PUT BACK
    SUPPLY_SENSE and PGOOD went with the BQ24075, so firmware could no longer answer
    "am I on USB?". R20/R21 divide the FireBeetle's VCC pin - which is only live when
    USB is plugged - down to a GPIO, which answers it more directly than the old
    two-divider comparison ever did.

PIN MAP (FireBeetle silkscreen -> ESP32-S3 GPIO -> signal)
    Deep-sleep wake uses EXT1, which needs RTC-capable pins: GPIO0-21 on the S3. Both
    MAG_TACH and ACQUIRE are inside that range. GPIO0 and GPIO3 are strapping pins and
    are left free; GPIO43/44 are UART0 and are left free so ROM boot chatter never
    reaches the GPS, which is the same reason BalancerREF used UART1.

        SCK   GPIO17  ACCEL_SCK        D10  GPIO14  OPT_LED_EN
        MOSI  GPIO15  ACCEL_MOSI       D11  GPIO13  ACQUIRE_BUTTON   (RTC, EXT1)
        MISO  GPIO16  ACCEL_MISO       D12  GPIO12  OPT_TACH
        A4/SS GPIO10  ACCEL_CS         D13  GPIO21  STATUS_LED
        D5    GPIO7   ACCEL_DRDY       A0   GPIO4   GPS_UART_TX
        D6    GPIO18  MAG_TACH  (RTC)  A1   GPIO5   GPS_UART_RX
                                       A2   GPIO6   SUPPLY_SENSE

    Free after this: D2(3) D3(38) D7(9) D9(0) D14(47) A3(8) A5(11) SDA(1) SCL(2)
    TX(43) RX(44) - eleven spare.

CAVEAT ON THE FOOTPRINT
    No official KiCad footprint for this board was available here, so the symbol's pin
    NUMBERS are this generator's own convention, listed in FIREBEETLE_PINS below. They
    must be matched against whatever footprint is used before the netlist means
    anything. Everything else is checked against KiCad's own ERC and netlist export.

Writes BalancerCarrier.kicad_sch.  Pass --apply to write; dry run otherwise.
"""
import sys, subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexp_helpers import *

ROOT = HERE.parent
APPLY = '--apply' in sys.argv
SCH = ROOT / 'BalancerCarrier.kicad_sch'
KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
SHEET = 'b1c0a5d2-0e41-4a7f-9d3c-1f2e3a4b5c6d'

# ---------------------------------------------------------------- the dev board
# (pin number, name, electrical type).  Numbering is this generator's convention.
# Taken pin-for-pin off DFR0975-U schematic V1.3 sheet 1, headers P3 and P4.
# Symbol pins 1-14 are P3.1-P3.14; 15-32 are P4.1-P4.18. Both run pin 1 at the top.
#
# VCC (P3.1) is NOT a USB-only 5 V rail. It is the merged system rail: the ETA6003's
# SYS output reaches it through Q3 (SI2301) gated by the Q4A/Q4B pair, so it is live on
# battery alone, at roughly VBAT (3.0-4.2 V), or ~5 V on USB. D1, a 6.2 V zener, clamps it.
FIREBEETLE_PINS = [
    (1,  'VCC',      'power_out'),     (2,  'USB_D_P',   'bidirectional'),
    (3,  'USB_D_N',  'bidirectional'), (4,  'IO47',      'bidirectional'),
    (5,  'IO11',     'bidirectional'), (6,  'IO10',      'bidirectional'),
    (7,  'IO8',      'bidirectional'), (8,  'IO6',       'bidirectional'),
    (9,  'IO5',      'bidirectional'), (10, 'IO4',       'bidirectional'),
    (11, 'IO21',     'bidirectional'), (12, 'IO12',      'bidirectional'),
    (13, 'IO13',     'bidirectional'), (14, 'IO14',      'bidirectional'),

    (15, 'IO44/RXD0','bidirectional'), (16, 'IO43/TXD0', 'bidirectional'),
    (17, 'IO3',      'bidirectional'), (18, 'IO38',      'bidirectional'),
    (19, 'IO7',      'bidirectional'), (20, 'IO18',      'bidirectional'),
    (21, 'IO9',      'bidirectional'), (22, 'IO0',       'bidirectional'),
    (23, 'IO1',      'bidirectional'), (24, 'IO2',       'bidirectional'),
    (25, 'IO16',     'bidirectional'), (26, 'IO15',      'bidirectional'),
    (27, 'IO17',     'bidirectional'), (28, 'GND',       'power_out'),
    # only one GND pin drives the net; the other two are passive so ERC does not
    # report three power outputs shorted together
    (29, 'GND',      'passive'),       (30, 'GND',       'passive'),
    (31, '3V3',      'power_out'),     (32, 'CHIP_EN',   'input'),
]
# which FireBeetle pin each carrier signal lands on
# Keyed by GPIO name so each choice can be checked against the ESP32-S3 datasheet.
#   ACQUIRE_BUTTON must be an RTC GPIO (0-21) to wake the part from deep sleep on EXT1.
#   SUPPLY_SENSE must be on ADC1 (GPIO1-10); ADC2 is unusable while Wi-Fi is up.
#   IO0 carries the board's own K3 boot button, IO43/IO44 are the UART0 console, and
#   IO3 is a strapping pin - all three are left alone.
NET_ON_GPIO = {
    'IO12': 'ACCEL_SCK',   'IO11': 'ACCEL_MOSI',  'IO13': 'ACCEL_MISO',
    'IO10': 'ACCEL_CS',    'IO14': 'ACCEL_DRDY',  'IO16': 'MAG_TACH',
    'IO17': 'OPT_LED_EN',  'IO15': 'OPT_TACH',    'IO18': 'STATUS_LED',
    'IO4':  'ACQUIRE_BUTTON',                     'IO5':  'SUPPLY_SENSE',
    'IO7':  'GPS_UART_TX', 'IO8':  'GPS_UART_RX', 'IO21': 'GPS_PPS',
}
NET_ON_PIN = {num: NET_ON_GPIO[nam] for num, nam, _ in FIREBEETLE_PINS
              if nam in NET_ON_GPIO}
assert len(NET_ON_PIN) == len(NET_ON_GPIO), 'a GPIO in NET_ON_GPIO is not on a header'
_g = {s: int(n[2:]) for n, s in NET_ON_GPIO.items()}
assert 0 <= _g['ACQUIRE_BUTTON'] <= 21, 'ACQUIRE_BUTTON is not an RTC GPIO - cannot wake deep sleep'
assert 1 <= _g['SUPPLY_SENSE'] <= 10, 'SUPPLY_SENSE is not on ADC1 - ADC2 is dead while Wi-Fi runs'

used, custom, instances, pins_of, wires, labels, ncs = {}, {}, [], {}, [], [], []
juncs = []


def rnd(v):
    return round(float(v), 4)


def custom_ic(name, w, h, plist, fp, url):
    s = node('symbol', name, node('pin_names', node('offset', 0.8)),
             node('in_bom', S('yes')), node('on_board', S('yes')),
             prop('Reference', 'U'), prop('Value', name),
             prop('Footprint', fp), prop('Datasheet', url))
    g = node('symbol', name + '_0_1',
             node('rectangle', node('start', -w, h), node('end', w, -h),
                  node('stroke', node('width', 0.254), node('type', S('default'))),
                  node('fill', node('type', S('background')))))
    pp = node('symbol', name + '_1_1')
    for num, nam, typ, x, y, a in plist:
        pp.append(node('pin', S(typ), S('line'), node('at', x, y, a), node('length', 5.08),
                       node('name', nam, node('effects', node('font', node('size', 1.016, 1.016)))),
                       node('number', str(num), node('effects', node('font', node('size', 1.016, 1.016))))))
    s.extend([g, pp])
    custom[name] = s


# --- FireBeetle symbol: power on top/bottom, IO down both sides ---------------
# --- FireBeetle symbol: P3 down the left, P4 down the right, pin 1 at the top --
P3_N, PITCH, PIN_X = 14, 2.54, 30.48
FB_TOP_L, FB_TOP_R = 16.51, 21.59   # symbol y of each side's first pin


def fb_xy(num):
    """Sheet offset (dx, dy) of FireBeetle pin `num` relative to the symbol origin."""
    if num <= P3_N:
        return -PIN_X, -FB_TOP_L + (num - 1) * PITCH
    return PIN_X, -FB_TOP_R + (num - P3_N - 1) * PITCH


_pl = []
for num, nam, typ in FIREBEETLE_PINS:
    dx, dy = fb_xy(num)
    _pl.append((num, nam, typ, dx, -dy, 0 if dx < 0 else 180))
custom_ic('FireBeetle2_ESP32S3', 25.4, 25.4, _pl,
          'BalancerCarrier:FireBeetle2_ESP32S3',
          'https://wiki.dfrobot.com/dfr1145')

custom_ic('SN74LVC1G123DCTR', 10.16, 10.16, [
    (3, '~{CLR}', 'input', -15.24, 5.08, 0), (2, 'B', 'input', -15.24, 0, 0),
    (1, '~{A}', 'input', -15.24, -5.08, 0),
    (5, 'Q', 'output', 15.24, 5.08, 180), (7, 'RCext', 'passive', 15.24, -2.54, 180),
    (6, 'Cext', 'passive', 15.24, -7.62, 180),
    (8, 'VCC', 'power_in', 0, 15.24, 270), (4, 'GND', 'power_in', 0, -15.24, 90)],
    'Package_SO:SSOP-8_2.95x2.8mm_P0.65mm',
    'https://www.ti.com/lit/ds/symlink/sn74lvc1g123.pdf')

custom_ic('SN74LVC1G132DBVR', 10.16, 7.62, [
    (1, 'A', 'input', -15.24, 2.54, 0), (2, 'B', 'input', -15.24, -2.54, 0),
    (4, 'Y', 'output', 15.24, 0, 180),
    (5, 'VCC', 'power_in', 0, 12.7, 270), (3, 'GND', 'power_in', 0, -12.7, 90)],
    'Package_TO_SOT_SMD:SOT-23-5',
    'https://www.ti.com/lit/ds/symlink/sn74lvc1g132.pdf')

# Pin geometry and names copied from BalancerREF's U2 so the two symbols agree.
custom_ic('IIS3DWBTR', 12.7, 12.7, [
    (12, 'CS',  'input',  -17.78, 7.62, 0),   (13, 'SPC', 'input',  -17.78, 2.54, 0),
    (14, 'SDI', 'input',  -17.78, -2.54, 0),  (1,  'SDO', 'output', -17.78, -7.62, 0),
    (4,  'INT1', 'output', 17.78, 7.62, 180), (9,  'INT2', 'output', 17.78, 2.54, 180),
    (10, 'RES', 'no_connect', 17.78, -2.54, 180),
    (11, 'RES', 'no_connect', 17.78, -7.62, 180),
    (8,  'VDD', 'power_in', -2.54, 17.78, 270),
    (5,  'VDD_IO', 'power_in', 2.54, 17.78, 270),
    (6,  'GND', 'power_in', -7.62, -17.78, 90),
    (7,  'GND', 'power_in', -2.54, -17.78, 90),
    (2,  'RES_GND', 'passive', 2.54, -17.78, 90),
    (3,  'RES_GND', 'passive', 7.62, -17.78, 90)],
    'Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y',
    'https://www.st.com/resource/en/datasheet/iis3dwb.pdf')

custom_ic('LM1815MX_NOPB', 15.24, 17.78, [
    (8, 'VCC', 'power_in', 0, 22.86, 270), (2, 'GND', 'power_in', 0, -22.86, 90),
    (3, 'VR_IN', 'input', -20.32, 10.16, 0), (5, 'MODE', 'input', -20.32, 5.08, 0),
    (9, 'TIMING_IN', 'input', -20.32, 0, 0), (11, 'INPUT_SEL', 'input', -20.32, -5.08, 0),
    (1, 'NC', 'no_connect', -20.32, -10.16, 0), (4, 'NC', 'no_connect', -20.32, -12.7, 0),
    (6, 'NC', 'no_connect', -20.32, -15.24, 0),
    (12, 'PULSE_OC', 'open_collector', 20.32, 10.16, 180),
    (14, 'RC_TIMING', 'passive', 20.32, 2.54, 180),
    (7, 'PEAK_DET', 'passive', 20.32, -7.62, 180),
    (10, 'GATED_OUT', 'output', 20.32, -12.7, 180), (13, 'NC', 'no_connect', 20.32, -15.24, 180)],
    'Package_SO:SOIC-14_3.9x8.7mm_P1.27mm',
    'https://www.ti.com/lit/ds/symlink/lm1815.pdf')


# ---------------------------------------------------------------- placement API
def place(ref, lib, value, x, y, angle=0, fp=None, mirror=None, unit=1):
    """Drop a symbol and remember where each of its pins landed."""
    used.setdefault(lib, None)
    sym = node('symbol', node('lib_id', lib), node('at', rnd(x), rnd(y), angle),
               node('unit', unit), node('exclude_from_sim', S('no')),
               node('in_bom', S('yes')), node('on_board', S('yes')),
               node('dnp', S('no')), node('uuid', uid()))
    if mirror:
        sym.insert(3, node('mirror', S(mirror)))
    sym.append(prop('Reference', ref, x + 5.08, y - 1.27, hide=False))
    sym.append(prop('Value', value, x + 5.08, y + 1.27, hide=False))
    if fp:
        sym.append(prop('Footprint', fp, x, y))
    sym.append(prop('Datasheet', '', x, y))
    sym.append(node('instances', node('project', 'BalancerCarrier',
                                      node('path', '/' + SHEET,
                                           node('reference', ref), node('unit', unit)))))
    instances.append(sym)
    return sym


def wire(a, b):
    a, b = (rnd(a[0]), rnd(a[1])), (rnd(b[0]), rnd(b[1]))
    assert a[0] == b[0] or a[1] == b[1], ('not orthogonal', a, b)
    if a != b:
        wires.append(node('wire', node('pts', node('xy', *a), node('xy', *b)),
                          node('stroke', node('width', 0), node('type', S('default'))),
                          node('uuid', uid())))


def label(net, x, y, angle=0):
    labels.append(node('label', net, node('at', rnd(x), rnd(y), angle),
                       node('effects', node('font', node('size', 1.27, 1.27)),
                            node('justify', S('left'), S('bottom'))), node('uuid', uid())))


def stub(net, frm, to, angle=0):
    """A short wire off a pin ending in a local label - how this project moves
    signals between blocks."""
    wire(frm, to)
    label(net, to[0], to[1], angle)


print('BalancerCarrier generator - FireBeetle 2 ESP32-S3 carrier')
print('  %d FireBeetle pins, %d signals mapped' % (len(FIREBEETLE_PINS), len(NET_ON_PIN)))
free = [p for p in FIREBEETLE_PINS if p[1].startswith('IO') and p[0] not in NET_ON_PIN]
print('  spare GPIO: %s' % ' '.join(n for _, n, _ in free))


# ---------------------------------------------------------------- helpers
R, C, LED = 'Device:R', 'Device:C', 'Device:LED'
FP_R, FP_C = 'Resistor_SMD:R_0603_1608Metric', 'Capacitor_SMD:C_0805_2012Metric'
# the VR sensor's series pair must keep BalancerREF's 1206 body: the pulse withstand
# that lets them take +/-60 V peaks is a function of body size, not resistance
FP_R1206 = 'Resistor_SMD:R_1206_3216Metric'
FP_SOT23 = 'Package_TO_SOT_SMD:SOT-23'
_n = [0]


def pwr(lib, val, x, y):
    _n[0] += 1
    place('#PWR%03d' % _n[0], lib, val, x, y)


def gnd(x, y):
    pwr('power:GND', 'GND', x, y)


def v3v3(x, y):
    pwr('power:+3V3', '+3V3', x, y)


def vpart(ref, lib, val, x, y, fp, top_net=None, bot_net=None):
    """Vertical two-pin part; pin 1 is 3.81 above centre, pin 2 is 3.81 below."""
    place(ref, lib, val, x, y, 0, fp)
    hi, lo = (x, y - 3.81), (x, y + 3.81)
    if top_net:
        stub(top_net, hi, (x, y - 7.62), 90)
    if bot_net:
        stub(bot_net, lo, (x, y + 7.62), 270)
    return hi, lo


def to_gnd(ref, lib, val, x, y, fp, net):
    """Two-pin part hanging from `net` down to its own ground symbol."""
    place(ref, lib, val, x, y, 0, fp)
    stub(net, (x, y - 3.81), (x, y - 7.62), 90)
    wire((x, y + 3.81), (x, y + 7.62))
    gnd(x, y + 7.62)


def to_3v3(ref, lib, val, x, y, fp, net):
    place(ref, lib, val, x, y, 0, fp)
    wire((x, y - 3.81), (x, y - 7.62))
    v3v3(x, y - 7.62)
    stub(net, (x, y + 3.81), (x, y + 7.62), 270)


def conn_pins(x, y, n, rot):
    """Pin coordinates of a Connector_Generic:Conn_01xNN. Its pins sit at local
    x = -5.08, so at rotation 0 they are on the LEFT of the placement point - which
    is the opposite of what you draw if you go by eye."""
    # Conn_01x02 is not vertically centred: its pin 1 is at local y = 0 and pin 2
    # at -2.54, unlike 01x05/01x07 which straddle the origin. Verified against the
    # symbol definitions, not assumed.
    off = 0.0 if n == 2 else (n - 1) * 2.54 / 2.0
    if rot == 0:
        return x - 5.08, [y - off + i * 2.54 for i in range(n)]
    if rot == 180:
        return x + 5.08, [y + off - i * 2.54 for i in range(n)]
    raise ValueError(rot)


def conn(ref, val, x, y, n, rot, fp, nets, out=10.16):
    """Place a connector and stub each pin to a label, ground or 3V3."""
    place(ref, 'Connector_Generic:Conn_01x%02d' % n, val, x, y, rot, fp)
    px, ys = conn_pins(x, y, n, rot)
    d = -1 if rot == 0 else 1
    for net, py in zip(nets, ys):
        if net == '+3V3':
            wire((px, py), (px + d * 5.08, py)); v3v3(px + d * 5.08, py)
        elif net == 'GND':
            wire((px, py), (px + d * 5.08, py)); gnd(px + d * 5.08, py)
        elif net:
            stub(net, (px, py), (px + d * out, py), 180 if d < 0 else 0)
        else:
            nc(px, py)


def junction(x, y):
    juncs.append(node('junction', node('at', rnd(x), rnd(y)), node('diameter', 0),
                      node('color', 0, 0, 0, 0), node('uuid', uid())))


def nc(x, y):
    ncs.append(node('no_connect', node('at', rnd(x), rnd(y)), node('uuid', uid())))


# ================================================================ B1 FireBeetle
FBX, FBY = 299.72, 120.65
place('U1', 'BalancerCarrier:FireBeetle2_ESP32S3', 'FireBeetle2 ESP32-S3 N16R8',
      FBX, FBY, 0, 'BalancerCarrier:FireBeetle2_ESP32S3')
GND_BUS_X, V3_X = FBX + 38.1, FBX + 45.72
_gnd_ys = []
for num, nam, typ in FIREBEETLE_PINS:
    dx, dy = fb_xy(num)
    px, py = FBX + dx, FBY + dy
    out = -10.16 if dx < 0 else 10.16
    ang = 180 if dx < 0 else 0
    if nam == 'VCC':
        stub('VCC_SYS', (px, py), (px + out, py), ang)
    elif nam == 'GND':
        wire((px, py), (GND_BUS_X, py)); _gnd_ys.append(py)
    elif nam == '3V3':
        wire((px, py), (V3_X, py)); wire((V3_X, py), (V3_X, py - 7.62))
        v3v3(V3_X, py - 7.62)
    elif NET_ON_PIN.get(num):
        stub(NET_ON_PIN[num], (px, py), (px + out, py), ang)
    else:
        nc(px, py)
# the three GND pins are adjacent rows; bus them and drop one symbol at the bottom
wire((GND_BUS_X, min(_gnd_ys)), (GND_BUS_X, max(_gnd_ys)))
for y in _gnd_ys[1:-1]:
    junction(GND_BUS_X, y)
gnd(GND_BUS_X, max(_gnd_ys))

# ================================================================ B2 (removed)
# The cell plugs straight into the FireBeetle's own J1. Nothing here.
#
# DFR0975-U schematic V1.3 sheet 1 shows Q2 (AO3400, N-channel) sitting in the
# battery's LOW side between the connector's negative pin and BAT-, with its gate
# taken from VBAT+. That is reverse-polarity protection, and a better arrangement
# than the discrete P-FET pair this carrier used to carry: one FET instead of three,
# in the return path so no gate-drive network is needed, and no standing drain on
# the cell. Z1 (ESD5B5.0ST1G) clamps the battery terminals as well.
#
# So J1, J2, Q1, Q2, Q3, R1-R4 and C1 all came out - ten parts and two connectors
# deleted, and the loop-back cable with them.

# ================================================================ B3 mag tach
MX, MY = 88.9, 144.78
place('U2', 'BalancerCarrier:LM1815MX_NOPB', 'LM1815MX/NOPB', MX, MY, 0,
      'Package_SO:SOIC-14_3.9x8.7mm_P1.27mm')
wire((MX, MY - 22.86), (MX, MY - 27.94)); v3v3(MX, MY - 27.94)
wire((MX, MY + 22.86), (MX, MY + 27.94)); gnd(MX, MY + 27.94)
for px, py in ((-20.32, -10.16), (-20.32, -12.7), (-20.32, -15.24),
               (20.32, -15.24), (20.32, -12.7), (-20.32, 5.08)):
    nc(MX + px, MY - py)
stub('VR_IN', (MX - 20.32, MY - 10.16), (MX - 30.48, MY - 10.16), 180)
# Pin 9 (TIMING_IN) and pin 11 (INPUT_SEL) are CMOS/TTL LOGIC inputs, not timing nodes.
# SNOSBU8F: "External pulse inputs at pin 9 are gated through to pin 10 when Input Select
# (pin 11) is pulled high", logic threshold 0.8/1.1/2.0 V, bias 5 uA. Driving pin 9 from
# the one-shot RC would load the timing node and slew a logic input through its threshold
# band. Both are grounded, matching BalancerREF U3. The one shot lives on pin 14 alone.
wire((MX - 20.32, MY), (MX - 27.94, MY))
wire((MX - 20.32, MY + 5.08), (MX - 27.94, MY + 5.08))
wire((MX - 27.94, MY), (MX - 27.94, MY + 5.08))
gnd(MX - 27.94, MY + 5.08)
stub('MAG_TACH', (MX + 20.32, MY - 10.16), (MX + 30.48, MY - 10.16))
stub('MAG_TIMING', (MX + 20.32, MY - 2.54), (MX + 30.48, MY - 2.54))
stub('MAG_PEAK', (MX + 20.32, MY + 7.62), (MX + 30.48, MY + 7.62))

conn('J3', 'MAG+ / MAG- PTH', 20.32, 119.38, 2, 180,
     'Connector_Wire:SolderWire-0.1sqmm_1x02_P3.6mm_D0.4mm_OD1mm', ('MAG_IN', 'GND'))
place('R5', R, '10k 1206 pulse', 43.18, 119.38, 90, FP_R1206)
place('R6', R, '10k 1206 pulse', 53.34, 119.38, 90, FP_R1206)
stub('MAG_IN', (39.37, 119.38), (33.02, 119.38), 180)
wire((46.99, 119.38), (49.53, 119.38))
wire((57.15, 119.38), (58.42, 119.38)); wire((58.42, 119.38), (58.42, 134.62))
stub('VR_IN', (58.42, 134.62), (48.26, 134.62), 180)

# One shot on pin 14: pulse width = 0.673 x R x C = 0.673 x 150k x 1n = 101 us, and
# Fin(max) = 1/(1.346 x R x C) = 5 kHz. R and C are in SERIES ACROSS THE SUPPLY with
# pin 14 at their junction - R up to +3V3, C down to GND. Not both to ground; that is
# the peak-store network on pin 7 (R8/C3 below). 150k is the datasheet's recommended
# maximum for R. Matches BalancerREF R16/C18.
to_3v3('R7', R, '150k 1%', 139.7, 149.86, FP_R, 'MAG_TIMING')
to_gnd('C2', C, '1n C0G', 149.86, 149.86, FP_C, 'MAG_TIMING')
to_gnd('R8', R, '1.6M', 160.02, 149.86, FP_R, 'MAG_PEAK')
to_gnd('C3', C, '330n', 170.18, 149.86, FP_C, 'MAG_PEAK')
to_3v3('R9', R, '5.6k', 129.54, 172.72, FP_R, 'MAG_TACH')

# ================================================================ B4 optical
OX, OY = 88.9, 226.06
place('U3', 'BalancerCarrier:SN74LVC1G132DBVR', 'SN74LVC1G132DBVR', OX, OY, 0,
      'Package_TO_SOT_SMD:SOT-23-5')
wire((OX, OY - 12.7), (OX, OY - 17.78)); v3v3(OX, OY - 17.78)
wire((OX, OY + 12.7), (OX, OY + 17.78)); gnd(OX, OY + 17.78)
stub('OPT_COMP', (OX - 15.24, OY - 2.54), (OX - 25.4, OY - 2.54), 180)
stub('SYNC_DELAY', (OX - 15.24, OY + 2.54), (OX - 25.4, OY + 2.54), 180)
stub('SYNC_HIT', (OX + 15.24, OY), (OX + 25.4, OY))

UX, UY = 165.1, 226.06
place('U4', 'BalancerCarrier:SN74LVC1G123DCTR', 'SN74LVC1G123DCTR', UX, UY, 0,
      'Package_SO:SSOP-8_2.95x2.8mm_P0.65mm')
wire((UX, UY - 15.24), (UX, UY - 20.32)); v3v3(UX, UY - 20.32)
wire((UX, UY + 15.24), (UX, UY + 20.32)); gnd(UX, UY + 20.32)
# SCES586E (rev E, March 2024) section 4 Pin Functions, verbatim:
#   pin 1 A    "Falling edge sensitive input; requires B and CLR to be held high."
#   pin 2 B    "Rising edge sensitive input; requires A to be held low and CLR high."
#   pin 3 CLR  "Clear, Active Low; also can operate as rising edge sensitive input..."
# U3 is a NAND, so Y falls on a detection - the trigger therefore belongs on A, with B
# and CLR both high, exactly as BalancerREF U10 does it. Driving CLR with the trigger
# and strapping A high (as this block did until 2026-09-20) leaves the one shot unable
# to fire at all. Section 5.3 note 1 also requires every unused input to sit at VCC or
# GND, which is the second reason B and CLR are tied up rather than left open.
stub('SYNC_HIT', (UX - 15.24, UY + 5.08), (UX - 25.4, UY + 5.08), 180)
wire((UX - 15.24, UY), (UX - 20.32, UY))
wire((UX - 15.24, UY - 5.08), (UX - 20.32, UY - 5.08))
wire((UX - 20.32, UY), (UX - 20.32, UY - 12.7)); junction(UX - 20.32, UY - 5.08)
v3v3(UX - 20.32, UY - 12.7)
stub('OPT_TACH', (UX + 15.24, UY - 5.08), (UX + 25.4, UY - 5.08))
stub('OPT_RCEXT', (UX + 15.24, UY + 2.54), (UX + 25.4, UY + 2.54))
stub('OPT_CEXT', (UX + 15.24, UY + 7.62), (UX + 25.4, UY + 7.62))

# SCES586E section 5.8: the characterised points are Cext 0.01 uF / Rext 10 k -> tw
# 100-110 us, and Cext 0.1 uF / Rext 10 k -> 1-1.1 ms, i.e. tw ~= Rext x Cext for any
# Cext large enough to swamp the ~40 pF internal Cpd. 100 k x 1 n therefore gives about
# 100 us, matching BalancerREF U10.
#
# 10 k / 10 n is the characterised row itself, so tw is a guaranteed 100-110 us across
# all four supply voltages and both temperature ranges - not a reading off the typical
# curves. The board ran 100 k / 1 n until 2026-09-20; that is legal (section 5.3 gives
# Rext a MINIMUM of 1 k at VCC >= 3 V and states no maximum) but sits ten times beyond
# the largest value TI characterises, and drives the timing node with only 33 uA.
# BalancerREF R30/C28 were changed to match.
#
# Section 5.3 note 2: "Rext/Cext is an I/O and must not be connected directly to GND or
# VCC" - satisfied, the 100 k is in series.
to_3v3('R10', R, '10k', 208.28, 213.36, FP_R, 'OPT_RCEXT')
place('C4', C, '10n C0G', 208.28, 236.22, 90, FP_C)
stub('OPT_RCEXT', (204.47, 236.22), (194.31, 236.22), 180)
stub('OPT_CEXT', (212.09, 236.22), (222.25, 236.22))

place('R11', R, '1k', 45.72, 233.68, 90, FP_R)
stub('OPT_LED_EN', (41.91, 233.68), (31.75, 233.68), 180)
wire((49.53, 233.68), (53.34, 233.68))
stub('SYNC_DELAY', (53.34, 233.68), (63.5, 233.68))
to_gnd('C5', C, '470p C0G', 53.34, 248.92, FP_C, 'SYNC_DELAY')
to_gnd('R12', R, '100k', 63.5, 248.92, FP_R, 'SYNC_DELAY')
to_gnd('R13', R, '100k', 33.02, 205.74, FP_R, 'OPT_COMP')

conn('J5', 'OPTICAL HEAD 7-WAY', 25.4, 274.32, 7, 180,
     'Connector_JST:JST_GH_SM07B-GHS-TB_1x07-1MP_P1.25mm_Horizontal',
     ('VCC_SYS', 'GND', 'OPT_LED_EN', 'GND', 'OPT_COMP', 'GND', '+3V3'))

# ================================================================ B5 connectors
conn('J4', 'GPS MODULE 3V3 UART', 378.46, 45.72, 5, 0,
     'Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical',
     ('+3V3', 'GND', 'GPS_UART_RX', 'GPS_UART_TX', 'GPS_PPS'))

# The IIS3DWB is soldered down rather than cabled out on J6, copying BalancerREF's U2
# block whole. Checked against DS12569 rev 8 Table 1 (Pin description) on 2026-09-20:
#   pin 2, 3   RES "Connect to VDD_IO or GND"                 -> GND, allowed
#   pin 6, 7   GND                                            -> GND
#   pin 5 VDD_IO, pin 8 VDD, both "Recommended 100 nF filter" -> C12, C11
#   pin 9      INT2, programmable interrupt                   -> unused, left open
#   pin 10, 11 RES "Connect to VDD_IO or leave unconnected"   -> open
#   pin 12 CS, 13 SPC, 14 SDI, 1 SDO, 4 INT1                  -> the SPI bus + DRDY
# Supply range is 2.1-3.6 V so 3V3 is fine (absolute max 4.8 V on any pin), and SPI runs
# to 10 MHz. LAYOUT NOTE: Table 1 note 3 says pins 10 and 11 must be "electrically
# unconnected AND SOLDERED TO PCB" - keep their pads, do not delete them as unused.
AX, AY = 370.84, 172.72   # both multiples of 2.54
place('U5', 'BalancerCarrier:IIS3DWBTR', 'IIS3DWBTR', AX, AY, 0,
      'Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y')
for net, dy in (('ACCEL_CS', -7.62), ('ACCEL_SCK', -2.54),
                ('ACCEL_MOSI', 2.54), ('ACCEL_MISO', 7.62)):
    stub(net, (AX - 17.78, AY + dy), (AX - 27.94, AY + dy), 180)
stub('ACCEL_DRDY', (AX + 17.78, AY - 7.62), (AX + 27.94, AY - 7.62))
for dy in (-2.54, 2.54, 7.62):          # INT2 and the two RES pins
    nc(AX + 17.78, AY + dy)
# VDD and VDD_IO bussed up to +3V3
wire((AX - 2.54, AY - 17.78), (AX + 2.54, AY - 17.78))
wire((AX, AY - 17.78), (AX, AY - 25.4)); junction(AX, AY - 17.78)
v3v3(AX, AY - 25.4)
# the four ground pins bussed down
wire((AX - 7.62, AY + 17.78), (AX + 7.62, AY + 17.78))
wire((AX, AY + 17.78), (AX, AY + 25.4))
for jx in (-2.54, 0.0, 2.54):        # pins 7 and 2 are mid-span, as is the drop to GND
    junction(AX + jx, AY + 17.78)
gnd(AX, AY + 25.4)
for ref, cx in (('C11', 320.04), ('C12', 332.74)):
    place(ref, C, '100n', cx, AY, 0, FP_C)
    wire((cx, AY - 3.81), (cx, AY - 7.62)); v3v3(cx, AY - 7.62)
    wire((cx, AY + 3.81), (cx, AY + 7.62)); gnd(cx, AY + 7.62)

# ================================================================ B6 UI + sense
place('SW1', 'Switch:SW_Push', 'ACQUIRE', 271.78, 220.98, 0,
      'Button_Switch_THT:SW_PUSH_6mm')
stub('ACQUIRE_BUTTON', (266.7, 220.98), (256.54, 220.98), 180)
wire((276.86, 220.98), (281.94, 220.98)); gnd(281.94, 220.98)
to_3v3('R14', R, '10k', 246.38, 210.82, FP_R, 'ACQUIRE_BUTTON')
to_gnd('C6', C, '10n', 236.22, 233.68, FP_C, 'ACQUIRE_BUTTON')

place('LED1', LED, 'STATUS GREEN', 311.15, 220.98, 0,
      'LED_SMD:LED_0603_1608Metric')
place('R15', R, '1k', 297.18, 220.98, 90, FP_R)
stub('STATUS_LED', (293.37, 220.98), (283.21, 220.98), 180)
wire((300.99, 220.98), (307.34, 220.98))
wire((314.96, 220.98), (320.04, 220.98)); gnd(320.04, 220.98)

vpart('R20', R, '100k', 350.52, 205.74, FP_R, 'VCC_SYS', 'SUPPLY_SENSE')
to_gnd('R21', R, '100k', 350.52, 226.06, FP_R, 'SUPPLY_SENSE')
# BalancerREF carries C12 100n across the bottom leg of this divider; the carrier had
# dropped it. VCC is the output of a switching charger's power path, so the ADC node
# needs the filter more here than it did there.
to_gnd('C10', C, '100n', 363.22, 226.06, FP_C, 'SUPPLY_SENSE')

for ref, val, x in (('C7', '100n', 215.9), ('C8', '100n', 226.06), ('C9', '10u 10V', 236.22)):
    place(ref, C, val, x, 271.78, 0, FP_C)
    wire((x, 267.97), (x, 264.16)); v3v3(x, 264.16)
    wire((x, 275.59), (x, 279.4)); gnd(x, 279.4)

# ---------------------------------------------------------------- emit
doc = node('kicad_sch', node('version', 20260306), node('generator', 'build_carrier'),
           node('generator_version', '10.0'), node('uuid', SHEET),
           node('paper', 'A3'),
           node('title_block', node('title', 'HOBOVibe Carrier - FireBeetle 2 ESP32-S3'),
                node('date', '2026-09-20'), node('rev', 'A'),
                node('comment', 1, 'Instrument only; MCU, USB and charging on the dev board')))
libs = node('lib_symbols')
for name, s in custom.items():
    c = deepcopy(s)
    c[1] = 'BalancerCarrier:' + name
    for sub in children(c, 'symbol'):
        sub[1] = name + sub[1][len(name):]
    libs.append(c)
for lib in sorted(used):
    if lib.startswith('BalancerCarrier:'):
        continue
    src, nm = lib.split(':')
    s = standard(src, nm)
    s[1] = lib
    libs.append(s)
doc.append(libs)
doc.extend(wires)
doc.extend(juncs)
doc.extend(ncs)
doc.extend(labels)
doc.extend(instances)
doc.append(node('sheet_instances', node('path', '/', node('page', '1'))))
doc.append(node('embedded_fonts', S('no')))

print('  symbols %d   wires %d   labels %d   no-connects %d'
      % (len(instances), len(wires), len(labels), len(ncs)))

if not APPLY:
    print('\nDRY RUN - nothing written.  Pass --apply.')
    sys.exit(0)

SYM = ROOT / 'BalancerCarrier.kicad_sym'
lib = node('kicad_symbol_lib', node('version', 20241209),
           node('generator', 'build_carrier'))
for _name, _s in custom.items():
    lib.append(deepcopy(_s))
SYM.write_text(dump(lib) + chr(10), encoding='utf8')
(ROOT / 'sym-lib-table').write_text(
    '(sym_lib_table (version 7) (lib (name "BalancerCarrier")(type "KiCad")'
    '(uri "${KIPRJMOD}/BalancerCarrier.kicad_sym")(options "")'
    '(descr "Generated carrier symbols")))' + chr(10), encoding='utf8')

SCH.write_text(dump(doc) + '\n', encoding='utf8')
subprocess.run([KC, 'sch', 'upgrade', '--force', str(SCH)], capture_output=True, check=True)
txt = SCH.read_text(encoding='utf8').rstrip('\n')
if '\n\t(embedded_fonts' not in txt:
    SCH.write_text(txt[:-2] + '\n\t(embedded_fonts no)\n)\n', encoding='utf8')
print('\nwrote %s' % SCH.name)
