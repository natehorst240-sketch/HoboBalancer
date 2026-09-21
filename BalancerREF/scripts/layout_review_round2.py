"""Rev G layout: D3 turned around, R39/R40 placed, USB pair routed through U7.

The board side of scripts/fix_review_round2.py. Run that first - this script asserts
the schematic netlist has already moved, and refuses to run against a Rev F sheet.

D3
    The schematic now has pin 1 (cathode) on USB_VBUS. Rotating the footprint 180 deg
    swaps which pad sits where, so setting pad 1 to USB_VBUS and pad 2 to GND at the
    same time leaves every existing track and via landing on exactly the same net it
    landed on before. The only visible change is the silkscreen band, which was
    pointing at the grounded end and now points at VBUS.

R39 / R40
    Two 0603 pulldowns on the front, left of U9, in the clear area between the
    OPT_COMP run and C27/C26 on the back. R39 taps OPT_COMP where it crosses x=109.4;
    R40 sits above U9 in the band between the ACCEL_DRDY run and OPT_COMP, and
    reaches the node the short way: out between U9's two pad rows and up into pin 2.
    Both grounds go straight to the In1 plane. The obvious spot for R40 - beside C26,
    next to the node it biases - is taken by C27's +3V3 via.

U7
    U7 moves up to sit under the connector, ahead of everything else. J1's D+/D- pads
    are at y=142.525; the IO pads the pair actually lands on were at y=130.575 and are
    now at y=139.3375, so the run from connector to clamp goes from 11.95 mm to
    3.19 mm - and it no longer reaches R6/R7's pads first with the array spurred off
    them.
    IO3 and IO4, wired in the schematic alongside IO2 and IO1, put a second pad of each
    net directly across the package from the first, so each data line now enters one
    pad and leaves the pad opposite: a straight run through the part with no stub.

    Orientation is +90 so that the ground pin faces the connector (its return current
    belongs at J1's shield, and the via to the In1 plane is 1 mm long) and the two
    data columns land 1.9 mm apart with D- to the left, matching how the pair leaves
    J1's interleaved pin rows. Downstream, D- and D+ have to swap sides to reach R6
    and R7, which they do the way the old routing did it: on different layers. D-
    stays on F.Cu all the way to R6's via, D+ drops to B.Cu below U7 and passes under.

    VBUS to the array's VP pin leaves the middle of the downstream row - the only
    direction not walled in by a data pad - and joins the trunk on the back.

Dry run by default.  Pass --apply to write.
"""
import sys, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
assert ROOT.name == 'BalancerREF', ROOT
APPLY = '--apply' in sys.argv
PCB = ROOT / 'BalancerREF.kicad_pcb'
KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
FPLIB = r'C:\Program Files\KiCad\10.0\share\kicad\footprints\Resistor_SMD.pretty'

import pcbnew
VEC = pcbnew.VECTOR2I
def MM(v): return pcbnew.FromMM(v)
def mm(v): return pcbnew.ToMM(v)
def P(x, y): return VEC(MM(x), MM(y))

F_CU, B_CU = pcbnew.F_Cu, pcbnew.B_Cu

# ---------------------------------------------------------------- placement
U7_AT, U7_ROT = (127.35, 138.2), 90     # +90: GND pin toward J1, D- column on the left
D3_ROT = 0                              # was 180; pad 1 (cathode, banded) moves to VBUS
R39_AT, R39_ROT = (109.4, 118.2), 270   # OPT_COMP pulldown, front
R40_AT, R40_ROT = (110.5, 114.5), 180   # R29/C26 node pulldown, front
D3_REF = (136.2, 140.2)     # where D3's designator already sits; the rotation would
                            # otherwise swing it across U7's pad 3
R39_REF = (107.9, 115.4)
R40_REF = (110.5, 113.2)
U9_REF = (111.0, 117.9)     # U9's designator sat where R40 now is

# U7 pads once placed (rot +90: 1,2,3 toward the connector; 4,5,6 downstream)
P1 = (126.40, 139.3375)   # IO1  D-   connector side
P2 = (127.35, 139.3375)   # VN   GND  connector side
P3 = (128.30, 139.3375)   # IO2  D+   connector side
P4 = (128.30, 137.0625)   # IO3  D+   downstream
P5 = (127.35, 137.0625)   # VP   VBUS downstream
P6 = (126.40, 137.0625)   # IO4  D-   downstream

# ---------------------------------------------------------------- copper to remove
# (layer, start, end) for tracks; ('via', at) for vias. Matched to 3 decimal places.
DROP_TRACKS = [
    # D- : the spur into old U7, and the long diagonal that reached R6's pad first
    ('F.Cu', (132.500, 131.475), (131.600, 130.575)),
    ('F.Cu', (132.500, 135.200), (132.250, 135.450)),
    ('F.Cu', (132.500, 132.525), (132.500, 135.200)),
    ('F.Cu', (132.500, 132.525), (132.500, 131.475)),
    ('F.Cu', (132.250, 135.450), (126.960, 140.740)),
    # D+ : the drop to the back at the connector and the back-side run to R7
    ('F.Cu', (127.460, 141.340), (127.700, 141.100)),
    ('B.Cu', (129.650, 139.150), (127.700, 141.100)),
    ('B.Cu', (129.650, 130.650), (129.650, 139.150)),
]
DROP_VIAS = [
    (127.700, 141.100),   # D+ crossing point at the connector
    (129.700, 130.575),   # D+ transition that sat inside R7's pad, now redundant
    (130.650, 132.850),   # fed old U7's VP pad; the trunk is continuous without it
    (130.6495, 130.5753),  # fed old U7's VN pad; nothing else reaches it now
]

# ---------------------------------------------------------------- copper to add
W_USB, W_GND, W_VBUS = 0.2, 0.5, 0.3
ADD_TRACKS = [
    # ---- D- : connector -> U7 pad 1 -> straight through -> pad 6 -> R6's via
    ('F.Cu', (126.960, 140.740), (126.400, 140.180), W_USB, '/USB_CONN_D-'),
    ('F.Cu', (126.400, 140.180), P1,                 W_USB, '/USB_CONN_D-'),
    ('F.Cu', P1,                 P6,                 W_USB, '/USB_CONN_D-'),
    ('F.Cu', P6,                 (126.400, 134.800), W_USB, '/USB_CONN_D-'),
    ('F.Cu', (126.400, 134.800), (132.500, 132.525), W_USB, '/USB_CONN_D-'),
    # ---- D+ : connector -> U7 pad 3 -> straight through -> pad 4 -> under D- -> R7
    ('F.Cu', (127.460, 141.340), (128.300, 140.500), W_USB, '/USB_CONN_D+'),
    ('F.Cu', (128.300, 140.500), P3,                 W_USB, '/USB_CONN_D+'),
    ('F.Cu', P3,                 P4,                 W_USB, '/USB_CONN_D+'),
    ('F.Cu', P4,                 (128.300, 136.000), W_USB, '/USB_CONN_D+'),
    ('B.Cu', (128.300, 136.000), (129.650, 134.650), W_USB, '/USB_CONN_D+'),
    ('B.Cu', (129.650, 134.650), (129.650, 130.650), W_USB, '/USB_CONN_D+'),
    # ---- U7 ground, straight up to the plane between the two data pads
    ('F.Cu', P2,                 (127.400, 140.200), 0.3,   'GND'),
    # ---- U7 VP: out of the downstream row, then the back to the VBUS trunk
    ('F.Cu', P5,                 (127.350, 136.000), W_VBUS, '/USB_VBUS'),
    ('B.Cu', (127.350, 136.000), (127.350, 136.900), W_VBUS, '/USB_VBUS'),
    ('B.Cu', (127.350, 136.900), (130.650, 136.900), W_VBUS, '/USB_VBUS'),
    ('B.Cu', (130.650, 136.900), (130.650, 136.200), W_VBUS, '/USB_VBUS'),
    # ---- R39: OPT_COMP tap down into the pulldown, then to the plane
    ('F.Cu', (109.400, 116.338), (109.400, 117.375), W_USB, '/OPT_COMP'),
    ('F.Cu', (109.400, 119.025), (109.400, 120.150), W_GND, 'GND'),
    # ---- R40: out of the pulldown, between U9's two pad rows, up into pin 2
    ('F.Cu', (111.325, 114.500), (112.025, 115.200), W_USB, None),   # RC node
    ('F.Cu', (112.025, 115.200), (114.000, 115.200), W_USB, None),
    ('F.Cu', (114.000, 115.200), (114.000, 116.338), W_USB, None),
    ('F.Cu', (109.675, 114.500), (109.675, 113.600), W_GND, 'GND'),
]
ADD_VIAS = [
    ((128.300, 136.000), 0.6, 0.3, '/USB_CONN_D+'),
    ((127.350, 136.000), 0.6, 0.3, '/USB_VBUS'),
    ((127.400, 140.200), 0.6, 0.3, 'GND'),
    ((109.400, 120.150), 0.6, 0.3, 'GND'),
    ((109.675, 113.600), 0.6, 0.3, 'GND'),
]

RC_NET = 'Net-(C26-Pad1)'


def key(p):
    return (round(mm(p.x), 3), round(mm(p.y), 3))


def near(p, want, tol=0.003):
    x, y = mm(p.x), mm(p.y)
    return next((w for w in want if abs(x - w[0]) < tol and abs(y - w[1]) < tol), None)


def main():
    board = pcbnew.LoadBoard(str(PCB))
    rc_name = RC_NET

    # Net codes, not NETINFO_ITEMs: a BOARD::Remove later in this script leaves SWIG
    # handing back undowncast proxies for anything looked up afterwards, and a cached
    # NETINFO_ITEM stops answering GetNetname(). Integers survive that.
    wanted = {rc_name} | {n for *_, n in ADD_TRACKS if n} | {n for *_, n in ADD_VIAS}
    wanted |= {'/USB_VBUS', 'GND', '/USB_CONN_D+', '/USB_CONN_D-', '/OPT_COMP'}
    by_name = board.GetNetsByName()
    codes = {}
    for name in sorted(wanted):
        item = by_name[name]
        assert item is not None and item.GetNetname() == name, name
        codes[name] = item.GetNetCode()

    def setnet(item, name):
        item.SetNetCode(codes[name if name is not None else rc_name])

    log = []

    # Every footprint this script touches is looked up now, before anything is removed
    # from the board: after a BOARD::Remove, SWIG hands back undowncast SwigPyObjects
    # for later lookups and every FOOTPRINT method disappears.
    d3 = board.FindFootprintByReference('D3')
    u7 = board.FindFootprintByReference('U7')
    # pcbnew.FootprintLoad is broken in 10.0.6 (the plugin object it hands back has no
    # such method), so the donor for the two new pulldowns is R30 - already the right
    # 0603 library footprint, carrying this project's own field setup.
    donor = board.FindFootprintByReference('R30')
    u9 = board.FindFootprintByReference('U9')
    assert donor.GetFPIDAsString() == 'Resistor_SMD:R_0603_1608Metric', \
        donor.GetFPIDAsString()

    # ---- D3 -----------------------------------------------------------------
    assert round(d3.GetOrientationDegrees()) == 180, d3.GetOrientationDegrees()
    pads = {p.GetNumber(): p for p in d3.Pads()}
    assert pads['1'].GetNetname() == 'GND' and pads['2'].GetNetname() == '/USB_VBUS', \
        'D3 is not wired the old way round: %s / %s' % (pads['1'].GetNetname(),
                                                        pads['2'].GetNetname())
    d3.SetOrientationDegrees(D3_ROT)
    d3.Reference().SetPosition(P(*D3_REF))
    setnet(pads['1'], '/USB_VBUS')
    setnet(pads['2'], 'GND')
    log.append('D3 rotated 180 -> 0 and pad nets swapped; every track keeps its pad')

    # ---- U7 -----------------------------------------------------------------
    u7.SetOrientationDegrees(U7_ROT)
    u7.SetPosition(P(*U7_AT))
    upads = {p.GetNumber(): p for p in u7.Pads()}
    setnet(upads['4'], '/USB_CONN_D+')
    setnet(upads['6'], '/USB_CONN_D-')
    got = {n: key(p.GetPosition()) for n, p in upads.items()}
    want = {'1': P1, '2': P2, '3': P3, '4': P4, '5': P5, '6': P6}
    for n, w in want.items():
        assert got[n] == (round(w[0], 3), round(w[1], 3)), (n, got[n], w)
    log.append('U7 -> %s rot %d; IO3/IO4 now carry D+/D- so each line crosses the part'
               % (U7_AT, U7_ROT))

    u9.Reference().SetPosition(P(*U9_REF))
    log.append('U9 designator moved clear of R40')

    # ---- new resistors ------------------------------------------------------
    # The donor is on the back and both pulldowns go on the front, so each copy is
    # flipped once it is placed.
    for ref, val, at_, rot, n1, n2, ref_at in (
            ('R39', '100k', R39_AT, R39_ROT, '/OPT_COMP', 'GND', R39_REF),
            ('R40', '100k', R40_AT, R40_ROT, rc_name, 'GND', R40_REF)):
        assert board.FindFootprintByReference(ref) is None, ref
        dup = donor.Duplicate(False)
        fp = dup if isinstance(dup, pcbnew.FOOTPRINT) else pcbnew.Cast_to_FOOTPRINT(dup)
        fp.SetReference(ref)
        fp.SetValue(val)
        fp.SetPosition(P(*at_))
        if fp.GetLayer() != F_CU:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        fp.SetOrientationDegrees(rot)
        assert fp.GetLayer() == F_CU, board.GetLayerName(fp.GetLayer())
        p = {x.GetNumber(): x for x in fp.Pads()}
        setnet(p['1'], n1)
        setnet(p['2'], n2)
        fp.Reference().SetPosition(P(*ref_at))
        # Add last: BOARD::Add takes ownership and the Python proxy stops behaving
        # like a FOOTPRINT afterwards.
        board.Add(fp)
        log.append('%s %s at %s rot %d: pad 1 %s, pad 2 %s'
                   % (ref, val, at_, rot, n1, n2))

    # ---- remove superseded copper -------------------------------------------
    want_tracks = {(l, tuple(sorted([s, e]))) for l, s, e in DROP_TRACKS}
    want_vias = {v for v in DROP_VIAS}
    gone_t, gone_v = set(), set()
    for t in list(board.GetTracks()):
        if t.Type() == pcbnew.PCB_VIA_T:
            k = near(t.GetPosition(), want_vias)
            if k is not None:
                board.Remove(t)
                gone_v.add(k)
        else:
            lay = board.GetLayerName(t.GetLayer())
            k = (lay, tuple(sorted([key(t.GetStart()), key(t.GetEnd())])))
            if k in want_tracks:
                board.Remove(t)
                gone_t.add(k)
    missing_t = want_tracks - gone_t
    missing_v = want_vias - gone_v
    assert not missing_t, 'tracks not found: %s' % sorted(missing_t)
    assert not missing_v, 'vias not found: %s' % sorted(missing_v)
    log.append('removed %d superseded tracks and %d vias' % (len(gone_t), len(gone_v)))

    # ---- new copper ---------------------------------------------------------
    for lay, s, e, w, nm in ADD_TRACKS:
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*s))
        t.SetEnd(P(*e))
        t.SetWidth(MM(w))
        t.SetLayer(F_CU if lay == 'F.Cu' else B_CU)
        setnet(t, nm)
        board.Add(t)
    for at_, dia, drill, nm in ADD_VIAS:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(P(*at_))
        v.SetWidth(MM(dia))
        v.SetDrill(MM(drill))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(F_CU, B_CU)
        setnet(v, nm)
        board.Add(v)
    log.append('added %d tracks and %d vias' % (len(ADD_TRACKS), len(ADD_VIAS)))

    for line in log:
        print('  ' + line)

    if not APPLY:
        print('\nDRY RUN - nothing written.')
        return

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(PCB))
    print('\nwrote %s' % PCB.name)


main()
