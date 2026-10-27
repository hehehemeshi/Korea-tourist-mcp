"""Verified anonymous Seoul public-site requests; source timestamps govern GPS display."""
import asyncio
import copy
import re
import time
from collections import OrderedDict
from datetime import datetime
from urllib.parse import urlencode
import httpx
from . import service as s,public_buses as common
BASE='https://bus.go.kr'
OPS={'search':'selectVApiTotalstr.do','detail':'selectRouteInfo.do','map':'selectBusposInfo.do'}
_cache=OrderedDict();_gate=asyncio.Semaphore(3)
NOTICE='Seoul: chấm xanh là tọa độ GPS nguồn cung cấp, chỉ hiển thị khi thời điểm đo còn trong 120 giây. Bản ghi cũ/thiếu thời điểm không hiển thị như xe trực tiếp. Không nội suy chuyển động.'

async def read(kind,params):
 key=(kind,tuple(sorted(params.items())));cached=_cache.get(key);ttl=15 if kind=='map' else 300
 if cached and time.monotonic()-cached[0]<ttl:
  result=copy.deepcopy(cached[1]);result['cached']=True;return result
 async with _gate:
  for attempt in range(2):
   try:
    async with httpx.AsyncClient(timeout=18,follow_redirects=False,headers={'User-Agent':'KoreaTouristMCP/0.5.2 (+https://github.com/hehehemeshi/Korea-tourist-mcp)'}) as client:
     response=await client.get(BASE+'/sbus/bus/'+OPS[kind],params=params);response.raise_for_status()
     if len(response.content)>3_000_000:raise ValueError()
     payload=response.json()
    if not isinstance(payload,dict):raise ValueError()
    break
   except (httpx.TimeoutException,httpx.ConnectError):
    if attempt==0:await asyncio.sleep(.4);continue
    raise s.Unavailable('Nguồn Seoul tạm mất kết nối hoặc quá thời gian.') from None
   except httpx.HTTPStatusError as exc:
    if exc.response.status_code>=500 and attempt==0:await asyncio.sleep(.4);continue
    raise s.Unavailable('Nguồn Seoul chưa trả dữ liệu hợp lệ; không thay bằng dữ liệu vùng khác.') from None
   except (httpx.HTTPError,ValueError):raise s.Unavailable('Cấu trúc hoặc kết nối nguồn Seoul chưa hợp lệ.') from None
 result=dict(payload=payload,source_url=BASE+'/sbus/bus/'+OPS[kind]+'?'+urlencode(params),fetched_at=s.now().isoformat(),cached=False)
 _cache[key]=(time.monotonic(),copy.deepcopy(result));_cache.move_to_end(key)
 while len(_cache)>64:_cache.popitem(last=False)
 return result


def data(payload):
 try:
  root=payload['ResponseVO']
  if str(root['code'])!='0' or not isinstance(root['data'],dict):raise ValueError()
  return root['data'],root.get('timestamp')
 except (KeyError,TypeError,ValueError):raise s.Unavailable('Seoul báo lỗi hoặc đã thay đổi schema; không coi là danh sách rỗng thành công.') from None


def records(payload,field):
 result,_=data(payload)
 if field not in result:raise s.Unavailable('Nguồn Seoul thiếu trường dữ liệu đã xác minh.')
 rows=result[field]
 if not isinstance(rows,list) or len(rows)>20000 or any(not isinstance(row,dict) for row in rows):raise s.Unavailable('Danh sách Seoul không hợp lệ.')
 return rows


async def search(query):
 result=await read('search',{'strkey':query.strip(),'strdiv':'1','pageIndex':1,'recordCountPerPage':100})
 selected=[]
 for row in records(result['payload'],'resultList'):
  if str(row.get('strdiv'))!='1' or row.get('strid') is None:continue
  ends=str(row.get('strkey') or '').split(' - ',1)
  selected.append(dict(route_id=str(row['strid']),number=str(row.get('strno') or row.get('strnm') or ''),region='서울',origin=ends[0] or None,destination=ends[1] if len(ends)==2 else None))
 exact=[row for row in selected if row['number'].casefold()==query.strip().casefold()]
 if exact:selected=exact
 return dict(status='ok' if selected else 'no_data',data=selected[:20],truncated=len(selected)>20,provider='Seoul public bus web',source_url=result['source_url'],fetched_at=result['fetched_at'],cached=result['cached'])


def xy(row):return common.point({'x':row.get('gpsX'),'y':row.get('gpsY')})


def observed(value,clock):
 try:
  if not isinstance(value,str) or not re.fullmatch(r'\d{14}',value):raise ValueError()
  stamp=datetime.strptime(value,'%Y%m%d%H%M%S').replace(tzinfo=s.KST);age=(clock-stamp).total_seconds()
  return stamp.isoformat(),'fresh' if -30<=age<=120 else 'stale' if age>120 else 'future'
 except (ValueError,TypeError):return None,'unknown'


def assemble(route_id,parts,clock=None):
 clock=clock or s.now();features=[];stops=[];vehicles=[];warnings=[];meta={};route=dict(route_id=route_id,number=None,region='서울',origin=None,destination=None)
 for kind,result in parts.items():
  target=('detail',) if kind=='detail' else ('stops','shape','vehicles')
  if isinstance(result,Exception):
   for field in target:meta[field]={'status':'unavailable','message':str(result)}
   warnings.append(f'Nguồn Seoul {kind} chưa đọc được.');continue
  for field in target:meta[field]={k:result[k] for k in ('source_url','fetched_at','cached')}
  try:
   payload=result['payload'];_,querytime=data(payload)
   for field in target:meta[field]['provider_response_time']=querytime
   if kind=='detail':
    rows=records(payload,'resultList')
    if not rows or str(rows[0].get('rtid'))!=route_id:raise s.Unavailable('Thông tin tuyến không khớp mã nguồn Seoul.')
    row=rows[0];route=dict(route_id=route_id,number=str(row.get('rtnm') or ''),region='서울',origin=row.get('sstnnm'),destination=row.get('estnnm'));meta['detail']['status']='ok'
   else:
    for row in records(payload,'resultRouteStop'):
     if str(row.get('busRouteId'))!=route_id:continue
     seq=common.integer(row.get('seq'))
     if seq is None or row.get('station') is None:continue
     stop=dict(station_id=str(row['station']),sequence=seq,name=row.get('stationName'),coordinates=xy(row),turnaround=None,direction=row.get('direction'))
     stops.append(stop)
     if stop['coordinates']:features.append(dict(type='Feature',geometry=dict(type='Point',coordinates=stop['coordinates']),properties=dict(kind='stop',sequence=seq,name=stop['name'])))
    stops.sort(key=lambda row:row['sequence']);meta['stops']['status']='ok' if stops else 'no_data'
    try:
     path=records(payload,'resultRoutePath');indexes=[common.integer(row.get('no')) for row in path]
     if any(i is None for i in indexes) or len(set(indexes))!=len(indexes):raise ValueError()
     coords=[xy(row) for row in sorted(path,key=lambda row:common.integer(row['no']))]
     if any(p is None for p in coords) or (coords and len(coords)<2):raise ValueError()
     if coords:features.insert(0,dict(type='Feature',geometry=dict(type='LineString',coordinates=coords),properties=dict(kind='provider_route_shape')))
     meta['shape']['status']='ok' if coords else 'no_data'
    except (ValueError,s.Unavailable):meta['shape']['status']='unavailable';warnings.append('Hình học Seoul chưa hợp lệ; không nối các bến thay đường tuyến.')
    stop_index={}
    for stop in stops:stop_index.setdefault((stop['station_id'],stop['sequence']),[]).append(stop)
    for row in records(payload,'resultRouteBuspos'):
     if str(row.get('rtId'))!=route_id:continue
     coords=xy(row);timestamp,freshness=observed(row.get('dataTm'),clock);seq=common.integer(row.get('lastStnOrd'));sid=str(row.get('lastStnId') or '')
     matches=stop_index.get((sid,seq),[])
     vehicle=dict(vehicle_id=str(row.get('vehId') or '') or None,plate=row.get('plainNo'),station_id=sid or None,station_sequence=seq,
      referenced_stop=matches[0] if len(matches)==1 else None,gps_coordinates=coords,vehicle_observed_at=timestamp,position_kind='provider_gps',freshness=freshness,
      direction=row.get('adirection') or None,state='unknown',operating_flag=row.get('isrunyn'))
     vehicles.append(vehicle)
     if coords and freshness=='fresh':features.append(dict(type='Feature',geometry=dict(type='Point',coordinates=coords),properties=dict(kind='vehicle_gps',name=vehicle['plate'],vehicle_id=vehicle['vehicle_id'],direction=vehicle['direction'],observed_at=timestamp)))
    meta['vehicles']['status']='ok' if vehicles else 'no_data'
  except (s.Unavailable,KeyError,TypeError,ValueError):
   for field in target:meta[field].setdefault('status','unavailable')
   warnings.append(f'Dữ liệu Seoul {kind} thiếu hoặc không đúng schema.')
 count=sum(p['status']!='unavailable' for p in meta.values())
 return dict(status='ok' if count==4 else 'partial' if count else 'unavailable',route_id=route_id,route=route,stops=stops,vehicles=vehicles,
  map=dict(type='FeatureCollection',features=features),parts=meta,warnings=warnings,fetched_at=meta.get('vehicles',{}).get('fetched_at') or clock.isoformat(),assembled_at=clock.isoformat(),
  cached=any(p.get('cached') for p in meta.values()),source_url=BASE,provider='Seoul public bus web',position_notice=NOTICE,vehicle_position_kind='provider_gps_when_fresh',note='Hướng đến lấy từ adirection; không suy đoán góc hướng xe. Số sân ga không có dữ liệu.')


async def snapshot(route_id):
 route_id=common.rid(route_id)
 kinds=('detail','map');results=await asyncio.gather(read('detail',{'rtId':route_id}),read('map',{'routeId':route_id,'isLowBus':'0'}),return_exceptions=True)
 for result in results:
  if isinstance(result,BaseException) and not isinstance(result,(s.Unavailable,ValueError)):raise result
 return assemble(route_id,dict(zip(kinds,results)))
