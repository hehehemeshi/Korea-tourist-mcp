"""Bounded keyless source adapters; published quotes are not current restaurant verification.

Only URLs in an operator-controlled catalog are fetched. No caller-supplied URLs,
no login, search-result scraping, image OCR or automatic branch identity matching.
"""
import asyncio
import copy
import ipaddress
import json
import os
import re
import time
import unicodedata
from collections import OrderedDict
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator
from . import evidence as e, service as s, open_data as o

class Profile(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    restaurant_id: str = Field(pattern=r'^source:[a-z0-9-]+$')
    name: str
    address: str | None = None
    aliases: list[str] = Field(default_factory=list)
    kind: str = Field(pattern=r'^(suwon_table|kto_article|merchant_jsonld)$')
    source_url: str
    published_on: str | None = None
    discovery_method: str
    snapshot: e.RestaurantEvidence
    bindings: list[str] = Field(default_factory=list)

    @field_validator('source_url')
    @classmethod
    def public_https(cls,value):
        p=urlparse(value)
        host=(p.hostname or '').lower()
        if not e.https_url(value) or p.port not in (None,443) or '.' not in host or host.endswith(('.local','.localhost','.internal')):
            raise ValueError('Only operator-approved public HTTPS URLs are allowed.')
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return value
        raise ValueError('IP-address URLs not allowed.')

class Catalog(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    restaurants: list[Profile] = Field(default_factory=list,max_length=2000)


def catalog():
    path=os.getenv('RESTAURANT_SOURCE_CATALOG') or str(Path(__file__).parent/'data'/'restaurant_sources.json')
    try:
        result=Catalog.model_validate_json(Path(path).read_text())
        ids=[p.restaurant_id for p in result.restaurants]
        bindings=[b for p in result.restaurants for b in p.bindings]
        if len(ids)!=len(set(ids)) or len(bindings)!=len(set(bindings)) or any(p.snapshot.restaurant_id!=p.restaurant_id for p in result.restaurants):
            raise ValueError('Conflicting source identities')
        return result.restaurants
    except (ValueError,OSError):
        raise s.Unavailable('Danh mục nguồn menu không hợp lệ hoặc chưa được cấu hình.') from None


def folded(value):
    return ''.join(unicodedata.normalize('NFKC',value).casefold().split())


def profile_for(rid):
    return next((p for p in catalog() if rid==p.restaurant_id or rid in p.bindings),None)


def find(query='',restaurant_id=''):
    q=folded(o.query_text(query)) if query.strip() else ''
    profiles=catalog()
    if restaurant_id:
        profiles=[p for p in profiles if restaurant_id==p.restaurant_id or restaurant_id in p.bindings]
    if q:
        profiles=[p for p in profiles if any(q in folded(v) for v in [p.name,p.address or '',*p.aliases])]
    if not q and not restaurant_id:
        profiles=profiles[:30]
    rows=[]
    for p in profiles[:30]:
        rows.append(dict(restaurant_id=p.restaurant_id,name=e.fact(p.name,p.source_url),address=e.fact(p.address,p.source_url),
            source_url=p.source_url,provider=p.kind,published_on=p.published_on,
            discovery_method=p.discovery_method,has_listed_menu=bool(p.snapshot.menu),
            has_explicit_order_notes=bool(p.snapshot.ordering_notes or any(i.minimum_servings.value is not None or i.minimum_diners.value is not None for i in p.snapshot.menu)),
            identity='catalog_entry_only' if not restaurant_id or restaurant_id==p.restaurant_id else 'operator_reviewed_binding'))
    return dict(status='ok' if rows else 'no_data',data=rows,fetched_at=s.now().isoformat(),
        note='Nguồn đã tìm được, chưa phải giá/quy định hiện tại đã xác minh tại quán. Không tự ghép quán trùng tên hoặc áp dụng menu chuỗi cho mọi chi nhánh.')


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows=[];self.current_row=None;self.current_cell=None
        self.images=[];self.visible=[];self.scripts=[];self.script=None;self.hidden=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='script':
            self.hidden+=1
            if a.get('type','').split(';')[0].lower()=='application/ld+json':self.script=[]
        elif tag in ('style','noscript'):self.hidden+=1
        if tag=='tr':self.current_row=[]
        if tag in ('td','th') and self.current_row is not None:self.current_cell=[]
        if tag=='br' and self.current_cell is not None:self.current_cell.append('\n')
        if tag=='img' and not self.hidden:self.images.append(a)
    def handle_endtag(self,tag):
        if tag=='script':
            if self.script is not None:
                try:self.scripts.append(json.loads(''.join(self.script)))
                except (ValueError,TypeError):pass
            self.script=None;self.hidden=max(0,self.hidden-1)
        elif tag in ('style','noscript'):self.hidden=max(0,self.hidden-1)
        if tag in ('td','th') and self.current_cell is not None:
            self.current_row.append(' '.join(self.current_cell).strip());self.current_cell=None
        if tag=='tr' and self.current_row is not None:
            self.rows.append(self.current_row);self.current_row=None
    def handle_data(self,data):
        if self.script is not None:self.script.append(data)
        if not self.hidden:
            self.visible.append(data)
            if self.current_cell is not None:self.current_cell.append(data)

_cache=OrderedDict()
_lock=asyncio.Lock()
_last=0.0
_day=None
_calls=0

async def fetch_page(profile):
    """Operator URL allowlist, no redirects, 2 MB cap, 2s spacing, 100/day, 1h cache."""
    global _last,_day,_calls
    approved={p.source_url for p in catalog()}
    if profile.source_url not in approved:raise s.Unavailable('URL không nằm trong danh mục nguồn được duyệt.')
    async with asyncio.timeout(16):
        async with _lock:
            now=time.monotonic()
            hit=_cache.get(profile.source_url)
            if hit and now-hit[0]<3600:
                _cache.move_to_end(profile.source_url)
                return hit[1],hit[2],True
            if _day!=date.today():_day,_calls=date.today(),0
            if _calls>=100:raise s.Unavailable('Đã đạt hạn mức tải nguồn menu hôm nay.')
            if now-_last<2:await asyncio.sleep(2-(now-_last))
            _last=time.monotonic();_calls+=1
            try:
                async with httpx.AsyncClient(timeout=12,follow_redirects=False) as client:
                    async with client.stream('GET',profile.source_url,headers={'User-Agent':o.USER_AGENT,'Accept':'text/html'}) as response:
                        response.raise_for_status()
                        if response.is_redirect or 'text/html' not in response.headers.get('content-type','').lower():
                            raise ValueError('Expected HTML without redirect')
                        body=bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body)>2_000_000:raise ValueError('Source too large')
                        html=body.decode(response.encoding or 'utf-8',errors='replace')
            except (httpx.HTTPError,ValueError):
                raise s.Unavailable('Nguồn menu không phản hồi hoặc định dạng đã thay đổi.') from None
            checked=s.now().isoformat()
            _cache[profile.source_url]=(time.monotonic(),html,checked)
            while len(_cache)>64:_cache.popitem(last=False)
            return html,checked,False


def source_fact(value,profile,checked,excerpt,method='government_listing'):
    f=e.fact(value,profile.source_url,checked,'Published source information; restaurant price/policy not independently confirmed now.')
    f.update(method=method,evidence_excerpt=excerpt[:2000],attribution='Suwon City' if profile.kind=='suwon_table' else 'Korea Tourism Organization' if profile.kind=='kto_article' else 'Restaurant website')
    return f


def clean_record(rid):
    return e.normalise_record(e.RestaurantEvidence(restaurant_id=rid))


def suwon_table(profile,page,checked):
    fields={row[0].strip():row[1].strip() for row in page.rows if len(row)==2}
    text=' '.join(page.visible)+' '+' '.join(i.get('alt','') for i in page.images)
    if folded(profile.name) not in folded(text):raise ValueError('Restaurant identity missing')
    if profile.address and folded(profile.address) not in folded(fields.get('주소','')):
        raise ValueError('Address does not match reviewed source identity')
    raw=fields.get('대표메뉴','')
    items=[]
    # Named fixed KRW prices only. No ranges, from-prices, market prices or unit guesses.
    for match in re.finditer(r'([^,;\n]+?)\s+([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\s*원',raw):
        name,price=match.group(1).strip(),int(match.group(2).replace(',',''))
        if not name or any(v in name for v in ('~','부터','추가','시가','가격변동','원')):continue
        item={k:e.fact() for k in e.MenuItem.model_fields}
        item['name_ko']=source_fact(name,profile,checked,match.group(0))
        item['name_original']=source_fact(name,profile,checked,match.group(0))
        item['price_krw']=source_fact(price,profile,checked,match.group(0))
        items.append(item)
    if not items:raise ValueError('No fixed menu prices in the restaurant table')
    result=clean_record(profile.restaurant_id);result['menu']=items
    return result


def types(node,kind):
    value=node.get('@type',[])
    return kind in ([value] if isinstance(value,str) else value)


def objects(value):
    if isinstance(value,dict):
        yield value
        for v in value.values():yield from objects(v)
    elif isinstance(value,list):
        for v in value:yield from objects(v)


def exact_money(value):
    if isinstance(value,bool):return None
    if not re.fullmatch(r'(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.0+)?',str(value)):return None
    try:
        d=Decimal(str(value).replace(',',''))
        return int(d) if 0<=d<=10_000_000 and d==int(d) else None
    except (InvalidOperation,ValueError):return None


def merchant_jsonld(profile,page,checked):
    nodes=list(objects(page.scripts))
    owners=[n for n in nodes if types(n,'Restaurant')]
    if len(owners)!=1 or folded(owners[0].get('name',''))!=folded(profile.name):
        raise ValueError('No unique matching restaurant identity')
    address=owners[0].get('address',{})
    street=address.get('streetAddress','') if isinstance(address,dict) else address
    if not profile.address or folded(street)!=folded(profile.address):
        raise ValueError('Exact branch street address required')
    result=clean_record(profile.restaurant_id)
    for node in nodes:
        if not types(node,'MenuItem') or not isinstance(node.get('name'),str):continue
        offers=node.get('offers',{})
        if isinstance(offers,list):
            if len(offers)!=1:continue
            offers=offers[0]
        if not isinstance(offers,dict) or offers.get('priceCurrency')!='KRW':continue
        price=exact_money(offers.get('price'))
        if price is None:continue
        item={k:e.fact() for k in e.MenuItem.model_fields}
        excerpt=json.dumps({'name':node['name'],'offers':offers},ensure_ascii=False)[:2000]
        item['name_original']=source_fact(node['name'],profile,checked,excerpt,'provider_response')
        if re.search('[가-힣]',node['name']):item['name_ko']=copy.deepcopy(item['name_original'])
        item['price_krw']=source_fact(price,profile,checked,excerpt,'provider_response')
        # Explicit named structured constraints only; a 2-serving set isn't a 2-serving minimum.
        for prop in node.get('additionalProperty',[]) if isinstance(node.get('additionalProperty'),list) else []:
            if not isinstance(prop,dict):continue
            name,value=prop.get('name'),prop.get('value')
            if name in ('minimum_servings','minimum_diners') and type(value) is int and value>=1:
                item[name]=source_fact(value,profile,checked,json.dumps(prop,ensure_ascii=False),'provider_response')
        result['menu'].append(item)
    for prop in owners[0].get('additionalProperty',[]) if isinstance(owners[0].get('additionalProperty'),list) else []:
        if not isinstance(prop,dict):continue
        name,value=prop.get('name'),prop.get('value')
        valid=(name in ('one_item_per_person','solo_allowed') and type(value) is bool) or (name in ('minimum_servings','minimum_order_krw','mandatory_extra_krw') and type(value) is int and value>=(1 if name=='minimum_servings' else 0))
        if valid:result['policy'][name]=source_fact(value,profile,checked,json.dumps(prop,ensure_ascii=False),'provider_response')
    if not result['menu'] and all(v['value'] is None for v in result['policy'].values()):raise ValueError('No supported menu/policy data')
    return result


def add_menu_images(record,profile,page,checked):
    for image in page.images:
        # A dish photo or an unlabelled article image is not a menu-board photo.
        if not re.search(r'메뉴판|가격표|menu\s*(?:board|price)',image.get('alt',''),re.I):continue
        url=urljoin(profile.source_url,image.get('src',''))
        if e.https_url(url):record['menu_images'].append(source_fact(url,profile,checked,image['alt']))
        if len(record['menu_images'])>=10:break


async def read_source(rid,refresh=True):
    profile=profile_for(rid)
    if not profile:raise s.Unavailable('Chưa có nguồn được liên kết với restaurant_id này.')
    record=e.normalise_record(profile.snapshot)
    metadata={'provider':profile.kind,'source_url':profile.source_url,'published_on':profile.published_on,
        'discovery_method':profile.discovery_method,'identity':'catalog_entry_only' if rid==profile.restaurant_id else 'operator_reviewed_binding',
        'refresh_status':'not_requested','cached':False}
    if refresh:
        try:
            html,checked,cached=await fetch_page(profile)
            page=Page();page.feed(html)
            if profile.kind=='suwon_table':record=suwon_table(profile,page,checked)
            elif profile.kind=='merchant_jsonld':record=merchant_jsonld(profile,page,checked)
            else:
                visible=folded(' '.join(page.visible))
                if folded(profile.name) not in visible or (profile.address and folded(profile.address) not in visible):
                    raise ValueError('Source restaurant identity no longer present')
                # Recheck each short reviewed quote; never copy statements from another section.
                for item in record['menu']:
                    for key,f in item.items():
                        if f['value'] is not None and f.get('evidence_excerpt') and folded(f['evidence_excerpt']) in visible:
                            f['checked_at']=checked
                        elif f['value'] is not None:
                            f['reason']='Reviewed quote not present on current page; historical snapshot only.'
                for f in record['ordering_notes']:
                    if f.get('evidence_excerpt') and folded(f['evidence_excerpt']) in visible:f['checked_at']=checked
            add_menu_images(record,profile,page,checked)
            metadata.update(refresh_status='fetched',retrieved_at=checked,cached=cached)
        except (s.Unavailable,TimeoutError,ValueError,TypeError,KeyError):
            metadata['refresh_status']='unavailable_snapshot_only'
    return record,metadata


async def details(rid,kind,refresh=True):
    record,metadata=await read_source(rid,refresh)
    if kind=='menu':
        data={'items':record['menu'],'images':record['menu_images'],'menu_link':e.fact(metadata['source_url'],metadata['source_url'])}
    else:
        data=record['policy']
    has_values=bool(record['menu']) if kind=='menu' else bool(record['ordering_notes']) or any(v['value'] is not None for v in record['policy'].values()) or any(i['minimum_servings']['value'] is not None or i['minimum_diners']['value'] is not None for i in record['menu'])
    item_rules=[{'item_name':i['name_original'] if i['name_original']['value'] is not None else i['name_ko'],
        'minimum_servings':i['minimum_servings'],'minimum_diners':i['minimum_diners']} for i in record['menu'] if i['minimum_servings']['value'] is not None or i['minimum_diners']['value'] is not None]
    return dict(status='partial' if has_values else 'unknown',restaurant_id=rid,data=data,ordering_notes=record['ordering_notes'],item_policies=item_rules,
        source=metadata,fetched_at=s.now().isoformat(),
        note='Thông tin nguồn công bố, chưa xác nhận giá/quy định hiện tại tại quán. Giữ nguyên giới hạn từng món; không suy khách tối thiểu từ số suất hoặc suy chính sách từ menu.')
