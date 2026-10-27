import asyncio
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse
from seoul_transit import open_data as o, discovery as d, service as s

class OpenDataTests(unittest.TestCase):
    def test_google_links_are_not_route_data(self):
        result=o.google_links(origin='서울역 & A', destination='Hongdae', mode='transit')
        self.assertEqual(result['status'], 'external_links')
        self.assertEqual(result['data'], [])
        params=parse_qs(urlparse(result['links'][0]['url']).query)
        self.assertEqual(params['origin'], ['서울역 & A'])
        self.assertEqual(params['travelmode'], ['transit'])
        self.assertNotIn('estimated_arrival',result)

    def test_open_first_even_if_paid_keys_exist(self):
        async def check():
            with patch.dict('os.environ', {'OPEN_DATA_FIRST':'true','KAKAO_REST_API_KEY':'test'}), patch.object(o,'search',new_callable=AsyncMock,return_value={'status':'ok'}) as search, patch('seoul_transit.travel.kakao_places',new_callable=AsyncMock) as paid:
                await d.places('cafe')
                search.assert_awaited_once()
                paid.assert_not_awaited()
        asyncio.run(check())

    def test_country_filter_and_no_platform(self):
        async def check():
            features=[{'properties':{'countrycode':code,'name':'Example','osm_key':'railway','osm_value':'station','osm_type':'N','osm_id':1,'platform':'8'},'geometry':{'coordinates':[127,37]}} for code in ['KR','KP','US']]
            with patch.object(o,'public_request',new_callable=AsyncMock,return_value=({'features':features},'2026-10-27T12:00:00+09:00',False)):
                result=await o.search('Example',stations=True)
                self.assertEqual(len(result['data']),1)
                self.assertIsNone(result['data'][0]['platform'])
                self.assertEqual(result['data_kind'],'community_map_not_live')
        asyncio.run(check())

    def test_osm_outage_yields_links_without_fake_results(self):
        async def check():
            with patch.object(o,'public_request',new_callable=AsyncMock,side_effect=s.Unavailable('outage')):
                result=await o.search('Seoul')
                self.assertEqual(result['status'],'external_links')
                self.assertEqual(result['data'],[])
        asyncio.run(check())

    def test_nearby_validation_and_partial_failure(self):
        async def check():
            for coords in [(float('nan'),37),(127,91),(127,37)]:
                with self.assertRaises(ValueError):
                    await o.nearby(*coords, radius=6000)
            with patch.object(o,'public_request',new_callable=AsyncMock,return_value=({'elements':[], 'remark':'timeout'},'',False)):
                with self.assertRaises(s.Unavailable):
                    await o.nearby(127,37)
        asyncio.run(check())

    def test_cache_preserves_retrieval_time_and_avoids_network(self):
        async def check():
            o._cache.clear()
            with patch.object(s,'request',new_callable=AsyncMock,return_value={'features':[]}) as request, patch.object(o,'_last',0),patch.object(o,'_calls',0):
                first=await o.public_request('https://photon.komoot.io/api/',{'q':'test'})
                second=await o.public_request('https://photon.komoot.io/api/',{'q':'test'})
                self.assertEqual(first[1],second[1])
                self.assertTrue(second[2])
                request.assert_awaited_once()
            o._cache.clear()
        asyncio.run(check())

    def test_route_without_graph_only_links(self):
        async def check():
            with patch.dict('os.environ', {'NETWORK_FILE':''}):
                result=await d.route('Seoul Station','Gangnam Station')
                self.assertEqual(result['data_kind'],'external_links_only')
        asyncio.run(check())

    def test_live_arrivals_still_require_official_key(self):
        with patch.dict('os.environ', {'SEOUL_SUBWAY_API_KEY':''}):
            with self.assertRaises(s.Unavailable):
                asyncio.run(s.arrivals('강남'))

if __name__=='__main__': unittest.main()
