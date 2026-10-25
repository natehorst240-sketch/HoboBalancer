"""Generate BalancerMain.kicad_pcb from the verified schematic netlist.

The carrier for an ESP32-S3 Feather on female headers, with the LM1815 magnetic-pickup
input, the Banner input, the boost-module power switch, a KX134 header, button and LED.
Footprint geometry is harvested from the carrier and optical-head boards in this repo
(KiCad's own R_1206, SOIC-14, SOT-23, headers, switch, solder pads, LED, and the Feather
footprint the carrier used); C_1206, the 3-pad solder strip and the M3 hole are built
here. Every part is placed with its nets and the outline drawn; routing is left to KiCad.
Run verify_main.py first (it writes BalancerMain.net.json). Pass --apply to write.
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
POWER = {'GND', '+3V3', '+12V', 'VBAT'}
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
for f in (REPO / 'BalancerCarrier' / 'BalancerCarrier.kicad_pcb', REPO / 'BalancerREF_OptHead' / 'BalancerREF_OptHead.kicad_pcb'):
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
sw2 = template('Connector_Wire:SolderWire-0.1sqmm_1x02_P3.6mm_D0.4mm_OD1mm'); sw2[:] = strip_instance(sw2)
sw2[1] = 'BalancerMain:SolderWire_1x02'
sw2[:] = [a for a in sw2 if not tagged(a, 'pad')]
sw2.extend([pad(1, 'thru_hole', 'rect', 0, 0, 2.2, 2.2, drill=1.3), pad(2, 'thru_hole', 'circle', 3.6, 0, 2.2, 2.2, drill=1.3)])
templates['BalancerMain:SolderWire_1x02'] = sw2
templates['BalancerMain:SolderWire_1x03'] = build('BalancerMain:SolderWire_1x03', 'through_hole',
    [pad(1, 'thru_hole', 'rect', 0, 0, 2.2, 2.2, drill=1.3), pad(2, 'thru_hole', 'circle', 3.6, 0, 2.2, 2.2, drill=1.3), pad(3, 'thru_hole', 'circle', 7.2, 0, 2.2, 2.2, drill=1.3)],
    [rect(-1.8, -1.8, 9.0, 1.8)], 'three solder-wire pads, 3.6 mm pitch')
h2 = template('MountingHole:MountingHole_2.2mm_M2'); h2[:] = strip_instance(h2); h2[1] = 'MountingHole:MountingHole_3.2mm_M3'
h2[:] = [a for a in h2 if not (tagged(a, 'pad') or tagged(a, 'fp_circle'))]
h2.append(node('pad', '', S('np_thru_hole'), S('circle'), node('at', 0, 0), node('size', 3.2, 3.2), node('drill', 3.2), node('layers', '*.Cu', '*.Mask'), node('uuid', uid())))
h2.append(node('fp_circle', node('center', 0, 0), node('end', 3.2, 0), node('stroke', node('width', 0.05), node('type', S('solid'))), node('fill', S('no')), node('layer', 'F.CrtYd'), node('uuid', uid())))
templates['MountingHole:MountingHole_3.2mm_M3'] = h2
# Feather on female headers: the FeatherS3 footprint the v1 carrier used. Pads 1-12 are the
# 12-pin header (BAT..SDA), 13-28 the 16-pin header; body outline on F.Fab, USB end at -y.
fs = template('BalancerCarrier:FeatherS3'); fs[:] = strip_instance(fs); fs[1] = 'BalancerMain:Feather_Socket'
templates['BalancerMain:Feather_Socket'] = fs

# ---------------------------------------------------------------- placement (mm, board origin 100,100)
X0, Y0, W, H = 100.0, 100.0, 64.0, 54.0
FXc, FYc = X0 + W - 12.5, Y0 + 25.0     # Feather body x -11.6..+11.3, y -24.3..+26.5 about this point; USB at the top edge
P = {   # ref: (x, y, rot)
    'U1': (FXc, FYc, 0),
    'H1': (X0 + 3.5, Y0 + 3.5, 0), 'H2': (X0 + 3.5, Y0 + H - 3.5, 0), 'H3': (X0 + 36.5, Y0 + 3.5, 0), 'H4': (X0 + 36.5, Y0 + H - 3.5, 0),
    # top edge: wire pads for the Banner and the boost module
    'J2': (X0 + 8.5, Y0 + 3.5, 0), 'J6': (X0 + 19.5, Y0 + 3.5, 0), 'J5': (X0 + 27.5, Y0 + 3.5, 0),
    'R14': (X0 + 10.0, Y0 + 8.5, 0), 'R15': (X0 + 10.0, Y0 + 12.0, 0),
    'Q2': (X0 + 22.0, Y0 + 9.0, 0), 'R17': (X0 + 28.0, Y0 + 9.0, 0),
    'Q1': (X0 + 22.0, Y0 + 14.0, 0), 'R16': (X0 + 28.0, Y0 + 14.0, 0), 'R18': (X0 + 33.5, Y0 + 14.0, 90),
    # button, LED
    'SW1': (X0 + 4.0, Y0 + 18.5, 0), 'R19': (X0 + 16.0, Y0 + 19.0, 0), 'C11': (X0 + 16.0, Y0 + 22.5, 0),
    'LED1': (X0 + 24.0, Y0 + 20.0, 0), 'R20': (X0 + 30.0, Y0 + 20.0, 0),
    # KX134 header
    'J4': (X0 + 25.0, Y0 + 27.0, 90),
    # LM1815 and the magnetic pickup pads at the bottom edge
    'U4': (X0 + 10.0, Y0 + 37.0, 90),
    'R11': (X0 + 19.0, Y0 + 33.0, 0), 'C8': (X0 + 19.0, Y0 + 36.5, 0), 'R12': (X0 + 25.0, Y0 + 33.0, 0), 'C9': (X0 + 25.0, Y0 + 36.5, 0),
    'R13': (X0 + 31.0, Y0 + 33.0, 0), 'C10': (X0 + 31.0, Y0 + 36.5, 0),
    'J3': (X0 + 9.0, Y0 + 50.5, 0), 'R9': (X0 + 19.0, Y0 + 44.0, 0), 'R10': (X0 + 25.0, Y0 + 44.0, 0),
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
doc.append(node('gr_text', 'Feather on female headers', node('at', FXc, FYc, 90), node('layer', 'F.Fab'),
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
for name in ('BalancerMain:Feather_Socket', 'BalancerMain:SolderWire_1x02', 'BalancerMain:SolderWire_1x03'):
    fp = deepcopy(templates[name]); fp[:] = strip_instance(fp); refresh_uuids(fp); fp[1] = name.split(':')[1]
    fp.insert(2, node('version', 20241229)); fp.insert(3, node('generator', 'build_pcb_main'))
    (pretty_dir / (fp[1] + '.kicad_mod')).write_text(pretty(fp) + '\n', encoding='utf8')
(ROOT / 'fp-lib-table').write_text('(fp_lib_table\n  (version 7)\n  (lib (name "BalancerMain")(type "KiCad")(uri "${KIPRJMOD}/BalancerMain.pretty")(options "")(descr "Project-local footprints"))\n)\n', encoding='utf8')
pro = json.loads((REPO / 'BalancerCarrier' / 'BalancerCarrier.kicad_pro').read_text(encoding='utf8'))
pro['meta']['filename'] = 'BalancerMain.kicad_pro'
for k in ('sheets', 'boards'): pro[k] = []
(ROOT / 'BalancerMain.kicad_pro').write_text(json.dumps(pro, indent=2) + '\n', encoding='utf8')
print('wrote BalancerMain.kicad_pcb, BalancerMain.pretty/, fp-lib-table, BalancerMain.kicad_pro')
