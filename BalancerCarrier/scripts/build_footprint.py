"""!! OBSOLETE - generates a footprint for the WRONG BOARD !!

This builds a 32-pin DFR0975 (FireBeetle 2 ESP32-S3) footprint. That board is
pre-order only and was dropped on 2026-09-20 for the Unexpected Maker FeatherS3[D],
which uses BalancerCarrier:FeatherS3 - Unexpected Maker's own 28-pad footprint,
taken from github.com/unexpectedmaker/esp32s3. Do not run this and do not assign
FireBeetle2_ESP32S3 to anything. Kept only as a record of how the geometry was
derived from DFRobot's DXF.
"""

_OBSOLETE_HEADER = r"""Generate the FireBeetle 2 footprint from DFRobot's own 2D CAD.

Every number below is read out of DFR0975_2D_CAD.dxf, not measured off a picture:

    two columns of 0.9 mm holes, 2.54 mm pitch, 22.86 mm apart
    14 holes at x=-55.410, y -5.890..27.130      -> header P3
    18 holes at x=-32.550, y -5.890..37.290      -> header P4
    both columns flush at y=-5.890; P4 runs 10.16 mm further the other way
    a 2.0 mm mounting hole at (-55.000, -9.390): 3.5 mm beyond the flush end
    and 0.41 mm inboard of the P3 column

Outline figures (60 x 25.4, R1.5 corners, mounting holes 22 x 56.6, 1.7 mm in from
each edge, 1.6 mm thick) come from DFR0975_2D_CAD.png, which agrees with the DXF
everywhere the two overlap.

ORIGIN is the P3 column's flush-end hole, +y running away from the USB connector.
Pad numbers follow the symbol: 1-14 = P3.1-P3.14, 15-32 = P4.1-P4.18, pin 1 of each
at the USB end.  See ORIENTATION in the README note - confirm VCC is the corner pin
nearest the USB before ordering.
"""
from pathlib import Path

PITCH, ROW, DRILL, PAD = 2.54, 22.86, 1.0, 1.7
P3_N, P4_N = 14, 18
BW, BL, CORNER = 25.4, 60.0, 1.5
MH_D, MH_DY, MH_EDGE = 2.0, 56.6, 1.7
CX = ROW / 2.0                      # centre line between the two columns
Y0 = 3.5                            # flush end -> nearest mounting-hole centre
BOT, TOP = Y0 + MH_EDGE, Y0 + MH_EDGE - BL
L, R = CX - BW / 2.0, CX + BW / 2.0

def pad(n, x, y):
    shape = 'rect' if n == 1 else 'circle'
    return (f'  (pad "{n}" thru_hole {shape} (at {x:.3f} {y:.3f}) (size {PAD} {PAD}) '
            f'(drill {DRILL}) (layers "*.Cu" "*.Mask"))')

out = ['(footprint "FireBeetle2_ESP32S3"',
       '  (version 20240108) (generator "build_footprint.py") (layer "F.Cu")',
       '  (descr "DFRobot FireBeetle 2 ESP32-S3 (DFR0975) on 2.54mm headers. '
       'Geometry from DFRobot DFR0975_2D_CAD.dxf/.png. Pads 1-14 = P3, 15-32 = P4.")',
       '  (tags "firebeetle dfrobot esp32-s3 module header")',
       '  (attr through_hole)',
       f'  (property "Reference" "U**" (at {CX:.3f} {TOP - 1.5:.3f} 0) (layer "F.SilkS")',
       '    (effects (font (size 1 1) (thickness 0.15))))',
       f'  (property "Value" "FireBeetle2_ESP32S3" (at {CX:.3f} {BOT + 1.5:.3f} 0) (layer "F.Fab")',
       '    (effects (font (size 1 1) (thickness 0.15))))']

for i in range(P3_N):                       # P3: pin 1 at the USB end (most -y)
    out.append(pad(i + 1, 0.0, -(P3_N - 1 - i) * PITCH))
for i in range(P4_N):                       # P4: symbol pins 15..32
    out.append(pad(15 + i, ROW, -(P4_N - 1 - i) * PITCH))

for mx in (CX - 11.0, CX + 11.0):           # 22 mm apart, 56.6 mm apart
    for my in (Y0, Y0 - MH_DY):
        out.append(f'  (pad "" np_thru_hole circle (at {mx:.3f} {my:.3f}) '
                   f'(size {MH_D} {MH_D}) (drill {MH_D}) (layers "F&B.Cu" "*.Mask"))')

def rect(layer, x0, y0, x1, y1, w):
    return [f'  (fp_line (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y0:.3f}) '
            f'(stroke (width {w}) (type solid)) (layer "{layer}"))',
            f'  (fp_line (start {x1:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f}) '
            f'(stroke (width {w}) (type solid)) (layer "{layer}"))',
            f'  (fp_line (start {x1:.3f} {y1:.3f}) (end {x0:.3f} {y1:.3f}) '
            f'(stroke (width {w}) (type solid)) (layer "{layer}"))',
            f'  (fp_line (start {x0:.3f} {y1:.3f}) (end {x0:.3f} {y0:.3f}) '
            f'(stroke (width {w}) (type solid)) (layer "{layer}"))']

out += rect('F.Fab', L, BOT, R, TOP, 0.1)
out += rect('F.CrtYd', L - 0.25, BOT + 0.25, R + 0.25, TOP - 0.25, 0.05)
out += rect('F.SilkS', L, BOT, R, TOP, 0.12)
# pin-1 marker: a silk chevron just outboard of pad 1
p1y = -(P3_N - 1) * PITCH
out += [f'  (fp_line (start {-2.2:.3f} {p1y - 1.3:.3f}) (end {-2.2:.3f} {p1y + 1.3:.3f}) '
        f'(stroke (width 0.25) (type solid)) (layer "F.SilkS"))',
        f'  (fp_text user "P3.1 VCC / USB end" (at {-3.4:.3f} {p1y:.3f} 90) (layer "F.Fab")',
        '    (effects (font (size 0.8 0.8) (thickness 0.12))))',
        '  (model "${KIPRJMOD}/BalancerCarrier.3dshapes/FireBeetle2_ESP32S3.step"',
        '    (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))',
        ')']
p = Path('BalancerCarrier.pretty/FireBeetle2_ESP32S3.kicad_mod')
p.write_text('\n'.join(out) + '\n', encoding='utf8')
print(f'wrote {p}  ({P3_N + P4_N} pads, board {BW} x {BL} mm)')
print(f'  P3 pin1 y={-(P3_N-1)*PITCH:.2f}  P4 pin1 y={-(P4_N-1)*PITCH:.2f}  flush end y=0')
print(f'  board y {TOP:.2f}..{BOT:.2f}   x {L:.2f}..{R:.2f}')
