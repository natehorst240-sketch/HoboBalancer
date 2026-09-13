"""Add UP / LEFT orientation markers to BalancerREF's front silkscreen.

The puck mounts vertically with the ESP32 to the left and the USB-C to the right.
On the board as drawn U1 sits at the top and J1 at the bottom, so mounting it that
way rotates the drawing 90 degrees counter-clockwise (top goes to the left). Under
that rotation:

    board +x  ->  UP      (so the UP arrow is drawn pointing screen-right)
    board -y  ->  LEFT    (so the LEFT arrow is drawn pointing screen-up)
    board +z  ->  out of the component face, i.e. lateral once mounted

UP is the one that matters for measurement: with the board vertical, the vertical
axis is IN-PLANE, which is the stiff direction, and the floppy out-of-plane axis
carries lateral instead. Gravity puts a static 1 g on whichever in-plane axis is
vertical, so firmware can identify it at startup and refuse to measure if no axis
reads ~1 g.

These markers are on F.SilkS and assume you are looking at the COMPONENT face. Seen
from the back the left/right sense mirrors.

Dry run by default. Pass --apply to write.
"""
import sys
import pcbnew

APPLY = '--apply' in sys.argv
PCB = r'C:\Users\nateh\hgs-linux\Balancer\BalancerREF\BalancerREF.kicad_pcb'

ORIGIN = (141.8, 128.8)     # corner of the L, inside the clear zone at (141,121)
ARM = 5.6                   # arrow length, mm
HEAD = 1.1                  # arrowhead length, mm
TXT = 1.1                   # text height, mm
THICK = 0.15

board = pcbnew.LoadBoard(PCB)
silk = board.GetLayerID('F.SilkS')


def seg(x1, y1, x2, y2):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(x1), pcbnew.FromMM(y1)))
    s.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(x2), pcbnew.FromMM(y2)))
    s.SetLayer(silk)
    s.SetWidth(pcbnew.FromMM(THICK))
    board.Add(s)


def text(t, x, y, rot=0):
    e = pcbnew.PCB_TEXT(board)
    e.SetText(t)
    e.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
    e.SetLayer(silk)
    e.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(TXT), pcbnew.FromMM(TXT)))
    e.SetTextThickness(pcbnew.FromMM(THICK))
    e.SetTextAngle(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
    board.Add(e)


ox, oy = ORIGIN

# UP: board +x, drawn pointing screen-right.
seg(ox, oy, ox + ARM, oy)
seg(ox + ARM, oy, ox + ARM - HEAD, oy - HEAD * 0.6)
seg(ox + ARM, oy, ox + ARM - HEAD, oy + HEAD * 0.6)
text('UP', ox + ARM - 1.4, oy - 1.5)

# LEFT: board -y, drawn pointing screen-up.
seg(ox, oy, ox, oy - ARM)
seg(ox, oy - ARM, ox - HEAD * 0.6, oy - ARM + HEAD)
seg(ox, oy - ARM, ox + HEAD * 0.6, oy - ARM + HEAD)
text('LEFT', ox + 1.6, oy - ARM + 1.2, 90)

print('UP   arrow %.1f,%.1f -> %.1f,%.1f  (board +x)' % (ox, oy, ox + ARM, oy))
print('LEFT arrow %.1f,%.1f -> %.1f,%.1f  (board -y)' % (ox, oy, ox, oy - ARM))

# Nothing on the front may sit under the markers.
box = (min(ox - 1.0, ox - 1.0), ox + ARM + 0.4, oy - ARM - 0.4, oy + 0.8)
clash = []
for f in board.GetFootprints():
    if f.GetLayer() != pcbnew.F_Cu:
        continue
    bb = f.GetBoundingBox(False, False)
    l, r = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight())
    t, b = pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())
    if box[0] < r and l < box[1] and box[2] < b and t < box[3]:
        clash.append(f.GetReference())
print('marker envelope x %.1f..%.1f y %.1f..%.1f  clashes: %s'
      % (box[0], box[1], box[2], box[3], clash or 'none'))

eb = board.GetBoardEdgesBoundingBox()
inside = (pcbnew.ToMM(eb.GetLeft()) <= box[0] and box[1] <= pcbnew.ToMM(eb.GetRight())
          and pcbnew.ToMM(eb.GetTop()) <= box[2] and box[3] <= pcbnew.ToMM(eb.GetBottom()))
print('inside board outline:', inside)

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)
if clash or not inside:
    print('\nREFUSING TO WRITE.')
    sys.exit(1)
board.Save(PCB)
print('Saved.')
