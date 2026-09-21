"""Package a successfully built firmware without touching connected hardware."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

root = Path(__file__).resolve().parents[1]
build = root/'.pio/build/balancerref'
release = root/'release'
release.mkdir(exist_ok=True)
images = {'bootloader.bin':0, 'partitions.bin':0x8000, 'firmware.bin':0x10000}
manifest = {'target':'ESP32-S3-MINI-1-N8', 'schematic':'BalancerREF Rev B',
            'firmware':'0.4.0-reference', 'flash_size':'8MB', 'flash_mode':'dio',
            'reference_only':True, 'hardware_tested':False, 'images':[]}
manifest['source_sha256'] = {
    str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
    for folder in ['src','vendor'] for p in sorted((root/folder).rglob('*')) if p.is_file()
}
for name, address in images.items():
    source = build/name
    if not source.exists():
        raise SystemExit(f'Missing build artifact: {source}; complete the ESP32 build first')
    shutil.copy2(source, release/name)
    manifest['images'].append({'file':name, 'offset':hex(address), 'bytes':source.stat().st_size,
                               'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
for name in ['firmware.elf','firmware.map']:
    if (build/name).exists():
        shutil.copy2(build/name,release/name)
for name in ['sdkconfig.balancerref','sdkconfig']:
    if (root/name).exists():
        shutil.copy2(root/name,release/'sdkconfig-built.txt')
        break
(release/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(release/'FLASH.txt').write_text('''BalancerREF Rev B / ESP32-S3-MINI-1-N8 / reference firmware 0.4.0
Switch ON. First flash: hold BOOT, tap RESET, release BOOT.
Replace COM5 with the confirmed puck USB port. From this release folder:

python -m esptool --chip esp32s3 --port COM5 --baud 460800 write_flash --flash_mode dio --flash_size 8MB 0x0 bootloader.bin 0x8000 partitions.bin 0x10000 firmware.bin

Use the PlatformIO-provided esptool 4.x, or the documented PlatformIO upload command.
Press RESET after upload if needed. Individual writes preserve the NVS region.
Do not erase flash unless intentionally resetting all saved profile settings.
No physical hardware test or calibrated IPS accuracy is claimed.
See ../README.md for protocol, controls, settings and bench acceptance checks.
''')
zip_path = root.parent/'BalancerREF-Firmware-0.4.0.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as archive:
    for p in root.rglob('*'):
        rel=p.relative_to(root)
        if not p.is_file() or any(x in {'.pio','build','__pycache__'} for x in rel.parts):
            continue
        if len(rel.parts)==1 and p.name.startswith('sdkconfig') and p.name!='sdkconfig.defaults':
            continue
        archive.write(p,Path('firmware')/rel)
print(f'Packaged {zip_path}')
