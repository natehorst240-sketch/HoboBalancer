"""Replay an unsaved pcbnew session from a Freerouting DSN export.

KiCad crashed on 2026-09-14 at about 22:02 with hours of unsaved board edits. There
was no autosave, but temp-freerouting.dsn had been exported at 22:00 and a Specctra
DSN is a complete snapshot: every footprint's position, side and rotation, every track
and every via that existed at export time. This puts all of that back into the saved
board file.

  * placements: applied to every footprint present in the DSN
  * wiring: each (wire (path layer width x y x y ...)) becomes PCB_TRACK segments,
    each (via padstack x y (net)) becomes a PCB_VIA sized from the padstack name
  * footprints missing from the DSN that also no longer exist in the schematic are
    removed from the file afterwards (board.Remove() is avoided - it has crashed the
    KiCad python before - so this is done on the saved text)

DSN units are micrometres with Y pointing up, so kicad_y = -dsn_y / 1000.

Run with KiCad's python:  python.exe -u scripts/recover_from_dsn.py [--apply]
"""
import sys, os, re, shutil
import pcbnew

APPLY = '--apply' in sys.argv
REPLACE = '--replace-tracks' in sys.argv          # drop the saved file's tracks/vias first
OUT = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--out=')), None)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, 'BalancerREF.kicad_pcb')
DSN = os.path.join(ROOT, 'temp-freerouting.dsn')
SCH = os.path.join(ROOT, 'BalancerREF.kicad_sch')

t = open(DSN, encoding='utf8', errors='replace').read()
mm = pcbnew.ToMM


def P(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(float(x) / 1000.0), pcbnew.FromMM(-float(y) / 1000.0))


place = {m.group(1): (m.group(2), m.group(3), m.group(4), float(m.group(5)))
         for m in re.finditer(r'\(place\s+(\S+)\s+([-\d.]+)\s+([-\d.]+)\s+(front|back)\s+([-\d.]+)', t)}
wiring = t[t.find('(wiring'):]
NET = r'\(net\s+(?:"([^"]*)"|([^\s()]+))\)'
wires = [(a, b, c, d or e) for a, b, c, d, e in
         re.findall(r'\(wire\s*\(path\s+(\S+)\s+([\d.]+)((?:\s+[-\d.]+)+)\)\s*' + NET, wiring)]
vias = [(a, b, c, d, e, f or g) for a, b, c, d, e, f, g in
        re.findall(r'\(via\s+"?(Via\[[^\]]*\]_(\d+):(\d+)_um)"?\s+([-\d.]+)\s+([-\d.]+)\s*' + NET, wiring)]
print('DSN: %d placements, %d wires, %d vias' % (len(place), len(wires), len(vias)))

SRC = PCB
if REPLACE:
    # strip every (segment ...) / (via ...) block from the saved text and load that,
    # so the DSN's wiring is the only copper. board.Remove() is avoided on purpose.
    txt = open(PCB, encoding='utf8').read()
    block = r'\n\t\((?:segment|via)\b(?:(?!\n\t\().)*?\n\t\)'
    txt = re.sub(block, '', txt, flags=re.S)
    SRC = os.path.join(ROOT, 'BalancerREF-backups', '_stripped.kicad_pcb')
    open(SRC, 'w', encoding='utf8').write(txt)
board = pcbnew.LoadBoard(SRC)
fps = {f.GetReference(): f for f in board.GetFootprints()}
print('starting copper: %d tracks/vias' % len(board.GetTracks()))
layers = {'F.Cu': pcbnew.F_Cu, 'B.Cu': pcbnew.B_Cu, 'In1.Cu': pcbnew.In1_Cu, 'In2.Cu': pcbnew.In2_Cu}

# --- how does the DSN rotation relate to KiCad orientation, per side? Learn it from
# the footprints that did not move, so back-side parts are not silently mirrored.
print('\nrotation convention check on unmoved parts:')
for side in ('front', 'back'):
    diffs = set()
    for ref, (x, y, s, rot) in place.items():
        if s != side or ref not in fps:
            continue
        f = fps[ref]
        if abs(mm(f.GetPosition().x) - float(x) / 1000) < 0.01 and abs(mm(f.GetPosition().y) + float(y) / 1000) < 0.01:
            diffs.add(round((f.GetOrientationDegrees() - rot) % 360, 1))
    print('  %-5s kicad - dsn angle offsets seen: %s' % (side, sorted(diffs)))

# --- placements
moved = 0
for ref, (x, y, side, rot) in place.items():
    f = fps.get(ref)
    if f is None:
        print('  DSN has %s but the board does not' % ref); continue
    want = pcbnew.F_Cu if side == 'front' else pcbnew.B_Cu
    if f.GetLayer() != want:
        f.Flip(f.GetPosition(), False)
        print('  flipped %s to %s' % (ref, side))
    pos = P(x, y)
    # verified on the unmoved parts above: KiCad = DSN on the front, DSN + 180 on the back
    krot = rot if side == 'front' else (rot + 180) % 360
    if pos != f.GetPosition() or abs((f.GetOrientationDegrees() - krot) % 360) > 0.01:
        moved += 1
    f.SetPosition(pos)
    f.SetOrientationDegrees(krot)
print('placements applied, %d changed' % moved)

# --- tracks
nseg = 0
for layer, width, pts, net in wires:
    q = pts.split()
    coords = [(q[i], q[i + 1]) for i in range(0, len(q), 2)]
    netcode = board.GetNetcodeFromNetname(net)
    for a, b in zip(coords, coords[1:]):
        tr = pcbnew.PCB_TRACK(board)
        tr.SetStart(P(*a)); tr.SetEnd(P(*b))
        tr.SetWidth(pcbnew.FromMM(float(width) / 1000.0))
        tr.SetLayer(layers[layer]); tr.SetNetCode(netcode)
        board.Add(tr); nseg += 1
print('tracks: %d segments' % nseg)

# --- vias
for name, size, drill, x, y, net in vias:
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(x, y))
    v.SetWidth(pcbnew.FromMM(int(size) / 1000.0))
    v.SetDrill(pcbnew.FromMM(int(drill) / 1000.0))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNetCode(board.GetNetcodeFromNetname(net))
    board.Add(v)
print('vias: %d' % len(vias))

# --- footprints that vanished from both DSN and schematic were deleted in the session
sch = open(SCH, encoding='utf8').read()
gone = [r for r in fps if r not in place and not r.startswith(('H', 'FID'))
        and ('(property "Reference" "%s"' % r) not in sch]
print('footprints deleted in the session (absent from DSN and schematic): %s' % gone)

if not APPLY:
    print('\nDRY RUN - nothing written.'); sys.exit(0)

DEST = OUT or PCB
if DEST == PCB:
    shutil.copy2(PCB, os.path.join(ROOT, 'BalancerREF-backups', 'BalancerREF-pre-recover.kicad_pcb'))
board.Save(DEST)
txt = open(DEST, encoding='utf8').read()
for r in gone:
    pat = re.compile(r'\n\t\(footprint\s+"[^"]+"(?:(?!\n\t\(footprint).)*?\(property "Reference" "%s"(?:(?!\n\t\(footprint).)*?\n\t\)' % re.escape(r), re.S)
    txt, n = pat.subn('', txt)
    print('  removed %s (%d block)' % (r, n))
open(DEST, 'w', encoding='utf8').write(txt)
print('Saved %s' % DEST)
