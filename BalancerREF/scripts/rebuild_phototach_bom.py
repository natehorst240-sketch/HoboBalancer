"""Rewrite PhotoTach-BOM.csv against what the schematics actually contain.

The old file had nine classes of error. The root cause of the worst of them was
structural: it had no Board column, and the optical chain spans two boards whose
designators collide. "U4" meant the TLV9062 in the BOM, but U4 on the head is the
TS3021 comparator; "U5" meant the TS3021, but U5 on BalancerREF is the BQ24075
charger; "U7" meant the monostable, but U7 on BalancerREF is the SRV05-4 ESD array.
Ordering or stuffing by those designators would have put parts in the wrong places.

Fixed here:
  designators   U4 -> U8, U5 -> U4, U7 -> U10, and a Board column so it cannot recur
  PD1           BPW34 -> SFH 2440 (see the note in the row)
  C21           10 pF -> 22 pF, and 0603 -> 0805
  R30/C28       100k / 1 nF -> 10k / 10 nF
  R23           200k -> 120k
  R28           was mis-referenced as R26
  C20           6.3 V -> 10 V
  packages      C21-C25 are 0805 and C20 is 1210, not the 0603 the BOM claimed
  added         R19, R20, R24, R25, R32 - five head resistors with no BOM line at
                all, including the R24/R25 divider that sets the op amp reference

Purchasing data (manufacturer, Digi-Key numbers, prices) is carried over from the
old file; only the parts that actually changed got new numbers.
"""
import csv
from pathlib import Path

H, M, X = 'OptHead', 'BalancerREF', 'mechanical'
DK = 'DigiKey PN / page'

PD1_NOTE = (
    'CHANGED 2026-09-21. Was BPW34S. Osram SMD version is discontinued, and Vishay '
    'BPW34S is LEADED (doc 81521: "packed in tubes, specifications like BPW34"), so '
    'the old line paired an SMD footprint with a through-hole part number. SFH 2440 '
    'is pad-identical to Osram_BPW34S-SMD so there is no layout change; peak 620 nm '
    'matches the 625 nm emitter, and its 400-690 nm window blocks the IR the BPW34 '
    '(peak 900 nm) was most sensitive to. NOT SFH 2430: 200 us rise time, 1000 pF, '
    'unusable for tach phase.'
)
C21_NOTE = (
    'CHANGED 2026-09-21 from 10 pF. TIA stability: SFH 2440 roughly doubles junction '
    'capacitance (135 pF vs ~72 pF at zero bias), so Cf_min = sqrt(Cin/(2*pi*Rf*GBW)) '
    'rises to about 12.3 pF with R21 10k and the TLV9062 10 MHz GBW; the fitted 10 pF '
    'would peak. 22 pF still leaves 723 kHz. Package WAS WRONG: BOM said 0603, '
    'schematic is 0805.'
)
R30_NOTE = (
    'CHANGED 2026-09-20 from 100k / 1 nF. One-shot timing: 10k/10n is the characterised '
    'row in TI SCES586E section 5.8, tw 100-110 us guaranteed across all four supply '
    'voltages. 100k is ten times beyond the largest Rext TI characterises.'
)

ROWS = [
 (H,'D1',1,'Red 625 nm high-power LED, 1 A max, Vf 2.2 V, 3535','Cree LED','XPEBRD-L1-0000-00501','XPEBRD-L1-0000-00501CT-ND','1.50','Pulsed 500 mA, 5 us at 20 kHz (10 percent duty); visible aiming spot; any XPEBRD-L1 bin works'),
 (H,'PD1',1,'Si PIN photodiode, SMD DIL 4.5x4 mm, 7.02 mm2, peak 620 nm, IR-filtered 400-690 nm, tr 90 ns','ams OSRAM','SFH 2440','SFH 2440, or SFH 2440-Z for tape and reel','1.30',PD1_NOTE),
 (H,'LENS1',1,'9.9 mm TINA spot lens 10-15 deg with adhesive holder for Cree XP-E','Ledil','FA10887_TINA-RS','711-1113-ND','3.50','Holder included; adhesive to PCB. Carclo 10193 and 10003 were out of stock 2026-09-09'),
 (H,'LENS1-ALT',0,'LISA2 spot lens 15-24 deg with pin holder (alternate)','Ledil','FP11055_LISA2-RS-PIN','711-1105-ND','3.00','Wider beam: about 8 in wide at 24 in; more aim tolerance'),
 (H,'U8',1,'Dual 10 MHz RRIO CMOS op amp, SOIC-8','Texas Instruments','TLV9062IDR','296-47857-1-ND','0.65','REF WAS WRONG: listed as U4, but U4 on this board is the TS3021. A: transimpedance 10k; B: AC-coupled gain 20. VSSOP TLV9062IDGKR was out of stock 2026-09-09, same die'),
 (H,'U8-ALT',0,'Dual 10 MHz op amp, SOIC-8, drop-in alternate','Microchip','MCP6292-E/SN','MCP6292-E/SN-ND','0.70','Same pinout and bandwidth class; use if the TLV9062 runs out'),
 (H,'U4',1,'Comparator, push-pull, SOT-23-5','STMicroelectronics','TS3021IYLT','already in Rev B BOM','0.45','REF WAS WRONG: listed as U5, but U5 on BalancerREF is the BQ24075 charger. Fixed divider threshold plus 470k hysteresis; RV1 deleted'),
 (H,'Q1',1,'N-channel MOSFET 30 V 5.7 A, SOT-23','Alpha and Omega','AO3400A','already in Rev B BOM','0.20','Switches the LED pulse current; gate driven from OPT_LED_EN through R19'),
 (H,'J5',1,'JST GH 7-way horizontal, 1.25 mm pitch','JST','SM07B-GHS-TB','455-1650-1-ND','0.60','To main board: VBAT, GND, OPT_LED_EN, GND, OPT_COMP, GND, +3V3'),
 (H,'R18',1,'3.9 ohm 1206 0.5 W pulse resistor','generic','any 1206 3R9 1 percent','search "3.9 ohm 1206 0.5W"','0.10','Sets about 490 mA peak at a full 4.2 V cell; size at the top of the VBAT range. MUST stay 1206: the pulse withstand is a function of body size, not resistance'),
 (H,'R19',1,'100 ohm 0603','generic','any','stock','0.01','ADDED - had no BOM line. Gate series resistor for Q1'),
 (H,'R20',1,'100k 0603','generic','any','stock','0.01','ADDED - had no BOM line'),
 (H,'R21',1,'10k 0603 1 percent','generic','any','stock','0.01','Transimpedance feedback'),
 (H,'R22, R23',2,'10k and 120k 0603 1 percent','generic','any','stock','0.02','Gain stage. WAS WRONG: BOM said 200k; schematic R23 is 120k'),
 (H,'R24, R25',2,'10k 0603 1 percent, qty 2','generic','any','stock','0.02','ADDED - had no BOM line. OPT_VREF mid-rail divider; without these the op amp has no reference'),
 (H,'R26, R27',2,'22k and 10k 0603 1 percent','generic','any','stock','0.02','Comparator threshold divider. Values are fixed in the schematic now; the BOM previously said "set on bench"'),
 (H,'R28',1,'470k 0603','generic','any','stock','0.01','Comparator hysteresis. The old BOM note mis-referenced this as R26; R26 is the 22k threshold leg'),
 (H,'R32',1,'33 ohm 0603','generic','any','stock','0.01','ADDED - had no BOM line'),
 (H,'C20',1,'100 uF 10 V low-ESR, 1210','generic','any','search "100uF 10V 1210"','0.30','Local reservoir for the 5 us 500 mA pulses; place at R18. WAS WRONG: BOM said 6.3 V, schematic is 10 V'),
 (H,'C21',1,'22 pF 0805 C0G','generic','any','stock','0.01',C21_NOTE),
 (H,'C22',1,'10 nF 0805 X7R','generic','any','stock','0.01','AC coupling into the gain stage. Package WAS WRONG: BOM said 0603, schematic is 0805'),
 (H,'C23, C24, C25',3,'100 nF 0805, qty 3','generic','any','stock','0.03','Decoupling for U4 and U8. Package WAS WRONG: BOM said 0603, schematic is 0805'),
 (M,'U9',1,'Single 2-input NAND gate, Schmitt inputs, SOT-23-5','Texas Instruments','SN74LVC1G132DBVR','296-13321-1-ND','0.12','Synchronous gate: comparator NAND delayed emitter pulse. MUST be the 1G132, not the 1G08 it replaced'),
 (M,'U10',1,'Retriggerable monostable, Schmitt inputs, SSOP-8','Texas Instruments','SN74LVC1G123DCTR','digikey.com/en/products/detail/texas-instruments','0.55','REF WAS WRONG: listed as U7, but U7 on BalancerREF is the SRV05-4 ESD array. Trigger is pin 1 A falling, with B and CLR held high'),
 (M,'R29, C26',2,'1k 0603 and 470 pF 0805 C0G','generic','any','stock','0.02','Delays the emitter pulse copy about 0.5 us into the gate to match receiver latency'),
 (M,'R30, C28',2,'10k 0603 and 10 nF 0805 C0G','generic','any','stock','0.02',R30_NOTE),
 (M,'R39, R40',2,'100k 0603, qty 2','generic','any','stock','0.02','R39 holds OPT_COMP low when the head is unplugged from J5; R40 holds the R29/C26 strobe low'),
 (X,'WINDOW',1,'Red-tinted acrylic window, 3 mm, covering LED and photodiode','enclosure part','n/a','McMaster or Tap Plastics','2.00','Long-pass filter; keep an internal baffle between LED and photodiode. Less critical now that the SFH 2440 blocks IR itself'),
 (X,'TAPE',1,'Retroreflective tape, 25 mm wide','3M','3M 7610 or Banner BRT-THG-2X2','not a Digi-Key item','10.00','Required: ordinary reflective tape returns far too little at 24 in'),
]

COLS = ['Board','Ref','Qty','Description','Manufacturer','MPN',DK,'Approx unit USD','Notes']
out = Path(__file__).resolve().parent.parent / 'PhotoTach-BOM.csv'
with out.open('w', encoding='utf8', newline='') as f:
    w = csv.writer(f)
    w.writerow(COLS)
    w.writerows(ROWS)
fitted = sum(float(r[7]) * int(r[2]) for r in ROWS if int(r[2]))
print(f'wrote {out.name}: {len(ROWS)} lines (was 24)')
print(f'  one fitted set, excluding zero-qty alternates: ${fitted:.2f}')
print(f'  boards covered: {sorted({r[0] for r in ROWS})}')
