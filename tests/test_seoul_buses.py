import asyncio
import unittest
from datetime import datetime,timedelta
from unittest.mock import AsyncMock,patch
from seoul_transit import seoul_buses as b,service as s
CLOCK=datetime(2026,10,27,23,0,tzinfo=s.KST)
def response(data):return {'ResponseVO':{'code':0,'timestamp':'2026-10-27T23:00:00','data':data}}
def part(data):return {'payload':response(data),'source_url':'https://bus.go.kr/sbus/bus/test.do','fetched_at':CLOCK.isoformat(),'cached':False}
def parts():return {'detail':part({'resultList':[{'rtid':100100022,'rtnm':'143','sstnnm':'A','estnnm':'B'}]}),'map':part({'resultRoutePath':[{'no':20,'gpsX':127.01,'gpsY':37.01},{'no':1,'gpsX':127.,'gpsY':37.}],
 'resultRouteStop':[{'busRouteId':100100022,'seq':1,'station':11,'stationName':'A','gpsX':127.,'gpsY':37.}],
 'resultRouteBuspos':[{'rtId':100100022,'vehId':9,'plainNo':'TEST','gpsX':127.005,'gpsY':37.005,'dataTm':'20261027225950','lastStnId':11,'lastStnOrd':1,'adirection':'B'}]})}
class SeoulTests(unittest.TestCase):
 def test_verified_fresh_gps_direction_and_measured_time(self):
  out=b.assemble('100100022',parts(),CLOCK);v=out['vehicles'][0]
  self.assertEqual(out['status'],'ok');self.assertEqual(v['direction'],'B');self.assertEqual(v['freshness'],'fresh')
  self.assertEqual(v['gps_coordinates'],[127.005,37.005]);self.assertIsNotNone(v['vehicle_observed_at'])
  self.assertTrue(any(f['properties']['kind']=='vehicle_gps' for f in out['map']['features']))
 def test_old_unknown_or_future_data_never_drawn_as_live_gps(self):
  for stamp,expected in [('20261027225000','stale'),('','unknown'),('20261028010000','future')]:
   p=parts();p['map']['payload']['ResponseVO']['data']['resultRouteBuspos'][0]['dataTm']=stamp
   out=b.assemble('100100022',p,CLOCK)
   self.assertEqual(out['vehicles'][0]['freshness'],expected)
   self.assertFalse(any(f['properties']['kind']=='vehicle_gps' for f in out['map']['features']))
 def test_cache_never_freezes_freshness(self):
  out=b.assemble('100100022',parts(),CLOCK+timedelta(minutes=3))
  self.assertEqual(out['vehicles'][0]['freshness'],'stale')
 def test_error_envelope_is_not_empty_success(self):
  with self.assertRaises(s.Unavailable):b.data({'ResponseVO':{'code':9,'data':{}}})
 def test_geometry_is_not_synthesized_from_stops(self):
  p=parts();p['map']['payload']['ResponseVO']['data']['resultRoutePath'][0]['gpsX']=0
  out=b.assemble('100100022',p,CLOCK)
  self.assertEqual(out['parts']['shape']['status'],'unavailable');self.assertEqual(len(out['stops']),1)
  self.assertFalse(any(f['geometry']['type']=='LineString' for f in out['map']['features']))
 def test_wrong_route_never_binds_vehicle(self):
  p=parts();p['map']['payload']['ResponseVO']['data']['resultRouteBuspos'][0]['rtId']=999
  self.assertEqual(b.assemble('100100022',p,CLOCK)['vehicles'],[])
 def test_search_uses_observed_public_schema_and_exact_number(self):
  data=part({'resultList':[{'strdiv':1,'strid':100100022,'strno':'143','strkey':'A - B'},{'strdiv':1,'strid':100100158,'strno':'1143'}]})
  with patch.object(b,'read',AsyncMock(return_value=data)) as source:out=asyncio.run(b.search('143'))
  self.assertEqual([r['route_id'] for r in out['data']],['100100022'])
  self.assertEqual(source.call_args.args[1]['strkey'],'143')
