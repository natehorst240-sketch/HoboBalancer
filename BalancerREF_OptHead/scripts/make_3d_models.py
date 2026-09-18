"""Build STEP models for the two optical parts that KiCad's library does not ship.

Run with FreeCAD's headless interpreter:
  "C:/Program Files/FreeCAD 1.0/bin/FreeCADCmd.exe" -c "exec(open('scripts/make_3d_models.py').read())"

Dimensions come from the manufacturer drawings, not guessed:

  Cree XLamp XP-E (CLD-DS18 rev 32, p.33): 3.45 x 3.45 mm ceramic, 0.58 mm thick,
  silicone dome R1.30 with the package 2.00 mm tall overall, so the sphere centre sits
  0.12 mm above the ceramic top and the dome base is 2.59 mm across. Optical origin is
  the package centre.

  Vishay BPW34S / VBPW34S (doc 81521): body 4.5 x 4.3 mm (4.65 over the flange), 2.0 mm
  tall, 0.7 x 0.35 mm leads. The SMD form is listed as 5.4 x 4.3 x 3.2 mm overall, so the
  body stands 1.2 mm off the board on bent leads whose feet span 5.4 mm. Sensitive area
  is 2.75 mm square (7.5 mm2) centred on the top face.

Both are placed with the footprint origin at the package centre and z = 0 on the board,
which is what KiCad expects with no offset.
"""
import os
import FreeCAD, Part
from FreeCAD import Vector as V


def export(shape, name):
    """Part.export wants document objects; a bare shape silently writes an empty file."""
    assert shape.isValid() and shape.Volume > 0.5, (name, shape.Volume)
    doc = FreeCAD.newDocument(name)
    obj = doc.addObject('Part::Feature', name)
    obj.Shape = shape
    Part.export([obj], os.path.join(OUT, name + '.step'))
    print('%s: volume %.2f mm3, bbox %s' % (name, shape.Volume, shape.BoundBox))
    FreeCAD.closeDocument(doc.Name)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
    globals().get('__file__', os.path.join(os.getcwd(), 'scripts', 'x.py'))))), '3dmodels')
os.makedirs(OUT, exist_ok=True)


def box(l, w, h, x=0.0, y=0.0, z=0.0):
    return Part.makeBox(l, w, h, V(x - l / 2, y - w / 2, z))


# ---------------------------------------------------------------- Cree XP-E
ceramic = box(3.45, 3.45, 0.58)
# thin metallisation lip the dome sits on (0.73 - 0.58 from the side view)
lip = Part.makeCylinder(1.35, 0.15, V(0, 0, 0.58))
dome = Part.makeSphere(1.30, V(0, 0, 0.70)).common(box(4, 4, 2.0, 0, 0, 0.58))
# corner chamfer on the cathode-side corner as the orientation cue (matches the silk)
notch = Part.makeBox(0.6, 0.6, 1.0, V(-1.725 - 0.3, -1.725 - 0.3, -0.1))
notch.rotate(V(-1.725, -1.725, 0), V(0, 0, 1), 45)
ceramic = ceramic.cut(notch)
# underside pads: anode, thermal, cathode (0.5 / 1.3 / 0.5 wide, 3.3 long, 0.02 proud)
pads = [box(0.5, 3.3, 0.02, -1.4, 0, -0.02), box(1.3, 3.3, 0.02, 0, 0, -0.02), box(0.5, 3.3, 0.02, 1.4, 0, -0.02)]
xpe = ceramic.fuse([lip, dome] + pads)
export(xpe, 'LED_Cree-XP')

# ---------------------------------------------------------------- Vishay BPW34S
STANDOFF, BODY_H, BODY_L, BODY_W = 1.2, 2.0, 4.5, 4.3
body = box(BODY_L, BODY_W, BODY_H, 0, 0, STANDOFF)
flange = box(4.65, BODY_W, 0.3, 0, 0, STANDOFF)          # 4.65 over the base flange
chip = box(2.75, 2.75, 0.05, 0, 0, STANDOFF + BODY_H)     # sensitive area, just proud of the top
lens_cut = box(3.0, 3.0, 0.2, 0, 0, STANDOFF + BODY_H - 0.2)  # shallow window recess
body = body.fuse(flange).cut(lens_cut).fuse(chip)
leads = []
for sx in (-1, 1):
    x_exit = sx * 1.9                                     # lead leaves the underside near each end
    vert = box(0.35, 0.7, STANDOFF, x_exit, 0, 0.0)       # down from the body to the board
    foot = box(2.7 - abs(x_exit) + 0.35, 0.7, 0.35, sx * ((abs(x_exit) - 0.175 + 2.7) / 2), 0, 0.0)
    leads += [vert, foot]
# cathode marking: small notch on the pin-1 end of the flange
mark = Part.makeCylinder(0.25, 0.4, V(-BODY_L / 2 + 0.1, BODY_W / 2 - 0.5, STANDOFF - 0.1))
bpw = body.fuse(leads).cut(mark)
export(bpw, 'BPW34S')

print('wrote', OUT, [f for f in os.listdir(OUT) if f.endswith('.step')])
