"""PD1: Osram BPW34S -> Osram SFH 2440, and retune the TIA feedback cap.

PATCHES the existing head schematic and board. Does not regenerate either.

WHY
    PD1 was unbuildable as drawn. Three sources disagreed:
      footprint  OptoDevice:Osram_BPW34S-SMD   Osram's SMD part, discontinued
      Value/MPN  BPW34S                        Vishay's BPW34S is LEADED - doc
                                               81521: "packed in tubes,
                                               specifications like BPW34"
    So the board carried an SMD footprint against a through-hole part number,
    naming a device that is out of production either way.

WHY SFH 2440 AND NOT SFH 2430
    Both share the BPW34S footprint exactly - KiCad's Osram_BPW34S-SMD,
    Osram_SFH2430 and Osram_SFH2440 all place pad 1 at (-3.05, 0) 1.4 x 2 mm and
    pad 2 at (3.05, 0) 1.4 x 1.2 mm, same 4.5 x 4 mm body, same 2.65 x 2.65 mm
    chip. So either is a drop-in with no layout change. But:

      SFH 2430   rise/fall 200 us,  C0 1000 pF,  0.17 A/W,  peak 570 nm
      SFH 2440   rise/fall 0.09 us, C0  135 pF,  0.37 A/W,  peak 620 nm

    The 2430 is a true ambient-light sensor and is 2000x too slow; at 3000 rpm a
    200 us edge delay is 3.6 degrees of rotor phase, and its delay varies with
    signal level so it cannot be calibrated out. The 2440 is peak-matched to the
    625 nm XP-E2 emitter (620 nm), holds the BPW34's ~100 ns speed, and its
    400-690 nm window rejects the IR that the BPW34 - peaking at 900 nm - was
    actually most sensitive to. It is a better detector here than the part it
    replaces, not merely an available one.

WHY C21 MOVES 10 pF -> 22 pF
    Junction capacitance roughly doubles, 72 pF -> 135 pF at zero bias. PD1 sits
    reverse-biased at about 1.65 V (cathode on the TIA's virtual reference, anode
    on ground, per the Rev F polarity fix), so call it ~90 pF in circuit. TIA
    stability wants

        Cf >= sqrt(Cin / (2*pi*Rf*GBW))

    With R21 = 10k and the TLV9062's 10 MHz GBW, Cin ~95 pF gives Cf_min 12.3 pF,
    so the fitted 10 pF is now under-damped and would peak. 22 pF restores margin
    and still leaves 723 kHz of TIA bandwidth against a tach rate of 1.3 kHz at
    20000 rpm with four blades.

POLARITY IS UNCHANGED
    Sensor_Optical:SFH2440 extends BP104-SMD, whose pins are (K,1) and (A,2) -
    identical to Sensor_Optical:BPW34. PD1 pin 1 stays on PD_TIA_IN and pin 2 on
    GND, preserving the Rev F fix.
"""
import sys, subprocess, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'BalancerCarrier' / 'scripts'))
from sexp_helpers import *

ROOT = HERE.parent
SCH = ROOT / 'BalancerREF_OptHead.kicad_sch'
PCB = ROOT / 'BalancerREF_OptHead.kicad_pcb'
APPLY = '--apply' in sys.argv
DS = 'https://look.ams-osram.com/m/68c5b1c5aa457db1/original/SFH-2440.pdf'

# ------------------------------------------------------------------ schematic
root = parse(SCH.read_text(encoding='utf8'))
libs = one(root, 'lib_symbols')

src = next((s for s in children(libs, 'symbol') if str(s[1]) == 'Sensor_Optical:BPW34'), None)
if src is None:
    sys.exit('Sensor_Optical:BPW34 not found in lib_symbols')
if any(str(s[1]) == 'Sensor_Optical:SFH2440' for s in children(libs, 'symbol')):
    sys.exit('Sensor_Optical:SFH2440 already present - already patched?')

import copy
clone = copy.deepcopy(src)
clone[1] = 'Sensor_Optical:SFH2440'
for n in clone:                                   # rename the graphic sub-units
    if tagged(n, 'symbol') and str(n[1]).startswith('BPW34_'):
        n[1] = str(n[1]).replace('BPW34_', 'SFH2440_', 1)
for p in children(clone, 'property'):
    key = str(p[1])
    if key == 'Value':       p[2] = 'SFH2440'
    elif key == 'Footprint': p[2] = 'OptoDevice:Osram_SFH2440'
    elif key == 'Datasheet': p[2] = DS
    elif key == 'Description': p[2] = 'Silicon PIN Photodiode, 620 nm peak, IR-filtered'
libs.append(clone)
print('  lib_symbols: added Sensor_Optical:SFH2440 (cloned from BPW34, pins K=1 A=2)')

changed = {'PD1': 0, 'C21': 0}
for n in root:
    if not tagged(n, 'symbol'):
        continue
    refp = next((p for p in children(n, 'property') if str(p[1]) == 'Reference'), None)
    if refp is None:
        continue
    ref = str(refp[2])
    if ref == 'PD1':
        lid = one(n, 'lib_id')
        assert str(lid[1]) == 'Sensor_Optical:BPW34', f'PD1 lib_id is {lid[1]}'
        lid[1] = 'Sensor_Optical:SFH2440'
        for p in children(n, 'property'):
            k = str(p[1])
            if k == 'Value':      assert str(p[2]) == 'BPW34S'; p[2] = 'SFH 2440'; changed['PD1'] += 1
            elif k == 'MPN':      p[2] = 'SFH 2440'; changed['PD1'] += 1
            elif k == 'Footprint':p[2] = 'OptoDevice:Osram_SFH2440'; changed['PD1'] += 1
            elif k == 'Datasheet':p[2] = DS
    elif ref == 'C21':
        for p in children(n, 'property'):
            if str(p[1]) in ('Value', 'MPN'):
                assert str(p[2]) == '10p C0G', f'C21 {p[1]} is {p[2]}'
                p[2] = '22p C0G'; changed['C21'] += 1
print('  PD1: lib_id, Value, MPN, Footprint, Datasheet updated (%d fields)' % changed['PD1'])
print('  C21: Value and MPN 10p C0G -> 22p C0G (%d fields)' % changed['C21'])
assert changed['PD1'] == 3 and changed['C21'] == 2, f'unexpected field counts {changed}'

# ------------------------------------------------------------------ board
pcb = PCB.read_text(encoding='utf8')
subs = [('(footprint "Osram_BPW34S-SMD"', '(footprint "Osram_SFH2440"', 1),
        ('(property "Value" "BPW34S"',    '(property "Value" "SFH 2440"', 1),
        ('(property "Value" "10p C0G"',   '(property "Value" "22p C0G"', 1)]
for old, new, want in subs:
    got = pcb.count(old)
    if got != want:
        sys.exit(f'PCB: {old!r} appears {got} times, expected {want}')
    pcb = pcb.replace(old, new)
print('  PCB: footprint id + PD1 value + C21 value updated (pads are identical, no re-layout)')

if not APPLY:
    print('\ndry run - pass --apply to write')
else:
    KC = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
    SCH.write_text(dump(root) + '\n', encoding='utf8')
    subprocess.run([KC, 'sch', 'upgrade', '--force', str(SCH)], capture_output=True, check=True)
    t = SCH.read_text(encoding='utf8')
    if '\n\t(embedded_fonts' not in t:
        SCH.write_text(t[:-2] + '\n\t(embedded_fonts no)\n)\n', encoding='utf8')
    PCB.write_text(pcb, encoding='utf8')
    print('\nwrote', SCH.name, 'and', PCB.name)
