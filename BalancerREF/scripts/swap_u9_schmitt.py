"""Swap U9 from SN74LVC1G08 to SN74LVC1G132 and move U10's trigger to ~A.

R29/C26 present a 0.47 us edge to U9. The SN74LVC1G08 specifies a maximum input
transition rate of 10 ns/V, so that edge is roughly 25x out of spec; an LVC input driven
slowly through its linear region can oscillate and draws shoot-through current. The
downstream retriggerable monostable hides the functional symptom - extra transitions
just retrigger it inside its ~100 us window - but the part is still being run outside
its datasheet.

The SN74LVC1G132 is the same SOT-23-5 pinout (1 A, 2 B, 3 GND, 4 Y, 5 VCC, verified
against SLVS322 Figure 4-1) with Schmitt-trigger inputs, so it drops straight in and
conditions BOTH inputs rather than only the RC branch. It is a NAND, so the output now
FALLS on a detection instead of rising, and U10's trigger has to move with it:

    before   U10 ~A = GND,   U10 B = U9.Y    -> triggers on B rising
    after    U10 ~A = U9.Y,  U10 B = +3V3    -> triggers on ~A falling

The SN74LVC1G123 supports both edges (~A falling with B high, or B rising with ~A low),
so this is a rewire, not a redesign.

Geometry note: U9.Y and U10.B are directly abutted - coincident pins, no wire between
them - so they cannot be separated without moving a symbol. U9 moves DOWN 5.08 mm, which
lands U9.Y exactly on U10.~A and frees U10.B. U10 itself does not move, which matters
because it has seven wired pins to U9's four. U10.B then ties to +3V3 with a single
5.08 mm wire up to U10.~CLR, which is already on that rail.

Dry run by default. Pass --apply to write.
"""
import sys, math, subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexp_helpers import *
from rollback import Rollback

ROOT = HERE.parent
assert ROOT.name == 'BalancerREF', ROOT
APPLY = '--apply' in sys.argv
SCH = ROOT / 'BalancerREF.kicad_sch'
SYM = ROOT / 'BalancerREF.kicad_sym'
KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'

NEWSYM = 'SN74LVC1G132'
NEWVAL = 'SN74LVC1G132DBVR'
DY = 5.08                      # U9 moves down exactly one pin pitch

U9_OLD = (198.12, 308.61)
LBL_OPT = (182.88, 306.07)     # OPT_COMP label, stays put
VESTIGIAL = ((173.99, 306.07), (182.88, 306.07))   # wire to a stale junction
STALE_JUNCTION = (173.99, 306.07)
U10_A = (210.82, 313.69)       # ~A  - U9.Y lands here after the move
U10_B = (210.82, 308.61)       # B   - freed by the move
U10_CLR = (210.82, 303.53)     # ~CLR, already on +3V3
GND_WIRE = ((210.82, 313.69), (210.82, 323.85))    # old ~A tie to GND
GND_SYM = (210.82, 323.85)     # #PWR037


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

d = parse(SCH.read_text(encoding='utf8'))

# ---- the new library symbol -------------------------------------------------
# 74LVC1G00 is the single-gate NAND: correct shape and bubble, same 5-pin SOT-23
# pinout. Cloning it means the sheet shows a NAND where a NAND now is, instead of
# leaving an AND body on a part that no longer ANDs.
proto = standard('74xGxx', '74LVC1G00')
rename(proto, NEWSYM)
for p in children(proto, 'property'):
    if p[1] == 'Value':
        p[2] = NEWSYM
    elif p[1] == 'Datasheet':
        p[2] = 'https://www.ti.com/lit/ds/symlink/sn74lvc1g132.pdf'
    elif p[1] == 'Description':
        p[2] = 'Single 2-input NAND gate with Schmitt-trigger inputs, SOT-23-5'
print('built library symbol %s from 74xGxx:74LVC1G00' % NEWSYM)

libs = one(d, 'lib_symbols')
if not any(str(s[1]) == 'BalancerREF:' + NEWSYM for s in children(libs, 'symbol')):
    emb = deepcopy(proto)
    # Only the PARENT takes the "Lib:Name" form. The unit sub-symbols keep the bare
    # name - every symbol already embedded in this sheet is shaped that way
    # (BalancerREF:SN74LVC1G123DCTR -> SN74LVC1G123DCTR_0_1). Prefixing the units too
    # makes a file KiCad refuses to load, with no message beyond "Failed to load
    # schematic", so it is worth asserting rather than rediscovering.
    emb[1] = 'BalancerREF:' + NEWSYM
    units = [str(a[1]) for a in children(emb, 'symbol')]
    assert all(u.startswith(NEWSYM + '_') for u in units), units
    libs.append(emb)
    print('added %s to the schematic lib_symbols cache' % ('BalancerREF:' + NEWSYM))

# ---- U9: retype and move ----------------------------------------------------
u9 = next(s for s in children(d, 'symbol') if refof(s) == 'U9')
at = one(u9, 'at')
assert (rnd(at[1]), rnd(at[2])) == U9_OLD, 'U9 is not where this script expects: %s' % at
one(u9, 'lib_id')[1] = 'BalancerREF:' + NEWSYM
for p in children(u9, 'property'):
    if p[1] == 'Value':
        p[2] = NEWVAL
    if p[1] == 'Datasheet':
        p[2] = 'https://www.ti.com/lit/ds/symlink/sn74lvc1g132.pdf'
at[2] = rnd(at[2] + DY)
for p in children(u9, 'property'):          # keep the ref/value text with the body
    pa = one(p, 'at')
    pa[2] = rnd(pa[2] + DY)
print('U9 -> %s, moved (%.2f, %.2f) -> (%.2f, %.2f)'
      % (NEWVAL, U9_OLD[0], U9_OLD[1], rnd(at[1]), rnd(at[2])))

# U9's GND symbol travels with it so it does not end up inside the body
gs = next((s for s in children(d, 'symbol')
           if refof(s) == '#PWR035'), None)
if gs is not None:
    ga = one(gs, 'at')
    ga[2] = rnd(ga[2] + DY)
    for p in children(gs, 'property'):
        pa = one(p, 'at')
        pa[2] = rnd(pa[2] + DY)
    print('#PWR035 (U9 GND) moved down with it')

# ---- wires ------------------------------------------------------------------
dead, added = [], []
for w in children(d, 'wire'):
    pp = wpts(w)
    if set(pp) == set(VESTIGIAL) or set(pp) == set(GND_WIRE):
        dead.append(w)
        continue
    xs = children(one(w, 'pts'), 'xy')
    for xy in xs:
        p = (rnd(xy[1]), rnd(xy[2]))
        # pin-side endpoints of U9's pin 2 / pin 5 stubs follow the symbol down
        if p in ((182.88, 311.15), (198.12, 298.45)):
            xy[2] = rnd(xy[2] + DY)
        # U9's pin 3 stub moves bodily with the symbol and its GND
        elif p in ((198.12, 318.77), (198.12, 321.31)):
            xy[2] = rnd(xy[2] + DY)

# the stale one-wire junction that was anchoring the vestigial wire
js = [j for j in children(d, 'junction')
      if (rnd(one(j, 'at')[1]), rnd(one(j, 'at')[2])) == STALE_JUNCTION]
# #PWR037 only existed to tie the old ~A low
p37 = [s for s in children(d, 'symbol') if refof(s) == '#PWR037']

d[:] = [a for a in d if id(a) not in {id(x) for x in dead + js + p37}]
print('removed: %d wire(s), %d stale junction(s), %d GND symbol(s) (#PWR037)'
      % (len(dead), len(js), len(p37)))

added.append(wire(LBL_OPT, (182.88, rnd(306.07 + DY))))      # OPT_COMP label -> new pin 1
added.append(wire(U10_B, U10_CLR))                            # B -> +3V3 via ~CLR
d.extend(added)
print('added %d wire(s): OPT_COMP label to U9.A, and U10.B up to ~CLR (+3V3)' % len(added))

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)

with Rollback(SCH, SYM) as guard:
    SCH.write_text(dump(d) + '\n', encoding='utf8')

    # project symbol library gets the part too, so the sheet is not the only copy
    lib = parse(SYM.read_text(encoding='utf8'))
    if not any(str(s[1]) == NEWSYM for s in children(lib, 'symbol')):
        lib.append(deepcopy(proto))
        SYM.write_text(dump(lib) + '\n', encoding='utf8')
        print('added %s to BalancerREF.kicad_sym' % NEWSYM)

    after = export_partition(tmp / 'a.net')
    moved = {k: (before.get(k), v) for k, v in after.items() if before.get(k) != v}
    print('\nendpoints that changed net:')
    for k, (b, a) in sorted(moved.items()):
        print('   %-8s %-22s -> %s' % (k, b, a))

    guard.require(set(after) == set(before),
                  'pin set changed: lost %s gained %s'
                  % (sorted(set(before) - set(after)), sorted(set(after) - set(before))))
    # U10.B must now sit on +3V3, U9.4 and U10.1 must share a net, and nothing else moves
    guard.require(after.get('U10.2') == '/+3V3',
                  'U10.B is on %r, expected /+3V3' % after.get('U10.2'))
    guard.require(after['U9.4'] == after['U10.1'],
                  'U9.Y (%s) and U10.~A (%s) are not the same net'
                  % (after['U9.4'], after['U10.1']))
    guard.require(after['U9.1'] == '/OPT_COMP',
                  'U9.A is on %r, expected /OPT_COMP' % after['U9.1'])
    guard.require(after['U9.2'] == before['U9.2'],
                  'U9.B left the RC node: %r -> %r' % (before['U9.2'], after['U9.2']))
    # U9.4 is expected here too: it did not move electrically, but the auto-generated
    # net name follows whichever U10 pin it pairs with, so Net-(U10-B) becomes
    # Net-(U10-~{A}). The pairing assertion above is what actually pins that down.
    unexpected = {k for k in moved if k not in ('U10.1', 'U10.2', 'U9.4')}
    guard.require(not unexpected,
                  'only U10.1, U10.2 and U9.4 should change net, also got %s'
                  % sorted(unexpected))
    print('\nVERIFIED: trigger moved to ~A, B tied high, every other pin unchanged.')
