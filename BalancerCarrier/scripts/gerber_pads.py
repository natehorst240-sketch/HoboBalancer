"""Pad -> net table from KiCad X2 Gerber attributes (TO.P / TO.N), all copper layers.

This is the connectivity of the board as fabricated, read from the files sent to the fab
rather than from the schematic. Produces BalancerCarrier/manufactured/as-built-pads.csv and
BalancerREF_OptHead/manufactured/as-built-pads.csv:

  python3 -I gerber_pads.py <dir-with-gerbers> > as-built-pads.csv
"""
import glob, os, re, sys

rows = set()
for f in sorted(glob.glob(os.path.join(sys.argv[1], '*_Cu.gbr'))):
    attrs = {}
    for line in open(f, encoding='ascii', errors='replace'):
        for m in re.finditer(r'%TO\.([A-Za-z]+),([^*]*)\*%', line):
            attrs[m.group(1)] = m.group(2)
        if re.search(r'%TD\*%', line):
            attrs = {}
        elif re.search(r'%TD\.([A-Za-z]+)\*%', line):
            attrs.pop(re.search(r'%TD\.([A-Za-z]+)\*%', line).group(1), None)
        if 'P' in attrs and re.search(r'D0?3\*', line):
            p = attrs['P'].split(',')
            rows.add((p[0], p[1], p[2] if len(p) > 2 else '', attrs.get('N', '')))
print('ref,pin,pinfunction,net')
for r in sorted(rows, key=lambda r: (r[0], int(r[1]) if r[1].isdigit() else 999, r[1])):
    print(','.join(r))
