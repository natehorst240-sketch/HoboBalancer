"""Reconcile every board pad's net against the schematic netlist.

This is the net half of what pcbnew's "Update PCB from Schematic" does, which has no
kicad-cli equivalent. The board had drifted across several edits: SW1/C30 still sat on
Net-(D2-K) after D2 was deleted, U9 on Net-(R28-Pad1) after the optical split, and -
worse - U1 pin 8 was never actually joined to the BAT_SENSE divider, because that
change assigned nets to the new passives but not to the MCU pad. The schematic netlist
verified clean throughout; only the board was wrong.

It exports the netlist from the schematic itself on every run and asserts the board
matches it exactly afterwards, so a silent miss is not possible.

It used to read the pad->net map from a JSON file left in the temp directory by an
earlier step, and that is exactly how it went wrong: after U9 became a Schmitt NAND and
U10's trigger moved to ~A, this script cheerfully reported "0 pads needing a change"
while the board still had U10.1 on GND and U10.2 on the old gate net. Comparing an
artifact against another artifact of unknown age proves nothing - the schematic is the
source of truth, so it gets re-exported here rather than trusted from a file.

KiCad's bundled Python has no sexpdata, hence the small reader below.

Dry run by default. Pass --apply to write.
"""
import sys, os, subprocess, tempfile
import pcbnew

APPLY = '--apply' in sys.argv
ROOT = r'C:\Users\nateh\hgs-linux\Balancer\BalancerREF'
PCB = os.path.join(ROOT, 'BalancerREF.kicad_pcb')
SCH = os.path.join(ROOT, 'BalancerREF.kicad_sch')
KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'


def sexp(text):
    """Minimal s-expression reader: lists, bare atoms, quoted strings."""
    i, n = 0, len(text)

    def parse():
        nonlocal i
        while i < n and text[i] in ' \t\r\n':
            i += 1
        if text[i] == '(':
            i += 1
            out = []
            while True:
                while i < n and text[i] in ' \t\r\n':
                    i += 1
                if text[i] == ')':
                    i += 1
                    return out
                out.append(parse())
        if text[i] == '"':
            i += 1
            buf = []
            while text[i] != '"':
                if text[i] == '\\':
                    i += 1
                buf.append(text[i])
                i += 1
            i += 1
            return ''.join(buf)
        start = i
        while i < n and text[i] not in ' \t\r\n()':
            i += 1
        return text[start:i]

    return parse()


def kids(node, tag):
    return [a for a in node if isinstance(a, list) and a and a[0] == tag]


def one_(node, tag):
    return next((a for a in node if isinstance(a, list) and a and a[0] == tag), None)


tmp = os.path.join(tempfile.mkdtemp(), 'sync.net')
r = subprocess.run([KC, 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
                    '-o', tmp, SCH], capture_output=True, text=True)
assert r.returncode == 0 and os.path.exists(tmp), \
    'netlist export failed: %s %s' % (r.returncode, (r.stderr or '').strip())
with open(tmp, encoding='utf8') as fh:
    doc = sexp(fh.read())

want = {}
for net in kids(one_(doc, 'nets'), 'net'):
    name = one_(net, 'name')[1]
    for nd in kids(net, 'node'):
        want[(one_(nd, 'ref')[1], one_(nd, 'pin')[1])] = name
print('schematic netlist: %d pads across %d nets (freshly exported)'
      % (len(want), len(kids(one_(doc, 'nets'), 'net'))))
board = pcbnew.LoadBoard(PCB)
nets = {}
for f in board.GetFootprints():
    for p in f.Pads():
        if p.GetNetname():
            nets[p.GetNetname()] = p.GetNet()

changes, missing, created = [], [], []
for f in board.GetFootprints():
    ref = f.GetReference()
    for p in f.Pads():
        key = (ref, p.GetPadName())
        tgt = want.get(key)
        if tgt is None:
            if p.GetNetname():
                missing.append('%s.%s (board has %s, schematic has none)'
                               % (ref, p.GetPadName(), p.GetNetname()))
            continue
        if p.GetNetname() != tgt:
            changes.append('%s.%-4s %-28s -> %s' % (ref, p.GetPadName(),
                                                    p.GetNetname() or '(none)', tgt))
            if tgt not in nets:
                ni = pcbnew.NETINFO_ITEM(board, tgt)
                board.Add(ni); nets[tgt] = ni; created.append(tgt)
            if APPLY:
                p.SetNet(nets[tgt])

print('pads needing a net change: %d' % len(changes))
for c in changes[:40]:
    print('   ' + c)
if len(changes) > 40:
    print('   ... and %d more' % (len(changes) - 40))
print('nets created: %s' % (sorted(set(created)) or 'none'))
print('board pads with no schematic counterpart: %s' % (missing or 'none'))

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)
board.Save(PCB)

# assert the board now matches the schematic exactly
b2 = pcbnew.LoadBoard(PCB)
bad = []
for f in b2.GetFootprints():
    for p in f.Pads():
        key = (f.GetReference(), p.GetPadName())
        if key in want and p.GetNetname() != want[key]:
            bad.append('%s.%s is %s, want %s' % (key[0], key[1], p.GetNetname(), want[key]))
assert not bad, bad[:10]
covered = sum(1 for f in b2.GetFootprints() for p in f.Pads()
              if (f.GetReference(), p.GetPadName()) in want)
print('VERIFIED: %d board pads match the schematic netlist exactly' % covered)
