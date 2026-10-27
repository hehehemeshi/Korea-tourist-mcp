import asyncio
import importlib
from unittest.mock import AsyncMock,patch
from test_public_buses import parts,result
from seoul_transit import public_buses as b

def snapshot():
 p=parts();p['shape']=result({'response':{'msgHeader':{'resultCode':0},'msgBody':{'busRouteLineList':[{'lineSeq':1,'x':127.,'y':37.},{'lineSeq':4,'x':127.01,'y':37.01}]}}})
 return b.assemble('200000060',p)

def test_bus_tools_resource_and_ui_only_geometry():
 from fastmcp import Client
 module=importlib.reload(importlib.import_module('seoul_transit.app'))
 async def check():
  async with Client(module.mcp) as client:
   tools={tool.name:tool for tool in await client.list_tools()}
   assert {'search_bus_routes','get_bus_route_map'} <= tools.keys()
   assert tools['get_bus_route_map'].model_dump(by_alias=True)['_meta']['ui']['resourceUri']==b.UI_URI
   with patch.object(module.buses,'snapshot',AsyncMock(return_value=snapshot())):
    output=await client.session.call_tool('get_bus_route_map',{'route_id':'200000060'})
   assert not output.isError
   assert 'map' not in output.structuredContent
   assert output.meta['busSnapshot']['map']['features']
   assert output.structuredContent['vehicles'][0]['gps_coordinates'] is None
   resource=(await client.read_resource(b.UI_URI))[0]
   assert resource.mimeType=='text/html;profile=mcp-app'
   assert resource.model_dump(by_alias=True)['_meta']['ui']['csp']['resourceDomains']==['https://tile.openstreetmap.org']
   assert 'navigator.geolocation' not in resource.text
   assert 'busSnapshot' in resource.text
 asyncio.run(check())

def test_public_bus_api_matches_public_mcp_without_opening_other_apis(monkeypatch):
 from fastapi.testclient import TestClient
 module=importlib.reload(importlib.import_module('seoul_transit.app'))
 monkeypatch.setenv('ACCESS_TOKEN','owner');monkeypatch.setenv('MCP_PUBLIC','true')
 with TestClient(module.app) as client:
  with patch.object(module.buses,'snapshot',AsyncMock(return_value=snapshot())):
   data=client.get('/api/bus/route?route_id=200000060')
  assert data.status_code==200 and data.json()['map']['features']
  assert client.get('/api/restaurants?longitude=127&latitude=37').status_code==401
  page=client.get('/bus');assert page.status_code==200
  assert '/static/bus-map.js' in page.text
  assert 'img-src' in page.headers['content-security-policy']
  assert 'tile.openstreetmap.org' in page.headers['content-security-policy']

def test_private_mcp_keeps_bus_api_private(monkeypatch):
 from fastapi.testclient import TestClient
 module=importlib.reload(importlib.import_module('seoul_transit.app'))
 monkeypatch.setenv('ACCESS_TOKEN','owner');monkeypatch.setenv('MCP_PUBLIC','false')
 with TestClient(module.app) as client:
  assert client.get('/api/bus/search?query=11').status_code==401
  with patch.object(module.buses,'search',AsyncMock(return_value={'status':'no_data','data':[]})):
   response=client.get('/api/bus/search?query=11',headers={'Authorization':'Bearer owner'})
  assert response.json()['data']==[]

def test_region_required_and_unsupported_api_never_reuses_provider(monkeypatch):
 from fastapi.testclient import TestClient
 module=importlib.reload(importlib.import_module('seoul_transit.app'))
 monkeypatch.setenv('MCP_PUBLIC','true')
 with TestClient(module.app) as client:
  assert client.get('/api/bus/search?query=11').json()['status']=='needs_region'
  assert client.get('/api/bus/search?query=11&region=Busan').json()['status']=='unsupported_region'
  assert client.get('/api/bus/coverage').json()['nationwide_coverage'] is False
  page=client.get('/bus').text
  assert '<select id="region">' not in page
  assert 'id="region" placeholder="Thành phố / tỉnh"' in page
  assert 'value="수원"' not in page
