import asyncio
import unittest
from unittest.mock import AsyncMock,patch
from seoul_transit import buses as b,service as s

class BusTests(unittest.TestCase):
    def parts(self):return {'stops':{'rows':[{'stationId':'1','stationSeq':1,'stationName':'A','x':127,'y':37}]},'shape':{'rows':[{'lineSeq':2,'x':127.01,'y':37.01},{'lineSeq':1,'x':127,'y':37}]},'vehicles':{'rows':[{'routeId':'123','vehId':'9','plateNo':'TEST','stationId':'1','stationSeq':1,'stateCd':2}]}}
    def test_stop_relative_vehicle_never_becomes_gps(self):
        out=b.normalize(self.parts(),'123');v=out['vehicles'][0]
        self.assertIsNone(v['gps_coordinates']);self.assertIsNone(v['vehicle_observed_at'])
        self.assertEqual(v['position_kind'],'provider_stop_reference');self.assertEqual(v['direction'],'unknown')
        self.assertEqual(v['referenced_stop']['name'],'A')
        self.assertNotIn('vehicle',[f['properties']['kind'] for f in out['route_map']['features']])
    def test_shape_uses_provider_order_not_stop_connections(self):
        out=b.normalize(self.parts(),'123');shape=out['route_map']['features'][0]
        self.assertEqual(shape['geometry']['coordinates'],[[127.,37.],[127.01,37.01]])
        p=self.parts();p['shape']['rows']=[];out=b.normalize(p,'123')
        self.assertFalse(any(f['geometry']['type']=='LineString' for f in out['route_map']['features']))
    def test_bad_shape_does_not_bridge_missing_data(self):
        p=self.parts();p['shape']['rows'].append({'lineSeq':3,'x':0,'y':0})
        out=b.normalize(p,'123');self.assertTrue(out['warnings'])
        self.assertFalse(any(f['geometry']['type']=='LineString' for f in out['route_map']['features']))
    def test_repeated_stops_require_sequence_not_name_or_id_only(self):
        p=self.parts();p['vehicles']['rows'][0]['stationSeq']=2
        self.assertIsNone(b.normalize(p,'123')['vehicles'][0]['referenced_stop'])
    def test_response_auth_error_is_not_empty_success(self):
        with self.assertRaises(s.Unavailable):b.envelope({'response':{'msgHeader':{'resultCode':20}}},'busLocationList')
        rows,_=b.envelope({'response':{'msgHeader':{'resultCode':4},'msgBody':None}},'busLocationList')
        self.assertEqual(rows,[])
    def test_partial_failure_keeps_geometry_and_missing_vehicle_status(self):
        p=self.parts();p['vehicles']={'status':'unavailable'}
        out=b.normalize(p,'123');self.assertEqual(out['vehicles'],[])
        self.assertEqual(out['parts']['vehicles']['status'],'unavailable');self.assertTrue(out['warnings'])
    def test_no_key_does_not_launch_requests(self):
        with patch.dict('os.environ',{'DATA_GO_KR_KEY':''}),patch.object(b,'fetch',AsyncMock()) as fetch:
            with self.assertRaises(s.Unavailable):asyncio.run(b.snapshot('123'))
        fetch.assert_not_called()
    def test_snapshot_combines_independent_parts(self):
        parts=self.parts()
        async def fetch(kind,params):return parts[kind]
        with patch.dict('os.environ',{'DATA_GO_KR_KEY':'test'}),patch.object(b,'fetch',fetch):out=asyncio.run(b.snapshot('123'))
        self.assertEqual(len(out['vehicles']),1)
    def test_wrong_route_not_bound_to_geometry(self):
        p=self.parts();p['vehicles']['rows'][0]['routeId']='999'
        self.assertEqual(b.normalize(p,'123')['vehicles'],[])
