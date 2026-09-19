"""Bring the board in line with the Rev G schematic (scripts/rev_g_usb_esd_tvs_u9.py).

Runs under KiCad's own Python (needs the pcbnew module; on Linux that is
/usr/bin/python3 with the kicad package installed, on Windows KiCad's bundled python).

- D3 is rotated 180 degrees so pad 1 (the cathode, marked end of the D_SMF footprint)
  lands where the VBUS copper already is; the pads are symmetric so nothing else moves.
- R39 (100k, OPT_COMP pull-down) is added on the back under U9, cloned from R38.
- Every pad's net is then set from a fresh kicad-cli netlist export of the schematic
  and asserted to match, the same idea as scripts/sync_pad_nets.py. That covers D3's
  two pads, U7 pads 4 and 6 (now on the USB data nets) and the new R39.

Routing is NOT touched: U7 pads 4/6 and R39 come up as ratsnest lines. The USB data
traces still have to be re-routed so each one enters U7 on pins 1/3 and leaves on
pins 6/4 on its way to R6/R7.

Dry run by default. Pass --apply to write.
"""
import os
import subprocess
import sys
import tempfile

import pcbnew

APPLY = '--apply' in sys.argv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, 'BalancerREF.kicad_pcb')
SCH = os.path.join(ROOT, 'BalancerREF.kicad_sch')
KC = os.environ.get('KICAD_CLI', 'kicad-cli')

R39_SCH_UUID = None   # filled from the schematic below
R39_AT = (113.75, 115.2)   # back side under U9, the nearest spot clear of existing copper
R39_ROT = 0


def sexp(text):
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
            s = i
            while text[i] != '"':
                if text[i] == '\\':
                    i += 1
                i += 1
            i += 1
            return text[s:i - 1]
        s = i
        while i < n and text[i] not in ' \t\r\n()':
            i += 1
        return text[s:i]
    return parse()


def netlist():
    tmp = os.path.join(tempfile.mkdtemp(), 'sch.net')
    subprocess.run([KC, 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', tmp, SCH],
                   check=True, capture_output=True)
    doc = sexp(open(tmp, encoding='utf8').read())
    nets = next(x for x in doc if isinstance(x, list) and x and x[0] == 'nets')
    out = {}
    for net in nets[1:]:
        name = next(x[1] for x in net if isinstance(x, list) and x[0] == 'name')
        for node in net:
            if isinstance(node, list) and node[0] == 'node':
                kv = {x[0]: x[1] for x in node[1:] if isinstance(x, list)}
                if not kv['ref'].startswith('#'):
                    out[(kv['ref'], kv['pin'])] = name
    return out


want = netlist()
print('schematic netlist: %d pins' % len(want))

with open(SCH, encoding='utf8') as f:
    s = f.read()
i = s.find('(property "Reference" "R39"')
assert i > 0, 'R39 is not in the schematic; run rev_g_usb_esd_tvs_u9.py first'
j = s.rfind('\n\t(symbol\n', 0, i)
R39_SCH_UUID = s[j:i].split('(uuid "')[1].split('"')[0]

b = pcbnew.LoadBoard(PCB)
fps = {f.GetReference(): f for f in b.GetFootprints()}
assert 'R39' not in fps, 'R39 is already on the board'

# --- D3 -----------------------------------------------------------------------
d3 = fps['D3']
before = d3.GetOrientationDegrees()
d3.SetOrientationDegrees((before + 180) % 360)
print('D3 rotated %.0f -> %.0f' % (before, d3.GetOrientationDegrees()))

# --- R39 ----------------------------------------------------------------------
r39 = pcbnew.FOOTPRINT(fps['R38'])
r39.SetReference('R39')
r39.SetValue('100k')
r39.SetPath(pcbnew.KIID_PATH('/' + R39_SCH_UUID))
r39.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(R39_AT[0]), pcbnew.FromMM(R39_AT[1])))
r39.SetOrientationDegrees(R39_ROT)
# the cloned reference text lands on C26's; stand it beside the body instead
r39.Reference().SetPosition(r39.GetPosition() + pcbnew.VECTOR2I(pcbnew.FromMM(-2.3), 0))
r39.Reference().SetTextAngleDegrees(90)
b.Add(r39)
fps['R39'] = r39
print('R39 cloned from R38 at %s rot %d on %s' % (R39_AT, R39_ROT, r39.GetLayerName()))

# --- pad nets ------------------------------------------------------------------
changed = []
for f in b.GetFootprints():
    for p in f.Pads():
        key = (f.GetReference(), p.GetPadName())
        if key not in want:
            continue
        # KiCad keeps the schematic's unconnected-(...) names on the board too, so
        # they are copied verbatim rather than blanked.
        name = want[key]
        if p.GetNetname() != name:
            net = b.FindNet(name)
            if net is None:
                net = pcbnew.NETINFO_ITEM(b, name)
                b.Add(net)
            changed.append('%s.%s %s -> %s' % (key[0], key[1], p.GetNetname() or '(none)', name))
            p.SetNet(net)
for c in changed:
    print('  ', c)
print('%d pads changed' % len(changed))

missing = [k for k in want if k[0] not in fps]
assert not missing, 'footprints missing from the board: %s' % sorted({k[0] for k in missing})
for f in b.GetFootprints():
    for p in f.Pads():
        key = (f.GetReference(), p.GetPadName())
        if key in want:
            assert p.GetNetname() == want[key], (key, p.GetNetname(), want[key])
print('board pads match the schematic netlist')

if APPLY:
    pcbnew.SaveBoard(PCB, b)
    print('written', PCB)
else:
    print('dry run; pass --apply to write')
