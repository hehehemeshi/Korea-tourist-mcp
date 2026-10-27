"""Anonymous reads used by the public GBIS web app; no keys/cookies or browser needed.

This is a web-source adapter, not the documented developer OpenAPI. If its schema
changes, fail explicitly. Never animate a stop reference as a GPS vehicle.
"""
import asyncio
import copy
import math
import os
import re
import time
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlencode
import httpx
from . import service as s

BASE='https://m.gbis.go.kr'
UI_URI='ui://korea-tourist/bus-map-v1.html'
SOURCE=BASE+'/search'
OPS={'search':'routeSearch','detail':'routeDetail','stops':'routeStations','vehicles':'busLocationsOfRoute','shape':'busRouteLine'}
_cache=OrderedDict()
_gate=asyncio.Semaphore(4)
NOTICE='Xe được nhà cung cấp tham chiếu theo bến/đoạn, không phải tọa độ GPS xe. Thời điểm tải không xác minh thời điểm đo vị trí từng xe. Không nội suy chuyển động.'


def rid(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{1,12}',value):raise ValueError('Cần route_id chính thức từ search_bus_routes, không dùng số tuyến làm ID.')
    return value


def integer(value):
    if isinstance(value,bool):return None
    try:
        n=int(str(value));return n if n>=0 else None
    except (TypeError,ValueError):return None


def point(row):
    try:
        x,y=float(row['x']),float(row['y'])
        if math.isfinite(x) and math.isfinite(y) and 124<=x<=132 and 33<=y<=39:return [x,y]
    except (KeyError,TypeError,ValueError):pass
    return None


def rows(payload,key='records'):
    if not isinstance(payload,dict) or key not in payload:raise s.Unavailable('Cấu trúc GBIS đã thay đổi hoặc nguồn báo lỗi; không tự tạo dữ liệu.')
    data=payload[key]
    if data is None:return []
    if not isinstance(data,list) or len(data)>20000 or any(not isinstance(row,dict) for row in data):raise s.Unavailable('Danh sách GBIS không hợp lệ.')
    return data


async def read(kind,params):
    cache_key=(kind,tuple(sorted(params.items())));clock=time.monotonic();ttl=15 if kind=='vehicles' else 300
    cached=_cache.get(cache_key)
    if cached and clock-cached[0]<ttl:
        result=copy.deepcopy(cached[1]);result['cached']=True;return result
    async with _gate:
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=18,follow_redirects=False,headers={'User-Agent':'KoreaTouristMCP/0.5.1 (+https://github.com/hehehemeshi/Korea-tourist-mcp)'}) as client:
                    response=await client.get(BASE+'/api/'+OPS[kind],params=params)
                    response.raise_for_status()
                    if len(response.content)>3_000_000:raise ValueError()
                    payload=response.json()
                if not isinstance(payload,dict):raise ValueError()
                break
            except (httpx.TimeoutException,httpx.ConnectError):
                if attempt==0:
                    await asyncio.sleep(.4);continue
                raise s.Unavailable('GBIS tạm mất kết nối hoặc quá thời gian sau 2 lần đọc; không có dữ liệu thay thế giả.') from None
            except httpx.HTTPStatusError as exc:
                code=exc.response.status_code
                if code>=500 and attempt==0:
                    await asyncio.sleep(.4);continue
                raise s.Unavailable(f'GBIS trả HTTP {code}; chưa có dữ liệu nguồn hợp lệ.') from None
            except (httpx.HTTPError,ValueError):
                raise s.Unavailable('Trang GBIS đổi định dạng hoặc chưa phản hồi hợp lệ; không có dữ liệu thay thế giả.') from None
    result=dict(payload=payload,fetched_at=s.now().isoformat(),source_url=BASE+'/api/'+OPS[kind]+'?'+urlencode(params),cached=False)
    _cache[cache_key]=(time.monotonic(),copy.deepcopy(result));_cache.move_to_end(cache_key)
    while len(_cache)>128:_cache.popitem(last=False)
    return result


def route_card(row):
    return dict(route_id=str(row['routeId']),number=str(row.get('routeName','')),
        region=row.get('regionName'),origin=row.get('stStaNm') or row.get('startStationName'),
        destination=row.get('edStaNm') or row.get('endStationName'))


async def search(query,region=''):
    if not isinstance(query,str) or not query.strip() or len(query)>30 or re.search(r'[\x00-\x1f/\\?#]',query):raise ValueError('Nhập số/tên tuyến bus (1–30 ký tự).')
    if not isinstance(region,str) or len(region)>40:raise ValueError('Tên khu vực quá dài.')
    region={'suwon':'수원','seoul':'서울','yongin':'용인','ansan':'안산','seongnam':'성남','incheon':'인천'}.get(region.strip().casefold(),region.strip())
    result=await read('search',{'keyword':query.strip()})
    selected=[route_card(row) for row in rows(result['payload']) if row.get('routeId') is not None and (not region or region.casefold() in str(row.get('regionName','')).casefold())]
    exact=[row for row in selected if row['number'].casefold()==query.strip().casefold()]
    if exact:selected=exact
    return dict(status='ok' if selected else 'no_data',data=selected[:20],truncated=len(selected)>20,
        source_url=result['source_url'],fetched_at=result['fetched_at'],cached=result['cached'],region=region,
        provider='GBIS public web',note='Chọn đúng khu vực và điểm đầu/cuối; các tuyến trùng số không tự coi là cùng tuyến. Dữ liệu nguồn web công khai, không phải API có cam kết ổn định.')


def vehicle_rows(payload):
    try:
        response=payload['response'];header=response['msgHeader'];code=str(header['resultCode'])
        if code=='4':return [],header.get('queryTime')
        if code!='0':raise ValueError()
        data=(response.get('msgBody') or {}).get('busLocationList',[])
        if data is None:data=[]
        if isinstance(data,dict):data=[data]
        if not isinstance(data,list) or len(data)>1000 or any(not isinstance(row,dict) for row in data):raise ValueError()
        return data,header.get('queryTime')
    except (KeyError,TypeError,AttributeError,ValueError):raise s.Unavailable('GBIS chưa trả danh sách xe hợp lệ; lỗi nguồn không có nghĩa là tuyến không có xe.') from None


def geometry(payload):
    try:
        response=payload['response'];code=str(response['msgHeader']['resultCode'])
        if code=='4':return []
        if code!='0':raise ValueError()
        data=(response.get('msgBody') or {}).get('busRouteLineList',[])
        if data is None:return []
        if not isinstance(data,list) or len(data)>20000:raise ValueError()
        seqs=[integer(row.get('lineSeq')) for row in data]
        if any(seq is None for seq in seqs) or len(set(seqs))!=len(seqs):raise ValueError()
        ordered=sorted(data,key=lambda row:integer(row['lineSeq']))
        coords=[point(row) for row in ordered]
        if any(p is None for p in coords) or (coords and len(coords)<2):raise ValueError()
        return coords
    except (KeyError,TypeError,AttributeError,ValueError):raise s.Unavailable('Đường tuyến nguồn GBIS chưa hợp lệ; không thay bằng đường nối các bến.') from None


def assemble(route_id,parts):
    warnings=[];features=[];stops=[];vehicles=[];metadata={}
    route=dict(route_id=route_id,number=None,region=None,origin=None,destination=None)
    for kind,result in parts.items():
        if isinstance(result,Exception):metadata[kind]={'status':'unavailable','message':str(result)};warnings.append(f'Nguồn {kind} chưa đọc được.');continue
        metadata[kind]={key:result[key] for key in ('source_url','fetched_at','cached')}
        try:
            payload=result['payload']
            if kind=='detail':
                row=payload.get('record')
                if not isinstance(row,dict) or str(row.get('routeId'))!=route_id:raise s.Unavailable('Thông tin tuyến không khớp ID.')
                route=route_card(row)
            elif kind=='stops':
                for row in rows(payload):
                    seq=integer(row.get('stationSeq'))
                    if seq is None or row.get('stationId') is None:continue
                    stops.append(dict(station_id=str(row['stationId']),sequence=seq,name=row.get('stationName'),coordinates=point(row),turnaround=row.get('turnYn')))
                stops.sort(key=lambda row:row['sequence'])
            elif kind=='shape':
                coords=geometry(payload)
                if coords:features.append(dict(type='Feature',geometry=dict(type='LineString',coordinates=coords),properties=dict(kind='provider_route_shape')))
            elif kind=='vehicles':
                data,request_time=vehicle_rows(payload);metadata[kind]['provider_request_time']=request_time
                for row in data:
                    if str(row.get('routeId'))!=route_id:continue
                    vehicles.append(dict(vehicle_id=str(row.get('vehId') or '') or None,plate=row.get('plateNo'),
                        station_id=str(row.get('stationId') or '') or None,station_sequence=integer(row.get('stationSeq')),
                        gps_coordinates=None,vehicle_observed_at=None,position_kind='provider_stop_reference',direction='unknown',
                        state={'0':'passing_intersection','1':'arrived_at_stop','2':'departed_stop'}.get(str(row.get('stateCd')),'unknown')))
                metadata[kind]['status']='ok' if data else 'no_data'
            metadata[kind].setdefault('status','ok')
        except (s.Unavailable,ValueError,TypeError,KeyError):metadata[kind]['status']='unavailable';warnings.append(f'Cấu trúc {kind} chưa hợp lệ; không tự suy đoán dữ liệu.')
    stop_index={}
    for stop in stops:
        stop_index.setdefault((stop['station_id'],stop['sequence']),[]).append(stop)
        if stop['coordinates']:features.append(dict(type='Feature',geometry=dict(type='Point',coordinates=stop['coordinates']),properties=dict(kind='stop',name=stop['name'],sequence=stop['sequence'])))
    groups={}
    for vehicle in vehicles:
        matches=stop_index.get((vehicle['station_id'],vehicle['station_sequence']),[])
        vehicle['referenced_stop']=matches[0] if len(matches)==1 else None
        if vehicle['referenced_stop'] and vehicle['referenced_stop']['coordinates']:
            key=(vehicle['station_id'],vehicle['station_sequence']);groups[key]=groups.get(key,0)+1
    for key,count in groups.items():
        stop=stop_index[key][0];features.append(dict(type='Feature',geometry=dict(type='Point',coordinates=stop['coordinates']),properties=dict(kind='vehicle_stop_reference',count=count,name=stop['name'],sequence=stop['sequence'],location_kind='stop_anchor_not_vehicle_gps')))
    available=sum(part['status']!='unavailable' for part in metadata.values())
    return dict(status='ok' if available==4 else 'partial' if available else 'unavailable',route_id=route_id,route=route,
        stops=stops,vehicles=vehicles,map=dict(type='FeatureCollection',features=features),parts=metadata,warnings=warnings,
        fetched_at=metadata.get('vehicles',{}).get('fetched_at') or s.now().isoformat(),assembled_at=s.now().isoformat(),cached=any(p.get('cached') for p in metadata.values()),source_url=SOURCE,
        provider='GBIS public web',position_notice=NOTICE,vehicle_observed_at=None,
        note='Bến có thể lặp trên hai chiều; tham chiếu xe dùng cả ID bến và thứ tự. Chưa xác minh hướng của từng xe hoặc GPS chính xác.')


async def snapshot(route_id):
    route_id=rid(route_id);kinds=('detail','stops','shape','vehicles')
    results=await asyncio.gather(*(read(kind,{'routeId':route_id}) for kind in kinds),return_exceptions=True)
    for result in results:
        if isinstance(result,BaseException) and not isinstance(result,(s.Unavailable,ValueError)):raise result
    return assemble(route_id,dict(zip(kinds,results)))


def ui_html():
    root=Path(__file__).parent/'static';html=(root/'bus-map.html').read_text()
    return html.replace('<link rel="stylesheet" href="/static/bus-map.css">','<style>'+(root/'bus-map.css').read_text()+'</style>').replace('<script defer src="/static/bus-map.js"></script>','').replace('</body>','<script>'+ (root/'bus-map.js').read_text()+'</script></body>')


def summary(data):
    route=data['route'];base=os.getenv('PUBLIC_BASE_URL','https://seoul-transit-mcp.onrender.com').rstrip('/')
    if not re.fullmatch(r'https://[a-zA-Z0-9.-]+(?::\d+)?',base):base='https://seoul-transit-mcp.onrender.com'
    return f"Bus {route.get('number') or 'Chưa có thông tin'} · {route.get('region') or 'GBIS'}: {len(data['stops'])} bến, {len(data['vehicles'])} bản ghi xe.\n\n{NOTICE}\n\nTrạng thái từng nguồn: "+', '.join(k+': '+v['status'] for k,v in data['parts'].items())+f"\n\nNguồn: {SOURCE}\nTải lúc: {data['fetched_at']}\n[Bản đồ tuyến]({base}/bus?route_id={data['route_id']})"
