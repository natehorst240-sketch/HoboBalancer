"""Independent check of the head board's optical chain.

It was transcribed from BalancerREF Rev C and NO LONGER simply reproduces it: Rev B
flips PD1, because Rev C had the detector's anode on the transimpedance summing node
and that orientation drives OPT_AMP the wrong way for the comparator - it could never
trip. Note what that means for this file: a spec like this proves the netlist matches
the intent, and it passed for months while the intent itself was wrong. It cannot
check signal direction through a gain chain.

These are circuit specifications transcribed from the Rev C spec groups in
BalancerREF/scripts/verify_netlist.py, not generated from the head schematic. Exact
net membership is compared, so an unintended short, a bypassed series part or a
reversed two-terminal part fails rather than passing quietly (R22 was reversed on
the first generated pass and this is what would have caught it).

Power symbols (#PWR) and PWR_FLAG (#FLG) are excluded: they carry no board pads.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'BalancerREF' / 'scripts'))
from sexp_helpers import *

ROOT = HERE.parent
d = parse((ROOT / 'review' / 'OptHead.net').read_text(encoding='utf8'))

actual = {}
for n in children(one(d, 'nets'), 'net'):
    name = one(n, 'name')[1]
    members = {one(p, 'ref')[1] + '.' + one(p, 'pin')[1] for p in children(n, 'node')}
    members = {m for m in members if not m.startswith('#')}
    if members:
        actual[name] = members

# The cable. Ground is interleaved between the two digital lines on purpose.
spec = {
    'SYS_SW':        'J5.1 R18.1 C20.1',
    'OPT_LED_EN':    'J5.3 R19.2',
    'OPT_COMP':      'J5.5 R32.2',
    '+3V3':          'J5.7 R24.1 R26.1 U4.5 U8.8 C24.1 C25.1',
    'GND':           'J5.2 J5.4 J5.6 PD1.2 Q1.2 R20.2 R25.2 R27.2 U4.2 U8.4 '
                     'C20.2 C23.2 C24.2 C25.2',
    # Emitter: C20 local so the 500 mA edges never reach the cable.
    'LED_A':         'R18.2 D1.2',
    'LED_K':         'D1.1 Q1.3',
    'MOS_GATE':      'R19.1 R20.1 Q1.1',
    # Detector front end.
    # PD1 CATHODE on the summing node, anode to GND. Reverse bias is the same
    # either way, but only this orientation pulls photocurrent OUT of the node,
    # so TIA_OUT rises, OPT_AMP falls, and the comparator can cross its 1.016 V
    # threshold. Wired the other way round the comparator never trips at all.
    'PD_TIA_IN':     'PD1.1 U8.2 R21.2 C21.1',
    'TIA_OUT':       'U8.1 R21.1 C21.2 C22.1',
    'AC_COUPLED':    'C22.2 R22.2',
    'AMP_INV':       'U8.6 R22.1 R23.2',
    'OPT_AMP':       'U8.7 R23.1 U4.4',
    'OPT_VREF':      'U8.3 U8.5 R24.2 R25.1 C23.1',
    # Detection: R28 on U4's own output, upstream of the R32 series damping.
    'CMP_THRESHOLD': 'U4.3 R26.2 R27.1 R28.2',
    'CMP_OUT':       'U4.1 R28.1 R32.1',
}

by_member = {}
for name, members in actual.items():
    for m in members:
        by_member[m] = name

fails = []
matched_nets = set()
for label, pinstr in spec.items():
    want = set(pinstr.split())
    homes = {by_member.get(m) for m in want}
    if None in homes:
        fails.append('%-14s pins absent from netlist: %s'
                     % (label, sorted(m for m in want if m not in by_member)))
        continue
    if len(homes) > 1:
        fails.append('%-14s split across %d nets: %s' % (label, len(homes), sorted(homes)))
        continue
    netname = homes.pop()
    got = actual[netname]
    matched_nets.add(netname)
    if got != want:
        extra = sorted(got - want); missing = sorted(want - got)
        fails.append('%-14s (net %s) extra=%s missing=%s' % (label, netname, extra, missing))

stray = {n: sorted(m) for n, m in actual.items() if n not in matched_nets}
if stray:
    fails.append('unaccounted nets: %s' % stray)

pins = sum(len(v) for v in actual.values())
if fails:
    print('FAIL')
    for f in fails:
        print('  ' + f)
    sys.exit(1)
print('PASS: %d exact circuit nets; %d pin endpoints; head board matches the Rev B '
      'optical chain.' % (len(spec), pins))
