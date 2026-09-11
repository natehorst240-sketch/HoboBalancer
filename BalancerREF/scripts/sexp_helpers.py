from pathlib import Path
from copy import deepcopy
import sexpdata as sx
import uuid, json, csv

ROOT=Path(__file__).resolve().parent.parent
LIB=Path('C:/Program Files/KiCad/10.0/share/kicad')
S=sx.Symbol
def node(k,*v): return [S(k),*v]
def tagged(x,k): return isinstance(x,list) and x and str(x[0])==k
def children(x,k): return [a for a in x if tagged(a,k)]
def one(x,k): return next((a for a in x if tagged(a,k)),None)
def uid(): return str(uuid.uuid4())
def parse(t): return sx.loads(t)
def dump(x): return sx.dumps(x)
def prop(k,v,x=0,y=0,hide=True):
    e=node('effects',node('font',node('size',1.27,1.27)))
    if hide:e.append(node('hide',S('yes')))
    return node('property',k,v,node('at',x,y,0),e)
cache={}
def standard(lib,name):
    if lib not in cache:
        cache[lib]={a[1]:a for a in sx.loads((LIB/'symbols'/(lib+'.kicad_sym')).read_text(encoding='utf8')) if tagged(a,'symbol')}
    original=deepcopy(cache[lib][name]);base=one(original,'extends')
    if base:
        result=standard(lib,base[1]);parent=result[1];result[1]=name
        overrides={p[1] for p in children(original,'property')}
        result=[a for a in result if not(tagged(a,'property') and a[1] in overrides)]
        result.extend(children(original,'property'))
        for a in children(result,'symbol'):a[1]=name+a[1][len(parent):]
        return result
    return original
def rename(sym,name):
    old=sym[1];sym[1]=name
    for a in children(sym,'symbol'):a[1]=name+a[1][len(old):]
    return sym
def block(name,left,right,width=12.7):
    height=max(len(left),len(right))*2.54+2.54
    out=node('symbol',name,node('pin_names',node('offset',1.016)),node('in_bom',S('yes')),node('on_board',S('yes')),
       prop('Reference','U'),prop('Value',name),prop('Footprint',''),prop('Datasheet',''),
       node('symbol',name+'_0_1',node('rectangle',node('start',-width,height/2),node('end',width,-height/2),node('stroke',node('width',0.254),node('type',S('default'))),node('fill',node('type',S('background'))))))
    pins=node('symbol',name+'_1_1')
    for side,items in [(-1,left),(1,right)]:
        for i,(number,label,typ) in enumerate(items):
            pins.append(node('pin',S(typ),S('line'),node('at',side*(width+5.08),height/2-2.54-i*2.54,0 if side<0 else 180),node('length',5.08),node('name',label,node('effects',node('font',node('size',1.016,1.016)))),node('number',str(number),node('effects',node('font',node('size',1.016,1.016))))))
    out.append(pins);return out
def triples(items,typ='passive'):return [(str(n),v,typ) for n,v in items]


