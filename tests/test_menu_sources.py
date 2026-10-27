import asyncio
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from pydantic import ValidationError
from seoul_transit import evidence as e, menu_sources as m, restaurants as r, service as s

class MenuSourceTests(unittest.TestCase):
    def profile(self,kind='merchant_jsonld'):
        rid='source:synthetic-test'
        return m.Profile(restaurant_id=rid,name='테스트 식당',address='1 Test Street',kind=kind,
            source_url='https://example.org/menu',discovery_method='synthetic_test',snapshot=e.RestaurantEvidence(restaurant_id=rid))
    def page(self,html):
        p=m.Page();p.feed(html);return p
    def test_real_catalog_is_not_empty_and_prices_are_not_current_verified(self):
        with patch.dict(os.environ,{'RESTAURANT_SOURCE_CATALOG':''}):
            catalog=m.catalog()
            self.assertEqual(len(catalog),5)
            self.assertEqual(sum(len(p.snapshot.menu) for p in catalog),15)
            result=m.find('Suwon')
            self.assertEqual(len(result['data']),2)
            record,_=asyncio.run(m.read_source('source:suwon-219569',refresh=False))
            self.assertEqual(record['menu'][0]['price_krw']['value'],5000)
            self.assertEqual(record['menu'][0]['price_krw']['status'],'unverified')
            self.assertEqual(record['menu'][0]['price_krw']['method'],'search_index')
    def test_two_people_rule_is_not_two_servings(self):
        record,_=asyncio.run(m.read_source('source:kto-hankookjib',refresh=False))
        item=record['menu'][1]
        self.assertEqual(item['minimum_diners']['value'],2)
        self.assertIsNone(item['minimum_servings']['value'])
        self.assertIsNone(item['price_basis']['value'])
    def test_two_serving_set_is_not_minimum_order_rule(self):
        record,_=asyncio.run(m.read_source('source:kto-apple-house',refresh=False))
        self.assertIsNone(record['menu'][1]['minimum_servings']['value'])
        self.assertIsNone(record['menu'][1]['minimum_diners']['value'])
    def test_explicit_serving_rule_kept_on_one_item_only(self):
        record,_=asyncio.run(m.read_source('source:kto-ohyeon-dongmun',refresh=False))
        self.assertEqual(record['menu'][0]['minimum_servings']['value'],2)
        self.assertIsNone(record['menu'][1]['minimum_servings']['value'])
        self.assertIsNone(record['policy']['minimum_servings']['value'])
    def test_source_outage_preserves_snapshot_timestamp_and_discloses_failure(self):
        async def check():
            p=m.profile_for('source:suwon-219569')
            old=p.snapshot.menu[0].price_krw.checked_at.isoformat()
            with patch.object(m,'fetch_page',new_callable=AsyncMock,side_effect=s.Unavailable('offline')):
                result=await m.details(p.restaurant_id,'menu')
                self.assertEqual(result['source']['refresh_status'],'unavailable_snapshot_only')
                self.assertEqual(result['data']['items'][0]['price_krw']['checked_at'],old)
                self.assertEqual(result['status'],'partial')
        asyncio.run(check())
    def test_suwon_parses_only_own_menu_table_and_does_not_infer_policies(self):
        profile=self.profile('suwon_table')
        html='<h1>테스트 식당</h1><table><tr><th>주소</th><td>1 Test Street</td></tr><tr><th>대표메뉴</th><td>칼국수 5,000원, 수제비 6,000원</td></tr></table><script>"다른메뉴 10원"</script>'
        record=m.suwon_table(profile,self.page(html),s.now().isoformat())
        self.assertEqual([i['price_krw']['value'] for i in record['menu']],[5000,6000])
        self.assertIsNone(record['policy']['minimum_servings']['value'])
        self.assertIsNone(record['menu'][0]['price_basis']['value'])
    def test_suwon_identity_mismatch_rejected(self):
        with self.assertRaises(ValueError):m.suwon_table(self.profile('suwon_table'),self.page('<table><tr><th>대표메뉴</th><td>칼국수 5,000원</td></tr></table>'),s.now().isoformat())
    def test_merchant_jsonld_exact_branch_and_currency(self):
        owner={'@type':'Restaurant','name':'테스트 식당','address':{'streetAddress':'1 Test Street'},'hasMenu':{'@type':'Menu','hasMenuItem':[{'@type':'MenuItem','name':'국밥','offers':{'price':'8,000','priceCurrency':'KRW'},'additionalProperty':[{'name':'minimum_servings','value':2}]}]}}
        page=self.page('<script type="application/ld+json">'+json.dumps(owner)+'</script>')
        record=m.merchant_jsonld(self.profile(),page,s.now().isoformat())
        self.assertEqual(record['menu'][0]['price_krw']['value'],8000)
        self.assertEqual(record['menu'][0]['price_krw']['status'],'unverified')
        self.assertEqual(record['menu'][0]['minimum_servings']['value'],2)
        self.assertIsNone(record['policy']['minimum_servings']['value'])
        owner['address']['streetAddress']='Another branch'
        with self.assertRaises(ValueError):m.merchant_jsonld(self.profile(),self.page('<script type="application/ld+json">'+json.dumps(owner)+'</script>'),s.now().isoformat())
    def test_range_and_currency_are_not_guessed(self):
        for value in ['from 8000','8,000~10,000','시가',True,None]:self.assertIsNone(m.exact_money(value))
        owner={'@type':'Restaurant','name':'테스트 식당','address':'1 Test Street','hasMenu':{'@type':'MenuItem','name':'Dish','offers':{'price':10,'priceCurrency':'USD'}}}
        with self.assertRaises(ValueError):m.merchant_jsonld(self.profile(),self.page('<script type="application/ld+json">'+json.dumps(owner)+'</script>'),s.now().isoformat())
    def test_menu_photo_requires_explicit_menu_caption(self):
        record=m.clean_record('source:synthetic-test')
        page=self.page('<img src="food.jpg" alt="food"><img src="menu.jpg" alt="메뉴판"><img src="javascript:bad" alt="메뉴판">')
        m.add_menu_images(record,self.profile(),page,s.now().isoformat())
        self.assertEqual(len(record['menu_images']),1)
        self.assertEqual(record['menu_images'][0]['value'],'https://example.org/menu.jpg')
    def test_only_catalog_urls_can_be_fetched(self):
        async def check():
            with patch.object(m,'catalog',return_value=[]):
                with self.assertRaises(s.Unavailable):await m.fetch_page(self.profile())
        asyncio.run(check())
    def test_private_ip_and_credential_urls_rejected(self):
        raw=self.profile().model_dump()
        for url in ['http://example.org/menu','https://127.0.0.1/menu','https://user:pw@example.org/menu','https://host.local/menu','https://example.org:8080/menu']:
            with self.assertRaises(ValidationError):m.Profile(**{**raw,'source_url':url})
    def test_same_name_does_not_create_an_osm_binding(self):
        self.assertIsNone(m.profile_for('osm:node:123456789'))
        self.assertEqual(m.find(restaurant_id='osm:node:123456789')['data'],[])
    def test_menu_source_wrapper_accepts_known_source_id(self):
        async def check():
            with patch.object(m,'fetch_page',new_callable=AsyncMock,side_effect=s.Unavailable('offline')):
                result=await r.details_with_sources('source:kto-hankookjib','policy')
                self.assertEqual(result['item_policies'][0]['minimum_diners']['value'],2)
                self.assertIsNone(result['data']['solo_allowed']['value'])
        asyncio.run(check())

if __name__=='__main__':unittest.main()

class SourceMergeTests(unittest.TestCase):
    def test_bound_source_does_not_overwrite_reviewed_menu(self):
        async def check():
            row=r.candidate('osm:node:1','Test','Address',127,37,'https://www.openstreetmap.org/node/1',s.now().isoformat())
            r.attach_evidence(row)
            row['menu']=[{'reviewed':'keep'}]
            record=m.clean_record('source:synthetic-test')
            record['menu']=[{'automatic':'do not replace'}]
            with patch.object(m,'profile_for',return_value=object()),patch.object(m,'read_source',new_callable=AsyncMock,return_value=(record,{'refresh_status':'fetched'})):
                await r.enrich_sources(row)
                self.assertEqual(row['menu'],[{'reviewed':'keep'}])
        asyncio.run(check())
    def test_menu_policy_return_does_not_promote_source_values(self):
        async def check():
            with patch.object(m,'fetch_page',new_callable=AsyncMock,side_effect=s.Unavailable('offline')):
                result=await r.details_with_sources('source:kto-ohyeon-dongmun','policy')
                self.assertEqual(result['item_policies'][0]['minimum_servings']['status'],'unverified')
                self.assertIsNone(result['data']['solo_allowed']['value'])
        asyncio.run(check())
    def test_missing_branch_identity_does_not_refresh_article_timestamp(self):
        async def check():
            with patch.object(m,'fetch_page',new_callable=AsyncMock,return_value=('<html>Some other restaurant</html>',s.now().isoformat(),False)):
                result=await m.details('source:kto-hankookjib','menu')
                self.assertEqual(result['source']['refresh_status'],'unavailable_snapshot_only')
        asyncio.run(check())

class FixedPriceTests(unittest.TestCase):
    def test_from_prices_do_not_become_fixed_prices(self):
        profile=MenuSourceTests().profile('suwon_table')
        page=m.Page()
        page.feed('<h1>테스트 식당</h1><table><tr><th>주소</th><td>1 Test Street</td></tr><tr><th>대표메뉴</th><td>칼국수 5,000원부터</td></tr></table>')
        with self.assertRaises(ValueError):m.suwon_table(profile,page,s.now().isoformat())
