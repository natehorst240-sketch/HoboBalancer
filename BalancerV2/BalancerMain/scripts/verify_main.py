"""Rebuild the netlist of BalancerMain.kicad_sch from the file itself and check it.

Connectivity rules this project's generator obeys: every pin is either marked no-connect
or wired by a straight stub to a label or a power symbol; wires meet only at endpoints.
This script unions wire endpoints, labels, pins and power-symbol pins at identical
coordinates, merges by label text and power net, then prints each net and checks the
expected connections below. Exit code 1 on any failure. Also writes BalancerMain.net.json
for the PCB generator.
"""
import sys, json
from pathlib import Path
import sexpdata as sx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
S = sx.Symbol
def tagged(x, k): return isinstance(x, list) and x and str(x[0]) == k
def children(x, k): return [a for a in x if tagged(a, k)]
def one(x, k): return next((a for a in x if tagged(a, k)), None)
def key(x, y): return (round(float(x), 2), round(float(y), 2))

doc = sx.loads((ROOT / 'BalancerMain.kicad_sch').read_text(encoding='utf8'))
libs = {str(s[1]): s for s in children(one(doc, 'lib_symbols'), 'symbol')}


def lib_pins(lib):
    out = []
    for sub in children(libs[lib], 'symbol'):
        for p in children(sub, 'pin'):
            at = one(p, 'at')
            out.append((str(one(p, 'number')[1]), str(one(p, 'name')[1]), float(at[1]), float(at[2]), str(p[1])))
    return out


def xform(px, py, X, Y, rot):
    if rot == 0: return X + px, Y - py
    if rot == 90: return X - py, Y - px
    if rot == 180: return X - px, Y + py
    if rot == 270: return X + py, Y + px


ok = True
parent = {}
def find(a):
    while parent.setdefault(a, a) != a:
        parent[a] = parent[parent[a]]; a = parent[a]
    return a
def union(a, b): parent[find(a)] = find(b)

pins = []      # (ref, num, name, point, type, value, footprint)
for sym in children(doc, 'symbol'):
    lib = str(one(sym, 'lib_id')[1]); at = one(sym, 'at')
    X, Y, rot = float(at[1]), float(at[2]), int(float(at[3]))
    props = {str(p[1]): str(p[2]) for p in children(sym, 'property')}
    ref = props['Reference']
    for num, nam, px, py, typ in lib_pins(lib):
        pt = key(*xform(px, py, X, Y, rot))
        pins.append((ref, num, nam, pt, typ, props.get('Value', ''), props.get('Footprint', '')))
        if ref.startswith('#PWR'):
            union(('net', props['Value']), ('pt', pt))
        elif ref.startswith('#FLG'):
            union(('flag', ref), ('pt', pt))
        else:
            union(('pin', ref, num), ('pt', pt))
for w in children(doc, 'wire'):
    pts = [key(p[1], p[2]) for p in children(one(w, 'pts'), 'xy')]
    union(('pt', pts[0]), ('pt', pts[1]))
for l in children(doc, 'label'):
    at = one(l, 'at'); union(('net', str(l[1])), ('pt', key(at[1], at[2])))
ncpts = {key(one(n, 'at')[1], one(n, 'at')[2]) for n in children(doc, 'no_connect')}

# geometry checks KiCad would also trip on: collinear wires overlapping (a hidden short),
# and a pin, label or power pin landing in the middle of a wire it was not meant to join
segs = []
for w in children(doc, 'wire'):
    pts = [key(p[1], p[2]) for p in children(one(w, 'pts'), 'xy')]
    segs.append((pts[0], pts[1]))
def inside(pt, seg):
    (x1, y1), (x2, y2) = seg
    if y1 == y2 == pt[1]: return min(x1, x2) < pt[0] < max(x1, x2)
    if x1 == x2 == pt[0]: return min(y1, y2) < pt[1] < max(y1, y2)
    return False
for i, a in enumerate(segs):
    for b in segs[i + 1:]:
        if any(inside(p, b) for p in a) or any(inside(p, a) for p in b):
            print('FAIL: overlapping wires', a, b); ok = False
endpoints = {('pt', p) for s_ in segs for p in s_}
for ref, num, nam, pt, typ, val, fp in pins:
    for s_ in segs:
        if inside(pt, s_): print('FAIL: pin %s.%s sits mid-wire on %s' % (ref, num, s_)); ok = False
for l in children(doc, 'label'):
    at = one(l, 'at'); pt = key(at[1], at[2])
    for s_ in segs:
        if inside(pt, s_): print('FAIL: label %s sits mid-wire on %s' % (l[1], s_)); ok = False
lab_pts = {}
for l in children(doc, 'label'):
    at = one(l, 'at'); lab_pts.setdefault(key(at[1], at[2]), []).append(str(l[1]))
for pt, names in lab_pts.items():
    if len(names) > 1: print('FAIL: labels stacked at one point', pt, names); ok = False

# collect nets
groups = {}
for ref, num, nam, pt, typ, val, fp in pins:
    if ref.startswith('#'): continue
    groups.setdefault(find(('pt', pt)), []).append((ref, num, nam, pt, typ))
names = {}
for k in list(parent):
    if k[0] == 'net': names.setdefault(find(k), set()).add(k[1])

nets = {}
for root, members in groups.items():
    nm = names.get(root, set())
    if len(nm) > 1:
        print('FAIL: nets shorted together:', sorted(nm)); ok = False
    if not nm:
        if len(members) == 1 and members[0][3] in ncpts:
            continue   # a deliberate no-connect
        if len(members) == 1:
            print('FAIL: dangling pin', members[0][:3]); ok = False; continue
        print('FAIL: unnamed net joining', [m[:2] for m in members]); ok = False; continue
    name = next(iter(nm))
    nets[name] = sorted((m[0], m[1]) for m in members)

# ---- expectations (ref, pin) that must share a net ------------------------------------
EXPECT = {
    'GND': [('U1', '10'), ('U1', 'EXP'), ('J5', '1'), ('U4', '2'), ('U3', '2'), ('J1', '2'), ('J3', '2'), ('J2', '2'), ('J6', '5'), ('SW1', '2'), ('LED1', '1'), ('J9', 'GND'), ('J9', 'GND2'), ('J9', 'SHLD'), ('R1', '2'), ('R2', '2'), ('C1', '2'), ('C2', '2')],
    '+3V3': [('U1', '16'), ('U4', '8'), ('J6', '1'), ('J6', '3'), ('R11', '1'), ('R13', '1'), ('R14', '1'), ('R19', '1'), ('J4', '1'), ('C10', '1')],
    'VBAT': [('J1', '1'), ('U1', '17'), ('U3', '5'), ('L2', '1'), ('C1', '1')],
    'VBUS': [('J9', 'VBUS1'), ('J9', 'VBUS2'), ('D1', '2')],
    'MOD_5V': [('D1', '1'), ('U1', '12'), ('C2', '1')],
    'USB_CC1': [('J9', 'A5'), ('R1', '1')], 'USB_CC2': [('J9', 'B5'), ('R2', '1')],
    'USB_DM': [('U1', '14'), ('J9', 'A7'), ('J9', 'B7')], 'USB_DP': [('U1', '15'), ('J9', 'A6'), ('J9', 'B6')],
    'PROG_IO0': [('U1', '13'), ('J5', '2')], 'PROG_RST': [('U1', '11'), ('J5', '3')],
    '+12V': [('D2', '1'), ('C7', '1'), ('R7', '1'), ('J2', '1')],
    'BOOST_SW': [('U3', '1'), ('L2', '2'), ('D2', '2')],
    'BOOST_FB': [('U3', '3'), ('R7', '2'), ('R8', '1')],
    'BOOST_EN': [('U3', '4'), ('R6', '1'), ('U1', '5')],
    'MAG_IN': [('J3', '1'), ('R9', '1')], 'MAG_MID': [('R9', '2'), ('R10', '1')], 'VR_IN': [('R10', '2'), ('U4', '3')],
    'MAG_TIMING': [('U4', '14'), ('R11', '2'), ('C8', '1')], 'MAG_PEAK': [('U4', '7'), ('R12', '1'), ('C9', '1')],
    'MAG_TACH': [('U4', '12'), ('R13', '2'), ('U1', '21')],
    'OPT_RAW': [('J2', '3'), ('R14', '2'), ('R15', '1')], 'OPT_TACH': [('R15', '2'), ('U1', '20')],
    'ACCEL_SCK': [('J7', '4'), ('U1', '6')], 'ACCEL_MOSI': [('J7', '6'), ('U1', '8')],
    'ACCEL_MISO': [('J7', '5'), ('U1', '7')], 'ACCEL_CS': [('J7', '2'), ('U1', '25')], 'ACCEL_DRDY': [('J6', '6'), ('U1', '22')],
    'ACQUIRE_BUTTON': [('SW1', '1'), ('R19', '2'), ('C11', '1'), ('U1', '19')],
    'STATUS_LED': [('U1', '18'), ('R20', '1')], 'LED_A': [('R20', '2'), ('LED1', '2')],
    'GPS_UART_RX': [('J4', '3'), ('U1', '2')], 'GPS_UART_TX': [('J4', '4'), ('U1', '1')],
}
for net, members in EXPECT.items():
    got = nets.get(net)
    if got is None:
        print('FAIL: net %s missing' % net); ok = False; continue
    missing = [m for m in members if m not in got]
    if missing:
        print('FAIL: net %s lacks %s (has %s)' % (net, missing, got)); ok = False
# nets that must not exist merged with others are covered by the shorted check above.
print('%d nets' % len(nets))
for net in sorted(nets):
    print('  %-16s %s' % (net, ' '.join('%s.%s' % m for m in nets[net])))
(ROOT / 'BalancerMain.net.json').write_text(json.dumps({'nets': nets, 'parts': sorted({(p[0], p[5], p[6]) for p in pins if not p[0].startswith('#')})}, indent=1))
print('PASS' if ok else 'FAILED')
sys.exit(0 if ok else 1)
