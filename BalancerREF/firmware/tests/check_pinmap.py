"""Check firmware GPIO assignments against the exported Rev C IC pin audit."""
from pathlib import Path
import csv
import re

root = Path(__file__).resolve().parents[2]
header = (root/'firmware/src/board.hpp').read_text()
pins = {k:int(v) for k,v in re.findall(r'\b(\w+)=(\d+)', header)}
expected = {
    'accelSck':'ACCEL_SCK', 'accelMosi':'ACCEL_MOSI', 'accelMiso':'ACCEL_MISO', 'accelCs':'ACCEL_CS', 'drdy':'ACCEL_DRDY',
    'mag':'MAG_TACH', 'opt':'OPT_TACH', 'emitter':'OPT_LED_EN',
    'acquire':'ACQUIRE_BUTTON', 'led':'STATUS_LED', 'supplyAdc':'SUPPLY_SENSE',
    'usbDm':'USB_D-_MCU', 'usbDp':'USB_D+_MCU',
    'gpsTx':'GPS_UART_TX', 'gpsRx':'GPS_UART_RX', 'gpsPps':'GPS_PPS',
}
rows = list(csv.reader((root/'review/IC-pin-audit.csv').open()))
gpio_nets = {}
for row in rows[1:]:
    ref,pad,function,net,*rest = row
    if ref=='U1' and (match:=re.match(r'GPIO(\d+)', function)):
        gpio_nets[int(match[1])] = (pad,net)
for name,signal in expected.items():
    pad,net = gpio_nets[pins[name]]
    if name.startswith('usb'):
        # Series resistors create unnamed MCU-side nets using the module USB pin name.
        assert ('USB_D-' if name=='usbDm' else 'USB_D+') in net, (name,pad,net)
    else:
        assert net.lstrip('/')==signal, (name,pad,net)
print(f'PASS: {len(expected)} GPIO assignments match the KiCad Rev C physical-pad audit.')
