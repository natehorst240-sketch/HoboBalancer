"""Drop lib_symbols entries no symbol on the sheet uses any more.

Every part swap leaves its old definition behind in the schematic's `lib_symbols`
cache. KiCad ignores them, but they are not inert: each carries a Value, an MPN-shaped
Description and a Datasheet URL for a part that is no longer fitted, and anything that
walks the cache to build a BOM can surface them. After the optical split, the charger
swap and the U9 Schmitt swap this sheet was still carrying MCP73831-2-OT, D_Schottky and
74LVC1G08 definitions for parts that are gone from the design entirely.

Only entries with zero referencing instances are removed, so this cannot change what is
fitted. The netlist is exported before and after to prove it.

Dry run by default. Pass --apply to write.
"""
import sys, subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexp_helpers import *
from rollback import Rollback

ROOT = HERE.parent
assert ROOT.name == 'BalancerREF', ROOT
APPLY = '--apply' in sys.argv
SCH = ROOT / 'BalancerREF.kicad_sch'
KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'


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


tmp = Path(tempfile.mkdtemp())
before = export_partition(tmp / 'b.net')
print('baseline: %d pin endpoints' % len(before))

d = parse(SCH.read_text(encoding='utf8'))
used = {str(one(s, 'lib_id')[1]) for s in children(d, 'symbol')}
cache = one(d, 'lib_symbols')
orphans = [s for s in children(cache, 'symbol') if str(s[1]) not in used]

print('lib_symbols entries: %d, referenced: %d, orphaned: %d'
      % (len(children(cache, 'symbol')), len(used), len(orphans)))
for s in orphans:
    val = next((p[2] for p in children(s, 'property') if p[1] == 'Value'), '')
    print('   %-38s (Value %r)' % (str(s[1]), val))
if not orphans:
    print('nothing to prune.')
    sys.exit(0)

ids = {id(s) for s in orphans}
cache[:] = [a for a in cache if id(a) not in ids]

if not APPLY:
    print('\nDRY RUN - nothing written.')
    sys.exit(0)

with Rollback(SCH) as guard:
    SCH.write_text(dump(d) + '\n', encoding='utf8')
    after = export_partition(tmp / 'a.net')
    guard.require(after == before,
                  'netlist changed: %s'
                  % {k: (before.get(k), after.get(k))
                     for k in set(before) | set(after) if before.get(k) != after.get(k)})
    left = {str(s[1]) for s in children(one(parse(SCH.read_text(encoding='utf8')),
                                            'lib_symbols'), 'symbol')}
    guard.require(left == used, 'cache is not exactly the referenced set: %s'
                  % sorted(left ^ used))
    print('\nVERIFIED: %d orphan(s) pruned, netlist identical, cache now matches the '
          'symbols actually placed.' % len(orphans))
