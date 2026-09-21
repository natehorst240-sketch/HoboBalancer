"""Rev G schematic corrections: D3 polarity, U9 input bias, USB pair through U7.

Three findings from the 2026-09-19 board review, all on the main board.

1. D3 IS BACKWARDS.  SMF5.0A is the UNIDIRECTIONAL member of the SMF family (the
   bidirectional part is the SMF5.0CA), and the KiCad symbol says so: Diode:SMF5V0A
   carries Description "200W unidirectional Transil Transient Voltage Suppressor,
   5Vrwm, SMF".  Its pin NAMES are inherited from SM6T6V8A and read A1/A2, which is
   what led DATASHEET-VERIFICATION.md to record "either orientation valid" - but the
   graphic is a cathode bar on pin 1 and an anode triangle on pin 2, and the footprint
   Diode_SMD:D_SMF puts its polarity band on pad 1.  Pin 1 is the cathode.

   As drawn, pin 1 (cathode) is on GND and pin 2 (anode) is on USB_VBUS, so D3 is a
   plain forward diode across the USB supply: it conducts at about 0.8 V, collapses
   VBUS and trips the host's port protection.  The board could never have enumerated.
   The fix is to turn the symbol around - 90 deg becomes 270 deg - which lands pin 1
   on VBUS and pin 2 on GND without moving a single wire.

2. U9's INPUTS CAN FLOAT.  Both of them, in different ways:

     pin 1 (A) is /OPT_COMP, which arrives from the optical head's comparator over
     J5.  Nothing on the main board holds it when the head is unplugged - and the
     head is a separate PCB, so unplugged is a normal state (MR-VERT runs the
     magnetic tach with no head fitted at all).

     pin 2 (B) is the R29/C26 delayed strobe, driven from GPIO13 through 1 k.  The
     ESP32-S3 leaves its GPIOs high-Z through reset and boot, so until firmware
     configures the pin, C26 is the only thing defining that node.

   A floating LVC input sits in its linear region, draws shoot-through current and
   makes the gate's output whatever the nearest coupled edge says it is.  Schmitt
   inputs slow that down; they do not define a DC level.  R39 and R40, 100 k each,
   pull both inputs LOW, which is the fail-safe direction: the NAND then holds Y HIGH,
   U10's ~A trigger never falls, and no phantom tach pulses reach the MCU.

   R40 barely touches the delay it sits on.  C26 sees 1 k || 100 k = 990 ohm instead
   of 1 k, so the 470 ns edge becomes 465 ns, and a driven-high strobe lands at
   3.27 V rather than 3.30 V - still well over the 1G132's VIH.  It also gives the
   head's LED gate a second path to ground during boot, in series with R29.

3. THE USB PAIR TEES OFF U7 INSTEAD OF PASSING THROUGH IT.  Only IO1 and IO2 were
   used, so each data line could only reach the array down a spur; on the board that
   spur hung off R6/R7's pads, which put the series resistors between the connector
   and the clamp.  IO3 and IO4 were sitting unused.

   Wiring IO4 alongside IO1 and IO3 alongside IO2 makes each line enter one pad and
   leave the pad directly across the package - the same flow-through arrangement the
   USBLC6-2SC6 is built around, and the reason an SRV05-4 has four channels.  The
   layout change that goes with it is in scripts/layout_review_round2.py.

   Cost: two channels in parallel per line, so about 6 pF to ground instead of 3 pF.
   The ESP32-S3's native USB is full-speed only (12 Mbit/s), where that is immaterial.

Dry run by default.  Pass --apply to write.
"""
import sys, json, subprocess, tempfile
from pathlib import Path
from copy import deepcopy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexp_helpers import *
from rollback import Rollback

ROOT = HERE.parent
assert ROOT.name == 'BalancerREF', ROOT
APPLY = '--apply' in sys.argv
SCH = ROOT / 'BalancerREF.kicad_sch'
UNUSED = ROOT / 'review' / 'unused-pins.json'
KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'

# ---- geometry ---------------------------------------------------------------
# Every endpoint below is a multiple of 1.27 mm except the SRV05-4's own pins, which
# the KiCad symbol places on the 1.27 half-grid; the wires already on those pins use
# the same values, and the sheet passes ERC with 0 errors.
D3_AT = (206.375, 79.375)

OPT_COMP_TAP = (121.92, 303.53)     # on the J5.5 -> U9.1 wire
R39_TOP = (121.92, 288.29)
R39_BOT = (121.92, 295.91)
R39_BODY = (121.92, 292.10)
R39_TEXT = 126.5            # clear of the body, and of nothing else up there
R39_GND = (121.92, 285.75)          # above the part, so the drop never crosses
                                    # OPT_LED_EN; the GND symbol is turned to suit

RC_NODE = (134.62, 312.42)          # C26 pin 1 == U9 pin 2 node
R40_RIGHT = (134.62, 312.42)
R40_LEFT = (127.0, 312.42)
R40_BODY = (127.0, 316.23)
R40_BOT = (127.0, 320.04)
R40_TEXT = 122.5            # to the LEFT: C26 and its own fields own the right
R40_GND = (127.0, 322.58)

U7_IO3 = (189.23, 118.745)          # pin 4, was NC -> joins D+ with IO2
U7_IO4 = (189.23, 123.825)          # pin 6, was NC -> joins D- with IO1
IO3_ELBOW = (194.31, 118.745)
IO3_LABEL = (194.31, 130.81)
IO4_ELBOW = (198.12, 123.825)
IO4_LABEL = (198.12, 133.35)

EXPECT = {
    'D3.1': '/USB_VBUS', 'D3.2': 'GND',
    'R39.1': '/OPT_COMP', 'R39.2': 'GND',
    'U7.4': '/USB_CONN_D+', 'U7.6': '/USB_CONN_D-',
}
NEW_PINS = {'R39.1', 'R39.2', 'R40.1', 'R40.2'}


def rnd(v):
    return round(float(v), 4)


def refof(s):
    return next((p[2] for p in children(s, 'property') if p[1] == 'Reference'), '')


def setprop(sym, key, val):
    for p in children(sym, 'property'):
        if p[1] == key:
            p[2] = val
            return


def clone(src, ref, value, x, y, angle=None, text_x=None):
    """Copy a live instance so lib_id, pin uuids and the instances block stay valid.
    The angle is always passed explicitly: the donors are not all at rotation 0, and
    an inherited rotation puts the pins somewhere the new wires do not reach."""
    c = deepcopy(src)
    a = one(c, 'at')
    a[1], a[2] = rnd(x), rnd(y)
    if angle is not None:
        while len(a) < 4:
            a.append(0)
        a[3] = angle
    one(c, 'uuid')[1] = uid()
    for p in children(c, 'pin'):
        one(p, 'uuid')[1] = uid()
    setprop(c, 'Reference', ref)
    setprop(c, 'Value', value)
    setprop(c, 'MPN', value)
    inst = one(c, 'instances')
    if inst:
        prj = one(inst, 'project')
        if prj:
            pth = one(prj, 'path')
            if pth:
                one(pth, 'reference')[1] = ref
    # The donor's fields carry (justify left), and KiCad flips that for a symbol at
    # 180 degrees, so an inherited offset lands the designator on whichever neighbour
    # happens to be on that side. Both new parts get an explicit centred anchor.
    for p in children(c, 'property'):
        at_ = one(p, 'at')
        tx = x + 3.81 if text_x is None else text_x
        if p[1] == 'Reference':
            at_[1], at_[2] = rnd(tx), rnd(y - 1.27)
        elif p[1] == 'Value':
            at_[1], at_[2] = rnd(tx), rnd(y + 1.27)
        else:
            at_[1], at_[2] = rnd(x), rnd(y)
        if len(at_) > 3:
            at_[3] = 0
        if text_x is not None and p[1] in ('Reference', 'Value'):
            eff = one(p, 'effects')
            if eff is not None:
                eff[:] = [a for a in eff if not tagged(a, 'justify')]
    return c


def wire(a, b):
    a, b = (rnd(a[0]), rnd(a[1])), (rnd(b[0]), rnd(b[1]))
    assert a[0] == b[0] or a[1] == b[1], (a, b)
    return node('wire', node('pts', node('xy', *a), node('xy', *b)),
                node('stroke', node('width', 0), node('type', S('default'))),
                node('uuid', uid()))


def label(net, x, y, angle=0):
    return node('label', net, node('at', rnd(x), rnd(y), angle),
                node('effects', node('font', node('size', 1.27, 1.27)),
                     node('justify', S('left'), S('bottom'))), node('uuid', uid()))


def junction(x, y):
    return node('junction', node('at', rnd(x), rnd(y)), node('diameter', 0),
                node('color', 0, 0, 0, 0), node('uuid', uid()))


def export(out):
    r = subprocess.run([KC, 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
                        '-o', str(out), str(SCH)], capture_output=True, text=True)
    assert Path(out).exists(), r.stdout + r.stderr
    return parse(Path(out).read_text(encoding='utf8'))


def partition(doc):
    o = {}
    for n in children(one(doc, 'nets'), 'net'):
        nm = one(n, 'name')[1]
        for p in children(n, 'node'):
            r = one(p, 'ref')[1]
            if not r.startswith('#'):
                o[r + '.' + one(p, 'pin')[1]] = nm
    return o


tmp = Path(tempfile.mkdtemp())
before = partition(export(tmp / 'b.net'))
print('baseline: %d pin endpoints' % len(before))

d = parse(SCH.read_text(encoding='utf8'))
syms = children(d, 'symbol')

# ---- 1. D3: turn the TVS around ---------------------------------------------
d3 = next(s for s in syms if refof(s) == 'D3')
a = one(d3, 'at')
assert (rnd(a[1]), rnd(a[2])) == D3_AT, 'D3 moved: %s' % a
assert rnd(a[3]) == 90.0, 'D3 is at %s, expected 90' % a[3]
assert one(d3, 'lib_id')[1] == 'Diode:SMF5V0A', one(d3, 'lib_id')[1]
a[3] = 270
print('D3 rotated 90 -> 270: pin 1 (cathode) now on USB_VBUS, pin 2 (anode) on GND')

# ---- 2. R39 / R40: define both U9 inputs ------------------------------------
src_r = next(s for s in syms if refof(s) == 'R30')       # Device:R, 100k, rotation 0
src_gnd = next(s for s in syms if refof(s) == '#PWR034')  # power:GND beneath C26
assert one(src_r, 'lib_id')[1] == 'Device:R', one(src_r, 'lib_id')[1]
assert one(src_gnd, 'lib_id')[1] == 'power:GND', one(src_gnd, 'lib_id')[1]

# The OPT_COMP tap runs UP. Everything below that wire between J5 and U9 is taken -
# OPT_LED_EN at 308.61 and R29's body sit across the whole span - so a downward drop
# would have to cross a signal wire to reach clear space. Going up is clear, and the
# ground symbol is rotated 180 so it still reads as a ground.
add = [
    # R39 is turned over so that, like R40, its pin 1 is the signal end and pin 2 the
    # ground end. Device:R pin 1 sits at the top of the body at rotation 0, and here
    # the ground is above the part.
    clone(src_r, 'R39', '100k', *R39_BODY, angle=180, text_x=R39_TEXT),
    clone(src_gnd, '#PWR803', 'GND', *R39_GND, angle=180),
    clone(src_r, 'R40', '100k', *R40_BODY, angle=0, text_x=R40_TEXT),
    clone(src_gnd, '#PWR804', 'GND', *R40_GND, angle=0),
]
wires = [
    wire(OPT_COMP_TAP, R39_BOT),        # OPT_COMP up into R39
    wire(R39_TOP, R39_GND),             # R39 to its ground
    wire(R40_RIGHT, R40_LEFT),          # RC node across to R40
    wire(R40_BOT, R40_GND),             # R40 to its ground
]
juncs = [junction(*OPT_COMP_TAP), junction(*RC_NODE)]
print('added R39 100k on /OPT_COMP (U9.A) and R40 100k on the R29/C26 node (U9.B)')

# ---- 3. U7: bring IO3 and IO4 onto the pair ---------------------------------
ncs = [n for n in children(d, 'no_connect')
       if (rnd(one(n, 'at')[1]), rnd(one(n, 'at')[2])) in (U7_IO3, U7_IO4)]
assert len(ncs) == 2, 'expected 2 no_connects on U7 IO3/IO4, found %d' % len(ncs)
d[:] = [x for x in d if id(x) not in {id(n) for n in ncs}]
print('removed the no_connect flags on U7.4 (IO3) and U7.6 (IO4)')

wires += [
    wire(U7_IO3, IO3_ELBOW), wire(IO3_ELBOW, IO3_LABEL),
    wire(U7_IO4, IO4_ELBOW), wire(IO4_ELBOW, IO4_LABEL),
]
labels = [
    label('USB_CONN_D+', *IO3_LABEL),
    label('USB_CONN_D-', *IO4_LABEL),
]
print('U7.4 -> USB_CONN_D+ (with IO2), U7.6 -> USB_CONN_D- (with IO1): each line now '
      'crosses the package pad-to-pad')

d.extend(wires)
d.extend(labels)
d.extend(juncs)
d.extend(add)

# ---- revision ---------------------------------------------------------------
tb = one(d, 'title_block')
one(tb, 'rev')[1] = 'G'
one(tb, 'date')[1] = '2026-09-19'
print('title block: Rev F -> Rev G, dated 2026-09-19')

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)

with Rollback(SCH, UNUSED) as guard:
    SCH.write_text(dump(d) + '\n', encoding='utf8')
    # sexpdata emits the whole sheet on one line, which is valid KiCad and an
    # unreadable diff. `sch upgrade --force` is KiCad's own writer, so it puts the
    # file back into canonical form; it drops the top-level (embedded_fonts no)
    # default on the way through, which is restored here so the diff shows only
    # what this patch meant to change.
    subprocess.run([KC, 'sch', 'upgrade', '--force', str(SCH)],
                   capture_output=True, text=True, check=True)
    txt = SCH.read_text(encoding='utf8').rstrip('\n')
    assert txt.endswith('\n)'), 'unexpected end of reformatted sheet'
    if '\n\t(embedded_fonts' not in txt:
        SCH.write_text(txt[:-2] + '\n\t(embedded_fonts no)\n)\n', encoding='utf8')

    nc = json.loads(UNUSED.read_text())
    for pin in ('U7.4', 'U7.6'):
        nc.pop(pin, None)
    UNUSED.write_text(json.dumps(nc, indent=2) + '\n')
    print('unused-pins.json: dropped U7.4 and U7.6, %d remain' % len(nc))

    after = partition(export(tmp / 'a.net'))
    moved = {k: (before.get(k), v) for k, v in after.items() if before.get(k) != v}
    print('\nendpoints that changed net:')
    for k, (b, x) in sorted(moved.items()):
        print('   %-8s %-32s -> %s' % (k, b, x))

    guard.require(set(after) == set(before) | NEW_PINS,
                  'pin set wrong: lost %s gained %s'
                  % (sorted(set(before) - set(after)),
                     sorted(set(after) - set(before) - NEW_PINS)))
    for pin, want in EXPECT.items():
        guard.require(after.get(pin) == want,
                      '%s is on %r, expected %r' % (pin, after.get(pin), want))
    # R40 shares U9.B's node whatever KiCad decides to call it after the membership
    # changed, so assert the pairing rather than the generated name.
    guard.require(after['R40.1'] == after['U9.2'] == after['C26.1'] == after['R29.1'],
                  'R40 did not land on the R29/C26/U9.B node: %s' % after['R40.1'])
    guard.require(after['R40.2'] == 'GND', 'R40.2 is on %r' % after['R40.2'])
    guard.require(after['U9.1'] == '/OPT_COMP', 'U9.A moved to %r' % after['U9.1'])
    # Everything that changed must be something this patch set out to change.
    allowed = NEW_PINS | set(EXPECT) | {'U9.2', 'C26.1', 'R29.1'}
    stray = set(moved) - allowed
    guard.require(not stray, 'unexpected endpoints changed net: %s' % sorted(stray))
    print('\nVERIFIED: D3 reversed, both U9 inputs biased low, USB pair through U7, '
          'every other pin unchanged.')
