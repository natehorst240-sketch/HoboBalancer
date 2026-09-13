"""Independent schematic requirements checked against KiCad's exported netlist.

Rev D main board: the optical front end moved to BalancerREF_OptHead (2026-09-11),
SW4 and R5's duplicate BOOT pull-up were dropped, and the MCP73831 + D2 + Q3 + R31
discrete charger/power-path was replaced by a BQ24075. The optical
chain is verified separately by BalancerREF_OptHead/scripts/verify_head.py; the only
thing crossing between the boards is J5's 7-way cable.
"""
from sexp_helpers import *
ROOT=Path(__file__).resolve().parents[1]
d=parse((ROOT/'review'/'BalancerREF.net').read_text())
nets={};actual={}
for n in children(one(d,'nets'),'net'):
 name=one(n,'name')[1];members={one(p,'ref')[1]+'.'+one(p,'pin')[1] for p in children(n,'node')};nets[name]=members
 for p in members:actual[p]=name
# These are circuit specifications, not generated from symbol positions or wires.
groups={
'3V3':'U1.3 U2.8 U2.5 U3.8 U6.1 U6.10 U9.5 U10.8 U10.3 U10.2 J4.1 J5.7 TP1.1 C6.1 C7.1 C8.1 C9.1 C13.1 C14.1 C15.1 C16.1 C17.1 C27.1 C29.1 R4.1 R8.1 R9.1 R15.1 R16.1 R30.1 R37.1 R38.1',
'VBUS':'J1.A4 J1.A9 J1.B4 J1.B9 U5.13 U7.5 TP4.1 C1.1 C2.1 D3.2',
'BAT':'U5.2 U5.3 Q4.2 TP3.1 C3.1',
'BAT_CONNECTOR':'J2.1 Q4.3',
# D2 and Q3 are gone: the BQ24075's internal power path feeds OUT directly, so
# SYS no longer carries a Schottky drop from VBUS.
'SYS':'U5.10 U5.11 SW1.1 C30.1',
'SYS_SW':'R11.1 SW1.2 U6.5 U6.8 U6.6 U6.7 C4.1 C5.1 J5.1',
# SW4 (RESET) removed: SW1 feeds U6 VIN and EN, so the power slide already
# power-cycles the MCU. R4/C10/TP13 still hold EN high and probeable.
'EN':'U1.45 R4.2 C10.1 TP13.1',
# R5 removed: it duplicated R9's 10k pull-up on the same net.
'BOOT':'U1.4 R9.2 SW3.2 TP14.1',
'ACCEL_SCK':'U1.18 U2.13','ACCEL_MOSI':'U1.19 U2.14','ACCEL_MISO':'U1.20 U2.1','ACCEL_CS':'U1.21 U2.12',
'DRDY':'U1.10 U2.4 TP10.1',
'MAG_TACH':'U1.11 U3.12 R15.2 TP7.1',
'OPT_TACH':'U1.12 U10.5 TP9.1',
'OPT_LED_EN':'U1.13 R29.2 J5.3',
'ACQUIRE':'U1.14 SW2.2 R8.2 C11.1','STATUS':'U1.15 R10.1',
'SUPPLY_SENSE':'U1.16 R11.2 R12.1 C12.1',
'USB_D-_MCU':'U1.23 R6.2','USB_D+_MCU':'U1.24 R7.2',
'USB_D-_CONNECTOR':'R6.1 J1.A7 J1.B7 U7.1 TP12.1',
'USB_D+_CONNECTOR':'R7.1 J1.A6 J1.B6 U7.3 TP11.1',
'CC1':'J1.A5 R1.2','CC2':'J1.B5 R2.2',
# BQ24075 programming and status. ISET sets fast-charge current (890/RISET),
# ILIM the input limit (1610/RILIM), TS needs 10k to VSS with no pack thermistor.
'ISET':'U5.16 R3.1','ILIM':'U5.12 R35.1','TS':'U5.1 R36.1',
'CHG_EN1':'U5.6 U1.9','CHG_EN2':'U5.5 U1.22',
'PGOOD_N':'U5.7 U1.25 R37.2','CHG_STAT':'U5.9 U1.34 R38.2',
'SWITCH_L1':'U6.4 L1.1','SWITCH_L2':'U6.2 L1.2',
'MAG+':'J3.1 TP5.1 R13.2','MAG_SERIES':'R13.1 R14.2','VR_IN':'U3.3 R14.1',
'PEAK':'U3.7 R17.1 C19.1','TIMING':'U3.14 R16.2 C18.1',
# The emitter, transimpedance, gain, reference and comparator stages moved to
# BalancerREF_OptHead on 2026-09-11 and are checked by that project's
# scripts/verify_head.py. What crosses to this board is the 7-way cable only.
'OPT_COMP':'J5.5 U9.1',
'SYNC_DELAY':'R29.1 C26.1 U9.2',
'SYNC_HIT':'U9.4 U10.1',
'RCEXT':'U10.7 R30.2 C28.1','CEXT':'U10.6 C28.2',
'STATUS_A':'R10.2 LED1.2',
'GPS_TX':'U1.5 J4.4','GPS_RX':'U1.6 J4.3','GPS_PPS':'U1.17 J4.5',
}
grounds='U1.1 U1.2 U1.42 U1.43 '+' '.join('U1.'+str(i) for i in range(46,66))+' U2.2 U2.3 U2.6 U2.7 U3.2 U3.9 U3.11 U5.4 U5.8 U5.15 U5.17 U6.3 U6.9 U6.11 U7.2 U9.3 U10.4 J1.A1 J1.A12 J1.B1 J1.B12 J1.SH J2.2 J3.2 J4.2 J5.2 J5.4 J5.6 TP2.1 TP6.1 Q4.1 LED1.1 D3.1 R1.1 R2.1 R3.2 R12.2 R17.2 R35.2 R36.2 SW2.1 SW3.1 '+' '.join('C'+str(i)+'.2' for i in list(range(1,20))+[26,27,29,30])
groups['GND']=grounds
failures=[];covered=set()
for group,spec in groups.items():
 want=set(spec.split());anchor=sorted(want)[0];got=nets[actual[anchor]]
 if got!=want:failures.append(f'{group}: missing={sorted(want-got)} extra={sorted(got-want)}')
 covered|=want
nc=json.loads((ROOT/'review'/'unused-pins.json').read_text())
for pin,reason in nc.items():
 if nets.get(actual.get(pin))!={pin}:failures.append(f'Unused {pin} is not isolated: {actual.get(pin)}')
 covered.add(pin)
if covered!=set(actual):failures.append(f'Unspecified endpoints: {sorted(set(actual)-covered)}; absent pins: {sorted(covered-set(actual))}')
# Compare every IC pad against the manufacturer pad/function table, including NC and ground pads.
functions={
'U1':{**{str(i+4):'GPIO'+str(i) for i in range(22)},'1':'GND','2':'GND','3':'3V3','23':'GPIO19/USB_D-','24':'GPIO20/USB_D+','25':'GPIO21','26':'GPIO26','27':'GPIO47','28':'GPIO33','29':'GPIO34','30':'GPIO48','31':'GPIO35','32':'GPIO36','33':'GPIO37','34':'GPIO38','35':'GPIO39','36':'GPIO40','37':'GPIO41','38':'GPIO42','39':'TXD0/GPIO43','40':'RXD0/GPIO44','41':'GPIO45','42':'GND','43':'GND','44':'GPIO46','45':'EN',**{str(i):'GND' for i in range(46,66)}},
# IIS3DWB DS12569 Table 1
'U2':dict(zip(map(str,range(1,15)),['SDO/SA0','RES->VDDIO_or_GND','RES->VDDIO_or_GND','INT1','VDD_IO','GND','GND','VDD','INT2','RES->VDDIO_or_open','RES->VDDIO_or_open','CS','SPC/SCL','SDI/SDA'])),
'U3':dict(zip(map(str,range(1,15)),['NC','GND','VIN','NC','MODE','NC','PEAK_DETECTOR','VCC','TIMING_INPUT','GATED_OUTPUT','INPUT_SELECT','REFERENCE_PULSE_OC','NC','RC_TIMING'])),
# BQ24075RGT, SLUS810N Rev N Table 7-1 / Figure 7-3. Pin 15 is SYSOFF on the '75
# (ITERM on the '74) and pin 17 is the exposed pad, internally tied to VSS.
'U5':{'1':'TS','2':'BAT','3':'BAT','4':'CE','5':'EN2','6':'EN1','7':'PGOOD','8':'VSS',
      '9':'CHG','10':'OUT','11':'OUT','12':'ILIM','13':'IN','14':'TMR','15':'SYSOFF',
      '16':'ISET','17':'EP_VSS'},
'U6':{'1':'VOUT','2':'L2','3':'PGND','4':'L1','5':'VIN','6':'EN','7':'PS/SYNC','8':'VINA','9':'GND','10':'FB','11':'EXPOSED_PAD/PGND'},
'U7':{'1':'I/O','2':'VN/GND','3':'I/O','4':'I/O','5':'VP','6':'I/O'},
# SN74LVC1G132 DBV - Schmitt-trigger NAND, same pinout as the 1G08 it replaced
'U9':{'1':'A','2':'B','3':'GND','4':'Y','5':'VCC'},
# SN74LVC1G123 DCT, SCES586E Table 4-1
'U10':{'1':'A','2':'B','3':'CLR','4':'GND','5':'Q','6':'Cext','7':'Rext/Cext','8':'VCC'},
}
with (ROOT/'review'/'IC-pin-audit.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['Reference','Physical pad','Manufacturer function','KiCad net','Unused rationale'])
 for ref,table in functions.items():
  assert {x.split('.')[1] for x in actual if x.startswith(ref+'.')}==set(table),(ref,'pad set mismatch')
  for pin,fun in sorted(table.items(),key=lambda kv:int(kv[0])):w.writerow([ref,pin,fun,actual[ref+'.'+pin],nc.get(ref+'.'+pin,'')])
with (ROOT/'review'/'pin-net-connections.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['Reference','Pin','Net']);w.writerows([*p.split('.'),n] for p,n in sorted(actual.items()))
report='PASS' if not failures else 'FAIL'
report+=f': {len(groups)} exact circuit nets; {len(actual)} pin endpoints; {sum(map(len,functions.values()))} IC pads; {len(nc)} documented unused pins.\n'
report+='\n'.join(failures)
(ROOT/'review'/'connectivity-check.txt').write_text(report)
print(report);assert not failures
