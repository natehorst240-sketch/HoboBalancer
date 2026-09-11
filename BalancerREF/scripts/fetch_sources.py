from pathlib import Path
import requests, fitz, concurrent.futures, json
out=Path(__file__).resolve().parents[1]/'sources'
urls={
'ESP32-S3-MINI-1':'https://documentation.espressif.com/esp32-s3-mini-1_mini-1u_datasheet_en.pdf',
'LIS2DW12':'https://www.st.com.cn/resource/en/datasheet/lis2dw12.pdf',
'LM1815':'https://www.ti.com/lit/ds/symlink/lm1815.pdf',
'TS3021':'https://www.st.com.cn/resource/en/datasheet/ts3021.pdf',
'TPS63031':'https://www.ti.com/lit/ds/symlink/tps63031.pdf',
'MCP73831':'https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP73831-Family-Data-Sheet-DS20001984H.pdf',
'AO3400A':'https://www.aosmd.com/sites/default/files/res/datasheets/AO3400A.pdf',
'USB4105':'https://gct.co/files/drawings/usb4105.pdf',
'LTR-4206E':'https://optoelectronics.liteon.com/upload/download/DS-50-92-0073/LTR-4206E%20Data%20Sheet%20%20Rev.D.PDF',
'LTE-4208':'https://optoelectronics.liteon.com/upload/download/DS-50-92-0015/LTE-4208%20Data%20Sheet%20Ver%20D.PDF',
'SRV05-4-onsemi':'https://www.onsemi.com/pdf/datasheet/srv05-4-d.pdf',
}
def fetch(kv):
 k,u=kv
 try:
  p=out/(k+'.pdf')
  if not p.exists():
   r=requests.get(u,timeout=20);r.raise_for_status()
   if not r.content.startswith(b'%PDF-'):raise ValueError('Server returned a non-PDF response')
   p.write_bytes(r.content)
  d=fitz.open(p);(out/(k+'.txt')).write_text('\n'.join(f'\n=== PAGE {i+1} ===\n'+p.get_text() for i,p in enumerate(d)),encoding='utf-8')
  return k,len(d)
 except Exception as e:return k,str(e)
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
 for result in ex.map(fetch,urls.items()):print(result)
(out/'urls.json').write_text(json.dumps(urls,indent=2))
