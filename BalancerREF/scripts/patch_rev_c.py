"""Turn build_schematic.py (Rev B) into the Rev C generator.

Rev C: IIS3DWB on SPI, pulsed-red synchronous-detection optical tach replacing the IR pair,
reverse-battery PMOS, VBUS TVS, ADC filter cap, A1 sheet with a detection-logic row.
Run once; the Rev B generator is kept as build_schematic_revb.py.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
src = ROOT / 'build_schematic.py'
keep = ROOT / 'build_schematic_revb.py'
s = src.read_text(encoding='utf8')
if not keep.exists():
    keep.write_text(s, encoding='utf8')


def rep(a, b, count=1):
    global s
    assert s.count(a) == count, (s.count(a), a[:90])
    s = s.replace(a, b)


# ---------------------------------------------------------------- place(): multi-unit support
rep("def place(ref,lib,x,y,angle=0,value=None,fp=None,field=None,mpn=None):",
    "def place(ref,lib,x,y,angle=0,value=None,fp=None,field=None,mpn=None,unit=1):")
rep(" inst=node('symbol',node('lib_id',libid),node('at',x,y,angle),node('unit',1),",
    " inst=node('symbol',node('lib_id',libid),node('at',x,y,angle),node('unit',unit),")
rep(""" ys=[]
 for sub in children(sym,'symbol'):
  for pin in children(sub,'pin'):
   at=one(pin,'at');num=one(pin,'number')[1];pos=pt((x+c*at[1]-s*at[2],y-s*at[1]-c*at[2]));pins[ref,num]=pos
   a=math.radians(at[3]+angle);dirs[ref,num]=pt((-math.cos(a),math.sin(a)));ys.append(pos[1]);inst.append(node('pin',num,node('uuid',uid())))""",
    """ ys=[]
 mine=[sub for sub in children(sym,'symbol') if sub[1].endswith(('_0_1',f'_{unit}_1'))]
 for sub in children(sym,'symbol'):
  for pin in children(sub,'pin'):
   at=one(pin,'at');num=one(pin,'number')[1]
   if sub in mine:
    pos=pt((x+c*at[1]-s*at[2],y-s*at[1]-c*at[2]));pins[ref,num]=pos
    a=math.radians(at[3]+angle);dirs[ref,num]=pt((-math.cos(a),math.sin(a)));ys.append(pos[1])
   inst.append(node('pin',num,node('uuid',uid())))""")
rep(" inst.append(node('instances',node('project','BalancerREF',node('path','/'+sheetid,node('reference',ref),node('unit',1)))))",
    " inst.append(node('instances',node('project','BalancerREF',node('path','/'+sheetid,node('reference',ref),node('unit',unit)))))")

# ---------------------------------------------------------------- new local symbols
rep("""custom_ic('LM1815MX_NOPB',15.24,17.78,[""",
    """# IIS3DWB LGA-14: DS12569 Table 1. Pads 2/3 RES -> GND, 10/11 RES -> unconnected, SPI only.
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
custom_ic('LM1815MX_NOPB',15.24,17.78,[""")

# ---------------------------------------------------------------- sheet, boxes, headers
rep("box('ACCELEROMETER - INTERNAL XYZ',10.16,266.7,172.72,114.3)", "box('ACCELEROMETER - IIS3DWB (SPI)',10.16,266.7,172.72,114.3)")
rep("box('TAIL ROTOR OPTICAL TACH',386.08,266.7,193.04,114.3)",
    "box('TAIL ROTOR OPTICAL TACH - PULSED EMITTER + RECEIVER',386.08,266.7,193.04,114.3)\nbox('OPTICAL TACH - SYNCHRONOUS DETECTION + PULSE STRETCH',187.96,396.24,391.16,83.82)")
rep("text('Single sheet | Rev B | KiCad 9 | schematic review before PCB',345.44,9,1.7)",
    "text('Single sheet | Rev C | KiCad 10 | schematic review before PCB',345.44,9,1.7)")
rep("node('paper','A2')", "node('paper','A1')")
rep("node('date','2026-09-07'),node('rev','B')", "node('date','2026-09-09'),node('rev','C')")
rep("(descr \"Verified symbols missing from KiCad 9\")", "(descr \"Verified local symbols\")")
rep("text('Test points are drawn at the circuit they measure. One common GND system. NC marks only identify documented unused pins.\\nBattery/USB flags denote external sources; SYS_SW flag denotes power through SW1. No flags on missing IC connections.',12.7,388.62,1.5)",
    "text('Test points are drawn at the circuit they measure. One common GND system. NC marks only identify documented unused pins.\\nBattery/USB flags denote external sources; SYS_SW flag denotes power through SW1. No flags on missing IC connections.',12.7,487.68,1.5)")

# ---------------------------------------------------------------- USB: VBUS TVS
rep("tp('TP4','TP_USB_VBUS',99.06,30.48,(99.06,35.56));flag('#FLG01',106.68,35.56);flag('#FLG02',30.48,119.38)",
    """tp('TP4','TP_USB_VBUS',99.06,30.48,(99.06,35.56));flag('#FLG01',106.68,35.56);flag('#FLG02',30.48,119.38)
# VBUS clamp: 5 V standoff TVS at the connector, before anything else sees the rail.
place('D3',('Diode','SMF5V0A'),132.08,45.72,90,'SMF5.0A',fp='Diode_SMD:D_SMF',field=(135.89,44.45),mpn='SMF5.0A')
route('D3',2,(132.08,35.56));route('D3',1,(132.08,53.34));gnd(132.08,53.34)""")
rep("text('Shield bonded to common GND at connector.\\nESD return short to connector ground.\\nUSB data series resistors are beside U1.',38.1,120.65,1.1)",
    "text('Shield bonded to common GND at connector. D3: 5 V TVS on VBUS.\\nESD return short to connector ground.\\nUSB data series resistors are beside U1.',38.1,120.65,1.1)")

# ---------------------------------------------------------------- battery: reverse-polarity PMOS
rep("route('J2',1,(223.52,86.36),(223.52,63.5));route('J2',2,(231.14,83.82),(231.14,106.68));gnd(231.14,106.68)",
    """# Q4: reverse-battery protection. Body diode BAT->load at first contact, then channel; a reversed pack sees a blocked diode.
place('Q4',('Transistor_FET','AO3401A'),226.06,74.93,180,'AO3401A',field=(236.22,67.31))
route('J2',1,(223.52,86.36),p('Q4',3));route('Q4',2,(223.52,63.5))
route('Q4',1,(238.76,74.93),(238.76,106.68));route('J2',2,(231.14,83.82),(231.14,106.68));wire((231.14,106.68),(238.76,106.68));gnd(231.14,106.68)""")
rep("text('Icharge = 1000 / 4020 = 249 mA nominal\\n4.2 V cell; use protected pack (no PCB cell protection).\\nCharging independent of SW1; see power sharing.\\nUSB programming: switch ON; battery optional.',139.7,111.76,1.2)",
    "text('Icharge = 1000 / 4020 = 249 mA nominal. Q4 blocks a reversed pack.\\n4.2 V cell; use protected pack (no PCB cell protection).\\nCharging independent of SW1; see power sharing.\\nUSB programming: switch ON; battery optional.',139.7,111.76,1.2)")

# ---------------------------------------------------------------- user block: ADC filter
rep("wire((68.58,236.22),(91.44,236.22));label('SUPPLY_SENSE',91.44,236.22)",
    "wire((68.58,236.22),(91.44,236.22));label('SUPPLY_SENSE',91.44,236.22)\nca=C('100n',81.28,243.84);route(ca,1,(81.28,236.22));route(ca,2,(81.28,251.46),(68.58,251.46))")
rep("Supply ADC: SYS_SW / 2; dead when OFF.\\nOne green status LED",
    "Supply ADC: SYS_SW / 2 with 100n at the pin; dead when OFF.\\nOne green status LED")

# ---------------------------------------------------------------- MCU GPIO map
rep("gpio={8:'ACCEL_SDA',9:'ACCEL_SCL',10:'ACCEL_DRDY',11:'MAG_TACH',12:'OPT_TACH',13:'OPT_LED_EN',14:'ACQUIRE_BUTTON',15:'STATUS_LED',16:'SUPPLY_SENSE'}",
    "gpio={10:'ACCEL_DRDY',11:'MAG_TACH',12:'OPT_TACH',13:'OPT_LED_EN',14:'ACQUIRE_BUTTON',15:'STATUS_LED',16:'SUPPLY_SENSE',18:'ACCEL_SCK',19:'ACCEL_MOSI',20:'ACCEL_MISO',21:'ACCEL_CS'}")
rep("text('GPIO4 SDA | GPIO5 SCL | GPIO6 DRDY\\nGPIO7 MAG capture | GPIO8 OPT capture\\nGPIO9 emitter | GPIO10 acquire | GPIO11 status\\nGPIO12 supply ADC | GPIO19/20 native USB\\nMAG/OPT: GPIO matrix to MCPWM capture or RMT.',302.26,238.76,1.15)",
    "text('GPIO14 SCK | GPIO15 MOSI | GPIO16 MISO | GPIO17 CS | GPIO6 DRDY\\nGPIO7 MAG capture | GPIO8 OPT capture\\nGPIO9 emitter 20 kHz PWM | GPIO10 acquire | GPIO11 status\\nGPIO12 supply ADC | GPIO19/20 native USB | GPIO1/2 GPS UART1\\nMAG/OPT: GPIO matrix to MCPWM capture. Sleep wake: EXT1 on GPIO7/GPIO10.',302.26,238.76,1.15)")

# ---------------------------------------------------------------- accelerometer block
start = s.index("# Accelerometer: physical pull-ups and explicit supply/CS/SA0/GND/RES wiring.")
end = s.index("# Magnetic pickup, protected by pulse-rated series resistance and internal LM1815 clamps.")
accel = """# Accelerometer: IIS3DWB on 4-wire SPI. RES pads 2/3 to GND, 10/11 unconnected, INT1 = data-ready.
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
text('SPI mode 3, CS active low; no pull-ups needed. 26.7 kHz ODR, 16-bit,\\nflat to 6.3 kHz: filter phase at rotor frequencies is negligible.\\nINT1 data-ready timestamps on GPIO6. RES 2/3 = GND; RES 10/11 open.\\nNo wake-on-motion: sleep wakes on MAG_TACH or the button (EXT1).\\nPlace near rigid mount; vertical axis set by orientation.',17.78,358.14,1.2)

"""
s = s[:start] + accel + s[end:]
rep("""# ST application figure 6 also calls for local bulk capacitance at VDD.
caprail('10u',172.72,335.28,292.1,350.52)
wire((154.94,292.1),(172.72,292.1));gnd(172.72,350.52)
""", "")

# ---------------------------------------------------------------- optical tach: emitter + receiver + logic row
start = s.index("# IR emitter on +3V3, MOSFET low-side switch with hardware default OFF.")
end = s.index("text('MR-VERT: external magnetic pickup; optical LED OFF.")
optical = """# Pulsed red emitter from the switched battery rail: 20 kHz, 5 us, ~500 mA peak through Q1.
rail('SYS_SW',396.24,292.1);wire((396.24,292.1),(416.56,292.1))
re=R('3R0 1206 0.5W',406.4,302.26);route(re,1,(406.4,292.1))
for inst in instances:
 if getprop(inst,'Reference')==re:next(z for z in children(inst,'property') if z[1]=='Footprint')[2]='Resistor_SMD:R_1206_3216Metric'
cbk=C('100u / 6.3V',416.56,302.26);route(cbk,1,(416.56,292.1));route(cbk,2,(416.56,309.88));gnd(416.56,309.88)
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
rf=R('10k',480.06,299.72,90);wire(p('U8',2),(467.36,322.58),(467.36,299.72),p(rf,1));wire(p(rf,2),(492.76,299.72),(492.76,320.04),p('U8',1))
cfb=C('10p C0G',480.06,307.34,90);wire((467.36,307.34),p(cfb,1));wire(p(cfb,2),(492.76,307.34))
# Inverting gain stage: baseline sits at VREF, received pulses swing down toward 0.45 V.
wire((492.76,320.04),(492.76,340.36),(499.11,340.36))
cac=C('10n',502.92,340.36,90);rg1=R('10k',510.54,340.36,90)
wire(p(rg1,2),(516.89,340.36),(516.89,335.28))
place('U8',('Amplifier_Operational','TLV9062xD'),525.78,332.74,value='TLV9062IDR',fp='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',field=(523.24,342.9),mpn='TLV9062IDR',unit=2)
wire((516.89,335.28),p('U8',6));wire(p('U8',5),(505.46,330.2));label('OPT_VREF',505.46,330.2)
rg2=R('120k',527.05,347.98,90);route('U8',7,(538.48,332.74),(538.48,347.98),p(rg2,2));wire(p(rg2,1),(516.89,347.98),(516.89,340.36))
wire((538.48,332.74),(543.56,332.74));label('OPT_AMP',543.56,332.74)
# 1.65 V reference and op amp supply.
rb1=R('10k',548.64,302.26);rb2=R('10k',548.64,317.5)
route(rb1,1,(548.64,292.1));route(rb1,2,(548.64,309.88),p(rb2,1));route(rb2,2,(548.64,325.12));gnd(548.64,325.12)
wire((548.64,309.88),(541.02,309.88));caprail('100n',541.02,317.5,309.88,325.12);gnd(541.02,325.12);label('OPT_VREF',548.64,309.88)
place('U8',('Amplifier_Operational','TLV9062xD'),563.88,330.2,value='TLV9062IDR',fp='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',field=(569.0,326.39),mpn='TLV9062IDR',unit=3)
route('U8',8,(563.88,292.1));route('U8',4,(563.88,363.22));gnd(563.88,363.22)
cv=caprail('100n',571.5,304.8,292.1,312.42);gnd(571.5,312.42)
text('D1 + PD1 face LEFT edge behind a red acrylic window; internal baffle between them.\\nD1: 5 us / 20 kHz pulses ~500 mA from SYS_SW (bulk cap local). Visible aiming spot.\\nTIA 10k, VREF 1.65 V, x12 inverting; OPT_AMP goes to the detection row below.\\nRetroreflective tape on the blade; 18-24 in working range with the Ledil TINA lens.',393.7,368.3,1.12)

# Detection row: comparator -> AND with the emitter pulse (synchronous) -> retriggerable monostable.
wire((198.12,406.4),(568.96,406.4));rail('+3V3',198.12,406.4)
place('U4','TS3021IYLT',254,431.8,field=(255.27,414.02))
wire((238.76,434.34),p('U4',4));label('OPT_AMP',238.76,434.34,180)
rth1=R('22k',233.68,416.56);rth2=R('10k',223.52,429.26,90)
route(rth1,1,(233.68,406.4));route(rth1,2,(233.68,429.26),p('U4',3));wire(p(rth2,2),(233.68,429.26));route(rth2,1,(219.71,429.26),(219.71,444.5));gnd(219.71,444.5)
rhys=R('470k',256.54,452.12,90);route('U4',1,(266.7,431.8));wire((266.7,431.8),(266.7,452.12),p(rhys,2));wire(p(rhys,1),(236.22,452.12),(236.22,429.26))
route('U4',5,(251.46,406.4));route('U4',2,(251.46,444.5));gnd(251.46,444.5)
caprail('100n',274.32,416.56,406.4,424.18);gnd(274.32,424.18)
place('U9',('74xGxx','74LVC1G08'),299.72,431.8,value='SN74LVC1G08DBVR',fp='Package_TO_SOT_SMD:SOT-23-5',field=(299.72,411.48),mpn='SN74LVC1G08DBVR')
wire((266.7,431.8),(276.86,431.8),(276.86,429.26),p('U9',1))
rdly=R('1k',218.44,457.2,90);wire((203.2,457.2),p(rdly,1));label('OPT_LED_EN',203.2,457.2)
cdly=C('470p C0G',228.6,464.82);route(rdly,2,(228.6,457.2),p(cdly,1));route(cdly,2,(228.6,472.44));gnd(228.6,472.44)
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
tp('TP9','TP_OPT_TACH',393.7,421.64,(393.7,426.72))
caprail('100n',365.76,416.56,406.4,424.18);gnd(365.76,424.18)
text('U4: IN- = OPT_AMP, IN+ = 1.03 V threshold, 470k hysteresis; output HIGH while a received 5 us pulse pulls the amp below threshold.\\nU9: hit accepted only during the emitter pulse (0.5 us RC-delayed copy of OPT_LED_EN) = synchronous detection; ambient never coincides.\\nU10: retriggerable, ~100 us (100k / 1 nF). First hit sets OPT_TACH; it clears 100 us after the last hit: one clean edge per tape pass.\\nThreshold and delay are bench-set values; firmware captures the RISING edge on GPIO8.',403.86,412.75,1.15)

"""
s = s[:start] + optical + s[end:]

# ---------------------------------------------------------------- notes text
rep("TR-VERT: onboard reflective optical tach; LED ON.", "TR-VERT: onboard pulsed-red synchronous optical tach.")
rep("Rigid mount near MEMS; baffled optical window on LEFT.", "Rigid mount near MEMS; red acrylic optical window on LEFT.")
src.write_text(s, encoding='utf8')
print('build_schematic.py is now the Rev C generator; Rev B kept as build_schematic_revb.py')
