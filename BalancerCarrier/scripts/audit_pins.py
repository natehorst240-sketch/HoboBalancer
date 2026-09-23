"""Read-only schematic/pad audit. Expected pins transcribed from manufacturer drawings.

Exports fresh netlists and ERC into review/pin-audit. Never edits the designs.
PASS means the stated pin/net check passes, not that the assembled instrument is validated.
"""
from pathlib import Path
import csv, hashlib, json, re, subprocess, sys
from sexp_helpers import parse, children, one, LIB

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUT = ROOT / 'review' / 'pin-audit'
KC = Path('C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')
OUT.mkdir(parents=True, exist_ok=True)
SOURCES = {
 'Feather': 'https://raw.githubusercontent.com/UnexpectedMaker/esp32s3/main/series_d/schematics/schematic-feathers3d-p1.pdf ; series_d/pinout_cards/feathers3d_pinout.jpg',
 'LM1815': 'https://www.ti.com/lit/ds/symlink/lm1815.pdf p1,8-10',
 '132': 'https://www.ti.com/lit/ds/symlink/sn74lvc1g132.pdf p3',
 '123': 'https://www.ti.com/lit/ds/symlink/sn74lvc1g123.pdf p3',
 'IIS3DWB': 'https://www.st.com/resource/en/datasheet/iis3dwb.pdf p3-4',
 'TS3021': 'https://www.st.com/resource/en/datasheet/ts3021.pdf pin connections / ordering table',
 'TLV9062': 'https://www.ti.com/lit/ds/symlink/tlv9062.pdf TLV9062 D-package pin table',
 'AO3400A': 'https://www.aosmd.com/sites/default/files/res/datasheets/AO3400A.pdf p1',
 'PD1': 'https://look.ams-osram.com/m/68c5b1c5aa457db1/original/SFH-2440.pdf p7-8; SFH 2440 cathode marking and land pattern',
 'D1': 'https://downloads.cree-led.com/files/ds/x/XLamp-XPE2.pdf mechanical dimensions',
 'generic': 'Circuit topology plus assigned KiCad footprint; exact purchasable part not specified',
 'J5': 'https://www.jst-mfg.com/product/index.php?lang=2&series=105 ; both J5 netlists',
}
# Each entry is (manufacturer pin identity, required circuit net), in pin-number order.
# NC means deliberately unconnected. Output pin names may differ cosmetically in KiCad.
SPECS = {
 'carrier': {
  'U1': ('Feather', [('VBAT','VBAT'),('EN','NC'),('5V','NC'),('IO11','ACCEL_MOSI'),('IO10','GPS_UART_TX'),('IO7','GPS_UART_RX'),('IO3','NC'),('IO1','MAG_TACH'),('IO38','NC'),('IO33','NC'),('IO9','NC'),('IO8','NC'),('LDO2_OUT','GPS_3V3'),('TX','NC'),('RX','NC'),('IO37','STATUS_LED'),('IO35','OPT_TACH'),('IO36','OPT_LED_EN'),('IO5','ACQUIRE_BUTTON'),('IO6','GPS_PPS'),('IO12','ACCEL_SCK'),('IO14','ACCEL_MISO'),('IO18','ACCEL_DRDY'),('IO17','ACCEL_CS'),('GND','GND'),('IO0','NC'),('3V3','+3V3'),('RST','NC')]),
  'U2': ('LM1815', [('NC','NC'),('GND','GND'),('VR input','VR_IN'),('NC','NC'),('MODE (open = mode 1)','NC'),('NC','NC'),('PEAK DET','MAG_PEAK'),('VCC','+3V3'),('TIMING INPUT','GND'),('GATED OUTPUT','NC'),('INPUT SELECT','GND'),('REFERENCE PULSE open collector','MAG_TACH'),('NC','NC'),('RC TIMING','MAG_TIMING')]),
  'U3': ('132', [('A','OPT_COMP'),('B','SYNC_DELAY'),('GND','GND'),('Y NAND','SYNC_HIT'),('VCC','+3V3')]),
  'U4': ('123', [('A active-low trigger','SYNC_HIT'),('B','+3V3'),('CLR active-low','+3V3'),('GND','GND'),('Q','OPT_TACH'),('Cext','OPT_CEXT'),('Rext/Cext','OPT_RCEXT'),('VCC','+3V3')]),
  'U5': ('IIS3DWB', [('SDO','ACCEL_MISO'),('RES ground or VDD_IO','GND'),('RES ground or VDD_IO','GND'),('INT1','ACCEL_DRDY'),('VDD_IO','+3V3'),('GND','GND'),('GND','GND'),('VDD','+3V3'),('INT2','NC'),('RES open or VDD_IO','NC'),('RES open or VDD_IO','NC'),('CS','ACCEL_CS'),('SPC','ACCEL_SCK'),('SDI','ACCEL_MOSI')]),
  'LED1': ('generic', [('K cathode','GND'),('A anode','LED_SERIES')]),
  'J3': ('generic', [('pickup positive','MAG_IN'),('pickup return','GND')]),
  'J4': ('generic', [('3.3V supply','GPS_3V3'),('ground','GND'),('GPS TX -> MCU RX','GPS_UART_RX'),('GPS RX <- MCU TX','GPS_UART_TX'),('GPS PPS -> MCU','GPS_PPS')]),
  'J5': ('J5', [('emitter supply','VBAT'),('ground','GND'),('emitter command','OPT_LED_EN'),('ground','GND'),('comparator return','OPT_COMP'),('ground','GND'),('receiver supply','+3V3')]),
 },
 'head': {
  'U4': ('TS3021', [('OUT','CMP_OUT'),('VCC-','GND'),('IN+','CMP_THRESHOLD'),('IN-','OPT_AMP'),('VCC+','+3V3')]),
  'U8': ('TLV9062', [('OUT1','TIA_OUT'),('IN1-','PD_TIA_IN'),('IN1+','OPT_VREF'),('V-','GND'),('IN2+','OPT_VREF'),('IN2-','AMP_INV'),('OUT2','OPT_AMP'),('V+','+3V3')]),
  'Q1': ('AO3400A', [('gate','MOS_GATE'),('source','GND'),('drain','Net-(D1-K)')]),
  'PD1': ('PD1', [('K cathode','PD_TIA_IN'),('A anode','GND')]),
  'D1': ('D1', [('K cathode','Net-(D1-K)'),('A anode','Net-(D1-A)')]),
  'J5': ('J5', [('emitter supply','SYS_SW'),('ground','GND'),('emitter command','OPT_LED_EN'),('ground','GND'),('comparator return','OPT_COMP'),('ground','GND'),('receiver supply','+3V3')]),
 }
}
# Independent circuit endpoint expectations for every two-terminal passive/switch.
PASSIVES = {
 'carrier': {
  'C2':('MAG_TIMING','GND'), 'C3':('MAG_PEAK','GND'), 'C4':('OPT_RCEXT','OPT_CEXT'),
  'C5':('SYNC_DELAY','GND'), 'C6':('ACQUIRE_BUTTON','GND'),
  **{r:('+3V3','GND') for r in ['C7','C8','C9','C11','C12']},
  'R5':('MAG_IN','Net-(R5-Pad2)'), 'R6':('Net-(R5-Pad2)','VR_IN'),
  'R7':('+3V3','MAG_TIMING'), 'R8':('MAG_PEAK','GND'), 'R9':('+3V3','MAG_TACH'),
  'R10':('+3V3','OPT_RCEXT'), 'R11':('OPT_LED_EN','SYNC_DELAY'),
  'R12':('SYNC_DELAY','GND'), 'R13':('OPT_COMP','GND'), 'R14':('+3V3','ACQUIRE_BUTTON'),
  'R15':('STATUS_LED','LED_SERIES'), 'SW1':('ACQUIRE_BUTTON','GND'),
 },
 'head': {
  'C20':('SYS_SW','GND'), 'C21':('PD_TIA_IN','TIA_OUT'), 'C22':('TIA_OUT','AC_COUPLED'),
  'C23':('OPT_VREF','GND'), 'C24':('+3V3','GND'), 'C25':('+3V3','GND'),
  'R18':('SYS_SW','Net-(D1-A)'), 'R19':('MOS_GATE','OPT_LED_EN'), 'R20':('MOS_GATE','GND'),
  'R21':('TIA_OUT','PD_TIA_IN'), 'R22':('AMP_INV','AC_COUPLED'), 'R23':('OPT_AMP','AMP_INV'),
  'R24':('+3V3','OPT_VREF'), 'R25':('OPT_VREF','GND'), 'R26':('+3V3','CMP_THRESHOLD'),
  'R27':('CMP_THRESHOLD','GND'), 'R28':('CMP_OUT','CMP_THRESHOLD'), 'R32':('CMP_OUT','OPT_COMP'),
 }
}
for board, parts in PASSIVES.items():
 for ref,nets in parts.items(): SPECS[board][ref]=('generic', [('terminal 1',nets[0]),('terminal 2',nets[1])])

def normalize(net):
 if net.startswith('unconnected-'): return 'NC'
 net=net.lstrip('/')
 # KiCad renames this unnamed series net when the diode is rotated.
 return 'LED_SERIES' if net in ['Net-(LED1-K)','Net-(LED1-A)'] else net

rows=[]; footprints=[]; findings=[]; allnets={}; hashes={}
for board, project in [('carrier',ROOT),('head',REPO/'BalancerREF_OptHead')]:
 sch=project/(project.name+'.kicad_sch')
 hashes[str(sch.relative_to(REPO))]=hashlib.sha256(sch.read_bytes()).hexdigest()
 netfile=OUT/(board+'.net')
 subprocess.run([str(KC),'sch','export','netlist','-o',str(netfile),str(sch)],check=True,capture_output=True)
 subprocess.run([str(KC),'sch','erc','--severity-all','-o',str(OUT/(board+'-erc.rpt')),str(sch)],check=True,capture_output=True)
 netlist=parse(netfile.read_text(encoding='utf8'))
 actual={}; names={}
 for net in children(one(netlist,'nets'),'net'):
  for p in children(net,'node'):
   key=(one(p,'ref')[1],one(p,'pin')[1]);actual[key]=normalize(one(net,'name')[1])
   names[key]=one(p,'pinfunction')[1] if one(p,'pinfunction') else ''
 allnets[board]=actual
 comps={one(c,'ref')[1]:c for c in children(one(netlist,'components'),'comp')}
 for ref,c in comps.items():
  value=one(c,'value')[1];fp=one(c,'footprint')[1];lib,name=fp.split(':')
  path=ROOT/'BalancerCarrier.pretty'/(name+'.kicad_mod') if lib=='BalancerCarrier' else LIB/'footprints'/(lib+'.pretty')/(name+'.kicad_mod')
  f=parse(path.read_text(encoding='utf8'));pads=children(f,'pad');numbers={p[1] for p in pads if p[1]}
  hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
  src, spec=SPECS[board].get(ref,('generic',[]))
  if not spec:findings.append(f'UNREVIEWED {board} {ref}')
  for i,(role,want) in enumerate(spec,1):
   key=(ref,str(i));got=actual.get(key,'MISSING');status='PASS' if got==want else 'FAIL'
   if str(i) not in numbers:status='FAIL';findings.append(f'{board} {ref}.{i} missing footprint pad')
   if got!=want:findings.append(f'{board} {ref}.{i} {role}: {got}, expected {want}')
   qualifier=''
   if board=='head' and ref=='PD1':qualifier='SFH 2440: pad 1 wider cathode lead to TIA; pad 2 anode ground. Optical/TIA performance needs bench validation.'
   elif src=='generic':qualifier='Exact component or external device not specified; topology/footprint convention only'
   if board=='carrier' and ref=='LED1':qualifier='Anode must face R15/GPIO37; cathode ground; exact LED MPN not specified'
   rows.append(dict(board=board,reference=ref,value=value,pin=i,manufacturer_function=role,schematic_pin_name=names.get(key,''),actual_net=got,expected_net=want,result=status,footprint=fp,source=SOURCES[src],qualification=qualifier))
  expected_nums={str(i) for i in range(1,len(spec)+1)}
  extra=numbers-expected_nums
  allowed={'MP'} if ref=='J5' else ({'3'} if board=='head' and ref=='D1' else set())
  if extra-allowed:findings.append(f'{board} {ref} unexpected footprint pads {extra-allowed}')
  for p in pads:
   if not p[1]:continue
   footprints.append(dict(board=board,reference=ref,pad=p[1],x=one(p,'at')[1],y=one(p,'at')[2],width=one(p,'size')[1],height=one(p,'size')[2],net=actual.get((ref,p[1]),'unconnected mechanical/thermal'),footprint=fp))
 # Check all exported endpoints have an expected entry, not just our expected subset.
 for (ref,pin) in actual:
  if ref not in SPECS[board] or not pin.isdigit() or int(pin)>len(SPECS[board][ref][1]):
   findings.append(f'UNREVIEWED endpoint {board} {ref}.{pin}')

# Actual OptHead PCB pad-net assignments (this is not a copper-continuity/DRC check).
pcb=REPO/'BalancerREF_OptHead/BalancerREF_OptHead.kicad_pcb'
hashes[str(pcb.relative_to(REPO))]=hashlib.sha256(pcb.read_bytes()).hexdigest()
pcbrows=[];seen=set()
for f in children(parse(pcb.read_text(encoding='utf8')),'footprint'):
 props={p[1]:p[2] for p in children(f,'property')};ref=props.get('Reference','')
 for p in children(f,'pad'):
  if (ref,p[1]) not in allnets['head']:continue
  net=one(p,'net');got=normalize(net[-1]) if net else '';want=allnets['head'][(ref,p[1])]
  status='PASS' if got==want else 'FAIL';seen.add((ref,p[1]))
  pcbrows.append(dict(reference=ref,pad=p[1],pcb_net=got,schematic_net=want,result=status))
  if got!=want:findings.append(f'PCB mismatch {ref}.{p[1]} {got} vs {want}')
for key in set(allnets['head'])-seen:findings.append(f'PCB missing {key}')

def writecsv(filename,data):
 with (OUT/filename).open('w',newline='',encoding='utf8') as out:
  writer=csv.DictWriter(out,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
writecsv('pin-by-pin.csv',rows);writecsv('footprint-pads.csv',footprints);writecsv('head-pcb-pad-nets.csv',pcbrows)
(OUT/'input-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf8')
summary={'pins':len(rows),'pass':sum(r['result']=='PASS' for r in rows),'fail':sum(r['result']=='FAIL' for r in rows),'pcb_pad_checks':len(pcbrows),'pcb_fail':sum(r['result']=='FAIL' for r in pcbrows),'findings':findings}
limitations=[]
if allnets['carrier'].get(('U1','10'))=='MAG_TACH':
 limitations.append('MAG_TACH on GPIO33 cannot provide ESP32-S3 EXT1 deep-sleep wake. Normal capture is valid.')
pd=parse((REPO/'BalancerREF_OptHead/BalancerREF_OptHead.kicad_sch').read_text(encoding='utf8'))
for s in children(pd,'symbol'):
 props={p[1]:p[2] for p in children(s,'property')}
 if props.get('Reference')=='PD1' and 'vishay' in props.get('Datasheet','').lower() and 'Osram' in props.get('Footprint',''):
  limitations.append('PD1 links Vishay BPW34/BPW34S through-hole datasheet but assigns OSRAM BPW 34 S SMD footprint; choose exact manufacturer/MPN.')
board_hpp=ROOT/'firmware/src/board.hpp'
firmware=board_hpp.read_text(encoding='utf8')
hashes[str(board_hpp.relative_to(REPO))]=hashlib.sha256(board_hpp.read_bytes()).hexdigest()
assignments={k:int(v) for k,v in re.findall(r'\b(\w+)\s*=\s*(\d+)',firmware)}
wanted={'drdy':18,'mag':1,'opt':35,'emitter':36,'acquire':5,'led':37,'accelSck':12,'accelMosi':11,'accelMiso':14,'accelCs':17,'gpsTx':10,'gpsRx':7,'gpsPps':6}
summary['firmware_pin_mismatches']={k:{'firmware':assignments.get(k),'carrier':v} for k,v in wanted.items() if assignments.get(k)!=v}
if summary['firmware_pin_mismatches']:
 limitations.append('Carrier board.hpp does not match the reviewed carrier GPIO assignments.')
updir=OUT/'sources'
if (updir/'FeatherS3-upstream.kicad_mod').exists() and (updir/'FeatherS3-upstream.kicad_sym').exists():
 def geometry(f):
  return {p[1]:(one(p,'at')[1:3],one(p,'size')[1:],one(p,'drill')[1:] if one(p,'drill') else []) for p in children(f,'pad') if p[1]}
 def pinnames(s):
  return {one(p,'number')[1]:one(p,'name')[1] for unit in children(s,'symbol') for p in children(unit,'pin')}
 local=parse((ROOT/'BalancerCarrier.pretty/FeatherS3.kicad_mod').read_text(encoding='utf8'))
 upstream=parse((updir/'FeatherS3-upstream.kicad_mod').read_text(encoding='utf8'))
 schroot=parse((ROOT/'BalancerCarrier.kicad_sch').read_text(encoding='utf8'))
 embedded=next(s for s in children(one(schroot,'lib_symbols'),'symbol') if s[1]=='BalancerCarrier:FeatherS3')
 upstreamsym=children(parse((updir/'FeatherS3-upstream.kicad_sym').read_text(encoding='utf8')),'symbol')[0]
 summary['feather_upstream_pad_geometry_match']=geometry(local)==geometry(upstream)
 summary['feather_upstream_symbol_pin_names_match']=pinnames(embedded)==pinnames(upstreamsym)
for source in (OUT/'sources').glob('*'):
 if source.suffix in ['.pdf','.jpg','.kicad_mod','.kicad_sym']:
  hashes[str(source.relative_to(REPO))]=hashlib.sha256(source.read_bytes()).hexdigest()
summary['limitations']=limitations
(OUT/'input-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf8')
(OUT/'audit-results.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
print(json.dumps(summary,indent=2))
sys.exit(1 if findings else 0)
