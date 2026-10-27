import asyncio
import unittest
from unittest.mock import AsyncMock,patch
from seoul_transit import public_buses as b,service as s

def result(payload):return dict(payload=payload,source_url='https://m.gbis.go.kr/api/test',fetched_at='2026-10-27T22:00:00+09:00',cached=False)
def parts():return dict(detail=result({'record':{'routeId':200000060,'routeName':11,'regionName':'수원,안산,용인','startStationName':'A','endStationName':'B'}}),
 stops=result({'records':[{'stationId':1,'stationSeq':1,'stationName':'A','x':127.0,'y':37.0},{'stationId':2,'stationSeq':2,'stationName':'B','x':127.01,'y':37.01}]}),
 shape=s.Unavailable('no shape'),vehicles=result({'response':{'comMsgHeader':'','msgHeader':{'resultCode':0,'queryTime':'2026-10-27 22:00:00'},'msgBody':{'busLocationList':[{'routeId':200000060,'vehId':9,'plateNo':'TEST','stationId':2,'stationSeq':2,'stateCd':2}]}}}))

class PublicBusTests(unittest.TestCase):
 def setUp(self):b._cache.clear()
 def test_search_exact_number_in_requested_region(self):
  payload={'records':[{'routeId':1,'routeName':11,'regionName':'의정부'},{'routeId':200000060,'routeName':11,'regionName':'수원,안산,용인','stStaNm':'A','edStaNm':'B'},{'routeId':3,'routeName':'11-1','regionName':'수원'}]}
  with patch.object(b,'read',AsyncMock(return_value=result(payload))):out=asyncio.run(b.search('11','Suwon'))
  self.assertEqual([row['route_id'] for row in out['data']],['200000060'])
 def test_unknown_region_does_not_invent_match(self):
  with patch.object(b,'read',AsyncMock(return_value=result({'records':[]}))):out=asyncio.run(b.search('11','Unknown'))
  self.assertEqual(out['status'],'no_data')
 def test_public_web_vehicle_envelope_and_time_semantics(self):
  out=b.assemble('200000060',parts());v=out['vehicles'][0]
  self.assertEqual(v['referenced_stop']['name'],'B');self.assertIsNone(v['gps_coordinates']);self.assertIsNone(v['vehicle_observed_at']);self.assertEqual(v['direction'],'unknown')
  self.assertEqual(out['parts']['vehicles']['provider_request_time'],'2026-10-27 22:00:00')
  feature=next(f for f in out['map']['features'] if f['properties']['kind']=='vehicle_stop_reference')
  self.assertEqual(feature['properties']['location_kind'],'stop_anchor_not_vehicle_gps')
  self.assertEqual(out['status'],'partial')
 def test_missing_shape_is_not_replaced_with_straight_stop_connections(self):
  out=b.assemble('200000060',parts())
  self.assertFalse(any(f['geometry']['type']=='LineString' for f in out['map']['features']))
 def test_wrong_route_or_stop_sequence_not_attached(self):
  p=parts();p['vehicles']['payload']['response']['msgBody']['busLocationList'][0]['stationSeq']=88
  self.assertIsNone(b.assemble('200000060',p)['vehicles'][0]['referenced_stop'])
  p['vehicles']['payload']['response']['msgBody']['busLocationList'][0]['routeId']=999
  self.assertEqual(b.assemble('200000060',p)['vehicles'],[])
 def test_auth_schema_failure_is_not_no_vehicles(self):
  p=parts();p['vehicles']=result({'response':{'msgHeader':{'resultCode':20}}})
  out=b.assemble('200000060',p);self.assertEqual(out['parts']['vehicles']['status'],'unavailable')
  p['vehicles']=result({'response':{'msgHeader':{'resultCode':4},'msgBody':None}})
  self.assertEqual(b.assemble('200000060',p)['parts']['vehicles']['status'],'no_data')
 def test_provider_failure_never_fabricates_snapshot(self):
  async def read(*args):raise s.Unavailable('source down')
  with patch.object(b,'read',read):out=asyncio.run(b.snapshot('200000060'))
  self.assertEqual(out['status'],'unavailable');self.assertEqual(out['stops'],[]);self.assertEqual(out['vehicles'],[])
 def test_no_key_or_cookie_sent_and_cache_preserves_read_time(self):
  class Response:
   content=b'{}'
   def raise_for_status(self):pass
   def json(self):return {'records':[]}
  mock=AsyncMock(return_value=Response())
  with patch('httpx.AsyncClient.get',mock):
   one=asyncio.run(b.read('search',{'keyword':'11'}));two=asyncio.run(b.read('search',{'keyword':'11'}))
  self.assertEqual(mock.await_count,1);self.assertTrue(two['cached']);self.assertEqual(one['fetched_at'],two['fetched_at'])
  self.assertEqual(mock.call_args.kwargs,{'params':{'keyword':'11'}})
 def test_route_id_and_coordinate_validation(self):
  for bad in ('../x','11?key=x','',None):
   with self.assertRaises(ValueError):b.rid(bad)
  self.assertIsNone(b.point({'x':float('nan'),'y':37}));self.assertIsNone(b.point({'x':0,'y':0}))
 def test_inline_widget_script_after_dom(self):
  html=b.ui_html();self.assertNotIn('/static/bus-map.js',html)
  self.assertGreater(html.index("const $=id"),html.index('id="map"'))
 def test_actual_public_shape_envelope_and_gapped_provider_order(self):
  shape={'response':{'comMsgHeader':'','msgHeader':{'resultCode':0},'msgBody':{'busRouteLineList':[{'lineSeq':4,'x':127.02,'y':37.02},{'lineSeq':1,'x':127.,'y':37.}]}}}
  self.assertEqual(b.geometry(shape),[[127.,37.],[127.02,37.02]])
  p=parts();p['shape']=result(shape);out=b.assemble('200000060',p)
  self.assertEqual(out['status'],'ok');self.assertTrue(any(f['geometry']['type']=='LineString' for f in out['map']['features']))
  shape['response']['msgBody']['busRouteLineList'][0]['x']=0
  with self.assertRaises(s.Unavailable):b.geometry(shape)
