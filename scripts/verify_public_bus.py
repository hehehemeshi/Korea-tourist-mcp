"""Real source and browser checks in two cities; unsupported city must not show an old map."""
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
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(base+'/bus',wait_until='domcontentloaded')
    assert page.locator('#region').input_value()=='','A region was silently preselected'
    for region,number,expected in [('Seoul','143','seoul:100100022'),('Suwon','11','gbis:200000060')]:
        page.locator('#region').fill(region);page.locator('#query').fill(number)
        with page.expect_response(lambda r:'/api/bus/route?' in r.url,timeout=100000) as loaded:
            page.locator('#search').click()
        snapshot=loaded.value.json()
        page.wait_for_function("!document.getElementById('search').disabled")
        if snapshot['parts']['vehicles']['status']=='unavailable':
            with page.expect_response(lambda r:'/api/bus/route?' in r.url,timeout=60000) as refreshed:page.locator('#refresh').click()
            snapshot=refreshed.value.json()
            page.wait_for_function("!document.getElementById('refresh').disabled")
        print('LIVE_REGION_MAP',json.dumps({'region':region,'status':snapshot['status'],'route_id':snapshot['route_id'],'stops':len(snapshot['stops']),'vehicles':len(snapshot['vehicles']),'shape_points':sum(len(f['geometry']['coordinates']) for f in snapshot['map']['features'] if f['geometry']['type']=='LineString'),'parts':{k:v['status'] for k,v in snapshot['parts'].items()},'fetched_at':snapshot['fetched_at']},ensure_ascii=False))
        assert snapshot['route_id']==expected,'Wrong source, region or route'
        assert snapshot['stops'] and any(f['geometry']['type']=='LineString' for f in snapshot['map']['features'])
        assert snapshot['parts']['vehicles']['status'] in ('ok','no_data')
        assert page.locator('#shape polyline').count()>0
        assert not errors,errors
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path='bus-map-'+region.lower()+'-desktop.png',full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Mobile overflow'
        page.screenshot(path='bus-map-'+region.lower()+'-mobile.png',full_page=True)
        page.set_viewport_size({'width':1280,'height':1000})
        # An unsupported city must clear the last successful city's map.
        page.locator('#region').fill('Busan');page.locator('#query').fill(number)
        with page.expect_response(lambda r:'/api/bus/search?' in r.url,timeout=15000) as unsupported:page.locator('#search').click()
        assert unsupported.value.json()['status']=='unsupported_region'
        page.wait_for_function("!document.getElementById('search').disabled")
        assert page.locator('#result').is_hidden(),'Previous-region map remained visible'
        print('UNSUPPORTED_REGION_NO_SUBSTITUTION',region,'to Busan')
    print('UI_VERIFIED_TWO_REGIONS_DESKTOP_MOBILE')
    browser.close()
