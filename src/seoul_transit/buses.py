"""GBIS official v2 data layer. Stop-relative bus positions are never GPS points."""
import asyncio
import math
import re
from urllib.parse import unquote
from . import service as s

DOCS='https://www.gbis.go.kr/gbis2014/publicService.action?cmd='
OPERATIONS={
 'routes':('busrouteservice','getBusRouteListv2','busRouteList','mBusRoute'),
 'stops':('busrouteservice','getBusRouteStationListv2','busRouteStationList','mBusRouteStation'),
 'shape':('busrouteservice','getBusRouteLineListv2','busRouteLineList','mBusRouteLine'),
 'vehicles':('buslocationservice','getBusLocationListv2','busLocationList','mBusLocation'),
}

def integer(value):
    if isinstance(value,bool):return None
    try:
        number=int(str(value))
        return number if number>=0 else None
    except (TypeError,ValueError):return None


def coordinates(row):
    try:
        x,y=float(row['x']),float(row['y'])
        if math.isfinite(x) and math.isfinite(y) and 124<=x<=132 and 33<=y<=39:return [x,y]
    except (KeyError,TypeError,ValueError):pass
    return None


def route_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{1,12}',value):raise ValueError('Cần routeId chính thức từ kết quả tìm tuyến, không dùng số tuyến làm ID.')
    return value


def envelope(payload,field):
    try:
        response=payload['response'];header=response['msgHeader'];code=str(header['resultCode'])
        if code not in ('0','4'):raise s.Unavailable('GBIS từ chối truy vấn hoặc chưa cấp quyền dịch vụ; không có dữ liệu thay thế giả.')
        rows=(response.get('msgBody') or {}).get(field,[]) if code=='0' else []
        if rows is None:rows=[]
        if isinstance(rows,dict):rows=[rows]
        if not isinstance(rows,list) or len(rows)>15000 or any(not isinstance(row,dict) for row in rows):raise ValueError()
        request_time=(response.get('comMsgHeader') or {}).get('queryTime')
        return rows,request_time
    except (KeyError,TypeError,AttributeError,ValueError):
        raise s.Unavailable('Cấu trúc GBIS chưa đúng tài liệu; không suy đoán dữ liệu.') from None


async def fetch(kind,params):
    family,operation,field,doc=OPERATIONS[kind]
    payload=await s.request(f'https://apis.data.go.kr/6410000/{family}/v2/{operation}',
        {'serviceKey':unquote(s.key('DATA_GO_KR_KEY')),'format':'json',**params})
    rows,request_time=envelope(payload,field)
    return dict(rows=rows,provider_request_time=request_time,source=DOCS+doc,fetched_at=s.now().isoformat())


async def search(keyword):
    if not isinstance(keyword,str) or not keyword.strip() or len(keyword)>30 or re.search(r'[\x00-\x1f/\\?#]',keyword):raise ValueError('Nhập số/tên tuyến bus (1–30 ký tự).')
    result=await fetch('routes',{'keyword':keyword.strip()})
    result['data']=[dict(route_id=str(row['routeId']),number=row.get('routeName'),region=row.get('regionName'),
        origin=row.get('startStationName'),destination=row.get('endStationName')) for row in result.pop('rows') if row.get('routeId') is not None]
    result.update(status='ok' if result['data'] else 'no_data',provider='GBIS',coverage='Gyeonggi_provider_results')
    return result


def normalize(parts,rid):
    stops=[];features=[];warnings=[]
    for row in parts.get('stops',{}).get('rows',[]):
        seq=integer(row.get('stationSeq'))
        if seq is None:continue
        stop=dict(station_id=str(row.get('stationId','')),sequence=seq,name=row.get('stationName'),
            coordinates=coordinates(row),turnaround=row.get('turnYn'),turn_sequence=integer(row.get('turnSeq')))
        stops.append(stop)
        if stop['coordinates']:features.append(dict(type='Feature',geometry=dict(type='Point',coordinates=stop['coordinates']),properties=dict(kind='stop',station_id=stop['station_id'],sequence=seq,name=stop['name'])))
    stops.sort(key=lambda row:row['sequence'])
    raw_shape=parts.get('shape',{}).get('rows',[])
    seqs=[integer(row.get('lineSeq')) for row in raw_shape]
    if raw_shape and all(seq is not None for seq in seqs) and len(set(seqs))==len(seqs):
        ordered=sorted(raw_shape,key=lambda row:integer(row['lineSeq']));points=[coordinates(row) for row in ordered]
        if len(points)>=2 and all(p is not None for p in points):
            features.insert(0,dict(type='Feature',geometry=dict(type='LineString',coordinates=points),properties=dict(kind='official_route_shape',route_id=rid)))
        else:warnings.append('Hình học tuyến thiếu/sai tọa độ; không nối các bến thành đường tuyến giả.')
    elif raw_shape:warnings.append('Thứ tự hình học thiếu hoặc trùng; chưa vẽ đường tuyến.')
    vehicles=[]
    for row in parts.get('vehicles',{}).get('rows',[]):
        if str(row.get('routeId',''))!=rid:
            warnings.append('Bỏ bản ghi xe không khớp routeId.');continue
        seq=integer(row.get('stationSeq'));sid=str(row.get('stationId',''))
        matches=[stop for stop in stops if stop['sequence']==seq and stop['station_id']==sid]
        vehicles.append(dict(vehicle_id=str(row.get('vehId') or row.get('plateNo') or '') or None,
            plate=row.get('plateNo'),route_id=rid,station_id=sid or None,station_sequence=seq,
            referenced_stop=matches[0] if len(matches)==1 else None,
            state={'0':'passing_intersection','1':'arrived_at_stop','2':'departed_stop'}.get(str(row.get('stateCd')),'unknown'),
            position_kind='provider_stop_reference',gps_coordinates=None,vehicle_observed_at=None,
            direction='unknown',remaining_seats=integer(row.get('remainSeatCnt'))))
    for kind,part in parts.items():
        if part.get('status')=='unavailable':warnings.append(f'Không lấy được {kind}; các phần khác giữ riêng trạng thái.')
    valid_parts=[part for part in parts.values() if part.get('status')!='unavailable']
    return dict(status='ok' if valid_parts else 'unavailable',provider='GBIS',route_id=rid,
        route_map=dict(type='FeatureCollection',features=features),stops=stops,vehicles=vehicles,
        parts={kind:{k:v for k,v in part.items() if k!='rows'} for kind,part in parts.items()},
        vehicle_position_kind='stop_relative_not_gps',vehicle_freshness='unknown',
        fetched_at=s.now().isoformat(),warnings=warnings,
        note='queryTime là thời điểm yêu cầu, không xác minh thời điểm GPS xe. Không nội suy/animate xe giữa hai bến; chưa suy đoán chiều chạy. Xe không tạo GeoJSON Point như vị trí GPS.')


async def snapshot(rid):
    rid=route_id(rid)
    s.key('DATA_GO_KR_KEY')  # Fail before launching three calls when not configured.
    kinds=('stops','shape','vehicles')
    values=await asyncio.gather(*(fetch(kind,{'routeId':rid}) for kind in kinds),return_exceptions=True)
    parts={}
    for kind,result in zip(kinds,values):
        if isinstance(result,Exception):
            if not isinstance(result,(s.Unavailable,ValueError)):raise result
            parts[kind]=dict(status='unavailable',source=DOCS+OPERATIONS[kind][3])
        else:
            result['status']='ok' if result['rows'] else 'no_data';parts[kind]=result
    return normalize(parts,rid)
