"""Restaurant discovery, explicit evidence and conservative budget decisions."""
import asyncio
import math
import os
import re
import time
import unicodedata
from collections import OrderedDict
from datetime import datetime
from urllib.parse import urlencode
from . import service as s, open_data as o
from . import evidence as e

KAKAO = 'https://developers.kakao.com/docs/en/local/dev-guide#search-by-category'
ORS = 'https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/'
_seen = OrderedDict()


def normalise_query(query):
    return unicodedata.normalize('NFKC', o.query_text(query)).strip()


def validate(longitude, latitude, radius=500, budget=10000, party=1, limit=15):
    lon, lat = float(longitude), float(latitude)
    if not all(math.isfinite(v) for v in (lon,lat)) or not (124 <= lon <= 132 and 33 <= lat <= 38.7):
        raise ValueError('Nhập tọa độ Hàn Quốc dạng kinh độ, vĩ độ (không tự lấy GPS điện thoại).')
    if not isinstance(radius,int) or isinstance(radius,bool) or not 1 <= radius <= 5000:
        raise ValueError('Bán kính từ 1 đến 5000 mét.')
    if not isinstance(budget,int) or isinstance(budget,bool) or not 1 <= budget <= 10000000:
        raise ValueError('Ngân sách phải là số nguyên KRW/người, lớn hơn 0.')
    if not isinstance(party,int) or isinstance(party,bool) or not 1 <= party <= 20:
        raise ValueError('Số người từ 1 đến 20.')
    if not isinstance(limit,int) or isinstance(limit,bool) or not 1 <= limit <= 30:
        raise ValueError('Số kết quả từ 1 đến 30.')
    return lon, lat


def metres(lon, lat, x, y):
    x,y=float(x),float(y)
    if not all(math.isfinite(v) for v in (lon,lat,x,y)) or not (-180<=x<=180 and -90<=y<=90):
        raise ValueError('Invalid provider coordinates')
    a,b,c,d=map(math.radians,(lon,lat,x,y))
    h=math.sin((d-b)/2)**2+math.cos(b)*math.cos(d)*math.sin((c-a)/2)**2
    return 6371008.8*2*math.asin(min(1,math.sqrt(h)))


def restaurant_id(value):
    if not re.fullmatch(r'(kakao:[0-9]+|osm:(node|way|relation):[0-9]+|source:[a-z0-9-]+)',value):
        raise ValueError('Dùng restaurant_id từ kết quả tìm kiếm: kakao:123, osm:node:123 hoặc source:...')
    return value


def candidate(rid, name, address, lon, lat, source, checked, opening=None, menu_url=None, updated=None):
    row=dict(restaurant_id=rid, name=e.fact(name,source,checked), address=e.fact(address,source,checked),
        longitude=e.fact(float(lon),source,checked), latitude=e.fact(float(lat),source,checked),
        opening_hours=e.fact(opening,source,checked), open_now=e.fact(),
        menu_link=e.fact(menu_url if e.https_url(menu_url) else None,source,checked),
        walking_distance_m=e.fact(), walking_duration_seconds=e.fact(), quality=e.fact())
    for f in row.values():
        if isinstance(f,dict) and 'source_updated_at' in f:
            f['source_updated_at']=updated
    return row


async def kakao(lon,lat,radius,query):
    params=dict(category_group_code='FD6',x=lon,y=lat,radius=radius,sort='distance',size=15,page=1)
    endpoint='category'
    if query:
        params['query']=query
        endpoint='keyword'
    # Coordinates are not included in logged errors and API key stays server-side.
    async with asyncio.timeout(15):
        payload=await s.request(f'https://dapi.kakao.com/v2/local/search/{endpoint}.json',params,
            headers={'Authorization':'KakaoAK '+s.key('KAKAO_REST_API_KEY')})
    if not isinstance(payload.get('documents'),list):
        raise s.Unavailable('Kakao trả định dạng không hợp lệ.')
    rows=[]
    checked=s.now().isoformat()
    for r in payload['documents']:
        if r.get('category_group_code') != 'FD6':
            continue
        source='https://place.map.kakao.com/'+str(r['id'])
        rows.append(candidate('kakao:'+str(r['id']),r.get('place_name'),r.get('road_address_name') or r.get('address_name'),
            r['x'],r['y'],source,checked))
    return rows, checked, not payload.get('meta',{}).get('is_end',True)


async def overpass(lon,lat,radius,query):
    q=f'[out:json][timeout:8];nwr(around:{radius},{lat},{lon})[amenity~"^(restaurant|fast_food)$"];out center meta 100;'
    async with asyncio.timeout(15):
        payload,checked,cached=await o.public_request('https://overpass-api.de/api/interpreter',{'data':q})
    if payload.get('remark') or not isinstance(payload.get('elements'),list):
        raise s.Unavailable('Overpass lỗi hoặc trả kết quả không đầy đủ.')
    rows=[]
    for r in payload['elements'][:100]:
        tags=r.get('tags',{})
        if tags.get('amenity') not in ('restaurant','fast_food'):
            continue
        name=tags.get('name:ko') or tags.get('name') or tags.get('name:en')
        names=' '.join(str(tags.get(k,'')) for k in ('name','name:ko','name:en','alt_name'))
        if query and normalise_query(query).casefold().replace(' ','') not in unicodedata.normalize('NFKC',names).casefold().replace(' ',''):
            continue
        xy=r.get('center',r)
        if 'lon' not in xy or 'lat' not in xy:
            continue
        source=f'https://www.openstreetmap.org/{r["type"]}/{r["id"]}'
        rows.append(candidate(f'osm:{r["type"]}:{r["id"]}',name,
            ', '.join(str(tags[k]) for k in ('addr:street','addr:housenumber','addr:city') if tags.get(k)),
            xy['lon'],xy['lat'],source,checked,tags.get('opening_hours'),tags.get('website:menu') or tags.get('contact:menu'),r.get('timestamp')))
    return rows,checked,len(payload['elements'])>=100


async def photon(lon,lat,radius,query):
    dy=radius/111000
    dx=radius/(111000*math.cos(math.radians(lat)))
    params={'lon':lon,'lat':lat,'limit':30,'osm_tag':['amenity:restaurant','amenity:fast_food']}
    endpoint='https://photon.komoot.io/reverse'
    if query:
        endpoint='https://photon.komoot.io/api/'
        params.update(q=query,bbox=f'{lon-dx},{lat-dy},{lon+dx},{lat+dy}')
    else:
        # Reverse category lookup does not require a generic word in the restaurant name.
        params['radius']=radius/1000
    # Do not force English output on Hangul names.
    async with asyncio.timeout(15):
        payload,checked,cached=await o.public_request(endpoint,params)
    if not isinstance(payload.get('features'),list):
        raise s.Unavailable('Photon trả định dạng không hợp lệ.')
    rows=[]
    for r in payload['features']:
        p=r.get('properties',{})
        if str(p.get('countrycode','')).upper()!='KR' or p.get('osm_key')!='amenity' or p.get('osm_value') not in ('restaurant','fast_food'):
            continue
        xy=r.get('geometry',{}).get('coordinates',[])
        typ={'N':'node','W':'way','R':'relation'}.get(p.get('osm_type'))
        if len(xy)!=2 or typ is None:
            continue
        source=f'https://www.openstreetmap.org/{typ}/{p["osm_id"]}'
        rows.append(candidate(f'osm:{typ}:{p["osm_id"]}',p.get('name'),
            ', '.join(str(p[k]) for k in ('housenumber','street','city') if p.get(k)),xy[0],xy[1],source,checked))
    return rows,checked,len(payload['features'])>=30


def attach_evidence(row):
    record, warning=e.record_payload(row['restaurant_id'])
    row.update(menu=record['menu'],menu_images=record['menu_images'],order_policy=record['policy'],
        rating=record['rating_out_of_five'],review_count=record['review_count'])
    for key in ('opening_hours','open_now'):
        if record[key]['value'] is not None:
            row[key]=record[key]
    if warning:
        row['evidence_warning']=warning
    return row


async def walking(row,lon,lat):
    if not os.getenv('ORS_API_KEY'):
        return  # No multiplying straight-line distance into a pretend walking route.
    x,y=row['longitude']['value'],row['latitude']['value']
    try:
        async with asyncio.timeout(12):
            payload=await s.request('https://api.heigit.org/openrouteservice/v2/directions/foot-walking',
                {'start':f'{lon},{lat}','end':f'{x},{y}'}, headers={'Authorization':s.key('ORS_API_KEY')})
        summary=payload['features'][0]['properties']['summary']
        distance,duration=float(summary['distance']),float(summary['duration'])
        if not all(math.isfinite(v) and v>=0 for v in (distance,duration)):
            raise ValueError()
        checked=s.now().isoformat()
        row['walking_distance_m']=e.fact(round(distance),ORS,checked,'Provider route estimate, not a measured walk; not live obstacles.')
        row['walking_duration_seconds']=e.fact(round(duration),ORS,checked,'Provider walking-time estimate.')
    except (s.Unavailable,TimeoutError,KeyError,TypeError,ValueError,IndexError):
        row['walking_distance_m']=e.fact(reason='Walking provider unavailable or route missing.')


async def search_nearby(longitude,latitude,radius=500,budget_krw_per_person=10000,party_size=1,query='',limit=15,include_walking=False):
    lon,lat=validate(longitude,latitude,radius,budget_krw_per_person,party_size,limit)
    query=normalise_query(query) if query.strip() else ''
    attempts=[]
    selected=[]
    provider=None
    truncated=False
    providers=[]
    if os.getenv('KAKAO_REST_API_KEY'):
        providers.append(('kakao',kakao))
    else:
        attempts.append({'provider':'kakao','status':'not_configured','reason':'KAKAO_REST_API_KEY absent'})
    providers += [('overpass',overpass),('photon',photon)]
    for name,fetch in providers:
        try:
            rows,checked,partial=await fetch(lon,lat,radius,query)
            filtered=[]
            ids=set()
            for row in rows:
                rid=restaurant_id(row['restaurant_id'])
                distance=metres(lon,lat,row['longitude']['value'],row['latitude']['value'])
                if distance>radius or rid in ids:
                    continue
                ids.add(rid)
                row['straight_line_distance_m']=e.fact(round(distance,1),row['longitude']['source_url'],checked,
                    'Haversine from mapped coordinates; not walking distance.')
                filtered.append(row)
            attempts.append({'provider':name,'status':'ok' if filtered else 'empty','checked_at':checked,'count':len(filtered),'truncated':partial})
            if filtered:
                selected,provider,truncated=filtered,name,partial
                break
        except (s.Unavailable,TimeoutError,ValueError,KeyError,TypeError,IndexError):
            attempts.append({'provider':name,'status':'error','reason':'Unavailable, timeout or malformed data; no result claims.'})
    selected.sort(key=lambda r:(r['straight_line_distance_m']['value'],r['restaurant_id']))
    truncated=truncated or len(selected)>limit
    selected=selected[:limit]
    for index,row in enumerate(selected):
        attach_evidence(row)
        await enrich_sources(row)
        x,y=row['longitude']['value'],row['latitude']['value']
        row['links']=o.google_links(query=(row['name']['value'] or 'restaurant')+' South Korea',
            origin=f'{lat},{lon}',destination=f'{y},{x}',mode='walking')['links']
        if include_walking and index<5:
            await walking(row,lon,lat)
        row['assessment']=assess(row,budget_krw_per_person,party_size)
        _seen[row['restaurant_id']]=(time.monotonic(),row)
        _seen.move_to_end(row['restaurant_id'])
        while len(_seen)>200:
            _seen.popitem(last=False)
    all_failed=all(a['status'] in ('error','not_configured') for a in attempts)
    return dict(status='ok' if selected else 'unavailable' if all_failed else 'no_data',data=selected,
        provider=provider,provider_attempts=attempts,fetched_at=s.now().isoformat(),timezone='Asia/Seoul',
        search={'longitude':lon,'latitude':lat,'radius_m':radius,'radius_kind':'straight_line','budget_krw_per_person':budget_krw_per_person,'party_size':party_size,'query':query},
        coverage='limited_provider_results_not_exhaustive',truncated=truncated,
        attribution='© OpenStreetMap contributors (ODbL) for OSM results; Kakao Local for Kakao results.',
        links=o.google_links(query=f'restaurants near {lat},{lon}')['links'],
        note='Bán kính là đường chim bay; không tự nới bán kính. Không có kết quả không có nghĩa là không có quán. Giá, giờ mở cửa và số suất chưa có bằng chứng sẽ là unknown. Chỉ tối đa 5 tuyến đi bộ khi đã cấu hình ORS.')


def is_verified(fact):
    return fact.get('status')=='verified' and fact.get('value') is not None


def assess(row,budget,party):
    """Confirm only complete explicit ordering constraints; distinguish portions from diners."""
    policy=row['order_policy']
    if party==1 and is_verified(policy['solo_allowed']) and policy['solo_allowed']['value'] is False:
        return dict(status='does_not_meet_verified_constraints',reason='Restaurant explicitly disallows solo diners.',total_krw=None)
    feasible=[]
    failures=[]
    for item in row['menu']:
        price,basis=item['price_krw'],item['price_basis']
        minimum=item['minimum_servings'] if item['minimum_servings']['value'] is not None else policy['minimum_servings']
        dish_name=item['name_ko'] if item['name_ko']['value'] is not None else item.get('name_original',e.fact())
        needed=[dish_name,price,basis,minimum,policy['one_item_per_person'],policy['minimum_order_krw'],policy['mandatory_extra_krw']]
        diners=item.get('minimum_diners',e.fact())
        if diners['value'] is not None:
            needed.append(diners)
            if is_verified(diners) and party<diners['value']:
                continue
        if party==1:
            needed.append(policy['solo_allowed'])
        if basis['value']=='per_set':
            needed.append(item['serves_people'])
        if not all(is_verified(f) for f in needed):
            continue
        portions=max(1,minimum['value'],party if policy['one_item_per_person']['value'] else 1)
        if basis['value']=='per_person':
            portions=max(portions,party)
        elif basis['value']=='per_set':
            portions=max(portions,math.ceil(party/item['serves_people']['value']))
        minimum_order=policy['minimum_order_krw']['value']
        if price['value']==0 and minimum_order>0:
            continue
        if price['value']>0:
            portions=max(portions,math.ceil(minimum_order/price['value']))
        total=portions*price['value']+policy['mandatory_extra_krw']['value']
        option=dict(item_name_ko=item['name_ko'],item_name_original=dish_name,quantity=portions,total_krw=total,per_person_krw=total/party)
        (feasible if total<=budget*party else failures).append(option)
    if feasible:
        best=min(feasible,key=lambda r:r['total_krw'])
        return dict(status='meets_verified_constraints',**best,
            reason='Fits reviewed menu and ordering constraints only; prices may change, opening status checked separately.')
    # Expensive known items do not prove the whole menu is unaffordable.
    return dict(status='insufficient_evidence',total_krw=None,known_over_budget_options=failures,
        reason='No fully verified affordable option. Unknown prices/policies are not assumed cheap or solo-friendly.')


async def rank(*args,**kwargs):
    result=await search_nearby(*args,**kwargs)
    group={'meets_verified_constraints':0,'insufficient_evidence':1,'does_not_meet_verified_constraints':2}
    use_walking=bool(result['data']) and all(r['walking_distance_m']['value'] is not None for r in result['data'])
    distance_field='walking_distance_m' if use_walking else 'straight_line_distance_m'
    def score(row):
        # No invented star ratings; only reviewed, source-backed ratings break distance ties.
        quality=row['rating']
        rating=-quality['value'] if is_verified(quality) else 0
        return (group[row['assessment']['status']],row[distance_field]['value'],
                0 if is_verified(quality) else 1,rating,row['restaurant_id'])
    result['data'].sort(key=score)
    result['ranking_method']='verified_budget_and_order_constraints_then_'+distance_field+'_then_verified_quality_tiebreak_then_id'
    result['ranking_limitations']='Walking distances and source-backed ratings are displayed separately, not mixed with geodesic distances or invented quality scores. Unknown evidence is never a confirmed recommendation.'
    for i,row in enumerate(result['data'],1):
        row['rank']=i
    return result


def details(rid,kind):
    restaurant_id(rid)
    record,warning=e.record_payload(rid)
    hit=_seen.get(rid)
    row=hit[1] if hit and time.monotonic()-hit[0]<3600 else None
    if kind=='menu':
        data={'items':record['menu'],'images':record['menu_images'],'menu_link':row['menu_link'] if row else e.fact()}
        status='ok' if record['menu'] else 'unknown'
    else:
        data=record['policy']
        status='ok' if all(is_verified(f) for f in data.values()) else 'partial' if any(is_verified(f) for f in data.values()) else 'unknown'
    return dict(status=status,restaurant_id=rid,data=data,fetched_at=s.now().isoformat(),
        evidence_warning=warning,note='Không suy quy định gọi món từ tên quán, loại món hoặc giá menu. Tên Việt chỉ có nếu đã có bản dịch ghi nguồn; link/ảnh không đồng nghĩa nội dung đã được đọc.')


async def enrich_sources(row):
    from . import menu_sources as ms
    try:
        profile=ms.profile_for(row['restaurant_id'])
        if profile is not None:
            record,meta=await ms.read_source(row['restaurant_id'])
            # Reviewed local data wins; automatic published data never becomes verified.
            if not row['menu']:row['menu']=record['menu']
            if not row['menu_images']:row['menu_images']=record['menu_images']
            for key,value in record['policy'].items():
                if row['order_policy'][key]['value'] is None:row['order_policy'][key]=value
            row['source_metadata']=meta
            row['ordering_notes']=record['ordering_notes']
        else:
            name=row['name']['value']
            if name:
                row['possible_menu_sources']=ms.find(query=name)['data']
                # These are suggestions, not identity matches; no facts are merged.
    except s.Unavailable:
        row['source_warning']='Menu source catalog unavailable; no additional claims.'
    return row


async def details_with_sources(rid,kind):
    from . import menu_sources as ms
    restaurant_id(rid)
    local=details(rid,kind)
    try:
        profile=ms.profile_for(rid)
        if profile is not None:
            external=await ms.details(rid,kind)
            if kind=='menu' and local['data']['items']:
                local['source_items']=external['data']
                local['source_metadata']=external['source']
                return local
            if kind=='policy':
                for key,value in local['data'].items():
                    if value['value'] is not None:external['data'][key]=value
            return external
        hit=_seen.get(rid)
        if hit and time.monotonic()-hit[0]<3600 and hit[1]['name']['value']:
            local['possible_sources']=ms.find(query=hit[1]['name']['value'])['data']
    except s.Unavailable as exc:
        local['source_warning']=str(exc)
    return local
