"""Draw BalancerMain.kicad_pcb pads, references and the Feather outline to placement-top.png."""
import math
from pathlib import Path
import sexpdata as sx, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
ROOT = Path(__file__).resolve().parent.parent
def tg(x, k): return isinstance(x, list) and x and str(x[0]) == k
def ch(x, k): return [a for a in x if tg(a, k)]
def one(x, k): return next((a for a in x if tg(a, k)), None)
doc = sx.loads((ROOT / 'BalancerMain.kicad_pcb').read_text(encoding='utf8'))
edge = [(float(one(g, k)[1]), float(one(g, k)[2])) for g in ch(doc, 'gr_line') if str(one(g, 'layer')[1]) == 'Edge.Cuts' for k in ('start', 'end')]
x0, x1 = min(p[0] for p in edge), max(p[0] for p in edge); y0, y1 = min(p[1] for p in edge), max(p[1] for p in edge)
fig, ax = plt.subplots(figsize=(11, 9.5)); ax.set_aspect('equal')
ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, lw=2))
for fp in ch(doc, 'footprint'):
    props = {str(p[1]): str(p[2]) for p in ch(fp, 'property')}
    ref, val = props['Reference'], props.get('Value', '')
    at = one(fp, 'at'); X, Y = float(at[1]), float(at[2]); rot = float(at[3]) if len(at) > 3 else 0
    r = math.radians(rot); xs = []; ys = []
    for p in ch(fp, 'pad'):
        pa = one(p, 'at'); px, py = float(pa[1]), float(pa[2]); sz = one(p, 'size')
        x = X + px * math.cos(r) + py * math.sin(r); y = Y - px * math.sin(r) + py * math.cos(r)
        w, h = float(sz[1]), float(sz[2])
        if ((float(pa[3]) if len(pa) > 3 else 0) + rot) % 180 == 90: w, h = h, w
        kind = str(p[2]); col = '#d4a017' if kind == 'smd' else ('#999' if kind == 'np_thru_hole' else '#4a7fb5')
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, color=col, alpha=.8)); xs.append(x); ys.append(y)
        if str(p[1]) == '1': ax.text(x, y, '1', fontsize=4, ha='center', va='center', color='w')
    if 'Feather' in str(fp[1]):
        ax.add_patch(Rectangle((X - 11.59, Y - 24.33), 22.86, 50.8, fill=False, ec='k', lw=0.8, ls='--'))
        ax.text(X, Y - 26.5 + 3.5, 'USB', fontsize=6, ha='center', color='gray')
    ax.text(sum(xs) / len(xs), sum(ys) / len(ys) - 1.3, ref if ref.startswith('H') else '%s\n%s' % (ref, val), fontsize=5.5, ha='center', va='center')
ax.set_xlim(x0 - 2, x1 + 2); ax.set_ylim(y1 + 2, y0 - 3); ax.set_xlabel('mm')
ax.set_title('BalancerMain v2 carrier, placement, top view (unrouted)')
plt.tight_layout(); plt.savefig(ROOT / 'placement-top.png', dpi=160)
