"""Flip PD1 so the optical comparator can actually trip.

As drawn the detector was wired cathode to +3V3 and anode to the transimpedance
summing node. The reverse bias is fine that way, but the signal direction is not:

    photocurrent in a reverse-biased diode leaves the ANODE terminal, so with the
    anode on the summing node it is injected INTO the node
      -> the inverting TIA (U8.2 is IN-, U8.3 is the 1.65 V reference) drives
         TIA_OUT DOWN
      -> the second inverting stage (gain -12) drives OPT_AMP UP from 1.65 V
      -> U4 has OPT_AMP on IN- against CMP_THRESHOLD on IN+

CMP_THRESHOLD is 3.3 * 10k/(22k+10k) = 1.016 V with the output low. OPT_AMP idles at
1.65 V, already above it, and light pushes it further up. IN- stays above IN+ no matter
how much light arrives, so the comparator output never leaves its low state. With the
Rev F NAND gating that means U9's output never falls and U10 never triggers: TR-VERT
had no tach at all. This is a design error, not a layout one, and no amount of
connectivity checking would have found it - the netlist matched the spec, and the spec
encoded the wrong intent.

Flipping the diode fixes the whole chain without touching anything else:

    cathode on the summing node, anode to GND
      -> photocurrent is pulled OUT of the node, TIA_OUT rises
      -> OPT_AMP falls from 1.65 V and crosses 1.016 V
      -> comparator trips high, the 470k hysteresis works in the direction drawn

Reverse bias is unchanged at 1.65 V (cathode at the virtual reference, anode at 0 V).
It takes about 5.3 uA of photocurrent to cross the threshold: 634 mV needed at OPT_AMP,
divided by the gain of 12, divided by the 10k feedback resistor.

Side benefit, and it matters given Rev F moved Q1 nearer PD1: the emitter turn-off edge
lands inside the synchronous gate window, and after the flip its capacitive coupling
into the summing node pushes TIA_OUT the same way as darkness - away from the trip
point - so it cannot manufacture a false detection.

Dry run by default. Pass --apply to write.
"""
import sys, subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / 'BalancerREF' / 'scripts'))
from sexp_helpers import *
from rollback import Rollback

ROOT = HERE.parent
assert ROOT.name == 'BalancerREF_OptHead', ROOT
APPLY = '--apply' in sys.argv
SCH = ROOT / 'BalancerREF_OptHead.kicad_sch'
KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'

K_LABEL = (152.40, 45.72)        # the +3V3 label feeding PD1's cathode
A_WIRE = ((167.64, 45.72), (175.26, 45.72))   # anode into the TIA node junction
A_PIN = (167.64, 45.72)
GND_AT = (167.64, 50.80)         # clear column checked against the sheet


def rnd(v):
    return round(float(v), 2)


def refof(s):
    return next((p[2] for p in children(s, 'property') if p[1] == 'Reference'), '')


def wpts(w):
    return [(rnd(a[1]), rnd(a[2])) for a in children(one(w, 'pts'), 'xy')]


def wire(a, b):
    assert a[0] == b[0] or a[1] == b[1], (a, b)
    return node('wire', node('pts', node('xy', *a), node('xy', *b)),
                node('stroke', node('width', 0), node('type', S('default'))),
                node('uuid', uid()))


def export_partition(path):
    subprocess.run([KC, 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
                    '-o', str(path), str(SCH)], capture_output=True, text=True)
    doc = parse(Path(path).read_text(encoding='utf8'))
    out = {}
    for n in children(one(doc, 'nets'), 'net'):
        nm = str(one(n, 'name')[1])
        for p in children(n, 'node'):
            r = str(one(p, 'ref')[1])
            if not r.startswith('#'):
                out[r + '.' + str(one(p, 'pin')[1])] = nm
    return out


tmp = Path(tempfile.mkdtemp())
before = export_partition(tmp / 'b.net')
print('baseline: %d pin endpoints' % len(before))
print('PD1.1 (K) is on %s, PD1.2 (A) is on %s' % (before['PD1.1'], before['PD1.2']))

d = parse(SCH.read_text(encoding='utf8'))

# 1. the label feeding the cathode becomes the summing node
lbl = next((n for n in children(d, 'label')
            if (rnd(one(n, 'at')[1]), rnd(one(n, 'at')[2])) == K_LABEL), None)
assert lbl is not None and str(lbl[1]) == '+3V3', 'expected a +3V3 label at %s' % (K_LABEL,)
lbl[1] = 'PD_TIA_IN'
print('label at %s: +3V3 -> PD_TIA_IN (cathode joins the summing node)' % (K_LABEL,))

# 2. drop the anode's wire into the TIA junction
dead = [w for w in children(d, 'wire') if set(wpts(w)) == set(A_WIRE)]
assert len(dead) == 1, 'expected exactly one anode wire, found %d' % len(dead)
d[:] = [a for a in d if id(a) not in {id(w) for w in dead}]
print('removed the anode wire into the TIA node')

# 3. anode down to a new ground symbol
src = next(s for s in children(d, 'symbol') if str(one(s, 'lib_id')[1]) == 'power:GND')
used = {refof(s) for s in children(d, 'symbol')}
n = 1
while ('#PWR%03d' % n) in used:
    n += 1
gnd = deepcopy(src)
at = one(gnd, 'at')
at[1], at[2] = GND_AT
one(gnd, 'uuid')[1] = uid()
for p in children(gnd, 'pin'):
    one(p, 'uuid')[1] = uid()
for p in children(gnd, 'property'):
    if p[1] == 'Reference':
        p[2] = '#PWR%03d' % n
    pa = one(p, 'at')
    pa[1], pa[2] = GND_AT
inst = one(gnd, 'instances')
if inst:
    prj = one(inst, 'project')
    if prj:
        pth = one(prj, 'path')
        if pth:
            one(pth, 'reference')[1] = '#PWR%03d' % n
d.append(gnd)
d.append(wire(A_PIN, GND_AT))
print('added %s (power:GND) at %s and wired the anode down to it' % ('#PWR%03d' % n, GND_AT))

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)

with Rollback(SCH) as guard:
    SCH.write_text(dump(d) + '\n', encoding='utf8')
    after = export_partition(tmp / 'a.net')

    moved = {k: (before.get(k), v) for k, v in after.items() if before.get(k) != v}
    print('\nendpoints that changed net:')
    for k, (b, a) in sorted(moved.items()):
        print('   %-8s %-14s -> %s' % (k, b, a))

    guard.require(set(after) == set(before),
                  'pin set changed: lost %s gained %s'
                  % (sorted(set(before) - set(after)), sorted(set(after) - set(before))))
    guard.require(after['PD1.1'] == '/PD_TIA_IN',
                  'PD1 cathode is on %r, expected /PD_TIA_IN' % after['PD1.1'])
    guard.require(after['PD1.2'] == 'GND',
                  'PD1 anode is on %r, expected GND' % after['PD1.2'])
    guard.require(set(moved) == {'PD1.1', 'PD1.2'},
                  'only PD1 should move, also got %s' % sorted(set(moved) - {'PD1.1', 'PD1.2'}))
    # the summing node must still be exactly the TIA parts plus the detector
    tia = sorted(k for k, v in after.items() if v == '/PD_TIA_IN')
    guard.require(tia == ['C21.1', 'PD1.1', 'R21.2', 'U8.2'],
                  'summing node membership is wrong: %s' % tia)
    print('\nVERIFIED: cathode on the summing node, anode on GND, nothing else moved.')
