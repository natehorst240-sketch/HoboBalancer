"""Generate BalancerMain.kicad_pcb from the verified schematic netlist.

Footprint geometry is harvested from the carrier and optical-head boards in this repo
(KiCad's own R_1206, SOIC-14, SOT-23, headers, switch, solder pads, FeatherS3) and the
few footprints those boards lack are built here: C_1206 (R_1206 pads), SOT-23-6 (from the
SOT-23-5 pattern), 2x3 socket, radial inductor, 1812 polyfuse, SMA diode, 3-pad solder
strip, pogo pins, M3 hole. Every part is placed with its nets and the outline drawn;
routing is left to KiCad. Run verify_main.py first (it writes BalancerMain.net.json).
Pass --apply to write.
"""
import sys, json, uuid
from copy import deepcopy
from pathlib import Path
import sexpdata as sx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent.parent
APPLY = '--apply' in sys.argv
S = sx.Symbol
def node(k, *v): return [S(k), *v]
def tagged(x, k): return isinstance(x, list) and x and str(x[0]) == k
def children(x, k): return [a for a in x if tagged(a, k)]
def one(x, k): return next((a for a in x if tagged(a, k)), None)
def uid(): return str(uuid.uuid4())

net = json.loads((ROOT / 'BalancerMain.net.json').read_text())
NETS = net['nets']                       # name -> [[ref, pin], ...]
PARTS = {p[0]: (p[1], p[2]) for p in net['parts']}   # ref -> (value, footprint)
for h in ('H1', 'H2', 'H3', 'H4'):   # pinless symbols are not in the netlist
    PARTS[h] = ('MountingHole', 'MountingHole:MountingHole_3.2mm_M3')
POWER = {'GND', '+3V3', 'VBUS', '+12V', 'VBAT'}
pin_net = {}
for name, members in NETS.items():
    kname = name if name in POWER else '/' + name
    for ref, pin in members:
        pin_net[(ref, pin)] = kname
# schematic symbol uuids for the footprint path property
sch = sx.loads((ROOT / 'BalancerMain.kicad_sch').read_text(encoding='utf8'))
SHEET = str(one(sch, 'uuid')[1])
sym_uuid = {}
for s in children(sch, 'symbol'):
    props = {str(p[1]): str(p[2]) for p in children(s, 'property')}
    sym_uuid[props['Reference']] = str(one(s, 'uuid')[1])

# ---------------------------------------------------------------- harvest footprints
templates = {}
for f in (REPO / 'BalancerCarrier' / 'BalancerCarrier.kicad_pcb', REPO / 'BalancerREF_OptHead' / 'BalancerREF_OptHead.kicad_pcb',
          ROOT / 'vendor' / 'OMGS3_Carrier_R1.kicad_pcb'):
    doc = sx.loads(f.read_text(encoding='utf8'))
    if 'header' not in templates:
        templates['header'] = {k: one(doc, k) for k in ('layers', 'setup')}
    for fp in children(doc, 'footprint'):
        templates.setdefault(str(fp[1]), fp)


def refresh_uuids(x):
    if isinstance(x, list):
        if tagged(x, 'uuid'): x[1] = uid()
        for a in x: refresh_uuids(a)


def strip_instance(fp):
    """Remove everything that belongs to a placed instance, keep the geometry."""
    keep = []
    for a in fp:
        if isinstance(a, list) and str(a[0]) in ('at', 'path', 'sheetname', 'sheetfile', 'units', 'property', 'uuid', 'version', 'generator', 'generator_version', 'model', 'tstamp'):
            continue
        keep.append(a)
    for a in keep:
        if tagged(a, 'pad'):
            a[:] = [b for b in a if not (isinstance(b, list) and str(b[0]) in ('net', 'pinfunction', 'pintype'))]
    return keep


def template(name):
    if name in templates: return deepcopy(templates[name])
    raise KeyError(name)


def pad(num, kind, shape, x, y, w, h, drill=None, rot=0, layers=None, rr=0.25):
    p = node('pad', str(num), S(kind), S(shape), node('at', x, y, rot) if rot else node('at', x, y), node('size', w, h))
    if drill: p.append(node('drill', drill))
    if layers is None:
        layers = ['F.Cu', 'F.Mask', 'F.Paste'] if kind == 'smd' else ['*.Cu', '*.Mask']
    p.append(node('layers', *layers))
    if shape == 'roundrect': p.append(node('roundrect_rratio', rr))
    p.append(node('uuid', uid()))
    return p


def line(x1, y1, x2, y2, layer='F.SilkS', w=0.12):
    return node('fp_line', node('start', x1, y1), node('end', x2, y2), node('stroke', node('width', w), node('type', S('solid'))), node('layer', layer), node('uuid', uid()))


def rect(x1, y1, x2, y2, layer='F.CrtYd', w=0.05):
    return node('fp_rect', node('start', x1, y1), node('end', x2, y2), node('stroke', node('width', w), node('type', S('solid'))), node('fill', S('no')), node('layer', layer), node('uuid', uid()))


def build(name, attr, pads, extras, descr=''):
    fp = node('footprint', name, node('layer', 'F.Cu'), node('descr', descr), node('attr', S(attr)))
    fp.extend(extras); fp.extend(pads)
    return fp


# C_1206: same pads as R_1206
c1206 = template('Resistor_SMD:R_1206_3216Metric'); c1206[1] = 'Capacitor_SMD:C_1206_3216Metric'
c1206[:] = strip_instance(c1206)
templates['Capacitor_SMD:C_1206_3216Metric'] = c1206
# SOT-23-6 from the SOT-23-5 pattern
s5 = template('Package_TO_SOT_SMD:SOT-23-5'); s5[:] = strip_instance(s5)
s5[1] = 'Package_TO_SOT_SMD:SOT-23-6'
s5[:] = [a for a in s5 if not tagged(a, 'pad')]
s5.extend([pad(1, 'smd', 'roundrect', -1.1375, -0.95, 1.325, 0.6, rot=270), pad(2, 'smd', 'roundrect', -1.1375, 0, 1.325, 0.6, rot=270),
           pad(3, 'smd', 'roundrect', -1.1375, 0.95, 1.325, 0.6, rot=270), pad(4, 'smd', 'roundrect', 1.1375, 0.95, 1.325, 0.6, rot=270),
           pad(5, 'smd', 'roundrect', 1.1375, 0, 1.325, 0.6, rot=270), pad(6, 'smd', 'roundrect', 1.1375, -0.95, 1.325, 0.6, rot=270)])
templates['Package_TO_SOT_SMD:SOT-23-6'] = s5
# 2x3 socket, 2.54 mm, pin 1 top-left; odd pins left column (matches the symbol and UG-1119)
templates['Connector_PinSocket_2.54mm:PinSocket_2x03_P2.54mm_Vertical'] = build(
    'Connector_PinSocket_2.54mm:PinSocket_2x03_P2.54mm_Vertical', 'through_hole',
    [pad(n, 'thru_hole', 'rect' if n == 1 else 'circle', (n - 1) % 2 * 2.54, (n - 1) // 2 * 2.54, 1.7, 1.7, drill=1.0) for n in range(1, 7)],
    [rect(-1.27, -1.27, 3.81, 6.35, 'F.SilkS', 0.12), rect(-1.77, -1.77, 4.31, 6.85)], '2x3 socket for the EVAL-ADXL357Z headers')
# radial inductor, 9-10 mm body, 5 mm pitch (Bourns RLB0914 / Murata 1400 series)
templates['BalancerMain:L_Radial_D9_P5'] = build('BalancerMain:L_Radial_D9_P5', 'through_hole',
    [pad(1, 'thru_hole', 'rect', -2.5, 0, 1.8, 1.8, drill=1.0), pad(2, 'thru_hole', 'circle', 2.5, 0, 1.8, 1.8, drill=1.0)],
    [node('fp_circle', node('center', 0, 0), node('end', 5.0, 0), node('stroke', node('width', 0.12), node('type', S('solid'))), node('fill', S('no')), node('layer', 'F.SilkS'), node('uuid', uid())),
     rect(-5.5, -5.5, 5.5, 5.5)], 'radial inductor 9-10 mm, 5 mm pitch')
templates['Fuse:Fuse_1812_4532Metric'] = build('Fuse:Fuse_1812_4532Metric', 'smd',
    [pad(1, 'smd', 'roundrect', -2.05, 0, 1.4, 3.4), pad(2, 'smd', 'roundrect', 2.05, 0, 1.4, 3.4)],
    [line(-1.0, -1.85, 1.0, -1.85), line(-1.0, 1.85, 1.0, 1.85), rect(-3.0, -1.95, 3.0, 1.95)], '1812 polyfuse')
templates['Diode_SMD:D_SMA'] = build('Diode_SMD:D_SMA', 'smd',
    [pad(1, 'smd', 'roundrect', -2.0, 0, 2.5, 1.8), pad(2, 'smd', 'roundrect', 2.0, 0, 2.5, 1.8)],
    [line(-3.5, -1.55, 1.5, -1.55), line(-3.5, 1.55, 1.5, 1.55), line(-3.5, -1.55, -3.5, 1.55), rect(-3.5, -1.65, 3.5, 1.65)], 'SMA (DO-214AC); pin 1 cathode, marked by the bar')
sw2 = template('Connector_Wire:SolderWire-0.1sqmm_1x02_P3.6mm_D0.4mm_OD1mm'); sw2[:] = strip_instance(sw2)
sw2[1] = 'BalancerMain:SolderWire_1x02'
sw2[:] = [a for a in sw2 if not tagged(a, 'pad')]
sw2.extend([pad(1, 'thru_hole', 'rect', 0, 0, 2.2, 2.2, drill=1.3), pad(2, 'thru_hole', 'circle', 3.6, 0, 2.2, 2.2, drill=1.3)])
templates['BalancerMain:SolderWire_1x02'] = sw2
templates['BalancerMain:SolderWire_1x03'] = build('BalancerMain:SolderWire_1x03', 'through_hole',
    [pad(1, 'thru_hole', 'rect', 0, 0, 2.2, 2.2, drill=1.3), pad(2, 'thru_hole', 'circle', 3.6, 0, 2.2, 2.2, drill=1.3), pad(3, 'thru_hole', 'circle', 7.2, 0, 2.2, 2.2, drill=1.3)],
    [rect(-1.8, -1.8, 9.0, 1.8)], 'three solder-wire pads, 3.6 mm pitch')
templates['BalancerMain:Pogo_1x03'] = build('BalancerMain:Pogo_1x03', 'through_hole',
    [pad(n, 'thru_hole', 'rect' if n == 1 else 'circle', (n - 1) * 2.54, 0, 2.3, 2.3, drill=1.5) for n in (1, 2, 3)],
    [rect(-1.8, -1.8, 6.9, 1.8)], 'three through-hole pogo pins, 2.54 mm pitch, 1.5 mm shank')
h2 = template('MountingHole:MountingHole_2.2mm_M2'); h2[:] = strip_instance(h2); h2[1] = 'MountingHole:MountingHole_3.2mm_M3'
h2[:] = [a for a in h2 if not (tagged(a, 'pad') or tagged(a, 'fp_circle'))]
h2.append(node('pad', '', S('np_thru_hole'), S('circle'), node('at', 0, 0), node('size', 3.2, 3.2), node('drill', 3.2), node('layers', '*.Cu', '*.Mask'), node('uuid', uid())))
h2.append(node('fp_circle', node('center', 0, 0), node('end', 3.2, 0), node('stroke', node('width', 0.05), node('type', S('solid'))), node('fill', S('no')), node('layer', 'F.CrtYd'), node('uuid', uid())))
templates['MountingHole:MountingHole_3.2mm_M3'] = h2
ph5 = template('Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical'); ph5[:] = strip_instance(ph5)
ph5[1] = 'Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical'
ph5[:] = [a for a in ph5 if not (tagged(a, 'pad') and str(a[1]) == '5')]
templates['Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical'] = ph5
# USB-C 16P from Unexpected Maker's OMGS3 carrier (vendor/OMGS3_Carrier_R1.kicad_pcb): signal pads at
# y -3.51 are the rear, the opening is +y; they place it 2.4 mm inside the board edge.
usb = template('Unexpected Maker:USB-C-16P-LESSPASTE-2-Fixed-Sqr-Front'); usb[:] = strip_instance(usb); usb[1] = 'BalancerMain:USB_C_16P'
templates['BalancerMain:USB_C_16P'] = usb
# JST PH 2-pin vertical (B2B-PH-K-S): 2.0 mm pitch, 0.7 mm pins; body 4.9 x 4.5 (constructed, check against the JST drawing)
templates['BalancerMain:JST_PH_1x02_Vertical'] = build('BalancerMain:JST_PH_1x02_Vertical', 'through_hole',
    [pad(1, 'thru_hole', 'rect', 0, 0, 1.3, 1.8, drill=0.75), pad(2, 'thru_hole', 'oval', 2.0, 0, 1.3, 1.8, drill=0.75)],
    [rect(-1.95, -1.7, 3.95, 2.8, 'F.SilkS', 0.12), rect(-2.2, -1.95, 4.2, 3.05)], 'JST PH 2-pin vertical, pin 1 square')
ph3 = template('Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical'); ph3[:] = strip_instance(ph3)
ph3[1] = 'Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical'
ph3[:] = [a for a in ph3 if not (tagged(a, 'pad') and str(a[1]) in ('4', '5'))]
templates['Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical'] = ph3
# OMGS3 footprint from Unexpected Maker's repo (vendor/OMGS3.kicad_mod): origin at the module
# corner, body 0..25 x -10..0, pads along three edges near x 1..14, antenna past x 17.
omg = sx.loads((ROOT / 'vendor' / 'OMGS3.kicad_mod').read_text(encoding='utf8')); omg[1] = 'BalancerMain:OMGS3'
templates['BalancerMain:OMGS3'] = omg

# ---------------------------------------------------------------- placement (mm, board origin 100,100; 76 x 64)
X0, Y0, W, H = 100.0, 100.0, 70.0, 64.0
P = {   # ref: (x, y, rot)
    'U1': (X0 + 44.0, Y0 + 13.0, 0),              # OMGS3 corner origin; body 44..69 x 3..13, antenna x 61..69 at the right edge
    'J9': (X0 + 14.0, Y0 + 2.4, 180),             # USB-C opening on the top edge, 2.4 mm inset like the UM carrier
    'R1': (X0 + 24.0, Y0 + 6.0, 0), 'R2': (X0 + 24.0, Y0 + 10.0, 0),
    'D1': (X0 + 33.0, Y0 + 4.0, 0), 'C2': (X0 + 33.0, Y0 + 9.0, 0),
    'J1': (X0 + 4.0, Y0 + 18.0, 90), 'C1': (X0 + 10.0, Y0 + 18.0, 0),
    'J5': (X0 + 44.0, Y0 + 18.0, 90),
    'U3': (X0 + 10.0, Y0 + 28.0, 0), 'L2': (X0 + 24.0, Y0 + 30.0, 0), 'D2': (X0 + 14.0, Y0 + 36.0, 0),
    'C7': (X0 + 22.0, Y0 + 36.0, 0), 'R6': (X0 + 4.5, Y0 + 28.0, 90), 'R7': (X0 + 4.5, Y0 + 36.0, 0), 'R8': (X0 + 8.5, Y0 + 40.0, 0),
    'J6': (X0 + 12.5, Y0 + 44.0, 0), 'J7': (X0 + 27.74, Y0 + 44.0, 0),   # ADXL357 sockets, 15.24 mm apart: VERIFY on the eval board
    'U4': (X0 + 10.0, Y0 + 54.0, 90), 'J3': (X0 + 8.0, Y0 + 61.5, 0), 'R9': (X0 + 18.0, Y0 + 61.0, 0), 'R10': (X0 + 24.0, Y0 + 61.0, 0),
    'R11': (X0 + 18.0, Y0 + 53.0, 0), 'C8': (X0 + 18.0, Y0 + 57.0, 0), 'R12': (X0 + 24.0, Y0 + 53.0, 0), 'C9': (X0 + 24.0, Y0 + 57.0, 0),
    'R13': (X0 + 30.0, Y0 + 53.0, 0), 'C10': (X0 + 30.0, Y0 + 57.0, 0),
    'J2': (X0 + 36.0, Y0 + 61.0, 0), 'R14': (X0 + 36.0, Y0 + 57.0, 0), 'R15': (X0 + 42.0, Y0 + 57.0, 0),
    'SW1': (X0 + 50.0, Y0 + 24.0, 0), 'R19': (X0 + 62.0, Y0 + 22.0, 0), 'C11': (X0 + 62.0, Y0 + 26.0, 0),
    'LED1': (X0 + 66.0, Y0 + 44.0, 0), 'R20': (X0 + 66.0, Y0 + 48.0, 0),
    'J4': (X0 + 52.0, Y0 + 60.0, 90),
    'H1': (X0 + 3.5, Y0 + H - 3.5, 0), 'H2': (X0 + W - 3.5, Y0 + H - 3.5, 0), 'H3': (X0 + 3.5, Y0 + 48.0, 0), 'H4': (X0 + 40.0, Y0 + 3.5, 0),
}
missing = [r for r in PARTS if r not in P]
assert not missing, 'no placement for %s' % missing

footprints = []
for ref, (value, fpname) in sorted(PARTS.items()):
    fp = template(fpname)
    fp[:] = strip_instance(fp); refresh_uuids(fp)
    x, y, rot = P[ref]
    fp.insert(2, node('uuid', uid()))
    fp.insert(3, node('at', x, y, rot) if rot else node('at', x, y))
    def tprop(k, v, layer, hide=False):
        p = node('property', k, v, node('at', 0, 0 if k != 'Value' else 1.5, 0), node('layer', layer))
        if hide: p.append(node('hide', S('yes')))
        p.append(node('uuid', uid()))
        p.append(node('effects', node('font', node('size', 1, 1), node('thickness', 0.15))))
        return p
    fp.insert(4, tprop('Reference', ref, 'F.SilkS'))
    fp.insert(5, tprop('Value', value, 'F.Fab'))
    fp.insert(6, tprop('Footprint', fpname, 'F.Fab', True))
    fp.insert(7, node('path', '/' + sym_uuid[ref]))
    fp.insert(8, node('sheetname', '/')); fp.insert(9, node('sheetfile', 'BalancerMain.kicad_sch'))
    for p in children(fp, 'pad'):
        num = str(p[1])
        n = pin_net.get((ref, num))
        if n:
            # insert after layers (and roundrect ratio if present)
            i = max(idx for idx, a in enumerate(p) if isinstance(a, list) and str(a[0]) in ('layers', 'roundrect_rratio', 'drill'))
            p.insert(i + 1, node('net', n))
    footprints.append(fp)

# ---------------------------------------------------------------- board
hdr = templates['header']
doc = node('kicad_pcb', node('version', 20260206), node('generator', 'build_pcb_main'), node('generator_version', '10.0'),
           node('general', node('thickness', 1.6), node('legacy_teardrops', S('no'))), node('paper', 'A4'),
           deepcopy(hdr['layers']), deepcopy(hdr['setup']))
doc.extend(footprints)
def gr_line(x1, y1, x2, y2):
    return node('gr_line', node('start', x1, y1), node('end', x2, y2), node('stroke', node('width', 0.05), node('type', S('default'))), node('layer', 'Edge.Cuts'), node('uuid', uid()))
doc.extend([gr_line(X0, Y0, X0 + W, Y0), gr_line(X0 + W, Y0, X0 + W, Y0 + H), gr_line(X0 + W, Y0 + H, X0, Y0 + H), gr_line(X0, Y0 + H, X0, Y0)])
# keep-out note for the sensor board under the sockets
doc.append(node('gr_text', 'EVAL-ADXL357Z underneath: no parts on B.Cu here', node('at', X0 + 20, Y0 + 42, 0), node('layer', 'F.Fab'),
                node('uuid', uid()), node('effects', node('font', node('size', 1, 1), node('thickness', 0.15)))))
doc.append(node('gr_text', 'OMGS3 antenna: no copper, no ground pour', node('at', X0 + 65, Y0 + 16, 0), node('layer', 'F.Fab'),
                node('uuid', uid()), node('effects', node('font', node('size', 1, 1), node('thickness', 0.15)))))
doc.append(node('embedded_fonts', S('no')))


def pretty(x, depth=0):
    if not isinstance(x, list): return sx.dumps(x)
    if not any(isinstance(a, list) for a in x): return '(' + ' '.join(sx.dumps(a) for a in x) + ')'
    head = [a for a in x if not isinstance(a, list)]; body = [a for a in x if isinstance(a, list)]
    ind = '\t' * (depth + 1)
    return '(' + ' '.join(sx.dumps(a) for a in head) + '\n' + '\n'.join(ind + pretty(b, depth + 1) for b in body) + '\n' + '\t' * depth + ')'


print('%d footprints, %d nets, board %g x %g mm' % (len(footprints), len(NETS), W, H))
if not APPLY:
    print('dry run; pass --apply'); sys.exit(0)
(ROOT / 'BalancerMain.kicad_pcb').write_text(pretty(doc) + '\n', encoding='utf8')
# project-local footprint library for the constructed and copied footprints
pretty_dir = ROOT / 'BalancerMain.pretty'; pretty_dir.mkdir(exist_ok=True)
for name in ('BalancerMain:OMGS3', 'BalancerMain:USB_C_16P', 'BalancerMain:JST_PH_1x02_Vertical', 'BalancerMain:L_Radial_D9_P5', 'BalancerMain:SolderWire_1x02', 'BalancerMain:SolderWire_1x03', 'BalancerMain:Pogo_1x03'):
    fp = deepcopy(templates[name]); fp[:] = strip_instance(fp); refresh_uuids(fp); fp[1] = name.split(':')[1]
    fp.insert(2, node('version', 20241229)); fp.insert(3, node('generator', 'build_pcb_main'))
    (pretty_dir / (fp[1] + '.kicad_mod')).write_text(pretty(fp) + '\n', encoding='utf8')
(ROOT / 'fp-lib-table').write_text('(fp_lib_table\n  (version 7)\n  (lib (name "BalancerMain")(type "KiCad")(uri "${KIPRJMOD}/BalancerMain.pretty")(options "")(descr "Project-local footprints"))\n)\n', encoding='utf8')
pro = json.loads((REPO / 'BalancerCarrier' / 'BalancerCarrier.kicad_pro').read_text(encoding='utf8'))
pro['meta']['filename'] = 'BalancerMain.kicad_pro'
for k in ('sheets', 'boards'): pro[k] = []
(ROOT / 'BalancerMain.kicad_pro').write_text(json.dumps(pro, indent=2) + '\n', encoding='utf8')
print('wrote BalancerMain.kicad_pcb, BalancerMain.pretty/, fp-lib-table, BalancerMain.kicad_pro')
