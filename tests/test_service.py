import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch
import pytest
from seoul_transit import service as s
from seoul_transit.routing import plan

CLOCK = datetime(2026, 10, 27, 12, tzinfo=s.KST)

def test_arrival_staleness_and_no_platform():
    for age in (121, 3600):
        row = s.arrival(dict(recptnDt=(CLOCK-timedelta(seconds=age)).isoformat(), barvlDt='300', platform='5'), CLOCK)
        assert row['estimated_arrival'] is None
        assert row['platform'] is None

def test_fresh_eta_and_direction():
    row = s.arrival(dict(recptnDt=CLOCK.isoformat(), barvlDt='300', updnLine='상행'), CLOCK)
    assert row['estimated_arrival'] == (CLOCK+timedelta(seconds=300)).isoformat()
    assert row['direction'] == '상행'

@pytest.mark.parametrize('seconds', ['0', '-1', '', 'abc', None])
def test_unknown_eta(seconds):
    assert s.arrival(dict(recptnDt=CLOCK.isoformat(), barvlDt=seconds), CLOCK)['estimated_arrival'] is None

def test_missing_time_never_live():
    assert s.arrival({'barvlDt': '300'}, CLOCK)['estimated_arrival'] is None

def test_no_key(monkeypatch):
    monkeypatch.delenv('SEOUL_SUBWAY_API_KEY', raising=False)
    with pytest.raises(s.Unavailable):
        asyncio.run(s.arrivals('강남'))

def test_route_requires_verified_data(monkeypatch):
    monkeypatch.delenv('NETWORK_FILE', raising=False)
    with pytest.raises(s.Unavailable):
        plan('a', 'b')

def test_explicit_transfer_route(tmp_path, monkeypatch):
    import json
    edges = [dict(**{'from': a, 'to': b}, kind=k, seconds=t) for a,b,k,t in [('a','b','ride',60),('b','c','transfer',90),('c','d','ride',60)]]
    path=tmp_path/'graph.json'
    path.write_text(json.dumps(dict(source=s.SOURCES['stations'], verified_on=s.now().date().isoformat(), edges=edges)))
    monkeypatch.setenv('NETWORK_FILE', str(path))
    route=plan('a','d')
    assert route['transfers']==1 and route['planned_seconds']==210
    assert plan('d','a')['status']=='no_data'

def test_mcp_and_http():
    from fastapi.testclient import TestClient
    from seoul_transit.app import app, mcp
    from fastmcp import Client
    async def check():
        async with Client(mcp) as client:
            tools=await client.list_tools()
            assert {'get_arrivals','plan_route','get_rail_schedule'} <= {t.name for t in tools}
    asyncio.run(check())
    with TestClient(app) as client:
        assert client.get('/healthz').status_code==200
        assert 'lang="vi"' in client.get('/').text
        with patch.dict('os.environ', {'ACCESS_TOKEN': 'test-token'}):
            assert client.get('/api/arrivals?station=강남').status_code == 401
            with patch.dict('os.environ', {'SEOUL_SUBWAY_API_KEY': ''}):
                response = client.get('/api/arrivals?station=강남', headers={'Authorization': 'Bearer test-token'})
                assert response.status_code == 200
                assert response.json()['status'] == 'unavailable'
