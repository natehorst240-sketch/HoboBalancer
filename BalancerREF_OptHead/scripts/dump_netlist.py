"""Pre-parse the exported netlist into JSON for build_pcb.py.

Run with SYSTEM python (has sexpdata). build_pcb.py runs under KiCad's bundled
python, which does not, and the exported netlist is pretty-printed multi-line so
regex parsing of it is fragile.
"""
import sys, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'BalancerREF', 'scripts'))
from sexp_helpers import parse, children, one

root = os.path.dirname(HERE)
d = parse(open(os.path.join(root, 'review', 'OptHead.net'), encoding='utf8').read())
comps = {one(c, 'ref')[1]: [one(c, 'value')[1], one(c, 'footprint')[1]]
         for c in children(one(d, 'components'), 'comp')}
nets = {}
for n in children(one(d, 'nets'), 'net'):
    nm = one(n, 'name')[1]
    for p in children(n, 'node'):
        nets['%s|%s' % (one(p, 'ref')[1], one(p, 'pin')[1])] = nm
out = os.path.join(root, 'review', 'netlist.json')
json.dump({'comps': comps, 'nets': nets}, open(out, 'w'), indent=1)
print('wrote %s: %d comps, %d pad-nets' % (out, len(comps), len(nets)))
