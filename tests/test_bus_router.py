import asyncio
import unittest
from unittest.mock import AsyncMock,patch
from seoul_transit import bus_router as r,service as s

def found(id='100100022',number='143'):return {'status':'ok','data':[{'route_id':id,'number':number,'region':'서울','origin':'A','destination':'B'}]}
class RouterTests(unittest.TestCase):
 def test_missing_region_does_not_default_or_call_sources(self):
  with patch.object(r.gbis,'search',AsyncMock()) as gbis,patch.object(r.seoul,'search',AsyncMock()) as seoul:
   out=asyncio.run(r.search('11'))
  self.assertEqual(out['status'],'needs_region');gbis.assert_not_called();seoul.assert_not_called()
 def test_unsupported_city_does_not_query_seoul_or_gg(self):
  for region in ('Busan','Daegu','Jeju','Daejeon','부산광역시','Unknown place'):
   with patch.object(r.gbis,'search',AsyncMock()) as gbis,patch.object(r.seoul,'search',AsyncMock()) as seoul:
    out=asyncio.run(r.search('11',region))
   self.assertEqual(out['status'],'unsupported_region');self.assertEqual(out['data'],[]);gbis.assert_not_called();seoul.assert_not_called()
 def test_seoul_has_own_source_not_gg_default(self):
  with patch.object(r.seoul,'search',AsyncMock(return_value=found())) as seoul,patch.object(r.gbis,'search',AsyncMock()) as gbis:
   out=asyncio.run(r.search('143','Seoul'))
  self.assertEqual(out['data'][0]['route_id'],'seoul:100100022');seoul.assert_awaited_once_with('143');gbis.assert_not_called()
 def test_suwon_explicit_and_city_aliases(self):
  for region in ('Suwon','Suwon-si','수원시','경기도 수원시'):
   with patch.object(r.gbis,'search',AsyncMock(return_value=found('200000060','11'))) as source:
    out=asyncio.run(r.search('11',region))
   source.assert_awaited_once_with('11','수원');self.assertEqual(out['data'][0]['source_id'],'gbis')
 def test_gwangju_ambiguity_is_not_resolved_to_gg(self):
  for name in ('Gwangju','광주','광주시'):
   self.assertEqual(asyncio.run(r.search('11',name))['status'],'needs_region')
  self.assertEqual(r.resolve('Gwangju Metropolitan City')['scope'],'unsupported')
  self.assertEqual(r.resolve('경기도 광주시')['scope'],'gyeonggi')
 def test_seoul_failure_only_allows_explicit_partial_cross_region_coverage(self):
  with patch.object(r.seoul,'search',AsyncMock(side_effect=s.Unavailable('down'))),patch.object(r.gbis,'search',AsyncMock(return_value=found('200000060','11'))) as source:
   out=asyncio.run(r.search('11','Seoul'))
  source.assert_awaited_once_with('11','서울');self.assertEqual(out['status'],'partial');self.assertTrue(out['warnings']);self.assertEqual(out['coverage_scope'],'gbis_listed_cross_region_routes')
 def test_no_cross_region_substitution_after_source_failure(self):
  with patch.object(r.gbis,'search',AsyncMock(side_effect=s.Unavailable('down'))),patch.object(r.seoul,'search',AsyncMock()) as other:
   out=asyncio.run(r.search('11','Suwon'))
  self.assertEqual(out['status'],'unavailable');other.assert_not_called()
 def test_source_namespaces_and_saved_link_compatibility(self):
  def snapshot():return {'route':{},'map':{},'stops':[],'vehicles':[]}
  for id,provider in [('seoul:100100022','seoul'),('gbis:200000060','gbis'),('200000060','gbis')]:
   with patch.object(r.seoul,'snapshot',AsyncMock(return_value=snapshot())) as seoul,patch.object(r.gbis,'snapshot',AsyncMock(return_value=snapshot())) as gbis:
    out=asyncio.run(r.snapshot(id))
   self.assertEqual(out['source_id'],provider)
   (seoul if provider=='seoul' else gbis).assert_awaited_once()
   (gbis if provider=='seoul' else seoul).assert_not_called()
  for bad in ('11','seoul:11','other:100100022'):
   with self.assertRaises(ValueError):asyncio.run(r.snapshot(bad))
 def test_explicit_target_region_takes_priority_over_current_coordinates(self):
  with patch.object(r,'from_coordinates',AsyncMock()) as resolver,patch.object(r.seoul,'search',AsyncMock(return_value=found())):
   out=asyncio.run(r.search('143','Seoul',127,37))
  resolver.assert_not_called();self.assertEqual(out['selection']['kind'],'explicit_region')
 def test_caller_coordinates_route_to_resolved_city_without_device_gps(self):
  with patch.object(r,'from_coordinates',AsyncMock(return_value=({'scope':'seoul','name':'서울','provider':'seoul'},{'kind':'coordinates_reverse_geocoded'}))),patch.object(r.seoul,'search',AsyncMock(return_value=found())):
   out=asyncio.run(r.search('143',longitude=126.98,latitude=37.56))
  self.assertEqual(out['selection']['region'],'서울')
 def test_reverse_failure_requests_city_instead_of_falling_back(self):
  with patch.object(r,'from_coordinates',AsyncMock(side_effect=s.Unavailable('unknown'))),patch.object(r.gbis,'search',AsyncMock()) as gbis:
   with self.assertRaises(s.Unavailable):asyncio.run(r.search('11',longitude=127,latitude=37))
  gbis.assert_not_called()
 def test_reverse_admin_province_disambiguates_gwangju(self):
  import httpx
  class Response:
   def raise_for_status(self):pass
   def json(self):return {'features':[{'properties':{'countrycode':'KR','city':'Gwangju','state':'Gwangju'},'geometry':{'coordinates':[126.85,35.16]}}]}
  with patch('httpx.AsyncClient.get',AsyncMock(return_value=Response())):
   region,_=asyncio.run(r.from_coordinates(126.85,35.16))
  self.assertEqual(region['scope'],'unsupported');self.assertEqual(region['name'],'광주광역시')
 def test_coverage_does_not_claim_nationwide(self):
  out=r.coverage();self.assertIsNone(out['default_region']);self.assertFalse(out['nationwide_coverage'])
