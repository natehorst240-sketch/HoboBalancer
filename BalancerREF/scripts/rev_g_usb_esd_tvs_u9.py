"""Rev G: three schematic fixes from the Reddit review of the Rev C sheet.

1. D3 (SMF5.0A, unidirectional TVS on USB_VBUS) was drawn cathode-to-GND and
   anode-to-VBUS: forward biased, so it would clamp VBUS at a diode drop the moment a
   cable was plugged in. KiCad's Diode:SMF5V0A symbol puts the cathode bar on pin 1,
   and D3 sat at rotation 90 with pin 1 on the GND symbol. Rotating the symbol to 270
   puts pin 1 (cathode) on the VBUS wire and pin 2 (anode) on GND. The footprint is
   rotated 180 in the board by scripts/sync_board_rev_g.py for the same reason.

2. U7 (SRV05-4) had its I/O3 and I/O4 pins marked no-connect and the D+/D- labels
   hung off the connector side, so the data lines reached the array as stubs. The
   SOT-23-6 puts pin 6 directly across from pin 1 and pin 4 across from pin 3, which
   is the "flow-through" layout onsemi's datasheet shows for USB: the trace enters one
   pad and leaves the opposite one. The nets do not change (the SRV05-4 has no internal
   I/O-to-I/O connection, only steering diodes to VP/VN), but the drawing now takes D-
   in at pin 1 and out at pin 6, D+ in at pin 3 and out at pin 4, and the outbound side gets its own
   labels (the connector side keeps the same net names, see the comment in the code). C1 moves right to make room for the outbound wires.

3. U9 (SN74LVC1G132) pin 1 is OPT_COMP, which arrives from the optical head through
   J5 pin 5. Unplug the head (which is the normal state in the MR-VERT profile) and
   that input floats. R39 100k to GND holds it low; the head drives it through R32
   (see BalancerREF_OptHead), so the pull-down costs nothing when the head is present.
   U9 pin 2 comes from OPT_LED_EN through R29 1k; that pin is a GPIO output, so it is
   only floating during ESP32 reset and is left alone.

Text-based edits so the file keeps KiCad's own formatting. Dry run by default; pass
--apply to write. Refuses to run twice.
"""
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCH = ROOT / 'BalancerREF.kicad_sch'
APPLY = '--apply' in sys.argv

s = SCH.read_text(encoding='utf8')
changes = []


def fmt(v):
    return ('%.3f' % v).rstrip('0').rstrip('.')


def remove_block(kind, at, extra=''):
    """Delete one top-level (kind ... (at x y ...) ...) element, asserting exactly one match."""
    global s
    x, y = at
    pat = re.compile(r'\n\t\(%s\b%s\s*\n\t\t\(at %s %s[^)]*\)\n(?:\t\t.*\n)*?\t\)' % (kind, extra, re.escape(fmt(x)), re.escape(fmt(y))))
    hits = pat.findall(s)
    assert len(hits) == 1, (kind, at, len(hits))
    s = pat.sub('', s, count=1)
    changes.append('removed %s at %s' % (kind, at))


def remove_wire(a, b):
    global s
    pat = re.compile(r'\n\t\(wire\n\t\t\(pts\n\t\t\t\(xy %s %s\) \(xy %s %s\)\n\t\t\)\n(?:\t\t.*\n)*?\t\)'
                     % tuple(re.escape(fmt(v)) for v in (a[0], a[1], b[0], b[1])))
    hits = pat.findall(s)
    if not hits:
        pat = re.compile(r'\n\t\(wire\n\t\t\(pts\n\t\t\t\(xy %s %s\) \(xy %s %s\)\n\t\t\)\n(?:\t\t.*\n)*?\t\)'
                         % tuple(re.escape(fmt(v)) for v in (b[0], b[1], a[0], a[1])))
        hits = pat.findall(s)
    assert len(hits) == 1, ('wire', a, b, len(hits))
    s = pat.sub('', s, count=1)
    changes.append('removed wire %s-%s' % (a, b))


def wire(a, b):
    assert a[0] == b[0] or a[1] == b[1], (a, b)
    return ('\n\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid "%s")\n\t)'
            % (fmt(a[0]), fmt(a[1]), fmt(b[0]), fmt(b[1]), uuid.uuid4()))


def junction(at):
    return '\n\t(junction\n\t\t(at %s %s)\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n\t\t(uuid "%s")\n\t)' % (fmt(at[0]), fmt(at[1]), uuid.uuid4())


def label(text, at, rot=0):
    return ('\n\t(label "%s"\n\t\t(at %s %s %d)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)'
            % (text, fmt(at[0]), fmt(at[1]), rot, uuid.uuid4()))


def text(body, at, size=1.1):
    return ('\n\t(text "%s"\n\t\t(exclude_from_sim no)\n\t\t(at %s %s 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size %s %s)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)'
            % (body, fmt(at[0]), fmt(at[1]), size, size, uuid.uuid4()))


def prop(name, value, at, rot=0, hide=False, justify=None):
    out = '\t\t(property "%s" "%s"\n\t\t\t(at %s %s %d)\n' % (name, value, fmt(at[0]), fmt(at[1]), rot)
    if hide:
        out += '\t\t\t(hide yes)\n'
    out += '\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n'
    if justify:
        out += '\t\t\t\t(justify %s)\n' % justify
    out += '\t\t\t)\n\t\t)\n'
    return out


PROJECT_PATH = '/817ec478-f84e-4d27-b6f3-c983c8ad991a'


def symbol(lib_id, ref, value, at, rot, footprint, pins, in_bom=True, mpn=None, textpos=None):
    u = str(uuid.uuid4())
    x, y = at
    out = '\n\t(symbol\n\t\t(lib_id "%s")\n\t\t(at %s %s %d)\n\t\t(unit 1)\n\t\t(body_style 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom %s)\n\t\t(on_board %s)\n\t\t(in_pos_files yes)\n\t\t(dnp no)\n\t\t(uuid "%s")\n' % (
        lib_id, fmt(x), fmt(y), rot, 'yes' if in_bom else 'no', 'yes' if in_bom else 'no', u)
    if textpos:
        out += prop('Reference', ref, textpos[0], justify='left')
        out += prop('Value', value, textpos[1], justify='left')
    else:
        out += prop('Reference', ref, (x, y - 5.08), hide=True)
        out += prop('Value', value, (x, y - 2.54), hide=True)
    out += prop('Footprint', footprint, at, hide=True)
    out += prop('Datasheet', '', at, hide=True)
    out += prop('Description', '', at)
    if mpn is not None:
        out += prop('MPN', mpn, at, hide=True)
    for p in pins:
        out += '\t\t(pin "%s"\n\t\t\t(uuid "%s")\n\t\t)\n' % (p, uuid.uuid4())
    out += '\t\t(instances\n\t\t\t(project "BalancerREF"\n\t\t\t\t(path "%s"\n\t\t\t\t\t(reference "%s")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)' % (PROJECT_PATH, ref)
    return out, u


assert '(property "Reference" "R39"' not in s, 'R39 already present: this script has been applied'
assert '\t\t(rev "F")' in s

# ---- 1. D3 orientation --------------------------------------------------------
old = '\t(symbol\n\t\t(lib_id "Diode:SMF5V0A")\n\t\t(at 206.375 79.375 90)\n'
assert s.count(old) == 1
s = s.replace(old, old.replace(' 90)\n', ' 270)\n'))
changes.append('D3 rotated 90 -> 270: pin 1 (cathode) now on USB_VBUS, pin 2 (anode) on GND')

# ---- 2. U7 flow-through -------------------------------------------------------
remove_block('label', (165.1, 97.155), extra=' "USB_CONN_D-"')
remove_block('label', (147.32, 104.775), extra=' "USB_CONN_D\\+"')
remove_wire((162.56, 97.155), (165.1, 97.155))
remove_wire((144.78, 104.775), (147.32, 104.775))
remove_block('junction', (162.56, 97.155))
remove_block('junction', (144.78, 104.775))
remove_block('no_connect', (189.23, 118.745))
remove_block('no_connect', (189.23, 123.825))

# C1 and its ground move 12.7 mm right so the outbound D+/D- wires have room.
DX = 12.7
c1 = re.search(r'\n\t\(symbol\n\t\t\(lib_id "Device:C"\)\n\t\t\(at 201\.93 116\.205 0\)\n(?:\t\t.*\n)*?\t\)', s)
assert c1 and '(property "Reference" "C1"' in c1.group(0)
moved = re.sub(r'\(at 20(\d\.\d+) (\d+\.\d+) (\d+)\)', lambda m: '(at %s %s %s)' % (fmt(float('20' + m.group(1)) + DX), m.group(2), m.group(3)), c1.group(0))
s = s.replace(c1.group(0), moved)
g = re.search(r'\n\t\(symbol\n\t\t\(lib_id "power:GND"\)\n\t\t\(at 201\.93 120\.015 0\)\n(?:\t\t.*\n)*?\t\)', s)
assert g and '"#PWR004"' in g.group(0)
moved = re.sub(r'\(at 201\.93 (\d+\.\d+) (\d+)\)', lambda m: '(at %s %s %s)' % (fmt(201.93 + DX), m.group(1), m.group(2)), g.group(0))
s = s.replace(g.group(0), moved)
remove_wire((201.93, 108.585), (201.93, 112.395))
changes.append('C1 and #PWR004 moved +%.2f mm in x' % DX)

new = ''
new += wire((201.93, 108.585), (214.63, 108.585))
new += wire((214.63, 108.585), (214.63, 112.395))
new += wire((189.23, 118.745), (199.39, 118.745))
new += wire((189.23, 123.825), (199.39, 123.825))
new += label('USB_CONN_D+', (199.39, 118.745))
new += label('USB_CONN_D-', (199.39, 123.825))
# The SRV05-4 has no internal I/O-to-I/O path, so the connector side must carry the
# same net name as the outbound side: the board joins pad 1 to pad 6 (and 3 to 4) with
# the data trace itself. Giving the two sides different nets would pass DRC with an
# open circuit. These labels sit on the vertical wires into pins 1 and 3.
new += label('USB_CONN_D-', (162.56, 112.395), rot=90)
new += label('USB_CONN_D+', (144.78, 117.475), rot=90)
new += text('U7: route each data line THROUGH the array. D- enters pin 1 and leaves pin 6,\\nD+ enters pin 3 and leaves pin 4; the opposite pads sit across from each other.',
            (137.16, 147.32))
changes.append('U7 pins 4/6 wired out to USB_CONN_D+ / USB_CONN_D- labels; routing note added')

# ---- 3. R39 pull-down on OPT_COMP ---------------------------------------------
# OPT_COMP runs (104.14,303.53)-(134.62,303.53) into U9 pin 1. R39 stands on it at
# x=124.46 with its other end up to a ground symbol; nothing else occupies that column.
sym, r39_uuid = symbol('Device:R', 'R39', '100k', (124.46, 299.72), 0, 'Resistor_SMD:R_0603_1608Metric', ['1', '2'],
                       mpn='100k', textpos=((125.73, 298.45), (125.73, 300.99)))
new += sym
gnd, _ = symbol('power:GND', '#PWR043', 'GND', (124.46, 295.91), 180, '', ['1'], in_bom=False, mpn='GND')
new += gnd
new += junction((124.46, 303.53))
changes.append('R39 100k added from OPT_COMP to GND at U9 pin 1 (symbol uuid %s)' % r39_uuid)

# ---- title block --------------------------------------------------------------
s = s.replace('\t\t(date "2026-09-13")\n\t\t(rev "F")', '\t\t(date "2026-09-19")\n\t\t(rev "G")')
assert '(rev "G")' in s
changes.append('title block -> Rev G, 2026-09-19')

anchor = '\n\t(sheet_instances\n'
assert s.count(anchor) == 1
s = s.replace(anchor, new + anchor)

for c in changes:
    print('-', c)
if APPLY:
    SCH.write_text(s, encoding='utf8')
    print('written', SCH)
else:
    print('dry run; pass --apply to write')
