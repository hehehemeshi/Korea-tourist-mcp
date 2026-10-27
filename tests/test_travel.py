import asyncio
import unittest
from unittest.mock import AsyncMock, patch
from seoul_transit import travel as t
from seoul_transit import service as s

class TravelTests(unittest.TestCase):
    def test_invalid_coordinates(self):
        for value in ('nan,37', '127,91', '181,37', '127,37,0'):
            with self.assertRaises(ValueError):
                t.point(value)

    def test_kakao_contract(self):
        async def check():
            with patch.object(s, 'key', return_value='test-secret'), patch.object(s, 'request', new_callable=AsyncMock) as get:
                get.return_value={'documents': [{'place_name':'테스트'}], 'meta':{'is_end':True}}
                result=await t.kakao_places('카페')
                self.assertEqual(result['data'][0]['place_name'], '테스트')
                self.assertEqual(get.call_args.kwargs['headers']['Authorization'], 'KakaoAK test-secret')
                self.assertNotIn('test-secret', str(result))
        asyncio.run(check())

    def test_kto_single_item_and_paging(self):
        async def check():
            with patch.object(s, 'key', return_value='secret'), patch.object(s, 'request', new_callable=AsyncMock) as get:
                get.return_value={'response':{'header':{'resultCode':'0000'}, 'body':{'items':{'item':{'title':'Example'}},'totalCount':1}}}
                result=await t.search_tourism('Seoul', 2)
                self.assertEqual(result['data'], [{'title':'Example'}])
                self.assertEqual(get.call_args.args[1]['pageNo'], 2)
                self.assertEqual(result['data_kind'],'tourism_directory_not_live')
        asyncio.run(check())

    def test_provider_error_is_not_no_data(self):
        async def check():
            with patch.object(s, 'key', return_value='secret'), patch.object(s, 'request', new_callable=AsyncMock, return_value={'response':{'header':{'resultCode':'30'}}}):
                with self.assertRaises(s.Unavailable):
                    await t.search_tourism('Seoul')
        asyncio.run(check())

    def test_driving_is_not_transit(self):
        async def check():
            with patch.object(t, 'naver_headers', return_value={}), patch.object(s, 'request', new_callable=AsyncMock) as get:
                get.return_value={'code':0,'route':{'traoptimal':[{'summary':{'distance':1000,'duration':60000}}]}}
                result=await t.driving_route('127,37', '128,38')
                self.assertEqual(result['data_kind'],'driving_route_not_public_transit')
                self.assertEqual(get.call_args.args[1]['start'], '127.0,37.0')
        asyncio.run(check())

    def test_missing_key(self):
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(s.Unavailable):
                asyncio.run(t.kakao_places('cafe'))

if __name__ == '__main__':
    unittest.main()
