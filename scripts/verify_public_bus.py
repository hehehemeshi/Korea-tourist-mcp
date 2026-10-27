"""Real public source and UI smoke, with no provider credentials or user location."""
import json
import shutil
import time
import httpx
from playwright.sync_api import sync_playwright
base='http://127.0.0.1:8765'
for attempt in range(30):
    try:
        if httpx.get(base+'/healthz').status_code==200:break
    except httpx.HTTPError:pass
    time.sleep(1)
else:raise RuntimeError('Verification server did not start')
with sync_playwright() as p:
    chrome=shutil.which('google-chrome') or shutil.which('chromium')
    assert chrome,'No preinstalled browser'
    browser=p.chromium.launch(executable_path=chrome,headless=True)
    page=browser.new_page(viewport={'width':1280,'height':1000})
    data=[];errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    def response(r):
        if '/api/bus/route?' in r.url:
            try:data.append(r.json())
            except Exception:pass
    page.on('response',response)
    page.goto(base+'/bus',wait_until='domcontentloaded')
    page.locator('#query').fill('11')
    page.locator('#search').click()
    page.wait_for_selector('#result:not([hidden])',timeout=100000)
    assert data,'No automatic server route request'
    snapshot=data[-1]
    print('LIVE_PUBLIC_MAP',json.dumps({'status':snapshot['status'],'route_id':snapshot['route_id'],'stops':len(snapshot['stops']),'vehicles':len(snapshot['vehicles']),'shape_points':sum(len(f['geometry']['coordinates']) for f in snapshot['map']['features'] if f['geometry']['type']=='LineString'),'parts':{k:v['status'] for k,v in snapshot['parts'].items()},'fetched_at':snapshot['fetched_at']},ensure_ascii=False))
    assert snapshot['route_id']=='200000060','Wrong region or route selection'
    assert snapshot['stops'],'No source stops'
    assert any(f['geometry']['type']=='LineString' for f in snapshot['map']['features']),'No provider shape'
    assert snapshot['parts']['vehicles']['status'] in ('ok','no_data'),'Vehicle source unavailable'
    assert all(v['gps_coordinates'] is None for v in snapshot['vehicles'])
    assert page.locator('#shape polyline').count()>0,'Route was not drawn'
    assert not errors,errors
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path='bus-map-desktop.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Mobile overflow'
    page.screenshot(path='bus-map-mobile.png',full_page=True)
    print('UI_VERIFIED_DESKTOP_MOBILE',len(snapshot['stops']),len(snapshot['vehicles']))
    browser.close()
