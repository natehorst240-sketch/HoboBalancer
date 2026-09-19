"""Route the four connections Rev G added, on top of the fully routed board (PR #7).

    /usr/bin/python3 scripts/route_rev_g.py BalancerREF.kicad_pcb     (KiCad's Python, pcbnew)

Run after sync_board_rev_g.py. Adds two 0.2 mm front-side tracks straight across U7
(pin 3 to pin 4 for D+, pin 1 to pin 6 for D-), a via at R39's OPT_COMP pad onto the
front-side OPT_COMP trace it sits under, and a via plus stub from R39's GND pad to the
ground planes. Zones are refilled and the board saved. The positions are for R39 at
(106.6, 116.3375) rot 0 on the back, which is where sync_board_rev_g.py now puts it;
DRC afterwards was 0 unconnected with only PR #7's accepted warnings remaining.
"""
import pcbnew
import sys

PCB = sys.argv[1] if len(sys.argv) > 1 else __file__.rsplit('/scripts/', 1)[0] + '/BalancerREF.kicad_pcb'
b=pcbnew.LoadBoard(PCB); FM=pcbnew.FromMM; mm=pcbnew.ToMM
def net(n):
    x=b.FindNet(n); assert x, n; return x
def track(a,c,layer,n,w=0.2):
    t=pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(FM(a[0]),FM(a[1]))); t.SetEnd(pcbnew.VECTOR2I(FM(c[0]),FM(c[1])))
    t.SetWidth(FM(w)); t.SetLayer(b.GetLayerID(layer)); t.SetNet(net(n)); b.Add(t)
def via(p,n,d=0.6,h=0.3):
    v=pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(FM(p[0]),FM(p[1]))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(FM(d)); v.SetDrill(FM(h)); v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu); v.SetNet(net(n)); b.Add(v)
# U7: pin 3 -> pin 4 (D+) and pin 1 -> pin 6 (D-) straight across the package
track((129.7,130.575),(129.7,132.85),'F.Cu','/USB_CONN_D+')
track((131.6,130.575),(131.6,132.85),'F.Cu','/USB_CONN_D-')
# R39 lies on the back directly under the front-side OPT_COMP trace (y=116.3375), left
# of the SYS_SW track and U9. A via at its OPT_COMP pad lands on that trace; the GND pad
# gets a via just above it, clear of the trace (below it is J5 pin 1).
r39=next(f for f in b.GetFootprints() if f.GetReference()=='R39')
pp={p.GetNetname():(mm(p.GetPosition().x),mm(p.GetPosition().y)) for p in r39.Pads()}
print('R39 pads',pp)
assert abs(pp['/OPT_COMP'][1]-116.3375)<0.01
via(pp['/OPT_COMP'],'/OPT_COMP')
g=pp['GND']; gv=(105.975,115.538); via(gv,"GND"); track(g,gv,"B.Cu","GND")
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(PCB,b); print('routed and saved')
