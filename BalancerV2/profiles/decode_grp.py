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
    b = open(path, 'rb').read()
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

if __name__ == '__main__':
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
