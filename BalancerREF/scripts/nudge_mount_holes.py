"""Pull the four M2.5 corner mounting holes 0.25 mm in on Y.

U1's courtyard is a T: the wide antenna keepout band spans the full board width but
sits almost entirely ABOVE the top edge - it dips only 0.44 mm onto the board. The top
mounting-hole courtyards started 0.30 mm in, so they overlapped that band by 0.14 mm.
Geometrically trivial, but it is two DRC violations, and an accepted baseline is where
a real violation goes to hide - which has already happened once on this board, when
U1's pads sat 0.35 mm off the edge inside a pile of ignored errors.

Both ends move so the pattern stays symmetric about the board centre: the bracket gets
a 43.40 x 42.90 mm rectangle instead of 43.40 x 43.40, still centred on (125, 125).

Dry run by default. Pass --apply to write.
"""
import sys
import pcbnew

APPLY = '--apply' in sys.argv
PCB = r'C:\Users\nateh\hgs-linux\Balancer\BalancerREF\BalancerREF.kicad_pcb'
DY = 0.25
CENTRE_Y = 125.0

board = pcbnew.LoadBoard(PCB)
holes = [f for f in board.GetFootprints() if f.GetReference().startswith('H')]
assert len(holes) == 4, 'expected 4 mounting holes, found %d' % len(holes)

for f in sorted(holes, key=lambda f: f.GetReference()):
    p = f.GetPosition()
    x, y = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
    ny = y + DY if y < CENTRE_Y else y - DY      # always toward the centre
    f.SetPosition(pcbnew.VECTOR2I(p.x, pcbnew.FromMM(ny)))
    print('  %-4s (%.2f, %.2f) -> (%.2f, %.2f)' % (f.GetReference(), x, y, x, ny))

ys = sorted({round(pcbnew.ToMM(f.GetPosition().y), 3) for f in holes})
xs = sorted({round(pcbnew.ToMM(f.GetPosition().x), 3) for f in holes})
assert len(xs) == 2 and len(ys) == 2, (xs, ys)
assert abs((ys[0] + ys[1]) / 2 - CENTRE_Y) < 1e-6, 'pattern no longer centred'
print('pattern now %.2f x %.2f mm, centred on (%.2f, %.2f)'
      % (xs[1] - xs[0], ys[1] - ys[0], (xs[0] + xs[1]) / 2, (ys[0] + ys[1]) / 2))

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)
board.Save(PCB)
print('Saved.')
