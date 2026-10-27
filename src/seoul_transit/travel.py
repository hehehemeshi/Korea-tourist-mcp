"""Direct official API adapters, independent of third-party MCP implementations."""
import math
from datetime import datetime
from . import service as s

s.SOURCES.update({
    'tourism': 'https://www.data.go.kr/data/15101753/openapi.do',
    'kakao': 'https://developers.kakao.com/docs/en/local/dev-guide',
    'naver': 'https://api.ncloud-docs.com/docs/en/application-maps-overview',
})

def coordinates(longitude, latitude):
    lon, lat = float(longitude), float(latitude)
    if not math.isfinite(lon) or not math.isfinite(lat) or not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError('Tọa độ WGS84 không hợp lệ; nhập kinh độ, vĩ độ.')
    return lon, lat

def point(value):
    pieces = value.split(',')
    if len(pieces) != 2:
        raise ValueError('Nhập tọa độ theo dạng kinh_độ,vĩ_độ.')
    return ','.join(str(v) for v in coordinates(*pieces))

async def tourism(operation, page=1, **params):
    if not 1 <= page <= 100:
        raise ValueError('Trang phải từ 1 đến 100.')
    payload = await s.request('https://apis.data.go.kr/B551011/EngService2/'+operation,
        dict(serviceKey=s.key('KTO_API_KEY'), MobileOS='ETC', MobileApp='DiHanMCP',
             _type='json', numOfRows=20, pageNo=page, **params))
    response = payload.get('response', {})
    if str(response.get('header', {}).get('resultCode')) not in ('0000', '00', '0'):
        raise s.Unavailable('KTO từ chối yêu cầu; kiểm tra quyền EngService2 và hạn mức.')
    body = response.get('body', {})
    items = body.get('items') or {}
    rows = items.get('item', []) if isinstance(items, dict) else []
    if isinstance(rows, dict):
        rows = [rows]
    return s.result('tourism', rows, total_count=body.get('totalCount'), page=page,
                    data_kind='tourism_directory_not_live',
                    note='Nội dung gốc tiếng Anh từ KTO; giờ mở cửa và giá cần xác nhận với địa điểm.')

async def search_tourism(query, page=1):
    return await tourism('searchKeyword2', page, keyword=s.text(query))

async def nearby_tourism(longitude, latitude, radius=2000, page=1):
    lon, lat = coordinates(longitude, latitude)
    if not 1 <= radius <= 20000:
        raise ValueError('Bán kính từ 1 đến 20000 mét.')
    return await tourism('locationBasedList2', page, mapX=lon, mapY=lat, radius=radius)

async def tourism_detail(content_id):
    if not content_id.isdigit() or len(content_id) > 20:
        raise ValueError('content_id phải là mã số KTO.')
    return await tourism('detailCommon2', contentId=content_id)

async def festivals(start_date, page=1):
    datetime.strptime(start_date, '%Y%m%d')
    return await tourism('searchFestival2', page, eventStartDate=start_date)

async def stays(area_code='', page=1):
    if area_code and not area_code.isdigit():
        raise ValueError('area_code phải là mã số KTO.')
    return await tourism('searchStay2', page, **({'areaCode': area_code} if area_code else {}))

async def kakao_places(query, page=1):
    if not 1 <= page <= 45:
        raise ValueError('Trang Kakao từ 1 đến 45.')
    payload = await s.request('https://dapi.kakao.com/v2/local/search/keyword.json',
        dict(query=s.text(query), page=page, size=15),
        headers={'Authorization': 'KakaoAK '+s.key('KAKAO_REST_API_KEY')})
    if not isinstance(payload.get('documents'), list):
        raise s.Unavailable('Định dạng dữ liệu Kakao không hợp lệ.')
    # Keep Korean names, phone numbers and attribution supplied by Kakao.
    return s.result('kakao', payload['documents'], page=page, meta=payload.get('meta'),
                    data_kind='place_directory', note='Tên và địa chỉ gốc Kakao; không xác nhận quán đang mở.')

def naver_headers():
    return {'x-ncp-apigw-api-key-id': s.key('NAVER_CLIENT_ID'),
            'x-ncp-apigw-api-key': s.key('NAVER_CLIENT_SECRET')}

async def naver_geocode(address):
    payload = await s.request('https://maps.apigw.ntruss.com/map-geocode/v2/geocode',
        dict(query=s.text(address)), headers=naver_headers())
    if payload.get('status') != 'OK':
        raise s.Unavailable('Naver không thể tra địa chỉ.')
    return s.result('naver', payload.get('addresses', []), data_kind='geocoding')

async def driving_route(origin, destination):
    payload = await s.request('https://maps.apigw.ntruss.com/map-direction/v1/driving',
        dict(start=point(origin), goal=point(destination), option='traoptimal'),
        headers=naver_headers())
    if payload.get('code') != 0:
        raise s.Unavailable('Naver không trả tuyến đường ô tô cho hai tọa độ này.')
    routes = payload.get('route', {}).get('traoptimal', [])
    return s.result('naver', routes, data_kind='driving_route_not_public_transit',
        note='Tuyến ô tô; duration tính bằng mili giây, distance bằng mét. taxiFare là ước tính, không phải giá đặt xe.')
