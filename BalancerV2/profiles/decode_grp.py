"""Decode a MicroVib II group (.grp) file: regimes, adjustment columns, angles.

Format worked out from A109.grp (2026-10-22), not from DSS documentation:
  header 16 bytes: name[8], 4 zero, uint32 id
  then 180-byte records:
    name[8], enabled u8, 2 zero, F16 A, 2 zero, F16 B, flags u16, n u8, then n x 20-byte entries:
      unit[8], F16 angle, label[8], F16 y (always 1.0 so far)
  F16 = value = low_byte * 2 ** (high_byte - 72); no sign, no implicit bit.
Decoded meaning so far: entry angle = adjustment position in degrees (TARGET/LOC1 = 0).
A = SENS (MicroBase 'SENS': solution sensitivity, adjustment units per IPS, e.g. 320 g/IPS,
8 deg/IPS) and B = TACH (tach angular offset in degrees, e.g. 340). Confirmed against a
MicroBase balance-history row for GND LT on 2026-10-22.
"""
import struct, sys

def f16(w):
    hi, lo = w[1], w[0]
    return lo * 2.0 ** (hi - 72) if (hi or lo) else 0.0

def s(x):
    return x.split(b'\0')[0].decode('ascii', 'replace')

def decode(path):
    b = open(path, 'rb').read()[:16 + 10 * 180]  # group section only (an .HST continues past it)
    out = {'name': s(b[:8]), 'id': struct.unpack('<I', b[12:16])[0], 'records': []}
    off, REC = 16, 180
    while off + REC <= len(b):
        r = b[off:off + REC]
        n = r[19]
        rec = {'name': s(r[0:8]), 'enabled': bool(r[8]), 'sens': f16(r[11:13]), 'tach': f16(r[15:17]),
               'flags': struct.unpack('<H', r[17:19])[0], 'entries': []}
        for i in range(n):
            e = r[20 + 20 * i:40 + 20 * i]
            rec['entries'].append({'label': s(e[10:18]), 'unit': s(e[0:8]), 'angle': f16(e[8:10]), 'y': f16(e[18:20])})
        out['records'].append(rec)
        off += REC
    return out

if __name__ == '__main__' and len(sys.argv) == 2:
    g = decode(sys.argv[1])
    print(f"{g['name']}  id={g['id']}")
    for r in g['records']:
        print(f"[{r['name']:8s}] {'on ' if r['enabled'] else 'off'} sens={r['sens']:g} tach={r['tach']:g} flags=0x{r['flags']:04x}")
        for e in r['entries']:
            print(f"    {e['label']:8s} {e['unit']:8s} {e['angle']:5.0f} deg")


# --- .TRK and .SPC (partial) -------------------------------------------------
# 731H1.TRK (96 bytes): "A109" + regime "HOV VT" + 0x50 bytes of fields, mixed
# 16-bit F16 and 32-bit values; field meanings not yet mapped (need the MicroVib
# screen values for the same record).
# PLOT0093.SPC (860 bytes): 0x3c header ("A109", "DVA VT", F16 fields incl.
# 0x48fa=250 and 0x41a0=1.25, read as span 250 and 1.25 per bin), then 200 IEEE
# little-endian float32 amplitudes.
def decode_spc(path):
    b = open(path, 'rb').read()
    n = (len(b) - 0x3c) // 4
    return {'name': s(b[2:10]), 'regime': s(b[10:18]),
            'hdr16': [(hex(i), f16(b[i:i + 2])) for i in range(0x12, 0x3c, 2)],
            'bins': struct.unpack('<%df' % n, b[0x3c:0x3c + 4 * n])}


# --- .HST history files -------------------------------------------------------
# Layout (worked out from A1090731.HST against MicroBase balance-history rows):
#   bytes 0..1815: the group file (same as .grp)
#   then 86-byte run records, each: u8 task index, u8 0, u16 days since 1980-01-01,
#   u16 time in 2-second units (day count is off by one on one of two files, +/-1 day), marker 03 c3 1b, u8 flag, u8 0x02, f32 x0 (constant per
#   file, unknown), f32 x1 (unknown), u8, u8, u8 avgs, u8 bw percent, u8 0, f32 rpm*64/60,
#   f32 level (does not always match the displayed level; use mag/sens), C32 phase deg,
#   C32 previous level, C32 previous phase, C32 entered change magnitude, C32 change
#   location (the 16-byte block; zero on a first run),
#   C32 sens, C32 tach, C32 chg1, C32 loc1, C32 rad1, C32 chg2, C32 loc2, C32 rad2, 2 bytes.
#   C32 = (m2 + m1/256 + m0/65536) * 2**(exp-72) with bytes [m0 m1 m2 exp].
#   Solution angle convention: -(phase + tach + 180) mod 360; magnitude = sens * level.
import datetime, math

def c32(w):
    m0, m1, m2, e = w
    return (m2 + m1 / 256 + m0 / 65536) * 2.0 ** (e - 72) if e else 0.0

def decode_hst(path):
    b = open(path, 'rb').read()
    g = decode(path)  # group section is identical
    tasks = [r['name'] for r in g['records']]
    runs = []
    import re
    for m in re.finditer(rb'\x03\xc3\x1b', b):
        o = m.start() - 6
        if o < 1816: continue
        r = b[o:o + 86]
        day, tm = struct.unpack('<HH', r[2:6])
        f = lambda k: struct.unpack('<f', r[k:k + 4])[0]
        run = {'task': tasks[r[0]] if r[0] < len(tasks) else r[0],
               'when': datetime.datetime(1980, 1, 1) + datetime.timedelta(days=day, seconds=tm * 2),
               'avgs': r[21], 'bw_pct': r[22], 'rpm': f(24) * 60 / 64, 'level_raw': f(28),
               'phase': c32(r[32:36]), 'sens': c32(r[52:56]), 'tach': c32(r[56:60]),
               'adj': [(c32(r[60:64]), c32(r[64:68])), (c32(r[72:76]), c32(r[76:80]))],
               'x0': f(11), 'x1': f(15), 'flag': r[9],
               'prev_level': c32(r[36:40]), 'prev_phase': c32(r[40:44]),
               'change': (c32(r[44:48]), c32(r[48:52]))}
        a, bb = run['adj']
        d = abs(a[1] - bb[1]) % 360
        mag = math.hypot(a[0], bb[0]) if d in (90, 270) else abs(a[0] - bb[0]) if d == 180 else a[0] + bb[0]
        run['level'] = mag / run['sens'] if run['sens'] else None
        run['solution_angle'] = (-(run['phase'] + run['tach'] + 180)) % 360
        runs.append(run)
    return g, runs

if __name__ == '__main__' and len(sys.argv) > 2 and sys.argv[2] == 'hst':
    g, runs = decode_hst(sys.argv[1])
    for r in runs:
        print(f"{r['task']:8s} {r['when']} rpm={r['rpm']:.1f} level={r['level']} phase={r['phase']:.1f} "
              f"sens={r['sens']:g} tach={r['tach']:g} adj={r['adj']} angle={r['solution_angle']:.1f}")
