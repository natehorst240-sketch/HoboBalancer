"""Check BalancerCarrier firmware GPIO assignments against the board as manufactured.

Run: python BalancerCarrier/firmware/tests/check_pinmap.py

Differences from BalancerREF's version, both deliberate:

  Source of truth (changed 2026-11-09). This now reads manufactured/as-built-pads.csv: the
  pad -> net table extracted from the Gerber X2 attributes of the package actually sent to
  the fab (scripts/gerber_pads.py, provenance in manufactured/SOURCE.txt). The exported
  BalancerCarrier.net had gone stale against the PCB (GPIO7 and all of J4 unconnected,
  J5.5 on GND), so this test failed on a netlist that was never built. The board that exists
  is the reference; a later board revision gets a new as-built table.

  Earlier source, kept for the record: BalancerREF's test reads review/IC-pin-audit.csv and says so in its
  own docstring: "this test is only as current as the last run of that". A generated
  CSV that nobody re-runs is not a guard. This reads BalancerCarrier.net, exported
  straight from the schematic, and REFUSES TO PASS if the .kicad_sch is newer - so
  staleness fails loudly instead of quietly certifying an old layout.

  Constraint checks. Matching net names is not enough. MAG_TACH sat on GPIO33 from the
  FeatherS3[D] swap until 2026-09-21: the net name matched, pulse capture worked, and
  EXT1 rotor-spin wake silently could not arm, because GPIO33 is outside the ESP32-S3's
  22 RTC GPIOs. A name-only check would have passed that. So this also asserts the
  electrical constraints each signal actually depends on.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]          # BalancerCarrier/
ASBUILT = ROOT / 'manufactured/as-built-pads.csv'
HPP = ROOT / 'firmware/src/board.hpp'

# ESP32-S3 facts, from the datasheet and CONFIG_SOC_RTCIO_PIN_COUNT
RTC_GPIO = range(0, 22)      # EXT1 deep-sleep wake is only possible on these
ADC1_GPIO = range(1, 11)     # ADC2 is unusable while Wi-Fi is up
RESERVED = {0: 'module boot button', 3: 'strapping pin', 43: 'UART0 console',
            44: 'UART0 console'}

# firmware name -> (schematic net, constraints it depends on)
EXPECTED = {
    'drdy':      ('ACCEL_DRDY', set()),
    'mag':       ('MAG_TACH', {'rtc'}),          # EXT1 wake: rotor spin-up
    'opt':       ('OPT_TACH', set()),
    'emitter':   ('OPT_LED_EN', set()),
    'acquire':   ('ACQUIRE_BUTTON', {'rtc'}),    # EXT1 wake: button press
    'led':       ('STATUS_LED', set()),
    'gpsTx':     ('GPS_UART_TX', set()),
    'gpsRx':     ('GPS_UART_RX', set()),
    'gpsPps':    ('GPS_PPS', set()),
    'accelSck':  ('ACCEL_SCK', set()),
    'accelMosi': ('ACCEL_MOSI', set()),
    'accelMiso': ('ACCEL_MISO', set()),
    'accelCs':   ('ACCEL_CS', set()),
}

# The far end of each signal on the built board: (ref, pin) that must sit on the same net.
# U5 IIS3DWB LGA-14: 1 SDO, 4 INT1, 12 CS, 13 SPC, 14 SDI. U2 LM1815 pin 12 reference pulse
# (open collector). U4 '1G123 pin 5 Q. J4 per audit_pins.py: 3 = GPS TX -> MCU RX,
# 4 = GPS RX <- MCU TX, 5 = PPS. J5 pin 3 = emitter command to the optical head.
FAR_END = {
    'ACCEL_DRDY': [('U5', '4')], 'ACCEL_SCK': [('U5', '13')], 'ACCEL_MOSI': [('U5', '14')],
    'ACCEL_MISO': [('U5', '1')], 'ACCEL_CS': [('U5', '12')],
    'MAG_TACH': [('U2', '12')], 'OPT_TACH': [('U4', '5')], 'OPT_LED_EN': [('J5', '3')],
    'ACQUIRE_BUTTON': [('SW1', '1')], 'STATUS_LED': [('R15', '1')],
    'GPS_UART_RX': [('J4', '3')], 'GPS_UART_TX': [('J4', '4')], 'GPS_PPS': [('J4', '5')],
    'GPS_3V3': [('J4', '1')],    # LDO2_OUT, switched by the module-internal ldo2 pin
}

# Fixed by the FeatherS3[D] itself, so they are in no carrier netlist and cannot be
# checked against the schematic. Values from unexpectedmaker/esp32s3 - the MicroPython
# helper gives LDO2 = const(39) and VBUS_SENSE = const(34); the I2C pins are the
# module's own bus, carrying the MAX17048 and the STEMMA QT connector. Checked here so
# a typo still fails rather than silently driving the wrong pin.
MODULE_INTERNAL = {'ldo2': 39, 'vbusSense': 34, 'i2cSda': 8, 'i2cScl': 9}


def fail(msg):
    print('FAIL: ' + msg)
    sys.exit(1)


if not ASBUILT.exists():
    fail(f'{ASBUILT} is missing; regenerate it with scripts/gerber_pads.py from the fab package')

# ---- what was built: U1 GPIO number -> net name, and every (ref, pin) -> net ----------
pad_net = {}
sch_gpio = {}
for line in ASBUILT.read_text(encoding='utf8').splitlines()[1:]:
    ref, pin, fn, net = line.split(',', 3)
    net = net.lstrip('/')
    pad_net[(ref, pin)] = net
    m = re.match(r'IO(\d+)_\d+$', fn)
    if ref == 'U1' and m:
        sch_gpio[int(m.group(1))] = net
if not sch_gpio:
    fail('could not read any U1 GPIO pads from the as-built table')

# ---- what firmware says: name -> GPIO number -------------------------------
decls = ';'.join(re.findall(r'^\s*constexpr\s+int\s+([^;]*);', HPP.read_text(encoding='utf8'), re.M))
pins = {k: int(v) for k, v in re.findall(r'\b(\w+)=(\d+)', decls)}
if not pins:
    fail('no constexpr pin declarations found in board.hpp')

problems = []
for name, (signal, needs) in EXPECTED.items():
    if name not in pins:
        problems.append(f'{name}: declared nowhere in board.hpp')
        continue
    g = pins[name]
    actual = sch_gpio.get(g)
    if actual is None:
        problems.append(f'{name}=GPIO{g}: the built board has no U1 pad for that GPIO')
    elif actual.startswith('unconnected-'):
        problems.append(f'{name}=GPIO{g}: that pad is unconnected on the built board')
    elif actual != signal:
        problems.append(f'{name}=GPIO{g}: built board has {actual!r}, expected {signal!r}')
    if g in RESERVED:
        problems.append(f'{name}=GPIO{g}: reserved - {RESERVED[g]}')
    if g in (MODULE_INTERNAL['i2cSda'], MODULE_INTERNAL['i2cScl']):
        problems.append(f'{name}=GPIO{g}: that is the module I2C bus (MAX17048 / STEMMA QT)')
    if 'rtc' in needs and g not in RTC_GPIO:
        problems.append(f'{name}=GPIO{g}: EXT1 deep-sleep wake needs an RTC GPIO (0-21)')
    if 'adc1' in needs and g not in ADC1_GPIO:
        problems.append(f'{name}=GPIO{g}: needs ADC1 (GPIO1-10); ADC2 is dead with Wi-Fi up')

for name, want in MODULE_INTERNAL.items():
    if name not in pins:
        problems.append(f'{name}: declared nowhere in board.hpp')
    elif pins[name] != want:
        problems.append(f'{name}=GPIO{pins[name]}: the FeatherS3[D] fixes this at GPIO{want}')

for signal, ends in FAR_END.items():
    for ref, pin in ends:
        got = pad_net.get((ref, pin))
        if got != signal:
            problems.append(f'{signal}: {ref} pin {pin} is on {got!r} on the built board')
if pad_net.get(('U1', '13')) != 'GPS_3V3':
    problems.append('GPS_3V3: U1 pad 13 (LDO2_OUT) does not feed it on the built board')

# the silent-gap case: a pin added to board.hpp but never checked here
uncovered = sorted(set(pins) - set(EXPECTED) - set(MODULE_INTERNAL))
if uncovered:
    problems.append(f'board.hpp pins not covered by this test: {uncovered}')

if problems:
    print(f'FAIL: {len(problems)} problem(s)')
    for p in problems:
        print('  - ' + p)
    sys.exit(1)

wake = [f'{n}=GPIO{pins[n]}' for n, (_, c) in EXPECTED.items() if 'rtc' in c]
print(f'PASS: {len(EXPECTED)} header signals match the as-built board, '
      f'{len(MODULE_INTERNAL)} module-internal pins match the FeatherS3[D]; '
      f'all {len(pins)} board.hpp pins covered.')
print(f'      {sum(len(v) for v in FAR_END.values())} far-end pads (IIS3DWB, LM1815, one-shot, J4, J5, button, LED) on the right nets')
print(f'      EXT1 wake sources all on RTC GPIO: {", ".join(wake)}')
