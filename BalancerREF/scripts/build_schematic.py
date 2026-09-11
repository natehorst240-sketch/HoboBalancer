"""Generate BalancerREF with real local wiring; KiCad 9 is the parser/ERC authority."""
import sys as _sys
if '--overwrite-hand-layout' not in _sys.argv:
    raise SystemExit('BalancerREF.kicad_sch has been hand-laid-out in KiCad since 2026-09-09 (Rev C, A2 sheet). '
                     'This generator would replace that layout. Re-run with --overwrite-hand-layout only on purpose.')

from sexp_helpers import *
import math, collections
ROOT=Path(__file__).resolve().parents[1]
sheetid='817ec478-f84e-4d27-b6f3-c983c8ad991a'
used={}; custom={}; instances=[]; pins={}; dirs={}; metadata={}; wires=[]; labels=[]; ncs=[]; art=[]; expected={}; nc_reasons={}
def rnd(v):return round(v,4)
def pt(p):return tuple(rnd(v) for v in p)
def getprop(s,k):return next((a[2] for a in children(s,'property') if a[1]==k),'')
def setprop(s,k,v):
 s[:]=[a for a in s if not(tagged(a,'property') and a[1]==k)];s.append(prop(k,v))
def custom_ic(name,w,h,plist,fp,url):
 s=node('symbol',name,node('pin_names',node('offset',0.8)),node('in_bom',S('yes')),node('on_board',S('yes')),prop('Reference','U'),prop('Value',name),prop('Footprint',fp),prop('Datasheet',url))
 g=node('symbol',name+'_0_1',node('rectangle',node('start',-w,h),node('end',w,-h),node('stroke',node('width',0.254),node('type',S('default'))),node('fill',node('type',S('background')))))
 pp=node('symbol',name+'_1_1')
 for num,nam,typ,x,y,a in plist:
  pp.append(node('pin',S(typ),S('line'),node('at',x,y,a),node('length',5.08),node('name',nam,node('effects',node('font',node('size',1.016,1.016)))),node('number',str(num),node('effects',node('font',node('size',1.016,1.016))))))
 s.extend([g,pp]);custom[name]=s

custom_ic('LIS2DW12TR',12.7,12.7,[
 (9,'VDD','power_in',-2.54,17.78,270),(10,'VDD_IO','power_in',2.54,17.78,270),
 (1,'SCL','input',-17.78,7.62,0),(4,'SDA','bidirectional',-17.78,2.54,0),
 (2,'CS','input',-17.78,-2.54,0),(3,'SA0','input',-17.78,-7.62,0),
 (12,'INT1','output',17.78,7.62,180),(11,'INT2','bidirectional',17.78,2.54,180),(5,'NC','no_connect',17.78,-7.62,180),
 (6,'GND','power_in',-5.08,-17.78,90),(7,'RES_GND','power_in',0,-17.78,90),(8,'GND','power_in',5.08,-17.78,90)],
 'Package_LGA:LGA-12_2x2mm_P0.5mm','https://www.st.com/resource/en/datasheet/lis2dw12.pdf')
# IIS3DWB LGA-14: DS12569 Table 1. Pads 2/3 RES -> GND, 10/11 RES -> unconnected, SPI only.
custom_ic('IIS3DWBTR',12.7,12.7,[
 (8,'VDD','power_in',-2.54,17.78,270),(5,'VDD_IO','power_in',2.54,17.78,270),
 (12,'CS','input',-17.78,7.62,0),(13,'SPC','input',-17.78,2.54,0),(14,'SDI','input',-17.78,-2.54,0),(1,'SDO','output',-17.78,-7.62,0),
 (4,'INT1','output',17.78,7.62,180),(9,'INT2','output',17.78,2.54,180),(10,'RES','no_connect',17.78,-2.54,180),(11,'RES','no_connect',17.78,-7.62,180),
 (6,'GND','power_in',-7.62,-17.78,90),(7,'GND','power_in',-2.54,-17.78,90),(2,'RES_GND','passive',2.54,-17.78,90),(3,'RES_GND','passive',7.62,-17.78,90)],
 'Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y','https://www.st.com/resource/en/datasheet/iis3dwb.pdf')
# SN74LVC1G123 DCT (SSOP-8): SCES586E Table 4-1.
custom_ic('SN74LVC1G123DCTR',10.16,10.16,[
 (3,'~{CLR}','input',-15.24,5.08,0),(2,'B','input',-15.24,0,0),(1,'~{A}','input',-15.24,-5.08,0),
 (5,'Q','output',15.24,5.08,180),(7,'RCext','passive',15.24,-2.54,180),(6,'Cext','passive',15.24,-7.62,180),
 (8,'VCC','power_in',0,15.24,270),(4,'GND','power_in',0,-15.24,90)],
 'Package_SO:SSOP-8_2.95x2.8mm_P0.65mm','https://www.ti.com/lit/ds/symlink/sn74lvc1g123.pdf')
custom_ic('LM1815MX_NOPB',15.24,17.78,[
 (8,'VCC','power_in',0,22.86,270),(2,'GND','power_in',0,-22.86,90),
 (3,'VR_IN','input',-20.32,10.16,0),(5,'MODE','input',-20.32,5.08,0),
 (9,'TIMING_IN','input',-20.32,0,0),(11,'INPUT_SEL','input',-20.32,-5.08,0),
 (1,'NC','no_connect',-20.32,-10.16,0),(4,'NC','no_connect',-20.32,-12.7,0),(6,'NC','no_connect',-20.32,-15.24,0),
 (12,'PULSE_OC','open_collector',20.32,10.16,180),(14,'RC_TIMING','passive',20.32,2.54,180),
 (7,'PEAK_DET','passive',20.32,-7.62,180),(10,'GATED_OUT','output',20.32,-12.7,180),(13,'NC','no_connect',20.32,-15.24,180)],
 'Package_SO:SOIC-14_3.9x8.7mm_P1.27mm','https://www.ti.com/lit/ds/symlink/lm1815.pdf')
# ST TS3021 has the conventional 1=OUT, 2=V-, 3=IN+, 4=IN-, 5=V+ mapping.
s=standard('Comparator','MCP6561-OT'); rename(s,'TS3021IYLT')
for sub in children(s,'symbol'):
 for pin in children(sub,'pin'):
  # MCP6561 SOT-23 symbol uses the same verified pin mapping.
  pass
setprop(s,'Value','TS3021IYLT');setprop(s,'Datasheet','https://www.st.com/resource/en/datasheet/ts3021.pdf');setprop(s,'Footprint','Package_TO_SOT_SMD:SOT-23-5');custom['TS3021IYLT']=s

def place(ref,lib,x,y,angle=0,value=None,fp=None,field=None,mpn=None,unit=1):
 if isinstance(lib,str):sym=deepcopy(custom[lib]);libid='BalancerREF:'+lib
 else:sym=standard(*lib);libid=':'.join(lib)
 used[libid]=deepcopy(sym)
 inst=node('symbol',node('lib_id',libid),node('at',x,y,angle),node('unit',unit),node('in_bom',S('no' if ref.startswith('#') else 'yes')),node('on_board',S('no' if ref.startswith('#') else 'yes')),node('dnp',S('no')),node('uuid',uid()))
 t=math.radians(angle);c=math.cos(t);s=math.sin(t)
 ys=[]
 def unit_of(name):
  parts=name.rsplit('_',2);return int(parts[1]) if len(parts)==3 and parts[1].isdigit() else 0
 mine=[sub for sub in children(sym,'symbol') if unit_of(sub[1]) in (0,unit)]
 for sub in children(sym,'symbol'):
  for pin in children(sub,'pin'):
   at=one(pin,'at');num=one(pin,'number')[1]
   if sub in mine:
    pos=pt((x+c*at[1]-s*at[2],y-s*at[1]-c*at[2]));pins[ref,num]=pos
    a=math.radians(at[3]+angle);dirs[ref,num]=pt((-math.cos(a),math.sin(a)));ys.append(pos[1])
   inst.append(node('pin',num,node('uuid',uid())))
 for k,v in [('Reference',ref),('Value',value if value is not None else getprop(sym,'Value')),('Footprint',fp if fp is not None else getprop(sym,'Footprint')),('Datasheet',getprop(sym,'Datasheet')),('MPN',mpn or value or getprop(sym,'Value'))]:
  ispass=ref.startswith(('R','C','L')) and not ref.startswith('LED')
  if field:fx,fy=field
  elif ispass and angle==0:fx,fy=x+3.81,y-1.27
  else:fx,fy=x,min(ys or [y])-5.08
  p=prop(k,v,fx,fy+(2.54 if k=='Value' else 0),k not in ('Reference','Value') or ref.startswith('#'))
  if ispass and angle==0 and not field and k in ('Reference','Value'):one(p,'effects').append(node('justify',S('left')))
  if angle in [90,270]:one(p,'at')[3]=90
  inst.append(p)
 inst.append(node('instances',node('project','BalancerREF',node('path','/'+sheetid,node('reference',ref),node('unit',unit)))))
 instances.append(inst);metadata[ref]={'lib_id':libid,'value':value or getprop(sym,'Value'),'footprint':fp or getprop(sym,'Footprint')};return ref
def p(r,n):return pins[r,str(n)]
def wire(*points):
 for a,b in zip(points,points[1:]):
  a,b=pt(a),pt(b)
  if a==b:continue
  assert a[0]==b[0] or a[1]==b[1],(a,b)
  wires.append((a,b))
def route(r,n,*points):wire(p(r,n),*points)
def label(net,x,y,angle=0):labels.append(node('label',net,node('at',x,y,angle),node('effects',node('font',node('size',1.27,1.27)),node('justify',S('left'),S('bottom'))),node('uuid',uid())))
def port(r,n,net,length=10.16):
 a=p(r,n);d=dirs[r,str(n)];b=pt((a[0]+d[0]*length,a[1]+d[1]*length));wire(a,b);label(net,*b,0 if d[0]>=0 else 180);return b
def nc(r,n,why):
 ncs.append(node('no_connect',node('at',*p(r,n)),node('uuid',uid())));nc_reasons[r+'.'+str(n)]=why
def mark(r,m):
 for n,v in m.items():expected[r,str(n)]=v
def text(t,x,y,size=1.5):art.append(node('text',t,node('at',x,y,0),node('effects',node('font',node('size',size,size)),node('justify',S('left'),S('top'))),node('uuid',uid())))
def box(title,x,y,w,h):
 art.append(node('rectangle',node('start',x,y),node('end',x+w,y+h),node('stroke',node('width',0.254),node('type',S('default'))),node('fill',node('type',S('none'))),node('uuid',uid())))
 text(title,x+3.81,y+3.81,2.1)
counts=collections.Counter()
def rc(kind,val,x,y,a=0,ref=None,fp=None):
 counts[kind]+=1;ref=ref or kind+str(counts[kind]);place(ref,('Device',kind),x,y,a,val,fp or ('Resistor_SMD:R_0603_1608Metric' if kind=='R' else 'Capacitor_SMD:C_0805_2012Metric'));return ref
def R(val,x,y,a=0,ref=None):return rc('R',val,x,y,270 if a==90 else a,ref)
def C(val,x,y,a=0):return rc('C',val,x,y,a)
gcount=0
def gnd(x,y):
 global gcount;gcount+=1;place('#PWR'+str(gcount).zfill(3),('power','GND'),x,y)
def rail(net,x,y):label(net,x,y)
def caprail(val,x,y,top,bottom):
 c=C(val,x,y);route(c,1,(x,top));route(c,2,(x,bottom));return c
def tp(ref,name,x,y,attach=None):
 place(ref,('Connector','TestPoint'),x,y,value=name,fp='TestPoint:TestPoint_Pad_D1.0mm',field=(x,y-6.35))
 if attach:wire(p(ref,1),attach)
def flag(ref,x,y):place(ref,('power','PWR_FLAG'),x,y)

box('POWER / USB - CHARGES WITH SW1 ON OR OFF',10.16,17.78,246.38,111.76)
box('3.3 V BUCK-BOOST',264.16,17.78,160.02,111.76)
box('REFERENCE ONLY / PROFILE NOTES',431.8,17.78,147.32,111.76)
box('MCU / BLE - ESP32-S3',182.88,137.16,241.3,121.92)
box('ACCELEROMETER - IIS3DWB (SPI)',10.16,266.7,172.72,114.3)
box('MAIN ROTOR MAG TACH',187.96,266.7,193.04,114.3)
box('TAIL ROTOR OPTICAL TACH - PULSED EMITTER + RECEIVER',386.08,266.7,193.04,114.3)
box('OPTICAL TACH - SYNCHRONOUS DETECTION + PULSE STRETCH',187.96,396.24,391.16,83.82)
box('USER INPUTS / STATUS',10.16,137.16,165.1,121.92)
text('BalancerREF - rotor vibration reference puck',12.7,7.62,3)
text('Single sheet | Rev C | KiCad 10 | schematic review before PCB',345.44,9,1.7)

# USB-C connector, CC terminations, clamp and power feed: all physically wired.
place('J1',('Connector','USB_C_Receptacle_USB2.0_16P'),30.48,66.04,value='USB4105-GF-A',fp='Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal')
route('J1','A4',(50.8,50.8),(50.8,35.56),(167.64,35.56));rail('USB_VBUS',50.8,35.56)
route('J1','A1',(30.48,119.38));route('J1','SH',(22.86,119.38),(30.48,119.38));gnd(30.48,119.38)
rcc1=R('5.1k 1%',60.96,53.34,90);rcc2=R('5.1k 1%',73.66,58.42,90)
route('J1','A5',(53.34,55.88),(53.34,53.34),p(rcc1,2));route(rcc1,1,(88.9,53.34),(88.9,60.96))
route('J1','B5',(55.88,58.42),p(rcc2,2));route(rcc2,1,(88.9,58.42));gnd(88.9,60.96)
nc('J1','A8','SBU unused in USB 2.0 device');nc('J1','B8','SBU unused in USB 2.0 device')
# Pair each reversible contact before ESD; routes above ESD are continuous data traces.
route('J1','A7',(53.34,63.5),(53.34,71.12),(132.08,71.12));route('J1','B7',(53.34,66.04))
route('J1','A6',(50.8,68.58),(50.8,76.2),(132.08,76.2));route('J1','B6',(50.8,71.12))
label('USB_CONN_D-',132.08,71.12);label('USB_CONN_D+',132.08,76.2)
place('U7',('Power_Protection','SRV05-4'),88.9,99.06,value='SRV05-4MR6T1G',fp='Package_TO_SOT_SMD:SOT-23-6',field=(88.9,81.28))
route('U7',1,(66.04,96.52),(66.04,71.12));route('U7',3,(60.96,101.6),(60.96,76.2))
route('U7',5,(116.84,86.36),(116.84,35.56));route('U7',2,(88.9,119.38));gnd(88.9,119.38)
nc('U7',4,'Unused ESD channel');nc('U7',6,'Unused ESD channel')
cu=caprail('100n / 10V',124.46,99.06,86.36,119.38);wire((116.84,86.36),(124.46,86.36));gnd(124.46,119.38)
tp('TP4','TP_USB_VBUS',99.06,30.48,(99.06,35.56));flag('#FLG01',106.68,35.56);flag('#FLG02',30.48,119.38)
# VBUS clamp: 5 V standoff TVS at the connector, before anything else sees the rail.
place('D3',('Diode','SMF5V0A'),132.08,45.72,90,'SMF5.0A',fp='Diode_SMD:D_SMF',field=(135.89,44.45),mpn='SMF5.0A')
route('D3',2,(132.08,35.56));route('D3',1,(132.08,53.34));gnd(132.08,53.34)
text('Shield bonded to common GND at connector. D3: 5 V TVS on VBUS.\nESD return short to connector ground.\nUSB data series resistors are beside U1.',38.1,120.65,1.1)

# Charger and protected battery: STAT is genuinely unused (MCP73831 drives high).
place('U5',('Battery_Management','MCP73831-2-OT'),167.64,66.04,value='MCP73831T-2ACI/OT',field=(167.64,48.26))
route('U5',4,(167.64,35.56));route('U5',2,(167.64,106.68));gnd(167.64,106.68)
cin=caprail('10u / 10V X7R',144.78,53.34,35.56,106.68);gnd(144.78,106.68)
rp=R('4.02k 1%',152.4,83.82);route('U5',5,(152.4,68.58),p(rp,1));route(rp,2,(152.4,106.68));wire((144.78,106.68),(167.64,106.68))
route('U5',3,(223.52,63.5));rail('BAT',193.04,63.5);nc('U5',1,'Optional STAT omitted; MCP73831 tri-state output can rise to VDD')
cb=caprail('10u / 10V X7R',190.5,83.82,63.5,106.68);gnd(190.5,106.68)
place('J2',('Connector_Generic','Conn_01x02'),213.36,86.36,180,'LiPo 500mAh PROTECTED','Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical',field=(220.98,91.44),mpn='JST B2B-PH-K-S')
# Q4: reverse-battery protection. Body diode BAT->load at first contact, then channel; a reversed pack sees a blocked diode.
place('Q4',('Transistor_FET','AO3401A'),226.06,74.93,180,'AO3401A',field=(236.22,67.31))
route('J2',1,(223.52,86.36),p('Q4',3));route('Q4',2,(223.52,63.5))
route('Q4',1,(238.76,74.93),(238.76,106.68));route('J2',2,(231.14,83.82),(231.14,106.68));wire((231.14,106.68),(238.76,106.68));gnd(231.14,106.68)
tp('TP3','TP_BAT',203.2,55.88,(203.2,63.5))
text('Icharge = 1000 / 4020 = 249 mA nominal. Q4 blocks a reversed pack.\n4.2 V cell; use protected pack (no PCB cell protection).\nCharging independent of SW1; see power sharing.\nUSB programming: switch ON; battery optional.',139.7,111.76,1.2)

# Fixed TPS63031. Supply only reaches VIN/VINA/EN/PS, never an L pin.
place('U6',('Regulator_Switching','TPS63031DSK'),340.36,68.58,value='TPS63031DSKR',field=(340.36,44.45))
wire((279.4,53.34),(325.12,53.34),(325.12,66.04))
rail('SYS_SW',279.4,53.34);flag('#FLG04',281.94,53.34)
for n in [5,8,6,7]:route('U6',n,(325.12,p('U6',n)[1]))
c6=caprail('10u / 10V X7R',284.48,76.2,53.34,104.14)
c7=caprail('100n / 10V',304.8,76.2,53.34,104.14)
place('L1',('Device','L'),317.5,73.66,value='1.5uH',fp='',field=(316.23,86.36),mpn='DFE201612PD-1R5M=P2')
route('U6',4,(317.5,68.58),p('L1',1));route('U6',2,(317.5,78.74),p('L1',2))
route('U6',1,(406.4,58.42));rail('+3V3',393.7,58.42)
route('U6',10,(363.22,66.04),(363.22,58.42))
for x in [375.92,398.78]:caprail('22u / 10V X7R',x,81.28,58.42,104.14)
for n in [9,3,11]:route('U6',n,(p('U6',n)[0],104.14))
wire((284.48,104.14),(406.4,104.14));gnd(340.36,104.14)
tp('TP1','TP_3V3',406.4,53.34,(406.4,58.42));tp('TP2','TP_GND',414.02,99.06,(414.02,104.14));wire((406.4,104.14),(414.02,104.14))
text('PS/SYNC high = forced PWM. FB wired to VOUT.\nPad 11 = exposed thermal pad; bond to PGND/GND.\nCout: retain >=20uF effective total at 3.3 V bias.\nL1 MPN: Murata DFE201612PD-1R5M=P2.',271.78,111.76,1.2)

# MCU: standard symbol retains all 65 physical pads, including all 24 ground pads.
place('U1',('RF_Module','ESP32-S3-MINI-1'),294.64,195.58,value='ESP32-S3-MINI-1-N8',field=(294.64,151.13))
route('U1',3,(294.64,160.02),(337.82,160.02));rail('+3V3',322.58,160.02)
for x,val in [(322.58,'10u / 10V X7R'),(340.36,'100n / 10V')]:
 caprail(val,x,172.72,160.02,185.42)
wire((337.82,160.02),(340.36,160.02));wire((322.58,185.42),(340.36,185.42));gnd(340.36,185.42)
route('U1',1,(294.64,233.68));gnd(294.64,233.68)
# EN RC and boot pulldown capability inside the MCU block.
ren=R('10k',223.52,160.02);route(ren,1,(223.52,152.4));rail('+3V3',223.52,152.4)
route(ren,2,(223.52,170.18),p('U1',45));cen=C('1u / 10V',223.52,182.88);route(cen,1,(223.52,170.18));route(cen,2,(223.52,195.58));gnd(223.52,195.58)
place('SW4',('Switch','SW_Push'),203.2,182.88,90,'RESET',field=(200.66,168.91));route('SW4',2,(203.2,170.18),(223.52,170.18));route('SW4',1,(203.2,195.58),(223.52,195.58))
rb=R('10k',254,160.02);route(rb,1,(254,152.4));rail('+3V3',254,152.4)
route(rb,2,(254,175.26),p('U1',4));port('U1',4,'BOOT',0) if False else None
label('BOOT',254,175.26)
tp('TP13','TP_EN',233.68,165.1,(233.68,170.18));tp('TP14','TP_BOOT',266.7,165.1,(266.7,175.26))
# Native USB series termination visibly between MCU and USB block boundary.
for n,y,net,tpref in [(23,177.8,'USB_CONN_D-','TP12'),(24,180.34,'USB_CONN_D+','TP11')]:
 # Fan out to separate rows so test points and values have room.
 yy=200.66 if n==23 else 218.44
 route('U1',n,(350.52 if n==23 else 345.44,y),(350.52 if n==23 else 345.44,yy),(358.14,yy))
 rr=R('22R',368.3,yy,90);wire((358.14,yy),p(rr,2));route(rr,1,(401.32,yy));label(net,401.32,yy)
 tp(tpref,'TP_USB_D-' if n==23 else 'TP_USB_D+',388.62,yy-5.08,(388.62,yy))
# GPIO allocations deliberately avoid strapping pins and internal flash signals.
gpio={10:'ACCEL_DRDY',11:'MAG_TACH',12:'OPT_TACH',13:'OPT_LED_EN',14:'ACQUIRE_BUTTON',15:'STATUS_LED',16:'SUPPLY_SENSE',18:'ACCEL_SCK',19:'ACCEL_MOSI',20:'ACCEL_MISO',21:'ACCEL_CS'}
for pin,net in gpio.items():
 a=p('U1',pin);wire(a,(241.3,a[1]));label(net,241.3,a[1])
usedpins={3,45,4,23,24,*gpio.keys(),1,2,42,43,*range(46,66)}
for (ref,n) in list(pins):
 if ref=='U1' and int(n) not in usedpins:nc(ref,n,'Unused GPIO; retain default strap states on GPIO3/45/46')
text('GPIO14 SCK | GPIO15 MOSI | GPIO16 MISO | GPIO17 CS | GPIO6 DRDY\nGPIO7 MAG capture | GPIO8 OPT capture\nGPIO9 emitter 20 kHz PWM | GPIO10 acquire | GPIO11 status\nGPIO12 supply ADC | GPIO19/20 native USB | GPIO1/2 GPS UART1\nMAG/OPT: GPIO matrix to MCPWM capture. Sleep wake: EXT1 on GPIO7/GPIO10.',302.26,238.76,1.15)
text('All module GND pads: 1, 2, 42, 43, 46-65.\nNo circuitry in future antenna keepout.',187.96,248.92,1.15)

# User block: individual conventional button circuits and a controllable status LED.
for ref,net,x,title in [('SW2','ACQUIRE_BUTTON',40.64,'ACQUIRE'),('SW3','BOOT',91.44,'BOOT / SERVICE')]:
 rr=R('10k',x,170.18);route(rr,1,(x,160.02));rail('+3V3',x,160.02)
 place(ref,('Switch','SW_Push'),x,195.58,90,title,field=(x+8.89,194.31));route(ref,2,(x,182.88),p(rr,2));route(ref,1,(x,208.28));gnd(x,208.28)
 wire((x,182.88),(x+20.32,182.88));label(net,x+20.32,182.88)
 if ref=='SW2':
  cc=C('10n',60.96,195.58);route(cc,1,(60.96,182.88));route(cc,2,(60.96,208.28),(40.64,208.28))
rs=R('1k',139.7,170.18);route(rs,1,(139.7,160.02));label('STATUS_LED',139.7,160.02)
place('LED1',('Device','LED'),139.7,190.5,90,'STATUS GREEN',fp='LED_SMD:LED_0603_1608Metric',field=(150,189.23));route(rs,2,p('LED1',2));route('LED1',1,(139.7,208.28));gnd(139.7,208.28)
# Switched supply divider: cannot back-power the MCU when SW1 is OFF.
rh=R('100k',35.56,233.68);rl=R('100k',68.58,241.3)
route(rh,1,(35.56,223.52));rail('SYS_SW',35.56,223.52)
route(rh,2,(35.56,236.22),(68.58,236.22),p(rl,1));route(rl,2,(68.58,251.46));gnd(68.58,251.46)
wire((68.58,236.22),(91.44,236.22));label('SUPPLY_SENSE',91.44,236.22)
ca=C('100n',81.28,243.84);route(ca,1,(81.28,236.22));route(ca,2,(81.28,251.46),(68.58,251.46))
text('Active-low buttons; debounce in firmware.\nBOOT held low during reset enters download.\nSupply ADC: SYS_SW / 2 with 100n at the pin; dead when OFF.\nOne green status LED; patterns set by firmware.',101.6,220.98,1.2)

# Accelerometer: IIS3DWB on 4-wire SPI. RES pads 2/3 to GND, 10/11 unconnected, INT1 = data-ready.
place('U2','IIS3DWBTR',99.06,325.12,field=(99.06,302.26),mpn='IIS3DWBTR')
wire((25.4,292.1),(172.72,292.1));rail('+3V3',25.4,292.1)
for n in [8,5]:route('U2',n,(p('U2',n)[0],292.1))
for x,val in [(134.62,'100n / VDD'),(154.94,'100n / VDDIO')]:caprail(val,x,304.8,292.1,312.42)
wire((134.62,312.42),(154.94,312.42));gnd(154.94,312.42)
caprail('10u',172.72,335.28,292.1,350.52);gnd(172.72,350.52)
for n,net in [(12,'ACCEL_CS'),(13,'ACCEL_SCK'),(14,'ACCEL_MOSI'),(1,'ACCEL_MISO')]:
 a=p('U2',n);wire(a,(20.32,a[1]));label(net,20.32,a[1],180)
for n in [6,7,2,3]:route('U2',n,(p('U2',n)[0],350.52))
wire((91.44,350.52),(106.68,350.52));gnd(99.06,350.52)
route('U2',4,(151.13,317.5));label('ACCEL_DRDY',151.13,317.5)
tp('TP10','TP_ACCEL_DRDY',124.46,312.42,(124.46,317.5))
nc('U2',9,'INT2 unused');nc('U2',10,'Reserved pad: leave unconnected per ST DS12569');nc('U2',11,'Reserved pad: leave unconnected per ST DS12569')
text('SPI mode 3, CS active low; no pull-ups needed. 26.7 kHz ODR, 16-bit,\nflat to 6.3 kHz: filter phase at rotor frequencies is negligible.\nINT1 data-ready timestamps on GPIO6. RES 2/3 = GND; RES 10/11 open.\nNo wake-on-motion: sleep wakes on MAG_TACH or the button (EXT1).\nPlace near rigid mount; vertical axis set by orientation.',17.78,358.14,1.2)

# Magnetic pickup, protected by pulse-rated series resistance and internal LM1815 clamps.
place('J3',('Connector_Generic','Conn_01x02'),203.2,320.04,180,'MAG+ / MAG- PTH',fp='',field=(215.9,300.99))
ri1=R('10k 1206 pulse',226.06,320.04,90);ri2=R('10k 1206 pulse',246.38,320.04,90)
for r in [ri1,ri2]:
 for inst in instances:
  if getprop(inst,'Reference')==r:
   next(z for z in children(inst,'property') if z[1]=='Footprint')[2]='Resistor_SMD:R_1206_3216Metric'
route('J3',1,p(ri1,2));wire(p(ri1,1),p(ri2,2))
route('J3',2,(213.36,317.5),(213.36,358.14),(281.94,358.14));gnd(281.94,358.14)
tp('TP5','TP_MAG+',218.44,314.96,(218.44,320.04));tp('TP6','TP_MAG-',208.28,347.98,(213.36,347.98))
place('U3','LM1815MX_NOPB',284.48,330.2,value='LM1815MX/NOPB',field=(284.48,307.34))
wire(p(ri2,1),p('U3',3));route('U3',2,(284.48,358.14),(281.94,358.14))
wire((226.06,292.1),(365.76,292.1));rail('+3V3',226.06,292.1);route('U3',8,(284.48,292.1))
for x,val in [(231.14,'100n'),(256.54,'10u / 10V')]:
 caprail(val,x,299.72,292.1,309.88)
wire((231.14,309.88),(256.54,309.88));gnd(231.14,309.88)
for n in [9,11]:route('U3',n,(259.08,p('U3',n)[1]))
wire((259.08,330.2),(259.08,358.14),(281.94,358.14))
nc('U3',5,'Intentional open selects adaptive Mode 1 per TI; not a missing bias')
for n in [1,4,6,13]:nc('U3',n,'No internal connection per TI')
nc('U3',10,'Unused gated output; using open-collector reference pulse on pin 12')
ro=R('5.6k',365.76,307.34);route(ro,1,(365.76,292.1));route(ro,2,(365.76,320.04))
route('U3',12,(365.76,320.04));label('MAG_TACH',365.76,320.04)
tp('TP7','TP_MAG_TACH',353.06,314.96,(353.06,320.04))
rt=R('150k 1%',325.12,307.34);route(rt,1,(325.12,292.1));route(rt,2,(325.12,327.66),p('U3',14))
ct=C('1n C0G',325.12,340.36);route(ct,1,(325.12,327.66));route(ct,2,(325.12,358.14));gnd(325.12,358.14)
cp=C('330n',345.44,347.98);rp=R('1.6M',368.3,347.98)
route('U3',7,(345.44,337.82),(368.3,337.82),p(rp,1));route(cp,1,(345.44,337.82))
for r in [cp,rp]:route(r,2,(p(r,2)[0],358.14))
wire((345.44,358.14),(368.3,358.14));gnd(345.44,358.14)
text('MAG- is common GND; isolated 2-wire VR pickup only.\n20k total limits input to <=3mA at +/-60V peak.\nUse two pulse-rated resistors; TI internal input clamp.\nMode 1; RC ~101us; timestamp leading FALLING edge.\nPolarity / phase offset set in profile. External twisted pair.',195.58,363.22,1.18)

# Pulsed red emitter from the switched battery rail: 20 kHz, 5 us, ~500 mA peak through Q1.
rail('SYS_SW',396.24,292.1);wire((396.24,292.1),(426.72,292.1))
re=R('3R0 1206 0.5W',406.4,302.26);route(re,1,(406.4,292.1))
for inst in instances:
 if getprop(inst,'Reference')==re:next(z for z in children(inst,'property') if z[1]=='Footprint')[2]='Resistor_SMD:R_1206_3216Metric'
cbk=C('100u / 6.3V',426.72,302.26);route(cbk,1,(426.72,292.1));route(cbk,2,(426.72,309.88));gnd(426.72,309.88)
for inst in instances:
 if getprop(inst,'Reference')==cbk:next(z for z in children(inst,'property') if z[1]=='Footprint')[2]='Capacitor_SMD:C_1210_3225Metric'
place('D1',('Device','LED'),406.4,317.5,90,'XPEBRD-L1 625nm',fp='LED_SMD:LED_Cree-XP',field=(414.02,312.42),mpn='XPEBRD-L1-0000-00501');route(re,2,p('D1',2))
place('Q1',('Transistor_FET','AO3400A'),403.86,337.82,value='AO3400A',field=(414.02,332.74));route('D1',1,p('Q1',3));route('Q1',2,(406.4,363.22));gnd(406.4,363.22)
rg=R('100R',398.78,353.06,90);route(rg,1,(421.64,353.06),(421.64,347.98),(393.7,347.98),(393.7,337.82),p('Q1',1));route(rg,2,(391.16,353.06));label('OPT_LED_EN',391.16,353.06,180)
rpd=R('100k',421.64,358.14);route(rpd,1,(421.64,347.98));route(rpd,2,(421.64,363.22),(406.4,363.22))
# Receiver: BPW34S reverse-biased into a 10k transimpedance stage referenced to 1.65 V, then x12 inverting AC gain.
wire((434.34,292.1),(571.5,292.1));rail('+3V3',434.34,292.1)
place('PD1',('Sensor_Optical','BPW34'),441.96,320.04,270,'BPW34S',fp='OptoDevice:Osram_BPW34S-SMD',field=(444.5,325.12),mpn='BPW34S')
route('PD1',1,(441.96,292.1));route('PD1',2,(472.44,322.58))
place('U8',('Amplifier_Operational','TLV9062xD'),480.06,320.04,value='TLV9062IDR',fp='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',field=(477.52,330.2),mpn='TLV9062IDR',unit=1)
wire((472.44,317.5),(459.74,317.5));label('OPT_VREF',459.74,317.5)
rf=R('10k',480.06,299.72,90);wire(p('U8',2),(467.36,322.58),(467.36,299.72),p(rf,2));wire(p(rf,1),(492.76,299.72),(492.76,320.04),p('U8',1))
cfb=C('10p C0G',480.06,307.34,90);wire((467.36,307.34),p(cfb,1));wire(p(cfb,2),(492.76,307.34))
# Inverting gain stage: baseline sits at VREF, received pulses swing down toward 0.45 V.
wire((492.76,320.04),(492.76,340.36),(499.11,340.36))
cac=C('10n',502.92,340.36,90);rg1=R('10k',510.54,340.36,90)
wire(p(rg1,1),(516.89,340.36),(516.89,335.28))
place('U8',('Amplifier_Operational','TLV9062xD'),525.78,332.74,value='TLV9062IDR',fp='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',field=(531.11,325.12),mpn='TLV9062IDR',unit=2)
wire((516.89,335.28),p('U8',6));wire(p('U8',5),(505.46,330.2));label('OPT_VREF',505.46,330.2)
rg2=R('120k',527.05,347.98,90);route('U8',7,(538.48,332.74),(538.48,347.98),p(rg2,1));wire(p(rg2,2),(516.89,347.98),(516.89,340.36))
wire((538.48,332.74),(543.56,332.74));label('OPT_AMP',543.56,332.74)
# 1.65 V reference and op amp supply.
rb1=R('10k',548.64,302.26);rb2=R('10k',548.64,317.5)
route(rb1,1,(548.64,292.1));route(rb1,2,(548.64,309.88),p(rb2,1));route(rb2,2,(548.64,325.12));gnd(548.64,325.12)
wire((548.64,309.88),(541.02,309.88));caprail('100n',541.02,317.5,309.88,325.12);gnd(541.02,325.12);label('OPT_VREF',548.64,309.88)
place('U8',('Amplifier_Operational','TLV9062xD'),563.88,330.2,value='TLV9062IDR',fp='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',field=(569.0,326.39),mpn='TLV9062IDR',unit=3)
route('U8',8,(563.88,292.1));route('U8',4,(563.88,363.22));gnd(563.88,363.22)
cv=caprail('100n',571.5,304.8,292.1,312.42);gnd(571.5,312.42)
text('D1 + PD1 face LEFT edge behind a red acrylic window; internal baffle between them.\nD1: 5 us / 20 kHz pulses ~500 mA from SYS_SW (bulk cap local). Visible aiming spot.\nTIA 10k, VREF 1.65 V, x12 inverting; OPT_AMP goes to the detection row below.\nRetroreflective tape on the blade; 18-24 in working range with the Ledil TINA lens.',393.7,368.3,1.12)

# Detection row: comparator -> AND with the emitter pulse (synchronous) -> retriggerable monostable.
wire((198.12,406.4),(414.02,406.4));rail('+3V3',198.12,406.4)
place('U4','TS3021IYLT',254,431.8,field=(255.27,414.02))
wire((238.76,434.34),p('U4',4));label('OPT_AMP',238.76,434.34,180)
rth1=R('22k',233.68,416.56);rth2=R('10k',223.52,429.26,90)
route(rth1,1,(233.68,406.4));route(rth1,2,(233.68,429.26),p('U4',3));wire(p(rth2,1),(233.68,429.26));route(rth2,2,(219.71,444.5));gnd(219.71,444.5)
rhys=R('470k',256.54,452.12,90);route('U4',1,(266.7,431.8));wire((266.7,431.8),(266.7,452.12),p(rhys,1));wire(p(rhys,2),(236.22,452.12),(236.22,429.26))
route('U4',5,(251.46,406.4));route('U4',2,(251.46,444.5));gnd(251.46,444.5)
caprail('100n',274.32,416.56,406.4,424.18);gnd(274.32,424.18)
place('U9',('74xGxx','74LVC1G08'),299.72,431.8,value='SN74LVC1G08DBVR',fp='Package_TO_SOT_SMD:SOT-23-5',field=(299.72,411.48),mpn='SN74LVC1G08DBVR')
wire((266.7,431.8),(276.86,431.8),(276.86,429.26),p('U9',1))
rdly=R('1k',218.44,457.2,90);wire((203.2,457.2),p(rdly,2));label('OPT_LED_EN',203.2,457.2)
cdly=C('470p C0G',228.6,464.82);route(rdly,1,(228.6,457.2),p(cdly,1));route(cdly,2,(228.6,472.44));gnd(228.6,472.44)
wire((228.6,457.2),(279.4,457.2),(279.4,434.34),p('U9',2))
route('U9',5,(299.72,406.4));route('U9',3,(299.72,444.5));gnd(299.72,444.5)
caprail('100n',312.42,416.56,406.4,424.18);gnd(312.42,424.18)
place('U10','SN74LVC1G123DCTR',355.6,431.8,field=(355.6,412.75),mpn='SN74LVC1G123DCTR')
route('U9',4,p('U10',2))
route('U10',3,(330.2,426.72),(330.2,414.02),(355.6,414.02));route('U10',8,(355.6,406.4))
route('U10',1,(335.28,436.88),(335.28,447.04));gnd(335.28,447.04)
route('U10',4,(355.6,449.58));gnd(355.6,449.58)
rext=R('100k',381.0,421.64);route(rext,1,(381.0,414.02),(355.6,414.02));route(rext,2,(381.0,434.34));route('U10',7,(381.0,434.34))
cext=C('1n C0G',388.62,436.88);wire((381.0,434.34),(388.62,434.34),p(cext,1));route('U10',6,(388.62,439.42),p(cext,2))
route('U10',5,(398.78,426.72));label('OPT_TACH',398.78,426.72)
tp('TP9','TP_OPT_TACH',396.24,419.1,(396.24,426.72))
caprail('100n',414.02,416.56,406.4,424.18);gnd(414.02,424.18)
text('U4: IN- = OPT_AMP, IN+ = 1.03 V threshold, 470k hysteresis; output HIGH while a received 5 us pulse pulls the amp below threshold.\nU9: hit accepted only during the emitter pulse (0.5 us RC-delayed copy of OPT_LED_EN) = synchronous detection; ambient never coincides.\nU10: retriggerable, ~100 us (100k / 1 nF). First hit sets OPT_TACH; it clears 100 us after the last hit: one clean edge per tape pass.\nThreshold and delay are bench-set values; firmware captures the RISING edge on GPIO8.',403.86,441.96,1.15)

text('MR-VERT: external magnetic pickup; optical LED OFF.\nTR-VERT: onboard pulsed-red synchronous optical tach.\nBoth use internal XYZ MEMS and BLE to phone.\n\nReport approximate RPM, 1/rev magnitude, phase,\nquality/stability and run-to-run trends.\n\nREFERENCE / TROUBLESHOOTING ONLY.\nMaintenance balancing remains with calibrated\nMicroVib / DynaVibe equipment.',439.42,35.56,1.75)
text('Mechanical intent only: future PCB ~50 x 40 mm.\nNo PCB generated. Keep antenna area clear.\nRigid mount near MEMS; red acrylic optical window on LEFT.\nValidate phase delay and tach SNR on bench before use.',439.42,99.06,1.45)
text('Test points are drawn at the circuit they measure. One common GND system. NC marks only identify documented unused pins.\nBattery/USB flags denote external sources; SYS_SW flag denotes power through SW1. No flags on missing IC connections.',12.7,487.68,1.5)


# Microchip AN1149 directional power sharing: PMOS D=BAT, S=SYS.
box('USB / BATTERY POWER SHARING',431.8,137.16,147.32,121.92)
place('D2',('Device','D_Schottky'),515.62,170.18,180,'PMEG4010CEH','Diode_SMD:D_SOD-123F',field=(515.62,158.75))
wire((444.5,160.02),(487.68,160.02),(487.68,170.18),p('D2',2));label('USB_VBUS',444.5,160.02)
route('D2',1,(556.26,170.18),(556.26,200.66))
place('Q3',('Transistor_FET','AO3401A'),515.62,203.2,90,'AO3401A',field=(515.62,186.69))
wire((444.5,200.66),p('Q3',3));label('BAT',444.5,200.66)
route('Q3',2,(556.26,200.66));label('SYS',556.26,200.66)
route('Q3',1,(487.68,208.28),(487.68,160.02))
rgq=R('1k',487.68,226.06)
route(rgq,1,(487.68,208.28));route(rgq,2,(487.68,241.3));gnd(487.68,241.3)
csys=C('10u 10V',538.48,226.06)
route(csys,1,(538.48,200.66));route(csys,2,(538.48,241.3));gnd(538.48,241.3)
place('SW1',('Switch','SW_SPST'),556.26,223.52,270,'POWER',field=(568.96,216))
route('SW1',1,(556.26,200.66));route('SW1',2,(556.26,236.22),(563.88,236.22));label('SYS_SW',563.88,236.22)
text('USB supplies puck + charger; battery takes over without USB.\nSW1 switches puck only. Q3: drain=BAT, source=SYS.',439.42,248.92,1.25)

# Final typography: compact values and keep boundary labels inside their circuit boxes.
for inst in instances:
 ref=getprop(inst,'Reference')
 for pr in children(inst,'property'):
  if pr[1]=='Value' and ref.startswith('C'):
   pr[2]=pr[2].replace(' / 10V X7R',' 10V').replace(' / 10V',' 10V')
   if pr[2]=='100n 10V':pr[2]='100n'
  if ref=='J1' and pr[1] in ['Reference','Value']:one(pr,'at')[2]-=5.08
  if ref=='TP13' and pr[1] in ['Reference','Value']:one(pr,'at')[1]+=5.08
  if ref=='U7' and pr[1]=='Datasheet':pr[2]='https://www.onsemi.com/pdf/datasheet/srv05-4-d.pdf'
for lab in labels:
 name=lab[1];at=one(lab,'at')
 if name=='MAG_TACH' and at[1]>300:at[1]=360.68
 if name=='OPT_TACH' and at[1]>500:at[1]=558.8
 if name=='ACCEL_DRDY' and at[1]<180:at[1]=151.13
 if name=='OPT_LED_EN' and at[1]>380:
  wire((at[1],at[2]),(at[1],358.14));at[2]=358.14
text('C1-C21: ceramic, X7R unless C0G noted; >=10V rating. Select effective capacitance at bias.\nJ3 = J_MAG: two plated wire holes only, 1 MAG+, 2 MAG-. No aircraft-specific board connector.',12.7,398.78,1.3)

# Split every wire at endpoints/pins so tee connections are explicit and KiCad has real junctions.
points=set(pins.values())|{q for seg in wires for q in seg}
def on(q,a,b):return (a[0]==b[0]==q[0] and min(a[1],b[1])<=q[1]<=max(a[1],b[1])) or (a[1]==b[1]==q[1] and min(a[0],b[0])<=q[0]<=max(a[0],b[0]))
segments=set()
for a,b in wires:
 split=sorted([q for q in points if on(q,a,b)])
 for q,r in zip(split,split[1:]):segments.add(tuple(sorted((q,r))))
degree=collections.Counter(q for seg in segments for q in seg)
wire_nodes=[node('wire',node('pts',node('xy',*a),node('xy',*b)),node('stroke',node('width',0),node('type',S('default'))),node('uuid',uid())) for a,b in sorted(segments)]
junc=[node('junction',node('at',*q),node('diameter',0),node('color',0,0,0,0),node('uuid',uid())) for q,d in degree.items() if d>=3]
embedded=[]
for libid,sym in used.items():
 ss=deepcopy(sym);ss[1]=libid;embedded.append(ss)
sch=node('kicad_sch',node('version',20250114),node('generator','eeschema'),node('uuid',sheetid),node('paper','A1'),node('title_block',node('title','BalancerREF - REFERENCE ONLY rotor vibration puck'),node('date','2026-09-09'),node('rev','C'),node('company','Human review required before PCB'),node('comment',1,'Approximate trends only; maintenance balancing uses calibrated equipment')),node('lib_symbols',*embedded),*junc,*ncs,*wire_nodes,*labels,*art,*instances,node('embedded_fonts',S('no')))
(ROOT/'BalancerREF.kicad_sch').write_text(dump(sch)+'\n',encoding='utf8')
(ROOT/'BalancerREF.kicad_sym').write_text(dump(node('kicad_symbol_lib',node('version',20241209),node('generator','kicad_symbol_editor'),*custom.values()))+'\n',encoding='utf8')
(ROOT/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "BalancerREF")(type "KiCad")(uri "${KIPRJMOD}/BalancerREF.kicad_sym")(options "")(descr "Verified local symbols")))\n')
(ROOT/'review'/'unused-pins.json').write_text(json.dumps(nc_reasons,indent=2))
(ROOT/'review'/'component-manifest.json').write_text(json.dumps(metadata,indent=2))
print(f'Wrote {len(instances)} symbols, {len(segments)} wires, {len(junc)} junctions, {len(ncs)} intentional NCs')


