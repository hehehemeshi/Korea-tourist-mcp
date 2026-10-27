import importlib
from unittest.mock import AsyncMock, patch

def module():return importlib.reload(importlib.import_module('seoul_transit.app'))

def test_companion_pages_and_config(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv('ACCESS_TOKEN','owner');monkeypatch.setenv('OPENAI_API_KEY','secret-llm');monkeypatch.setenv('GOOGLE_ROUTES_API_KEY','secret-route');monkeypatch.setenv('GOOGLE_MAPS_BROWSER_KEY','public-browser-key')
    with TestClient(module().app) as client:
        page=client.get('/');assert page.status_code==200
        assert 'Bật đồng hành GPS' in page.text
        assert 'geolocation=(self)' in page.headers['permissions-policy']
        assert page.headers['referrer-policy']=='strict-origin-when-cross-origin'
        for path in ['/tools','/privacy','/terms','/companion']:assert client.get(path).status_code==200
        assert client.get('/api/journey/status').status_code==401
        config=client.get('/api/journey/status',headers={'Authorization':'Bearer owner'})
        assert config.json()['llm_ready']
        assert config.json()['map_browser_key']=='public-browser-key'
        assert 'secret-llm' not in config.text and 'secret-route' not in config.text

def test_journey_api_preserves_auth_and_rejects_cross_origin(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv('ACCESS_TOKEN','owner');mod=module()
    with TestClient(mod.app) as client:
        payload={'origin':'Suwon','destination':'Seoul'}
        assert client.post('/api/journey/plan',json=payload).status_code==401
        headers={'Authorization':'Bearer owner','Origin':'https://unrelated.example'}
        assert client.post('/api/journey/plan',headers=headers,json=payload).status_code==403
        with patch.object(mod.j,'plan',AsyncMock(return_value={'status':'no_data','routes':[]})) as provider:
            response=client.post('/api/journey/plan',headers={'Authorization':'Bearer owner','Origin':'http://testserver'},json=payload)
        assert response.json()['routes']==[];provider.assert_awaited_once()

def test_chat_without_llm_key_reports_missing_configuration(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv('ACCESS_TOKEN','owner');monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    with TestClient(module().app) as client:
        response=client.post('/api/journey/chat',headers={'Authorization':'Bearer owner'},json={'message':'Đi Seoul bằng tàu thế nào?'})
        assert response.status_code==200
        assert response.json()['status']=='unavailable'
        assert 'OPENAI_API_KEY' in response.json()['message']
