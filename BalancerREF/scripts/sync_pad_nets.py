"""Reconcile every board pad's net against the schematic netlist.

This is the net half of what pcbnew's "Update PCB from Schematic" does, which has no
kicad-cli equivalent. The board had drifted across several edits: SW1/C30 still sat on
Net-(D2-K) after D2 was deleted, U9 on Net-(R28-Pad1) after the optical split, and -
worse - U1 pin 8 was never actually joined to the BAT_SENSE divider, because that
change assigned nets to the new passives but not to the MCU pad. The schematic netlist
verified clean throughout; only the board was wrong.

Reads the pad->net map exported from the schematic and asserts the board matches it
exactly afterwards, so a silent miss is not possible.

Dry run by default. Pass --apply to write.
"""
import sys, os, json
import pcbnew

APPLY = '--apply' in sys.argv
PCB = r'C:\Users\nateh\hgs-linux\Balancer\BalancerREF\BalancerREF.kicad_pcb'
MAP = r'C:\Users\nateh\AppData\Local\Temp\claude\padnets.json'

want = {tuple(k.split('|', 1)): v for k, v in json.load(open(MAP)).items()}
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
