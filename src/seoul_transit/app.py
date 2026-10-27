import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastmcp import FastMCP
from . import presentation as view
from .widget import TouristMCP, TOOL_META, UI_META, BUS_UI_META, html as restaurant_html, tool_result
from . import service as s
from .routing import plan
from . import travel as t
from . import discovery as d, open_data as o
from . import restaurants as food, menu_sources as menus
from . import bus_router as buses

mcp = TouristMCP('Du lịch Hàn Quốc — Tiếng Việt', instructions='Explain in Vietnamese. For bus requests use search_bus_routes then get_bus_route_map automatically. Never default to Suwon, Gyeonggi or any region. Use the explicit requested city/province, otherwise caller-provided coordinates. Missing/ambiguous region requires clarification. Unsupported regions must be reported, never substituted with Seoul/GBIS. Follow source-scoped route IDs; vehicle accuracy and observation time are source-specific. Preserve partial coverage and staleness. ChatGPT supplies the location context; MCP uses caller-provided coordinates and must not try to acquire device GPS. For restaurant results follow presentation.restaurants: show at most 10, nearest first, inline Korean/Vietnamese menu and KRW prices, rating/count/source-backed review highlights, address and walking links, and the shared map. Missing fields must say Chưa có thông tin; never invent review summaries. Do not replace inline menu with a link. Prefer open data and Google Maps hand-off links. Links are not retrieved search results or verified routes. Never invent arrivals, transfers, platforms, menu prices or restaurant ordering policies. Distinguish unknown restaurant evidence from verified budget compatibility. Never infer minimum servings from a dish name. Geodesic distance is not walking distance. Timetables and community map data are not live. Preserve sources, timestamps, cached state and limitations.')

async def safe(fn, *args):
    try:
        value = fn(*args)
        if hasattr(value, '__await__'):
            value = await value
        return value
    except (s.Unavailable, ValueError) as exc:
        return dict(status='unavailable', data=[], message=str(exc), fetched_at=s.now().isoformat())
    except (KeyError, TypeError, OSError):
        return dict(status='unavailable', data=[], message='Cấu hình hoặc định dạng nguồn không hợp lệ.', fetched_at=s.now().isoformat())

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True})
async def search_stations(query: str):
    """Search railway stations in South Korea using OSM/Photon first. Community coverage; no official station IDs or live data."""
    return await safe(d.stations, query)

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True})
async def get_arrivals(station: str):
    """Official Seoul arrivals with direction and freshness; Korean station name required. No verified platform feed."""
    return await safe(s.arrivals, station)

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True})
async def plan_route(origin: str, destination: str):
    """Return a Google Maps transit directions link for station names. No route or ETA is retrieved. If NETWORK_FILE is configured, plan its verified static graph instead."""
    return await safe(d.route, origin, destination)

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True})
async def search_rail_stations(city_code: str = '11'):
    """Official TAGO railway station IDs, including KORAIL. City code 11 is Seoul."""
    return await safe(s.rail_stations, city_code)

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True})
async def get_rail_schedule(origin: str, destination: str, date: str):
    """TAGO direct train timetable; date YYYYMMDD; use TAGO nodeid. Never real-time arrivals."""
    return await safe(s.rail_schedule, origin, destination, date)

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True})
async def search_tourism(query: str, page: int = 1):
    """Open-data-first place discovery via OSM/Photon in Korea. Not live opening status; Google links included."""
    return await safe(d.tourism, query, page)

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True})
async def nearby_tourism(longitude: float, latitude: float, radius: int = 2000, page: int = 1):
    """Nearby OSM attractions, restaurants and stays in Korea. WGS84 longitude,latitude; radius at most 5000 metres. Community data, not live."""
    return await safe(d.nearby, longitude, latitude, radius, page)

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True})
async def tourism_detail(content_id: str):
    """Read official KTO details using a contentid returned by tourism search."""
    return await safe(t.tourism_detail, content_id)

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True})
async def search_festivals(start_date: str, page: int = 1):
    """Google search links for festivals from YYYYMMDD unless KTO is explicitly enabled. Links are not verified event listings."""
    return await safe(d.festivals, start_date, page)

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True})
async def search_stays(area_code: str = '', page: int = 1):
    """Google hotel search links unless KTO is explicitly enabled. No availability or booking guarantees; KTO area codes only apply to KTO."""
    return await safe(d.stays, area_code, page)

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True})
async def search_places(query: str, page: int = 1):
    """OSM/Photon place search first, with Google Maps links. Kakao optional if OPEN_DATA_FIRST=false and key configured."""
    return await safe(d.places, query, page)

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True})
async def geocode_address(address: str):
    """OSM/Photon search for Korean addresses and coordinates. Naver optional if OPEN_DATA_FIRST=false and keys configured."""
    return await safe(d.geocode, address)

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True})
async def get_driving_route(origin: str, destination: str):
    """Google Maps driving link using place names or latitude,longitude; no route or fare retrieved. Optional Naver mode uses longitude,latitude."""
    return await safe(d.driving, origin, destination)

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})
async def get_google_maps_links(query: str = '', origin: str = '', destination: str = '', mode: str = 'transit'):
    """Build keyless Google Maps/search URLs. No API request, result scraping, live arrival or platform claims."""
    return await safe(o.google_links, query, origin, destination, mode)

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True}, meta=TOOL_META)
async def search_nearby_restaurants(longitude: float, latitude: float, radius: int = 500,
    budget_krw_per_person: int = 10000, party_size: int = 1, query: str = '', limit: int = 10, include_walking: bool = False):
    """Use the location ChatGPT supplies as WGS84 longitude,latitude; do not acquire device GPS. Return inline Vietnamese cards and a common map for up to 10 restaurants within the requested radius, nearest first, including Korean/Vietnamese menu, KRW prices and source-backed review fields. Kakao FD6 if keyed, then Overpass, then Photon. Radius is geodesic, not walking. Never infer menu prices, solo rules, live opening or minimum portions. Each fact has source/time/verification. include_walking uses optional ORS for at most 5 places. Does not access phone GPS."""
    result = await safe(food.search_nearby, longitude, latitude, radius, budget_krw_per_person, party_size, query, limit, include_walking)
    return tool_result(view.format_result(result))

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})
async def get_restaurant_menu(restaurant_id: str):
    """Read reviewed registry plus mapped municipal/KTO/merchant menu sources. Use source: IDs from get_restaurant_sources, or operator-bound OSM/Kakao IDs. Listed historical prices remain unverified; no key needed for public sources. No guessed price, translation, photo or branch match."""
    return await safe(food.details_with_sources, restaurant_id, 'menu')

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})
async def get_order_policy(restaurant_id: str):
    """Read explicit registry or source-backed evidence for minimum servings, minimum diners, one item/person, solo allowance and minimum bill. Minimum servings is not minimum diners. Unknown if not separately verified; never infer from menu or cuisine."""
    return await safe(food.details_with_sources, restaurant_id, 'policy')

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True}, meta=TOOL_META)
async def rank_restaurants(longitude: float, latitude: float, radius: int = 500,
    budget_krw_per_person: int = 10000, party_size: int = 1, query: str = '', limit: int = 10, include_walking: bool = False):
    """Use coordinates supplied by ChatGPT. Display up to 10 restaurants nearest first with common map, inline Korean/Vietnamese menu, KRW prices, rating/count/review highlights, address and walking links. Budget/order assessments remain separate; missing data says Chưa có thông tin. Unknown evidence is not an affordable/solo-friendly recommendation. No invented quality score. Public provider coverage is incomplete."""
    result = await safe(food.rank, longitude, latitude, radius, budget_krw_per_person, party_size, query, limit, include_walking)
    return tool_result(view.format_result(result))

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})
async def get_restaurant_sources(query: str = '', restaurant_id: str = ''):
    """Find real menu/price/order sources in the curated keyless source catalog (Suwon and VISITKOREA initially). Returns source: IDs accepted by menu/policy tools. Sources and snapshots are not current verified prices, do not guarantee nearby coverage, and are not matched to another branch by name alone."""
    return await safe(menus.find, query, restaurant_id)

@mcp.resource(view.UI_URI, name='restaurant_results_map', mime_type='text/html;profile=mcp-app', meta=UI_META)
def restaurant_widget():
    return restaurant_html()

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True})
async def search_bus_routes(query: str, region: str = '', longitude: float | None = None, latitude: float | None = None):
    """Select a verified bus source from the requested city/province, or caller-provided WGS84 coordinates. No default region. Without location return needs_region; unsupported areas return unsupported_region without querying another region. Seoul uses its public source, Gyeonggi uses GBIS; cross-region GBIS fallbacks are explicitly limited. Do not acquire device GPS. Use source-scoped route_id from results with get_bus_route_map. Distinguish this route lookup/map from A-to-B multi-leg planning, which is not implemented here."""
    return await safe(buses.search,query,region,longitude,latitude)

@mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': True}, meta={'ui':{'resourceUri':buses.UI_URI},'openai/outputTemplate':buses.UI_URI})
async def get_bus_route_map(route_id: str):
    """Retrieve the provider in source-scoped route_id from search_bus_routes; never infer provider from bus number. Returns route shape, ordered stops and source-specific vehicle positions. Seoul GPS markers require valid coordinates and a fresh dataTm (120 seconds). GBIS amber markers are stop references, not GPS. Preserve observation/read times, direction evidence, stale/missing data and source errors. Existing numeric saved links retain GBIS compatibility only."""
    data=await safe(buses.snapshot,route_id)
    if 'map' not in data:return data
    from fastmcp.tools.tool import ToolResult
    return ToolResult(content=buses.summary(data),structured_content={k:v for k,v in data.items() if k!='map'},meta={'busSnapshot':data})

@mcp.resource(buses.UI_URI,name='bus_route_map',mime_type='text/html;profile=mcp-app',meta=BUS_UI_META)
def bus_map_widget():
    return buses.ui_html()

transport = mcp.http_app(path='/mcp', stateless_http=True)
@asynccontextmanager
async def lifespan(app):
    async with transport.lifespan(app):
        yield
app = FastAPI(lifespan=lifespan)

@app.middleware('http')
async def security(request: Request, call_next):
    token = os.getenv('ACCESS_TOKEN')
    is_mcp = request.url.path == '/mcp' or request.url.path.startswith('/mcp/')
    public_mcp = os.getenv('MCP_PUBLIC', 'false').strip().lower() in ('true', '1', 'yes', 'on')
    public_bus = request.url.path.startswith('/api/bus/') and public_mcp
    protected = (request.url.path.startswith('/api/') and not public_bus) or (is_mcp and not public_mcp)
    if protected and token:
        provided = request.headers.get('authorization', '')
        if not secrets.compare_digest(provided, 'Bearer '+token):
            return JSONResponse({'detail': 'Unauthorized'}, status_code=401)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src https://tile.openstreetmap.org; frame-ancestors 'self'; base-uri 'none'" if request.url.path == '/restaurant-map' else "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
    if request.url.path == '/bus':
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https://tile.openstreetmap.org; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    return response

@app.get('/healthz')
async def health():
    public_mcp = os.getenv('MCP_PUBLIC', 'false').strip().lower() in ('true', '1', 'yes', 'on')
    requires_token = bool(os.getenv('ACCESS_TOKEN')) and not public_mcp
    return {'status': 'ok', 'mcp_auth': 'bearer' if requires_token else 'none', 'version': '0.5.2', 'restaurant_tools': True}

@app.get('/restaurant-map')
async def shared_restaurant_map():
    from fastapi.responses import HTMLResponse
    return HTMLResponse(restaurant_html())

@app.get('/api/stations')
async def api_stations(query: str):
    return await safe(d.stations, query)
@app.get('/api/arrivals')
async def api_arrivals(station: str):
    return await safe(s.arrivals, station)
@app.get('/api/route')
async def api_route(origin: str, destination: str):
    return await safe(d.route, origin, destination)
@app.get('/api/rail-stations')
async def api_rail_stations(city_code: str = '11'):
    return await safe(s.rail_stations, city_code)
@app.get('/api/rail')
async def api_rail(origin: str, destination: str, date: str):
    return await safe(s.rail_schedule, origin, destination, date)

@app.get('/api/tourism')
async def api_tourism(query: str, page: int = 1):
    return await safe(d.tourism, query, page)
@app.get('/api/nearby')
async def api_nearby(longitude: float, latitude: float, radius: int = 2000, page: int = 1):
    return await safe(d.nearby, longitude, latitude, radius, page)
@app.get('/api/tourism-detail')
async def api_tourism_detail(content_id: str):
    return await safe(t.tourism_detail, content_id)
@app.get('/api/festivals')
async def api_festivals(start_date: str, page: int = 1):
    return await safe(d.festivals, start_date, page)
@app.get('/api/stays')
async def api_stays(area_code: str = '', page: int = 1):
    return await safe(d.stays, area_code, page)
@app.get('/api/places')
async def api_places(query: str, page: int = 1):
    return await safe(d.places, query, page)
@app.get('/api/geocode')
async def api_geocode(address: str):
    return await safe(d.geocode, address)
@app.get('/api/driving')
async def api_driving(origin: str, destination: str):
    return await safe(d.driving, origin, destination)

@app.get('/api/google')
async def api_google(query: str = '', origin: str = '', destination: str = '', mode: str = 'transit'):
    return await safe(o.google_links, query, origin, destination, mode)

@app.get('/api/restaurants')
async def api_restaurants(longitude: float, latitude: float, radius: int = 500,
    budget_krw_per_person: int = 10000, party_size: int = 1, query: str = '', limit: int = 10, include_walking: bool = False):
    result = await safe(food.search_nearby, longitude, latitude, radius, budget_krw_per_person, party_size, query, limit, include_walking)
    return view.format_result(result)

@app.get('/api/restaurants/rank')
async def api_restaurant_rank(longitude: float, latitude: float, radius: int = 500,
    budget_krw_per_person: int = 10000, party_size: int = 1, query: str = '', limit: int = 10, include_walking: bool = False):
    result = await safe(food.rank, longitude, latitude, radius, budget_krw_per_person, party_size, query, limit, include_walking)
    return view.format_result(result)

@app.get('/api/restaurants/menu')
async def api_restaurant_menu(restaurant_id: str):
    return await safe(food.details_with_sources, restaurant_id, 'menu')

@app.get('/api/restaurants/policy')
async def api_restaurant_policy(restaurant_id: str):
    return await safe(food.details_with_sources, restaurant_id, 'policy')

@app.get('/api/restaurants/sources')
async def api_restaurant_sources(query: str = '', restaurant_id: str = ''):
    return await safe(menus.find, query, restaurant_id)

@app.get('/api/bus/search')
async def api_bus_search(query: str,region: str='',longitude: float | None=None,latitude: float | None=None):
    return await safe(buses.search,query,region,longitude,latitude)

@app.get('/api/bus/coverage')
async def api_bus_coverage():
    return buses.coverage()

@app.get('/api/bus/route')
async def api_bus_route(route_id: str):
    return await safe(buses.snapshot,route_id)

static = Path(__file__).parent / 'static'
@app.get('/bus')
async def bus_page():
    return FileResponse(static / 'bus-map.html')

@app.get('/')
async def home():
    return FileResponse(static / 'index.html')
app.mount('/static', StaticFiles(directory=static), name='static')
app.mount('/', transport)

