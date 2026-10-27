"""Vietnamese restaurant output contract. Coordinates come from the caller, not GPS."""
import base64
import copy
import json
import math
import os
from urllib.parse import urlencode, urlparse

MISSING = 'Chưa có thông tin'
UI_URI = 'ui://korea-tourist/restaurants-v1.html'
GLOSSARY = {
    '칼국수':'Mì cắt dao', '수제비':'Canh bột mì xé', '콩국수':'Mì sữa đậu nành',
    '김밥':'Cơm cuộn', '떡볶이':'Bánh gạo sốt cay', '라면':'Mì ramyeon',
    '냉면':'Mì lạnh', '비빔밥':'Cơm trộn', '돈까스':'Thịt heo tẩm bột chiên',
    '김치찌개':'Canh kimchi', '된장찌개':'Canh tương đậu nành', '순두부찌개':'Canh đậu hũ non cay',
}

def value(fact):
    return fact.get('value') if isinstance(fact,dict) else fact

def show(fact):
    v=value(fact)
    return MISSING if v is None or v=='' else str(v)

def safe_url(url):
    if not isinstance(url,str):return None
    try:
        p=urlparse(url)
        return url if p.scheme=='https' and p.hostname and not p.username and not p.password else None
    except ValueError:return None

def coords(lon,lat):
    try:
        x,y=float(value(lon)),float(value(lat))
        return [x,y] if math.isfinite(x) and math.isfinite(y) and -180<=x<=180 and -85<=y<=85 else None
    except (TypeError,ValueError):return None

def provenance(fact):
    if not isinstance(fact,dict):return {'status':'unknown','source_url':None,'checked_at':None}
    return {key:fact.get(key) for key in ('status','source_url','checked_at','source_updated_at','method')}

def numeric(fact):
    v=value(fact)
    return v if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0 else None

def money(fact):
    n=numeric(fact)
    return MISSING if n is None else '₩'+format(n,',.0f')

def distance(fact):
    n=numeric(fact)
    return MISSING if n is None else f'{n:,.0f} m'

def menu_card(item):
    ko=show(item.get('name_ko'))
    original=show(item.get('name_original'))
    vi=show(item.get('name_vi'))
    method='provided' if vi!=MISSING else 'unknown'
    if vi==MISSING and ko in GLOSSARY:
        vi,method=GLOSSARY[ko],'literal_glossary_translation'
    basis=value(item.get('price_basis'))
    return dict(name_ko=ko,name_original=original,name_vi=vi,translation_method=method,
        price_krw=numeric(item.get('price_krw')),price_display=money(item.get('price_krw')),
        price_basis={'per_serving':'/suất','per_person':'/người','per_set':'/set'}.get(basis,MISSING),
        price_evidence=provenance(item.get('price_krw')),
        name_evidence=provenance(item.get('name_ko')),
        translation_evidence=provenance(item.get('name_vi')) if method=='provided' else {'status':'unverified','method':method},
        minimum_servings=show(item.get('minimum_servings')),minimum_diners=show(item.get('minimum_diners')))

def review_card(row):
    highlights=[]
    for f in row.get('review_highlights',[]):
        if isinstance(f,dict) and f.get('value') and safe_url(f.get('source_url')):
            highlights.append({'text':str(f['value']),'evidence':provenance(f)})
    rating=numeric(row.get('rating'))
    count=numeric(row.get('review_count'))
    if rating is not None and rating>5:rating=None
    if count is not None and count!=int(count):count=None
    return dict(rating=rating,rating_display=MISSING if rating is None else f'{rating:g}/5',
        review_count=count,review_count_display=MISSING if count is None else f'{count:,.0f}',
        summary='; '.join(h['text'] for h in highlights) if highlights else MISSING,
        highlights=highlights,rating_evidence=provenance(row.get('rating')),
        count_evidence=provenance(row.get('review_count')))

def walking_link(origin,destination):
    if origin is None or destination is None:return None
    return 'https://www.google.com/maps/dir/?'+urlencode({'api':1,
        'origin':f'{origin[1]},{origin[0]}','destination':f'{destination[1]},{destination[0]}','travelmode':'walking'})

def format_result(result):
    """Keep machine evidence, add canonical nearest-first cards, GeoJSON and Markdown."""
    out=copy.deepcopy(result)
    search=out.get('search',{})
    origin=coords(search.get('longitude'),search.get('latitude'))
    rows=out.get('data',[])
    if not isinstance(rows,list):rows=[]
    rows.sort(key=lambda r:(numeric(r.get('straight_line_distance_m')) is None,
        numeric(r.get('straight_line_distance_m')) if numeric(r.get('straight_line_distance_m')) is not None else float('inf'),
        str(r.get('restaurant_id',''))))
    out['display_truncated']=len(rows)>10
    out['data']=rows[:10]
    cards=[];features=[]
    if origin:
        features.append({'type':'Feature','geometry':{'type':'Point','coordinates':origin},
            'properties':{'kind':'origin','name':'Vị trí ChatGPT cung cấp'}})
    for i,row in enumerate(out['data'],1):
        xy=coords(row.get('longitude'),row.get('latitude'))
        link=walking_link(origin,xy)
        card=dict(number=i,restaurant_id=row.get('restaurant_id'),name=show(row.get('name')),
            address=show(row.get('address')),coordinates=xy,
            distance_display=distance(row.get('straight_line_distance_m')),
            distance_kind='straight_line',distance_evidence=provenance(row.get('straight_line_distance_m')),
            walking_distance_display=distance(row.get('walking_distance_m')),
            walking_directions_url=link,
            menu=[menu_card(item) for item in row.get('menu',[])],
            reviews=review_card(row),assessment=row.get('assessment'),
            name_evidence=provenance(row.get('name')),address_evidence=provenance(row.get('address')))
        cards.append(card)
        if xy:
            features.append({'type':'Feature','geometry':{'type':'Point','coordinates':xy},
                'properties':{'kind':'restaurant','number':i,'restaurant_id':card['restaurant_id'],
                    'name':card['name'],'address':card['address'],'walking_directions_url':link}})
    collection={'type':'FeatureCollection','features':features}
    compact={'origin':origin,'restaurants':[{'number':c['number'],'name':c['name'],'coordinates':c['coordinates']} for c in cards if c['coordinates']]}
    fragment=base64.urlsafe_b64encode(json.dumps(compact,ensure_ascii=False,separators=(',',':')).encode()).decode().rstrip('=')
    base=os.getenv('PUBLIC_BASE_URL','https://seoul-transit-mcp.onrender.com').rstrip('/')
    if not safe_url(base):base='https://seoul-transit-mcp.onrender.com'
    report=dict(restaurants=cards,missing_label=MISSING,sort_order='straight_line_distance_ascending',limit=10,
        location_source='caller_chatgpt',map=collection,map_url=base+'/restaurant-map#'+fragment,
        fetched_at=out.get('fetched_at'),status=out.get('status'),message=out.get('message'),notice='Khoảng cách là đường chim bay, không phải đường đi bộ. Giá/đánh giá chưa xác minh sẽ giữ nhãn nguồn. Bản dịch tên món không xác nhận thành phần hoặc dị ứng.')
    out['presentation']=report
    if 'ranking_method' in out:out['assessment_ranking_method']=out['ranking_method']
    out['ranking_method']='display_nearest_first_straight_line_distance'
    out['markdown']=markdown(report)
    return out

def escape(text):
    return str(text).replace('\\','\\\\').replace('|','\\|').replace('\n',' ').replace('\r',' ').replace('<','&lt;').replace('>','&gt;').replace('[','\\[').replace(']','\\]')

def markdown(report):
    lines=[f"Tìm được {len(report['restaurants'])} quán — gần đến xa (đường chim bay), tối đa 10 quán.",
        f"[Bản đồ chung]({report['map_url']})",f"Truy vấn lúc: {escape(report.get('fetched_at') or MISSING)}"]
    if report.get('message'):lines.append(escape(report['message']))
    if report.get('status') in ('unavailable','error'):lines.append('Nguồn hiện không khả dụng; đây không phải xác nhận khu vực không có quán.')
    for c in report['restaurants']:
        lines += ['',f"### {c['number']}. {escape(c['name'])}",
            f"- Khoảng cách: {c['distance_display']} (đường chim bay). Đi bộ: {c['walking_distance_display']}.",
            f"- Địa chỉ: {escape(c['address'])}",
            f"- [Chỉ đường đi bộ]({c['walking_directions_url']})" if c['walking_directions_url'] else f'- Chỉ đường đi bộ: {MISSING}',
            '', '| Món tiếng Hàn | Tiếng Việt | Giá KRW | Đơn vị |','|---|---|---:|---|']
        for item in c['menu'] or [None]:
            if item is None:lines.append(f'| {MISSING} | {MISSING} | {MISSING} | {MISSING} |');continue
            price=item['price_display']
            if price!=MISSING and item['price_evidence']['status']!='verified':price+=' (chưa xác minh hiện tại)'
            lines.append('| '+' | '.join(escape(v) for v in [item['name_ko'],item['name_vi'],price,item['price_basis']])+' |')
        review=c['reviews']
        lines += ['',f"- Điểm đánh giá: {review['rating_display']}",f"- Số lượt đánh giá: {review['review_count_display']}",f"- Nhận xét nổi bật: {escape(review['summary'])}"]
        if review['rating'] is not None and review['rating_evidence']['status']!='verified':lines.append('- Điểm đánh giá chưa xác minh hiện tại.')
        sources=[]
        for f in [c['name_evidence'],c['address_evidence'],review['rating_evidence'],review['count_evidence'],*[v['price_evidence'] for v in c['menu']],*[h['evidence'] for h in review['highlights']]]:
            url=safe_url(f.get('source_url'))
            pair=(url,f.get('checked_at'))
            if url and pair not in sources:sources.append(pair)
        for url,checked in sources:
            lines.append(f"- [Nguồn](<{url.replace('<','%3C').replace('>','%3E')}>) · Kiểm tra: {escape(checked or MISSING)}")
    lines += ['',report['notice']]
    return '\n'.join(lines)
