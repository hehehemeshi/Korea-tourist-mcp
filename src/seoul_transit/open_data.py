"""Low-volume keyless OSM discovery and Google hand-off links. No live transit claims."""
import asyncio
import copy
import json
import math
import os
import time
from collections import OrderedDict
from datetime import date, datetime
from urllib.parse import urlencode
from . import service as s

ATTRIBUTION = '© OpenStreetMap contributors — ODbL; served by Photon / Overpass'
SOURCE = 'https://www.openstreetmap.org/copyright'
USER_AGENT = 'KoreaTravelMCP/0.2 (+https://github.com/hehehemeshi/Korea-tourist-mcp)'
_cache = OrderedDict()
_lock = asyncio.Lock()
_last = 0.0
_day = None
_calls = 0


def query_text(value):
    value = value.strip()
    if not value or len(value) > 120 or any(ord(c) < 32 for c in value):
        raise ValueError('Nhập tên hoặc địa chỉ từ 1 đến 120 ký tự.')
    return value


def google_links(query='', origin='', destination='', mode='transit'):
    """Construct URLs only. No Google search results, route, ETA, or platform retrieved."""
    if mode not in ('transit', 'walking', 'driving', 'bicycling'):
        raise ValueError('Chế độ phải là transit, walking, driving hoặc bicycling.')
    links = []
    if query:
        query = query_text(query)
        links.append({'label': 'Mở Google Maps', 'url': 'https://www.google.com/maps/search/?'+urlencode({'api':1,'query':query})})
        links.append({'label': 'Tìm trên Google', 'url': 'https://www.google.com/search?'+urlencode({'q':query})})
    if origin or destination:
        origin, destination = query_text(origin), query_text(destination)
        links.append({'label': 'Xem chỉ đường trên Google Maps', 'url': 'https://www.google.com/maps/dir/?'+urlencode({'api':1,'origin':origin,'destination':destination,'travelmode':mode})})
    if not links:
        raise ValueError('Cần từ khóa hoặc điểm đi và điểm đến.')
    return dict(status='external_links', data=[], links=links, fetched_at=s.now().isoformat(),
        source='https://developers.google.com/maps/documentation/urls/get-started',
        data_kind='external_links_only', note='Liên kết mở Google; MCP chưa đọc kết quả, tuyến, giờ tàu hoặc sân ga từ Google.')


def link_fallback(query, reason):
    result = google_links(query)
    result['note'] = reason + ' ' + result['note']
    return result


async def public_request(url, params):
    """One process, 2s spacing, hourly bounded cache and 300 requests/day cap.

    Deploy one worker/replica with public endpoints. For scale use your own OSM service.
    """
    global _last, _day, _calls
    cache_key = (url, json.dumps(params, sort_keys=True))
    async with _lock:
        clock = time.monotonic()
        hit = _cache.get(cache_key)
        if hit and clock-hit[0] < 3600:
            _cache.move_to_end(cache_key)
            return copy.deepcopy(hit[1]), hit[2], True
        today = date.today()
        if today != _day:
            _day, _calls = today, 0
        if _calls >= 300:
            raise s.Unavailable('Đã đạt hạn mức nguồn mở tạm thời của máy chủ.')
        delay = 2-(clock-_last)
        if delay > 0:
            await asyncio.sleep(delay)
        _last, _calls = time.monotonic(), _calls+1
        payload = await s.request(url, params, headers={'User-Agent': USER_AGENT})
        retrieved = s.now().isoformat()
        _cache[cache_key] = (time.monotonic(), copy.deepcopy(payload), retrieved)
        while len(_cache) > 128:
            _cache.popitem(last=False)
        return payload, retrieved, False


async def search(query, stations=False, page=1):
    query = query_text(query)
    if page != 1:
        return link_fallback(query+' South Korea', 'Nguồn mở chỉ hỗ trợ trang đầu; dùng Google để xem thêm.')
    params = {'q':query,'limit':15,'lang':'en','bbox':'124,33,132,38.7'}
    if stations:
        params['osm_tag'] = 'railway:station'
    try:
        payload, retrieved, cached = await public_request('https://photon.komoot.io/api/', params)
    except s.Unavailable:
        return link_fallback(query+' South Korea', 'Nguồn OSM tạm thời không khả dụng; không có kết quả được xác minh.')
    if not isinstance(payload.get('features'), list):
        raise s.Unavailable('Nguồn Photon trả định dạng không hợp lệ.')
    rows = []
    for feature in payload['features']:
        p = feature.get('properties', {})
        if str(p.get('countrycode', '')).upper() != 'KR':
            continue
        if stations and (p.get('osm_key'), p.get('osm_value')) != ('railway', 'station'):
            continue
        xy = feature.get('geometry', {}).get('coordinates', [])
        if len(xy) != 2:
            continue
        rows.append(dict(name=p.get('name'), address=', '.join(str(p[k]) for k in ('housenumber','street','city','state') if p.get(k)),
            longitude=xy[0], latitude=xy[1], category=p.get('osm_value'),
            source_url=f'https://www.openstreetmap.org/{dict(N="node",W="way",R="relation").get(p.get("osm_type"), "node")}/{p.get("osm_id")}',
            google_maps_url=google_links(str(p.get('name') or query)+' South Korea')['links'][0]['url'],
            platform=None, platform_status='not_verified'))
    return dict(status='ok' if rows else 'no_data', data=rows,
        source=SOURCE, attribution=ATTRIBUTION, provider='Photon / OpenStreetMap',
        fetched_at=s.now().isoformat(), retrieved_at=retrieved, cached=cached,
        data_kind='community_map_not_live', links=google_links(query+' South Korea')['links'],
        note='Dữ liệu cộng đồng OSM, có thể thiếu ga/địa điểm. Không có giờ tàu, sân ga hoặc xác nhận đang mở cửa.')


async def nearby(longitude, latitude, radius=2000, page=1):
    lon, lat = float(longitude), float(latitude)
    if not math.isfinite(lon) or not math.isfinite(lat) or not (124 <= lon <= 132 and 33 <= lat <= 38.7):
        raise ValueError('Tọa độ phải trong vùng tìm kiếm Hàn Quốc, dạng kinh độ và vĩ độ.')
    if not 1 <= radius <= 5000:
        raise ValueError('Nguồn mở hỗ trợ bán kính 1–5000 mét.')
    if page != 1:
        raise ValueError('Nguồn mở chỉ hỗ trợ trang đầu, tối đa 30 địa điểm.')
    # Numeric parameters only; never interpolate user query text into Overpass QL.
    q=f'[out:json][timeout:8];(nwr(around:{int(radius)},{lat},{lon})[tourism~"^(attraction|museum|hotel|guest_house)$"];nwr(around:{int(radius)},{lat},{lon})[amenity~"^(restaurant|cafe)$"];);out center meta 30;'
    try:
        payload, retrieved, cached = await public_request('https://overpass-api.de/api/interpreter', {'data':q})
    except s.Unavailable:
        return link_fallback(f'attractions near {lat},{lon}', 'Nguồn Overpass tạm thời không khả dụng.')
    if payload.get('remark') or not isinstance(payload.get('elements'), list):
        raise s.Unavailable('Overpass không trả dữ liệu đầy đủ; thử lại sau.')
    rows=[]
    for e in payload['elements'][:30]:
        tags=e.get('tags', {})
        center=e.get('center', e)
        rows.append(dict(name=tags.get('name:en') or tags.get('name'), name_ko=tags.get('name:ko') or tags.get('name'),
            category=tags.get('tourism') or tags.get('amenity'), longitude=center.get('lon'), latitude=center.get('lat'),
            source_updated_at=e.get('timestamp'), source_url=f'https://www.openstreetmap.org/{e["type"]}/{e["id"]}',
            platform=None, platform_status='not_verified'))
    return dict(status='ok' if rows else 'no_data', data=rows, source=SOURCE, attribution=ATTRIBUTION,
        fetched_at=s.now().isoformat(), retrieved_at=retrieved, cached=cached,
        data_kind='community_map_not_live', note='Tối đa 30 địa điểm OSM; không phải danh sách đầy đủ hoặc xếp theo khoảng cách. Không xác nhận giờ mở cửa hoặc chỗ trống.')
