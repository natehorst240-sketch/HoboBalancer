from pathlib import Path
import concurrent.futures, requests, pymupdf as fitz
root=Path(__file__).resolve().parents[1]
urls={
'AN1149':'https://ww1.microchip.com/downloads/en/AppNotes/01149c.pdf',
'AO3401A':'https://www.aosmd.com/sites/default/files/res/datasheets/AO3401A.pdf',
'PMEG4010CEH':'https://assets.nexperia.com/documents/data-sheet/PMEG4010CEH.pdf',
}
def fetch(kv):
 name,url=kv;r=requests.get(url,timeout=20);r.raise_for_status();assert r.content.startswith(b'%PDF-'),name
 p=root/'sources'/(name+'.pdf');p.write_bytes(r.content);d=fitz.open(p)
 p.with_suffix('.txt').write_text('\n'.join(x.get_text() for x in d),encoding='utf8')
 page=4 if name=='AN1149' else 0
 d[page].get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(root/'review'/(name+'-pinout.png'))
 return name,len(d)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
 for r in ex.map(fetch,urls.items()):print(r)
