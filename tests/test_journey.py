import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, patch
from seoul_transit import journey as j, service as s

def loc(lat=37.267,lon=127.001):return {'latLng':{'latitude':lat,'longitude':lon}}

def provider():
    return {'routes':[{'duration':'900s','distanceMeters':2000,'polyline':{'encodedPolyline':'encoded'},'legs':[{'steps':[
        {'travelMode':'WALK','startLocation':loc(),'endLocation':loc(37.268),'staticDuration':'60s','navigationInstruction':{'instructions':'Đi tới ga'}},
        {'travelMode':'TRANSIT','startLocation':loc(37.268),'endLocation':loc(37.28),'transitDetails':{'headsign':'Seoul','stopCount':2,'transitLine':{'nameShort':'1','vehicle':{'type':'SUBWAY'}},'stopDetails':{'departureStop':{'name':'수원','location':loc(37.268)},'arrivalStop':{'name':'Test stop','location':loc(37.28)},'departureTime':'2026-10-27T03:00:00Z'}}}
    ]}]}]}

class JourneyTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'ACCESS_TOKEN':'owner','GOOGLE_ROUTES_API_KEY':'server-secret','OPENAI_API_KEY':'llm-secret'})
        self.env.start();j._plans.clear()
    def tearDown(self):self.env.stop()
    def test_verified_provider_fields_not_live_or_platform(self):
        with patch.object(j,'post_json',AsyncMock(return_value=provider())) as post:
            out=asyncio.run(j.plan(j.PlanRequest(origin='Suwon Station',destination='Seoul Station')))
        self.assertEqual(out['status'],'ok');self.assertEqual(out['data_kind'],'provider_plan_not_live')
        step=out['routes'][0]['steps'][1]
        self.assertEqual(step['line'],'1');self.assertEqual(step['headsign'],'Seoul');self.assertIsNone(step['platform'])
        self.assertEqual(step['arrival_stop']['name'],'Test stop');self.assertEqual(out['routes'][0]['transfers'],0)
        self.assertEqual(out['routes'][0]['fare'],j.MISSING)
        self.assertNotIn('server-secret',json.dumps(out))
        self.assertEqual(post.call_args.args[1]['travelMode'],'TRANSIT')
        self.assertNotIn('encoded',json.dumps(j.cached_query(out['route_id'])))
    def test_explicit_gps_uses_coordinate_waypoint(self):
        with patch.object(j,'post_json',AsyncMock(return_value=provider())) as post:
            asyncio.run(j.plan(j.PlanRequest(destination='Seoul',origin_location={'latitude':37.267,'longitude':127.001})))
        self.assertEqual(post.call_args.args[1]['origin'],{'location':loc()})
    def test_missing_provider_key_is_unavailable_no_network(self):
        with patch.dict(os.environ,{'GOOGLE_ROUTES_API_KEY':''}),patch.object(j,'post_json',AsyncMock()) as post:
            with self.assertRaises(s.Unavailable):asyncio.run(j.plan(j.PlanRequest(origin='Suwon',destination='Seoul')))
        post.assert_not_called()
    def test_missing_owner_protection_disables_paid_endpoints(self):
        with patch.dict(os.environ,{'ACCESS_TOKEN':''}):
            with self.assertRaises(s.Unavailable):asyncio.run(j.chat(j.ChatRequest(message='Hello')))
    def test_empty_or_out_of_region_provider_route_is_not_invented(self):
        bad=provider();bad['routes'][0]['legs'][0]['steps'][0]['startLocation']=loc(50,1)
        for response in ({'routes':[]},bad):
            with patch.object(j,'post_json',AsyncMock(return_value=response)):
                out=asyncio.run(j.plan(j.PlanRequest(origin='Suwon',destination='Seoul')))
            self.assertEqual(out['status'],'no_data');self.assertEqual(out['routes'],[])
    def test_unshared_location_does_not_become_fake_origin(self):
        intent={'action':'plan','origin':'CURRENT_LOCATION','destination':'Seoul','reply':'Tra cứu','preference':'FEWER_TRANSFERS'}
        with patch.object(j,'post_json',AsyncMock(return_value={'choices':[{'message':{'content':json.dumps(intent)}}]})):
            out=asyncio.run(j.chat(j.ChatRequest(message='Từ đây đi Seoul')))
        self.assertEqual(out['status'],'unavailable');self.assertNotIn('journey',out)
    def test_llm_cannot_supply_itinerary_in_place_of_provider(self):
        intent={'action':'plan','origin':'Suwon','destination':'Seoul','reply':'Bịa tuyến 999','preference':'FEWER_TRANSFERS'}
        response={'choices':[{'message':{'content':json.dumps(intent)}}]}
        with patch.object(j,'post_json',AsyncMock(side_effect=[response,provider()])):
            out=asyncio.run(j.chat(j.ChatRequest(message='Đi Seoul từ Suwon')))
        self.assertEqual(out['journey']['routes'][0]['steps'][1]['line'],'1')
        self.assertNotIn('999',out['reply'])
    def test_malformed_llm_does_not_make_route(self):
        with patch.object(j,'post_json',AsyncMock(return_value={'choices':[]})):
            with self.assertRaises(s.Unavailable):asyncio.run(j.chat(j.ChatRequest(message='Hello')))
    def test_expired_query_is_not_reused(self):
        j._plans['expired']=(0,{'origin':'Suwon','destination':'Seoul'})
        self.assertIsNone(j.cached_query('expired'))
    def test_provider_errors_do_not_leak_keys(self):
        import httpx
        with patch('httpx.AsyncClient.post',AsyncMock(side_effect=httpx.ConnectError('secret URL'))):
            with self.assertRaises(s.Unavailable) as error:asyncio.run(j.post_json('https://example.org',{},{}))
        self.assertNotIn('secret',str(error.exception))
