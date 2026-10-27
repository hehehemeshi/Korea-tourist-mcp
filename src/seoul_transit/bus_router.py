"""Select a verified regional source explicitly; never default to Suwon or GBIS."""
import asyncio
import math
import re
import unicodedata
from urllib.parse import urlparse
import httpx
from . import service as s, public_buses as gbis, seoul_buses as seoul

UI_URI=gbis.UI_URI
ui_html=gbis.ui_html
summary=gbis.summary
GG_CITIES={'suwon':'수원','seongnam':'성남','uijeongbu':'의정부','anyang':'안양','bucheon':'부천','gwangmyeong':'광명','pyeongtaek':'평택','dongducheon':'동두천','ansan':'안산','goyang':'고양','gwacheon':'과천','guri':'구리','namyangju':'남양주','osan':'오산','siheung':'시흥','gunpo':'군포','uiwang':'의왕','hanam':'하남','yongin':'용인','paju':'파주','icheon':'이천','anseong':'안성','gimpo':'김포','hwaseong':'화성','gwangju':'광주','yangju':'양주','pocheon':'포천','yeoju':'여주','yeoncheon':'연천','gapyeong':'가평','yangpyeong':'양평'}
OTHER={'busan':'부산','daegu':'대구','daejeon':'대전','ulsan':'울산','sejong':'세종','jeju':'제주','gangwon':'강원','chungbuk':'충청북도','chungnam':'충청남도','jeonbuk':'전북','jeonnam':'전라남도','gyeongbuk':'경상북도','gyeongnam':'경상남도','gwangju metropolitan city':'광주광역시'}


def key(value):return re.sub(r'[\s_-]','',unicodedata.normalize('NFC',value).casefold())


def resolve(region):
    raw=region.strip();name=key(raw)
    if not name:return None
    if name in ('korea','southkorea','hànquốc','전국','대한민국'):return dict(scope='needs_city',name=raw)
    if name in ('seoul','서울','서울특별시'):return dict(scope='seoul',name='서울',provider='seoul')
    if name in ('gyeonggi','gyeonggido','경기','경기도'):return dict(scope='gyeonggi',name='경기도',provider='gbis')
    if name in ('incheon','인천','인천광역시'):return dict(scope='incheon',name='인천',provider='gbis_partial')
    # 광주 is ambiguous between Gyeonggi's city and the metropolitan city.
    if name in ('gwangju','광주','광주시'):return dict(scope='ambiguous',name=raw)
    gg_name=name.replace('경기도','').replace('gyeonggido','').replace('gyeonggi','')
    for english,korean in GG_CITIES.items():
        if gg_name in (key(english),key(english+'si'),key(english+'gun'),key(korean),key(korean+'시'),key(korean+'군')) or (korean=='광주' and name in ('경기도광주','경기도광주시','gyeonggigwangju')):
            return dict(scope='gyeonggi',name=korean,provider='gbis')
    for english,korean in OTHER.items():
        if name in (key(english),key(english+'si'),key(english+'gun'),key(korean),key(korean+'광역시'),key(korean+'특별자치도')):return dict(scope='unsupported',name=korean)
    return dict(scope='unsupported',name=raw)


def coverage():
    return dict(default_region=None,providers=[
        dict(id='seoul',scope='Seoul public bus index',status='verified_public_web',gps='only_when_provider_coordinate_and_fresh_timestamp_exist'),
        dict(id='gbis',scope='Gyeonggi and GBIS-listed cross-region routes',status='verified_public_web',gps='not_available_stop_reference_only')],
        other_regions='not_integrated_report_unsupported',nationwide_coverage=False,
        note='Cần thành phố/tỉnh hoặc tọa độ do ChatGPT cung cấp; không lấy GPS thiết bị trong MCP. Phạm vi phụ thuộc nguồn, không tuyên bố phủ toàn Hàn Quốc.')


async def from_coordinates(longitude,latitude):
    if isinstance(longitude,bool) or isinstance(latitude,bool):raise ValueError('Tọa độ không hợp lệ.')
    try:lon,lat=float(longitude),float(latitude)
    except (TypeError,ValueError):raise ValueError('Cần đủ kinh độ và vĩ độ.') from None
    if not math.isfinite(lon) or not math.isfinite(lat) or not 124<=lon<=132 or not 33<=lat<=39:raise ValueError('Tọa độ cần nằm trong phạm vi Hàn Quốc được hỗ trợ.')
    try:
        async with httpx.AsyncClient(timeout=12,follow_redirects=False) as client:
            response=await client.get('https://photon.komoot.io/reverse',params={'lon':lon,'lat':lat,'limit':1,'lang':'en'})
            response.raise_for_status();data=response.json()
        feature=data['features'][0];p=feature['properties'];xy=feature['geometry']['coordinates']
        if str(p.get('countrycode','')).upper()!='KR':raise ValueError()
        # A nearest point far away is not trustworthy evidence of this administrative region.
        fx,fy=float(xy[0]),float(xy[1])
        if not math.isfinite(fx) or not math.isfinite(fy):raise ValueError()
        dy=(fy-lat)*111195;dx=(fx-lon)*111195*math.cos(math.radians(lat))
        if math.hypot(dx,dy)>5000:raise ValueError()
        state=str(p.get('state') or '')
        if key(state) in ('gwangju','광주','광주광역시'):resolved={'scope':'unsupported','name':'광주광역시'}
        else:
            resolved=None
            for field in ('city','county','state'):
                candidate=resolve(str(p.get(field) or ''))
                if candidate and candidate['scope'] not in ('unsupported','ambiguous'):
                    resolved=candidate;break
            if resolved is None:resolved=resolve(state or str(p.get('city') or ''))
        if not resolved:raise ValueError()
        return resolved,dict(kind='coordinates_reverse_geocoded',source='https://photon.komoot.io',fetched_at=s.now().isoformat(),address={k:p.get(k) for k in ('city','county','state','countrycode')})
    except (httpx.HTTPError,KeyError,TypeError,ValueError,IndexError):
        raise s.Unavailable('Chưa xác định chắc khu vực từ tọa độ. Hãy cho biết thành phố/tỉnh; không tự chuyển sang Gyeonggi.') from None


def namespace(result,provider):
    out=dict(result);out['data']=[{**row,'route_id':provider+':'+row['route_id'],'provider_route_id':row['route_id'],'source_id':provider} for row in result.get('data',[])]
    return out


async def search(query,region='',longitude=None,latitude=None):
    if not isinstance(query,str) or not query.strip() or len(query)>30 or re.search(r'[\x00-\x1f/\\?#]',query):raise ValueError('Nhập số/tên tuyến bus (1–30 ký tự).')
    if not isinstance(region,str) or len(region)>80:raise ValueError('Tên khu vực không hợp lệ.')
    selection={'kind':'explicit_region'}
    if region.strip():resolved=resolve(region)
    elif longitude is not None or latitude is not None:resolved,selection=await from_coordinates(longitude,latitude)
    else:return dict(status='needs_region',data=[],message='Bạn muốn tìm bus ở thành phố/tỉnh nào? Có thể dùng tọa độ ChatGPT cung cấp.',coverage=coverage())
    if resolved['scope']=='needs_city':return dict(status='needs_region',data=[],message='Cần thành phố/tỉnh cụ thể để chọn nguồn; hiện chưa có phạm vi toàn quốc.',coverage=coverage())
    if resolved['scope']=='ambiguous':return dict(status='needs_region',data=[],message='Gwangju là 광주광역시 hay 광주시 thuộc Gyeonggi? Cần xác định đúng vùng trước khi chọn nguồn.',coverage=coverage())
    if resolved['scope']=='unsupported':return dict(status='unsupported_region',data=[],requested_region=resolved['name'],message=f"Chưa tích hợp nguồn bus đã xác minh cho {resolved['name']}. Không dùng kết quả Seoul/Gyeonggi thay thế.",coverage=coverage())
    attempts=[];warnings=[]
    if resolved['scope']=='seoul':
        try:
            result=namespace(await seoul.search(query),'seoul');attempts.append({'source':'seoul','status':result['status']})
            if result['data']:
                result.update(selection={**selection,'region':'서울'},provider_attempts=attempts,coverage_scope='seoul_source_index');return result
        except s.Unavailable:attempts.append({'source':'seoul','status':'unavailable'})
        warnings.append('Nguồn Seoul chưa trả tuyến phù hợp. Kết quả GBIS bổ sung chỉ gồm tuyến nguồn GBIS ghi nhận chạy qua Seoul, không đại diện toàn bộ bus Seoul.')
        filter_region='서울'
    else:filter_region=resolved['name']
    try:result=namespace(await gbis.search(query,filter_region),'gbis')
    except s.Unavailable:
        return dict(status='unavailable',data=[],message='Nguồn đúng khu vực hiện không phản hồi. Không đổi sang khu vực khác.',provider_attempts=attempts+[{'source':'gbis','status':'unavailable'}],selection={**selection,'region':resolved['name']})
    attempts.append({'source':'gbis','status':result['status']})
    if resolved['scope']=='incheon':warnings.append('Chỉ có các tuyến Incheon được GBIS liệt kê; nguồn địa phương Incheon chưa tích hợp.')
    result.update(selection={**selection,'region':resolved['name']},provider_attempts=attempts,warnings=warnings,
        coverage_scope='gbis_listed_cross_region_routes' if warnings else 'gbis_requested_region')
    if warnings and result['data']:result['status']='partial'
    return result


async def snapshot(route_id):
    if not isinstance(route_id,str):raise ValueError('route_id không hợp lệ.')
    if ':' in route_id:provider,raw=route_id.split(':',1)
    elif re.fullmatch(r'\d{9,12}',route_id):provider,raw='gbis',route_id  # Existing saved links only.
    else:raise ValueError('Dùng route_id có nguồn từ search_bus_routes, ví dụ seoul:… hoặc gbis:…; số tuyến không phải mã tuyến.')
    if not re.fullmatch(r'\d{9,12}',raw):raise ValueError('Cần mã tuyến chính thức từ kết quả tìm kiếm, không phải số bus.')
    gbis.rid(raw)
    if provider=='seoul':data=await seoul.snapshot(raw)
    elif provider=='gbis':data=await gbis.snapshot(raw)
    else:raise ValueError('Nguồn route_id chưa được tích hợp; không tự đổi nguồn.')
    data['provider_route_id']=raw;data['route_id']=provider+':'+raw;data['source_id']=provider
    data['route']['route_id']=data['route_id']
    return data
