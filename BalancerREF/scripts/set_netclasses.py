"""Set track-width / clearance net classes on both projects.

Widths are sized from IPC-2221 for 1 oz outer copper at a 10 C rise
(I = 0.048 * dT^0.44 * A^0.725, A in mil^2):

    0.20 mm  ->  0.74 A      signals
    0.50 mm  ->  1.45 A      power rails
    0.80 mm  ->  2.03 A      switching node / emitter loop

Inner layers carry roughly half that (k = 0.024), which matters on the main board's
In1/In2 but not for the classes below - power is routed on the outer layers.

Against the actual loads:
  * +3V3 / SYS / SYS_SW / BAT / VBUS - a few hundred mA in normal operation (TPS63031
    feeding an ESP32-S3 on BLE, BQ24075 charging at ~250 mA). 0.5 mm gives about 3x
    margin there. SYS is the one to watch: the BQ24075's power path can pass well over
    an amp to OUT if firmware raises the input limit and the load ever asks for it, so
    keep that run short as well as wide.
  * U6's L1/L2 inductor node sees the full switch current, over an amp in boost at
    low battery, and the highest di/dt on the board. 0.8 mm, kept short.
  * The head board's LED_A / LED_K carry 500 mA pulses at 10% duty. Thermally that
    is only ~50 mA average, so 0.8 mm is about loop inductance and pulse-edge
    integrity rather than heating.

USB D+/D- get their own class so the pair can be tuned and length-matched, but the
numbers here are NOT an impedance solution - that needs the fab's actual stackup.
The ESP32-S3's native USB is Full Speed (12 Mbps), where impedance control is much
less critical than it would be at High Speed.

Dry run by default. Pass --apply to write.
"""
import sys, json, os

APPLY = '--apply' in sys.argv
BASE = r'C:\Users\nateh\hgs-linux\Balancer'

COMMON = {'bus_width': 12, 'line_style': 0, 'microvia_diameter': 0.3,
          'microvia_drill': 0.1, 'pcb_color': 'rgba(0, 0, 0, 0.000)',
          'schematic_color': 'rgba(0, 0, 0, 0.000)', 'tuning_profile': '',
          'wire_width': 6, 'diff_pair_gap': 0.25, 'diff_pair_via_gap': 0.25,
          'diff_pair_width': 0.2}


def cls(name, track, clearance, via_d, via_drill, priority, **kw):
    c = dict(COMMON)
    c.update({'name': name, 'track_width': track, 'clearance': clearance,
              'via_diameter': via_d, 'via_drill': via_drill, 'priority': priority})
    c.update(kw)
    return c


MAIN_CLASSES = [
    cls('Default', 0.20, 0.20, 0.60, 0.30, 2147483647),
    cls('Power',   0.50, 0.20, 0.80, 0.40, 1),
    # Clearance stays at 0.20, not 0.25: the TPS63031's WSON-10 puts its own L1/L2
    # pads 0.20 mm from its thermal pad, so anything stricter fails inside the
    # package itself and no routing choice can fix it. The 0.80 mm track is the
    # point of this class.
    cls('Switch',  0.80, 0.20, 0.80, 0.40, 0),
    cls('USB',     0.20, 0.20, 0.60, 0.30, 2, diff_pair_width=0.20, diff_pair_gap=0.15),
]
# /SYS is the BQ24075's OUT rail and carries the whole system load - charger output
# plus battery, through SW1 into U6. It is the highest-current net on the board after
# the switching node, so it belongs in Power; at the 0.20 mm default it would be rated
# 0.74 A. Net-(D2-K) was the old MCP73831 OR-ing diode and no longer exists.
MAIN_PATTERNS = [
    ('Power', '/+3V3'), ('Power', '/SYS'), ('Power', '/SYS_SW'), ('Power', '/BAT'),
    ('Power', '/USB_VBUS'), ('Power', 'GND'),
    ('Switch', 'Net-(U6-L1)'), ('Switch', 'Net-(U6-L2)'),
    ('USB', '/USB_CONN_D+'), ('USB', '/USB_CONN_D-'),
    ('USB', 'Net-(U1-USB_D+)'), ('USB', 'Net-(U1-USB_D-)'),
]

HEAD_CLASSES = [
    cls('Default', 0.20, 0.20, 0.60, 0.30, 2147483647),
    cls('Power',   0.50, 0.20, 0.80, 0.40, 1),
    cls('Emitter', 0.80, 0.25, 0.80, 0.40, 0),
]
HEAD_PATTERNS = [
    ('Power', '/+3V3'), ('Power', 'GND'),
    ('Emitter', '/SYS_SW'), ('Emitter', 'Net-(D1-A)'), ('Emitter', 'Net-(D1-K)'),
]

JOBS = [
    (os.path.join(BASE, 'BalancerREF', 'BalancerREF.kicad_pro'),
     MAIN_CLASSES, MAIN_PATTERNS, 'MAIN'),
    (os.path.join(BASE, 'BalancerREF_OptHead', 'BalancerREF_OptHead.kicad_pro'),
     HEAD_CLASSES, HEAD_PATTERNS, 'HEAD'),
]

for path, classes, patterns, tag in JOBS:
    d = json.load(open(path, encoding='utf8'))
    ns = d.setdefault('net_settings', {})
    ns['classes'] = classes
    ns['netclass_patterns'] = [{'netclass': nc, 'pattern': pat} for nc, pat in patterns]
    ns.setdefault('meta', {'version': 5})
    ns['netclass_assignments'] = None
    print('%s  %s' % (tag, os.path.basename(path)))
    for c in classes:
        used = [p for n, p in patterns if n == c['name']]
        print('   %-8s track %.2f mm  clearance %.2f  via %.2f/%.2f   %s'
              % (c['name'], c['track_width'], c['clearance'],
                 c['via_diameter'], c['via_drill'],
                 ' '.join(used) if used else '(everything else)'))
    if APPLY:
        json.dump(d, open(path, 'w', encoding='utf8'), indent=2)
        print('   written')

if not APPLY:
    print('\nDRY RUN - nothing written.')
