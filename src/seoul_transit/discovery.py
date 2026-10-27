"""Open-data-first selection; paid/keyed providers remain opt-in."""
import os
from . import service as s, travel as t, open_data as o
from .routing import plan


def official():
    return os.getenv('OPEN_DATA_FIRST', 'true').lower() == 'false'

async def stations(query):
    if official() and os.getenv('SEOUL_API_KEY'):
        return await s.stations(query)
    return await o.search(query, stations=True)

async def places(query, page=1):
    if official() and os.getenv('KAKAO_REST_API_KEY'):
        return await t.kakao_places(query, page)
    return await o.search(query, page=page)

async def geocode(address):
    if official() and os.getenv('NAVER_CLIENT_ID') and os.getenv('NAVER_CLIENT_SECRET'):
        return await t.naver_geocode(address)
    return await o.search(address)

async def tourism(query, page=1):
    if official() and os.getenv('KTO_API_KEY'):
        return await t.search_tourism(query, page)
    return await o.search(query, page=page)

async def nearby(longitude, latitude, radius=2000, page=1):
    if official() and os.getenv('KTO_API_KEY'):
        return await t.nearby_tourism(longitude, latitude, radius, page)
    return await o.nearby(longitude, latitude, radius, page)

async def route(origin, destination):
    if os.getenv('NETWORK_FILE'):
        return plan(origin, destination)
    return o.google_links(origin=origin, destination=destination, mode='transit')

async def driving(origin, destination):
    if official() and os.getenv('NAVER_CLIENT_ID') and os.getenv('NAVER_CLIENT_SECRET'):
        return await t.driving_route(origin, destination)
    return o.google_links(origin=origin, destination=destination, mode='driving')

async def festivals(start_date, page=1):
    if official() and os.getenv('KTO_API_KEY'):
        return await t.festivals(start_date, page)
    from datetime import datetime
    datetime.strptime(start_date, '%Y%m%d')
    return o.link_fallback('South Korea festivals '+start_date, 'Chưa có dữ liệu lễ hội đã xác minh; đây là liên kết tìm kiếm.')

async def stays(area_code='', page=1):
    if official() and os.getenv('KTO_API_KEY'):
        return await t.stays(area_code, page)
    return o.link_fallback('hotels South Korea', 'Không có danh sách khách sạn hay tình trạng phòng đã xác minh. Mã vùng KTO không áp dụng cho tìm kiếm này.')
