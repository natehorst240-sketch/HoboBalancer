"""Check decode_spc against MicroBase Pro's own unpacked spectrum for PLOT0093.SPC (saverecs
SAVEKEY 1082: MINVAL 0.00039589, MAXVAL 0.47308543, 200 bins, DELTA 1.25 Hz; specrecs rows
1-4, log-packed one byte per bin per the DSS FAQ "MicroBase Pro Database & 3rd Party
Applications"). Run: python3 BalancerV2/profiles/test_decode_spc.py"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode_grp import decode_spc

MINVAL, MAXVAL = 0.00039589, 0.47308543
PACKED = bytes.fromhex('ffefe4dee8d19ba8b5c4b3739792bdbfb4bbbdd5d29d927b7f9f9d9c9f9397969699a697937e88b7ccb2836b889d87686c7a897c636c7781775061799f996b435d736e5d4a516263524f678a7b958b5667614c44444b45313b35474b3b3b46435a504a304966623a2e3538413133463a3d31323e4b3d3d3b36525849252f353d342f272128232626382e272c273a47322a121b1a25231b12172d3838352f2a2e2e20252d364141282b231b2e2a353b3623252b2001122529261d2b2b262c252b32291e2f2a30362a')
lmin, lrange = math.log10(MINVAL), math.log10(MAXVAL) - math.log10(MINVAL)
dss = [10 ** (lmin + lrange * c / 255.0) for c in PACKED]
step = 10 ** (lrange / 255) - 1          # 2.8%: one packing step

d = decode_spc(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PLOT0093.SPC'))
assert len(d['bins']) == 200 == len(PACKED)
assert abs(d['delta_hz'] - 1.25) < 1e-9 and abs(d['fmax_hz'] - 250) < 1e-9 and abs(d['flow_hz'] - 3) < 1e-9, d
assert abs(max(d['bins']) - MAXVAL) < 1e-6, max(d['bins'])
assert abs(min(d['bins']) - MINVAL) < 1e-6, min(d['bins'])
# One byte per bin cannot do better than one packing step, and the stored bytes show no
# consistent rounding direction (199 bins at or above the unpacked value, one a step below),
# so agreement within one step is the strongest claim the data supports.
ratios = [d['bins'][k] / dss[k] - 1 for k in range(200)]
assert max(abs(r) for r in ratios) < step + 2e-3, ('ratio range', min(ratios), max(ratios))
# 1x, 2x, 4x and 8x of 385 RPM (6.42, 12.8, 25.7, 51.3 Hz) land on bins 4, 9, 19, 40 only
# with the (k + 1) x DELTA axis.
for k, order in ((4, 1), (9, 2), (19, 4), (40, 8)):
    assert abs(d['hz'][k] - order * 385 / 60) < 1.25, (k, d['hz'][k])
    assert d['bins'][k] > d['bins'][k - 1] and d['bins'][k] > d['bins'][k + 1], ('not a peak', k)
print('PASS: decode_spc matches MicroBase for all 200 bins of PLOT0093.SPC; axis (k+1) x 1.25 Hz')
