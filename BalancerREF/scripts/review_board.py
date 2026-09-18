"""Layout review checks that DRC does not do. Read-only.

  python.exe -u scripts/review_board.py
"""
import os, math, collections
import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
b = pcbnew.LoadBoard(os.path.join(ROOT, 'BalancerREF.kicad_pcb'))
mm = pcbnew.ToMM
fps = {f.GetReference(): f for f in b.GetFootprints()}
tracks = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK']
vias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA']
LN = {pcbnew.F_Cu: 'F', pcbnew.In1_Cu: 'In1', pcbnew.In2_Cu: 'In2', pcbnew.B_Cu: 'B'}


def pad(ref, name):
    return next(p for p in fps[ref].Pads() if p.GetPadName() == name)


def ppos(p):
    return mm(p.GetPosition().x), mm(p.GetPosition().y)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def net_tracks(net):
    return [t for t in tracks if t.GetNetname() == net]


def net_vias(net):
    return [v for v in vias if v.GetNetname() == net]


def net_len(net):
    return sum(mm(t.GetLength()) for t in net_tracks(net))


print('=' * 70)
print('1. DECOUPLING: distance from cap pad to the IC pin it serves (want < 3 mm)')
pairs = [('C8', '1', 'U1', '3'), ('C9', '1', 'U1', '3'), ('C10', '1', 'U1', '45'),
         ('C13', '1', 'U2', None), ('C14', '1', 'U2', None), ('C15', '1', 'U2', None),
         ('C16', '1', 'U3', None), ('C17', '1', 'U3', None),
         ('C1', '1', 'U5', '13'), ('C2', '1', 'U5', '13'), ('C3', '1', 'U5', '2'), ('C30', '1', 'U5', '11'),
         ('C4', '1', 'U6', '5'), ('C5', '1', 'U6', '8'), ('C6', '1', 'U6', '1'), ('C7', '1', 'U6', '1'),
         ('C27', '1', 'U9', None), ('C29', '1', 'U10', None), ('C11', None, 'SW2', None)]
for cref, cpad, icref, icpad in pairs:
    if cref not in fps or icref not in fps:
        continue
    c = fps[cref]
    cp = pad(cref, cpad) if cpad else list(c.Pads())[0]
    net = cp.GetNetname()
    if icpad:
        ip = pad(icref, icpad)
    else:
        ip = next((p for p in fps[icref].Pads() if p.GetNetname() == net), None)
    if ip is None:
        print('  %-4s no %s pad on %s' % (cref, net, icref)); continue
    d = dist(ppos(cp), ppos(ip))
    side = 'same side' if c.GetLayer() == fps[icref].GetLayer() else 'OTHER SIDE (via)'
    flag = '' if d < 3 else '  <-- far'
    print('  %-4s %-14s -> %s.%-3s %5.2f mm  %s%s' % (cref, net, icref, ip.GetPadName(), d, side, flag))

print('=' * 70)
print('2. POWER PATH: track width and via count per net (class Power = 0.5 mm, via 0.8/0.4)')
for net in ['/USB_VBUS', '/BAT', '/SYS', '/SYS_SW', '/+3V3', 'GND']:
    ts = net_tracks(net); vs = net_vias(net)
    widths = collections.Counter(round(mm(t.GetWidth()), 2) for t in ts)
    layers = collections.Counter(LN.get(t.GetLayer(), '?') for t in ts)
    vsz = collections.Counter((round(mm(v.GetWidth(pcbnew.F_Cu)), 2), round(mm(v.GetDrillValue()), 2)) for v in vs)
    thin = sum(mm(t.GetLength()) for t in ts if mm(t.GetWidth()) < 0.45)
    print('  %-10s %5.1f mm routed  widths %s  layers %s  vias %s%s'
          % (net, net_len(net), dict(widths), dict(layers), dict(vsz),
             ('  <-- %.1f mm under 0.45 wide' % thin) if thin > 0 else ''))

print('=' * 70)
print('3. BUCK-BOOST SWITCH NODE (class Switch = 0.8 mm, keep it short)')
for net in ['Net-(U6-L1)', 'Net-(U6-L2)']:
    ts = net_tracks(net)
    print('  %-12s %.2f mm, widths %s, vias %d, layers %s' % (
        net, net_len(net), dict(collections.Counter(round(mm(t.GetWidth()), 2) for t in ts)),
        len(net_vias(net)), dict(collections.Counter(LN.get(t.GetLayer(), '?') for t in ts))))

print('=' * 70)
print('4. USB: D+/D- lengths, layer changes, series R placement')
for a, b_ in [('/USB_CONN_D+', '/USB_CONN_D-'), ('Net-(U1-USB_D+)', 'Net-(U1-USB_D-)')]:
    la, lb = net_len(a), net_len(b_)
    print('  %-18s %6.2f mm  %d vias   |  %-18s %6.2f mm  %d vias   mismatch %.2f mm'
          % (a, la, len(net_vias(a)), b_, lb, len(net_vias(b_)), abs(la - lb)))
for r in ('R6', 'R7'):
    print('  %s at (%.1f, %.1f) %s; J1 at (%.1f, %.1f); U7 at (%.1f, %.1f)' % (
        r, *ppos(list(fps[r].Pads())[0]), LN[fps[r].GetLayer()], mm(fps['J1'].GetPosition().x),
        mm(fps['J1'].GetPosition().y), mm(fps['U7'].GetPosition().x), mm(fps['U7'].GetPosition().y)))

print('=' * 70)
print('5. ANTENNA KEEP-OUT: copper inside U1 footprint rule areas')
u1 = fps['U1']
kos = [z for z in u1.Zones() if z.GetIsRuleArea()]
for z in kos:
    bb = z.GetBoundingBox()
    box = (mm(bb.GetLeft()), mm(bb.GetRight()), mm(bb.GetTop()), mm(bb.GetBottom()))
    inside_t = [t for t in tracks if box[0] <= mm(t.GetStart().x) <= box[1] and box[2] <= mm(t.GetStart().y) <= box[3]]
    inside_v = [v for v in vias if box[0] <= mm(v.GetPosition().x) <= box[1] and box[2] <= mm(v.GetPosition().y) <= box[3]]
    inside_f = [f.GetReference() for f in b.GetFootprints() if f.GetReference() != 'U1'
                and box[0] <= mm(f.GetPosition().x) <= box[1] and box[2] <= mm(f.GetPosition().y) <= box[3]]
    print('  rule area x %.1f..%.1f y %.1f..%.1f (%s): tracks %d, vias %d, footprints %s, copper pour blocked=%s'
          % (*box, z.GetZoneName() or 'unnamed', len(inside_t), len(inside_v), inside_f, z.GetDoNotAllowZoneFills()))
if not kos:
    print('  U1 has no rule area -- antenna region is NOT protected')

print('=' * 70)
print('6. PLANES: zones and what cuts them')
for z in b.Zones():
    if z.GetIsRuleArea():
        continue
    lay = LN.get(z.GetLayer(), z.GetLayerName())
    cuts = [t for t in tracks if t.GetLayer() == z.GetLayer()]
    print('  zone %-8s on %-4s filled=%s  tracks on that layer: %d (%.1f mm) nets %s'
          % (z.GetNetname(), lay, z.IsFilled(), len(cuts), sum(mm(t.GetLength()) for t in cuts),
             sorted({t.GetNetname() for t in cuts})[:8]))
print('  tracks on In1:', sum(1 for t in tracks if t.GetLayer() == pcbnew.In1_Cu),
      ' on In2:', sum(1 for t in tracks if t.GetLayer() == pcbnew.In2_Cu))

print('=' * 70)
print('7. THERMAL / EP VIAS: GND vias inside exposed pads')
for ref, epname in [('U5', '17'), ('U6', '11')]:
    ep = pad(ref, epname); bb = ep.GetBoundingBox()
    n = sum(1 for v in vias if bb.Contains(v.GetPosition()) and v.GetNetname() == 'GND')
    print('  %s EP (%.2f x %.2f mm): %d GND vias' % (ref, mm(bb.GetWidth()), mm(bb.GetHeight()), n))

print('=' * 70)
print('8. SENSITIVE ANALOGUE: LM1815 input and timing nets, length and layers')
for net in ['Net-(J3-Pin_1)', 'Net-(R13-Pad1)', 'Net-(U3-VR_IN)', 'Net-(U3-RC_TIMING)', 'Net-(U3-PEAK_DET)', '/MAG_TACH']:
    ts = net_tracks(net)
    print('  %-20s %6.2f mm  vias %d  layers %s' % (net, net_len(net), len(net_vias(net)),
          dict(collections.Counter(LN.get(t.GetLayer(), '?') for t in ts))))

print('=' * 70)
print('9. SWITCHER NEIGHBOURS: what sits within 4 mm of L1')
l1 = (mm(fps['L1'].GetPosition().x), mm(fps['L1'].GetPosition().y))
near = sorted((dist(l1, (mm(f.GetPosition().x), mm(f.GetPosition().y))), f.GetReference())
              for f in b.GetFootprints() if f.GetReference() != 'L1')
print('  ' + ', '.join('%s %.1f' % (r, d) for d, r in near if d < 4.0))
aud = [t for t in tracks if t.GetNetname() in ('Net-(J3-Pin_1)', 'Net-(R13-Pad1)', 'Net-(U3-VR_IN)', '/USB_CONN_D+', '/USB_CONN_D-')
       and dist(l1, (mm(t.GetStart().x), mm(t.GetStart().y))) < 5]
print('  sensitive tracks within 5 mm of L1: %d' % len(aud))

print('=' * 70)
print('10. UNROUTED and dangling')
conn = b.GetConnectivity()
print('  unconnected count: %d' % conn.GetUnconnectedCount(True))
