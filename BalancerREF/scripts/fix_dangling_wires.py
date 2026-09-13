"""Sweep the wire stubs left behind by removed parts.

Every part deletion on this sheet - the optical split, SW4, R5, and the MCP73831 to
BQ24075 swap - left behind the wires that used to reach the deleted pins. They connect
to a live net at one end and to nothing at the other, which is what KiCad reports as
`unconnected_wire_endpoint`.

Wire pruning has gone wrong on this sheet twice, so the rules here are deliberately
narrow:

  * Only a wire with a genuinely FREE end is a candidate. Free means no other wire ends
    there, no pin, no label, no junction and no no-connect. Pin positions come from the
    lib_symbols pin table transformed by each instance's position/rotation/mirror; that
    model is checked against KiCad's own ERC before anything is removed, and the run
    aborts if the two disagree.
  * A wire carrying a label ANYWHERE along its length is never removed. Labels attach to
    wire bodies, not only to endpoints, so deleting such a wire could silently rename or
    split a net - the exact failure behind the earlier reverts.
  * Peeling is iterative: removing a stub can expose the one behind it. Each pass
    recomputes from scratch rather than trusting a list built before the edits.
  * The netlist is exported before and after and the pin -> net mapping must come out
    identical. Connectivity is the thing being preserved; the wires are not. If anything
    moved, the schematic is restored from backup and the run fails.

Dry run by default. Pass --apply to write.
"""
import sys, math, re, subprocess, tempfile
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexp_helpers import *

ROOT = HERE.parent
assert ROOT.name == 'BalancerREF', ROOT
APPLY = '--apply' in sys.argv
SCH = ROOT / 'BalancerREF.kicad_sch'
KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
LABEL_KINDS = ('label', 'global_label', 'hierarchical_label')


def rnd(v):
    return round(float(v), 2)


def wire_pts(w):
    return [(rnd(a[1]), rnd(a[2])) for a in children(one(w, 'pts'), 'xy')]


def lib_pin_table(d):
    out = {}
    for s in children(one(d, 'lib_symbols'), 'symbol'):
        acc = []
        for unit in children(s, 'symbol'):
            for p in children(unit, 'pin'):
                a = one(p, 'at')
                acc.append((float(a[1]), float(a[2])))
        out[str(s[1])] = acc
    return out


def pin_coords(d):
    """Every pin's sheet coordinate: library table plus the instance transform."""
    lp = lib_pin_table(d)
    out = set()
    for s in children(d, 'symbol'):
        lib = str(one(s, 'lib_id')[1])
        if lib not in lp:
            continue
        a = one(s, 'at')
        sx, sy = float(a[1]), float(a[2])
        rot = float(a[3]) if len(a) > 3 else 0.0
        m = one(s, 'mirror')
        mir = str(m[1]) if m else None
        th = math.radians(rot)
        c, s_ = math.cos(th), math.sin(th)
        for px, py in lp[lib]:
            x, y = px, py
            if mir == 'y':
                x = -x
            elif mir == 'x':
                y = -y
            out.add((rnd(sx + x * c - y * s_), rnd(sy - (x * s_ + y * c))))
    return out


def label_points(d):
    return {(rnd(one(n, 'at')[1]), rnd(one(n, 'at')[2]))
            for k in LABEL_KINDS for n in children(d, k)}


def anchor_points(d):
    pts = label_points(d)
    for k in ('junction', 'no_connect'):
        for n in children(d, k):
            pts.add((rnd(one(n, 'at')[1]), rnd(one(n, 'at')[2])))
    return pts


def on_segment(p, a, b, tol=0.01):
    """Is point p on segment a-b? Wires on this sheet are axis-aligned."""
    if abs(a[0] - b[0]) < tol:
        return (abs(p[0] - a[0]) < tol
                and min(a[1], b[1]) - tol <= p[1] <= max(a[1], b[1]) + tol)
    if abs(a[1] - b[1]) < tol:
        return (abs(p[1] - a[1]) < tol
                and min(a[0], b[0]) - tol <= p[0] <= max(a[0], b[0]) + tol)
    d1 = math.hypot(p[0] - a[0], p[1] - a[1])
    d2 = math.hypot(p[0] - b[0], p[1] - b[1])
    return abs(d1 + d2 - math.hypot(a[0] - b[0], a[1] - b[1])) < tol


def free_ends(d, pins, anc):
    ends = Counter(e for w in children(d, 'wire') for e in wire_pts(w))
    return {e for e, n in ends.items() if n == 1 and e not in pins and e not in anc}


def erc_dangling_count():
    rpt = ROOT / 'review' / 'erc.rpt'
    if not rpt.exists():
        return None
    return len(re.findall(r'\[unconnected_wire_endpoint\]',
                          rpt.read_text(encoding='utf8')))


def export_partition(path):
    subprocess.run([KC, 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
                    '-o', str(path), str(SCH)], capture_output=True, text=True)
    doc = parse(Path(path).read_text(encoding='utf8'))
    out = {}
    for n in children(one(doc, 'nets'), 'net'):
        nm = str(one(n, 'name')[1])
        for p in children(n, 'node'):
            r = str(one(p, 'ref')[1])
            if not r.startswith('#'):
                out[r + '.' + str(one(p, 'pin')[1])] = nm
    return out


def main():
    tmp = Path(tempfile.mkdtemp())
    before = export_partition(tmp / 'before.net')
    print('baseline netlist: %d pin endpoints' % len(before))

    d = parse(SCH.read_text(encoding='utf8'))
    start = free_ends(d, pin_coords(d), anchor_points(d))
    erc_n = erc_dangling_count()
    print('free ends found: %d   ERC unconnected_wire_endpoint: %s' % (len(start), erc_n))
    assert erc_n is None or erc_n == len(start), (
        'geometry model disagrees with ERC (%s vs %d) - refusing to touch the sheet'
        % (erc_n, len(start)))

    labels = label_points(d)
    removed, skipped, rounds = [], [], 0
    while True:
        free = free_ends(d, pin_coords(d), anchor_points(d))
        if not free:
            break
        victims = []
        for w in children(d, 'wire'):
            pp = wire_pts(w)
            if not any(e in free for e in pp):
                continue
            held = [l for l in labels if on_segment(l, pp[0], pp[1])]
            if held:
                skipped.append((pp, held))
                continue
            victims.append((w, pp))
        if not victims:
            break
        rounds += 1
        ids = {id(w) for w, _ in victims}
        d[:] = [a for a in d if id(a) not in ids]
        removed.extend(pp for _, pp in victims)
        print('  pass %d: %d free end(s) -> removed %d wire(s)'
              % (rounds, len(free), len(victims)))

    pins_now = pin_coords(d)
    ncs = [n for n in children(d, 'no_connect')
           if (rnd(one(n, 'at')[1]), rnd(one(n, 'at')[2])) not in pins_now]
    if ncs:
        d[:] = [a for a in d if id(a) not in {id(n) for n in ncs}]
    print('removed %d wire stub(s) in %d pass(es); %d dangling no-connect(s)'
          % (len(removed), rounds, len(ncs)))
    if skipped:
        print('kept %d wire(s) carrying a label' % len(skipped))

    # Phase 2: the wires held back above still have a dead tail running past their
    # label. Deleting them is not an option - the label is what carries the net to
    # the rest of the sheet - so trim the tail instead, back to the outermost label
    # on the wire. The label then sits on the endpoint, which is a real anchor, and
    # the free end is gone without any connectivity moving.
    trimmed = []
    for w in children(d, 'wire'):
        pp = wire_pts(w)
        free = free_ends(d, pin_coords(d), anchor_points(d))
        if not free:
            break
        loose = [e for e in pp if e in free]
        if len(loose) != 1:
            continue
        tip = loose[0]
        anchored = pp[0] if pp[1] == tip else pp[1]
        held = [l for l in labels if on_segment(l, pp[0], pp[1])]
        if not held:
            continue
        # keep every label: cut at the one furthest from the anchored end
        cut = max(held, key=lambda l: math.hypot(l[0] - anchored[0], l[1] - anchored[1]))
        if cut == tip:
            continue
        for xy in children(one(w, 'pts'), 'xy'):
            if (rnd(xy[1]), rnd(xy[2])) == tip:
                xy[1], xy[2] = cut[0], cut[1]
        trimmed.append((anchored, tip, cut))
    for anchored, tip, cut in trimmed:
        print('  trimmed %s -> %s  back to %s (label sits there)' % (anchored, tip, cut))
    print('trimmed %d wire(s) to their outermost label' % len(trimmed))
    print('free ends remaining: %d' % len(free_ends(d, pin_coords(d), anchor_points(d))))

    if not APPLY:
        print('\nDRY RUN - nothing written.')
        sys.exit(0)

    backup = SCH.with_suffix('.prestub')
    backup.write_bytes(SCH.read_bytes())
    SCH.write_text(dump(d) + '\n', encoding='utf8')

    after = export_partition(tmp / 'after.net')
    changed = {k: (before.get(k), v) for k, v in after.items() if before.get(k) != v}
    lost = sorted(set(before) - set(after))
    gained = sorted(set(after) - set(before))
    print('\npin endpoints after: %d' % len(after))
    print('changed nets : %s' % (changed or 'NONE'))
    print('lost pins    : %s' % (lost or 'none'))
    print('gained pins  : %s' % (gained or 'none'))
    if changed or lost or gained:
        SCH.write_bytes(backup.read_bytes())
        print('\n!! CONNECTIVITY CHANGED - schematic restored from backup. Nothing kept.')
        sys.exit(1)
    backup.unlink()
    print('\nVERIFIED: every pin is on exactly the net it was on before.')


if __name__ == '__main__':
    main()
