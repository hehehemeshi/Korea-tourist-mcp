"""Wire checks: real FastMCP serialization/resource metadata, mocked discovery only."""
import asyncio
import importlib
from unittest.mock import AsyncMock, patch
from test_presentation import result, row

def test_mcp_output_and_resource():
    from fastmcp import Client
    module=importlib.reload(importlib.import_module('seoul_transit.app'))
    from seoul_transit.presentation import UI_URI
    async def check():
        async with Client(module.mcp) as client:
            tools={t.name:t for t in await client.list_tools()}
            for name in ['search_nearby_restaurants','rank_restaurants']:
                meta=tools[name].model_dump(by_alias=True)['_meta']
                assert meta['ui']['resourceUri']==UI_URI
                assert tools[name].inputSchema['properties']['limit']['default']==10
                backend='search_nearby' if name.startswith('search') else 'rank'
                with patch.object(module.food,backend,AsyncMock(return_value=result([row(2),row(1)]))):
                    output=await client.call_tool(name,{'longitude':127.,'latitude':37.266})
                assert not output.is_error
                assert output.structured_content['presentation']['restaurants'][0]['number']==1
                assert output.structured_content['data'][0]['restaurant_id']=='osm:node:1'
                assert '₩5,000' in output.content[0].text
                assert 'Chưa có thông tin' in output.content[0].text
            resource=(await client.read_resource(UI_URI))[0]
            assert resource.mimeType=='text/html;profile=mcp-app'
            meta=resource.model_dump(by_alias=True)['_meta']
            assert meta['ui']['csp']['resourceDomains']==['https://tile.openstreetmap.org']
            assert 'navigator.geolocation' not in resource.text
            assert '__SCRIPT__' not in resource.text
            assert 'ui/notifications/tool-result' in resource.text
    asyncio.run(check())

def test_rest_presentation_and_static_map(monkeypatch):
    from fastapi.testclient import TestClient
    module=importlib.reload(importlib.import_module('seoul_transit.app'))
    monkeypatch.setenv('ACCESS_TOKEN','test-token')
    with TestClient(module.app) as client:
        assert client.get('/api/restaurants?longitude=127&latitude=37.266').status_code==401
        with patch.object(module.food,'search_nearby',AsyncMock(return_value=result([row()]))):
            response=client.get('/api/restaurants?longitude=127&latitude=37.266',headers={'Authorization':'Bearer test-token'})
        assert response.status_code==200
        assert response.json()['presentation']['restaurants'][0]['menu'][0]['price_display']=='₩5,000'
        page=client.get('/restaurant-map')
        assert page.status_code==200
        assert 'text/html' in page.headers['content-type']
        assert 'img-src https://tile.openstreetmap.org' in page.headers['content-security-policy']
        assert '© OpenStreetMap contributors' in page.text
        assert 'navigator.geolocation' not in page.text
