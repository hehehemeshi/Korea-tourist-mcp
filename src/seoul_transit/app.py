import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastmcp import FastMCP
from . import service as s
from .routing import plan
from . import travel as t
from . import discovery as d, open_data as o

mcp = FastMCP('Du lịch Hàn Quốc — Tiếng Việt', instructions='Explain in Vietnamese. Prefer open data and Google Maps hand-off links. Links are not retrieved search results or verified routes. Never invent arrivals, transfers or platforms. Timetables and community map data are not live. Preserve sources, timestamps, cached state and limitations.')

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
    public_mcp = os.getenv('MCP_PUBLIC', 'false').lower() == 'true'
    protected = request.url.path.startswith('/api/') or (is_mcp and not public_mcp)
    if protected and token:
        provided = request.headers.get('authorization', '')
        if not secrets.compare_digest(provided, 'Bearer '+token):
            return JSONResponse({'detail': 'Unauthorized'}, status_code=401)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    return response

@app.get('/healthz')
async def health():
    return {'status': 'ok'}

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

static = Path(__file__).parent / 'static'
@app.get('/')
async def home():
    return FileResponse(static / 'index.html')
app.mount('/static', StaticFiles(directory=static), name='static')
app.mount('/', transport)
