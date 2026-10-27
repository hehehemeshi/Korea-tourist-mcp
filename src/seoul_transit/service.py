"""Official feeds only; provider failures never become fabricated results."""
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote
import httpx

KST = ZoneInfo('Asia/Seoul')
SOURCES = {
    'stations': 'https://data.seoul.go.kr/dataList/OA-15442/A/1/datasetView.do',
    'arrivals': 'https://data.seoul.go.kr/dataList/OA-12764/A/1/datasetView.do',
    'routes': 'https://www.data.go.kr/data/15143842/openapi.do',
    'rail': 'https://www.data.go.kr/data/15098552/openapi.do',
}

class Unavailable(Exception):
    pass

def now():
    return datetime.now(KST)

def text(value):
    value = value.strip()
    if not value or len(value) > 80 or re.search(r'[/\\?#\x00-\x1f]', value):
        raise ValueError('Tên hoặc mã ga không hợp lệ (1–80 ký tự).')
    return value

def result(kind, data, **extra):
    return dict(status='ok' if data else 'no_data', data=data,
                fetched_at=now().isoformat(), timezone='Asia/Seoul',
                source=SOURCES[kind], **extra)

async def request(url, params=None, headers=None):
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError()
            return data
    except (httpx.HTTPError, ValueError):
        # Never include request URLs: Seoul places secret keys in URL paths.
        raise Unavailable('Nguồn chính thức không phản hồi hoặc trả dữ liệu không hợp lệ.') from None

def key(name):
    value = os.getenv(name)
    if not value:
        raise Unavailable(f'Chưa cấu hình {name}.')
    return value

def arrival(row, clock=None):
    clock = clock or now()
    try:
        generated = datetime.fromisoformat(row['recptnDt'])
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=KST)
        age = (clock - generated).total_seconds()
        fresh = -30 <= age <= 120
    except (ValueError, KeyError, TypeError):
        generated, fresh = None, False
    try:
        seconds = int(row['barvlDt'])
    except (ValueError, KeyError, TypeError):
        seconds = -1
    # Zero is commonly an unknown estimate. Departed trains are not arrivals.
    eta = generated + timedelta(seconds=seconds) if fresh and seconds > 0 and str(row.get('arvlCd')) != '2' else None
    if eta and eta <= clock:
        eta = None
    return dict(station=row.get('statnNm'), line=row.get('subwayId'),
                direction=row.get('updnLine'), towards=row.get('trainLineNm'),
                destination=row.get('bstatnNm'), train=row.get('btrainNo'),
                message=row.get('arvlMsg2'), generated_at=generated.isoformat() if generated else None,
                freshness='fresh' if fresh else 'stale_or_unknown',
                estimated_arrival=eta.isoformat() if eta else None,
                platform=None, platform_status='not_verified')

async def stations(query):
    q = text(query)
    token = quote(key('SEOUL_API_KEY'), safe='')
    payload = await request(f'https://openapi.seoul.go.kr:8088/{token}/json/SearchSTNBySubwayLineInfo/1/1000/')
    body = payload.get('SearchSTNBySubwayLineInfo', {})
    code = body.get('RESULT', payload.get('RESULT', {})).get('CODE')
    if code not in ('INFO-000', 'INFO-200'):
        raise Unavailable('Không thể đọc danh sách ga Seoul.')
    rows = body.get('row', [])
    return result('stations', [dict(id=r.get('STATION_CD'), name=r.get('STATION_NM'),
        english=r.get('STATION_NM_ENG'), line=r.get('LINE_NUM')) for r in rows
        if q.casefold() in (str(r.get('STATION_NM', ''))+' '+str(r.get('STATION_NM_ENG', ''))).casefold()],
        coverage='Seoul Metro dataset; not all KORAIL commuter stations')

async def arrivals(station):
    station = text(station)
    token = quote(key('SEOUL_SUBWAY_API_KEY'), safe='')
    payload = await request(f'https://swopenapi.seoul.go.kr/api/subway/{token}/json/realtimeStationArrival/0/100/{quote(station, safe="")}')
    code = payload.get('errorMessage', payload.get('RESULT', {})).get('code', payload.get('RESULT', {}).get('CODE'))
    if code not in (None, 'INFO-000', 'INFO-200'):
        raise Unavailable('Nguồn Seoul từ chối yêu cầu; kiểm tra khóa và hạn mức.')
    if 'realtimeArrivalList' not in payload and code != 'INFO-200':
        raise Unavailable('Định dạng dữ liệu Seoul đã thay đổi.')
    return result('arrivals', [arrival(r) for r in payload.get('realtimeArrivalList', [])],
                  note='Không có dữ liệu không có nghĩa là hết tàu. Số sân ga chưa được xác minh.')

async def tago(operation, **params):
    payload = await request('https://apis.data.go.kr/1613000/TrainInfoService/'+operation,
        dict(serviceKey=key('DATA_GO_KR_KEY'), _type='json', numOfRows=100, pageNo=1, **params))
    response = payload.get('response', {})
    if str(response.get('header', {}).get('resultCode')) not in ('00', '0'):
        raise Unavailable('TAGO từ chối yêu cầu; kiểm tra khóa và quyền truy cập.')
    body = response.get('body', {})
    items = body.get('items') or {}
    rows = items.get('item', []) if isinstance(items, dict) else []
    return rows if isinstance(rows, list) else [rows]

async def rail_stations(city_code='11'):
    if not re.fullmatch(r'\d{2}', city_code):
        raise ValueError('Mã thành phố gồm 2 chữ số; Seoul: 11.')
    return result('rail', await tago('getCtyAcctoTrainSttnList', cityCode=city_code),
                  note='Dùng nodeid khi tìm lịch tàu; đây không phải mã ga metro.')

async def rail_schedule(origin, destination, date):
    if not re.fullmatch(r'\d{8}', date):
        raise ValueError('Ngày có định dạng YYYYMMDD.')
    datetime.strptime(date, '%Y%m%d')
    rows = await tago('getStrtpntAlocFndTrainInfo', depPlaceId=text(origin),
                      arrPlaceId=text(destination), depPlandTime=date)
    return result('rail', [dict(train=r.get('trainno'), type=r.get('traingradename'),
        origin=r.get('depplacename'), destination=r.get('arrplacename'),
        scheduled_departure=r.get('depplandtime'), scheduled_arrival=r.get('arrplandtime'),
        platform=None, platform_status='not_verified') for r in rows],
        data_kind='timetable_not_live', note='Lịch dự kiến, không phải thời gian thực; tối đa 100 kết quả.')
