"""Synthetic fixtures only: no fixture is exposed as a real restaurant/menu."""
import asyncio
import json
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch
from seoul_transit import restaurants as r, evidence as e, service as s


def verified(value, **overrides):
    return dict(value=value,status='verified',source_url='https://example.org/restaurant/menu',
        checked_at=s.now().isoformat(),method='restaurant_official',evidence_excerpt='Synthetic test evidence',**overrides)


def evidence_record(price=8000, minimum=1, solo=True):
    return {'restaurant_id':'osm:node:1','menu':[{'name_ko':verified('테스트 메뉴'),'price_krw':verified(price),
        'price_basis':verified('per_serving')}], 'policy':{'minimum_servings':verified(minimum),
        'one_item_per_person':verified(True),'solo_allowed':verified(solo),'minimum_order_krw':verified(0),'mandatory_extra_krw':verified(0)}}


def row(rid='osm:node:1',x=127.01,y=37.27,name='가상 식당'):
    return r.candidate(rid,name,'Synthetic test address',x,y,'https://www.openstreetmap.org/node/1',s.now().isoformat())

class RestaurantTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'KAKAO_REST_API_KEY':'','ORS_API_KEY':'','RESTAURANT_EVIDENCE_FILE':''})
        self.env.start()
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'evidence.json'
        os.environ['RESTAURANT_EVIDENCE_FILE']=str(self.path)
        self.path.write_text('{"restaurants":[]}')
        r._seen.clear()
    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()
    def store(self,*records):
        self.path.write_text(json.dumps({'restaurants':list(records)}))
    def assessed(self):
        return r.attach_evidence(row())

    def test_500m_failure_falls_back_to_photon(self):
        async def check():
            with patch.object(r,'overpass',new_callable=AsyncMock,side_effect=s.Unavailable('timeout')), patch.object(r,'photon',new_callable=AsyncMock,return_value=([row()],s.now().isoformat(),False)):
                result=await r.search_nearby(127.01,37.27,500)
                self.assertEqual(result['provider'],'photon')
                self.assertEqual(result['provider_attempts'][1]['status'],'error')
                self.assertEqual(result['data'][0]['assessment']['status'],'insufficient_evidence')
        asyncio.run(check())

    def test_empty_primary_also_uses_fallback_and_keeps_radius(self):
        async def check():
            with patch.object(r,'overpass',new_callable=AsyncMock,return_value=([],s.now().isoformat(),False)), patch.object(r,'photon',new_callable=AsyncMock,return_value=([row(x=127.01),row('osm:node:2',x=128)],s.now().isoformat(),False)):
                result=await r.search_nearby(127.01,37.27,500)
                self.assertEqual(len(result['data']),1)
                self.assertEqual(result['search']['radius_m'],500)
                self.assertIsNone(result['data'][0]['walking_distance_m']['value'])
        asyncio.run(check())

    def test_missing_key_does_not_call_kakao(self):
        async def check():
            with patch.object(r,'kakao',new_callable=AsyncMock) as kakao, patch.object(r,'overpass',new_callable=AsyncMock,return_value=([row()],s.now().isoformat(),False)):
                await r.search_nearby(127.01,37.27)
                kakao.assert_not_awaited()
        asyncio.run(check())

    def test_kakao_fd6_query_coordinates_and_radius(self):
        async def check():
            with patch.dict(os.environ,{'KAKAO_REST_API_KEY':'secret'}), patch.object(s,'request',new_callable=AsyncMock,return_value={'documents':[],'meta':{'is_end':True}}) as request:
                await r.kakao(127.01,37.27,500,'김밥')
                url,params=request.call_args.args
                self.assertTrue(url.endswith('keyword.json'))
                self.assertEqual(params['category_group_code'],'FD6')
                self.assertEqual((params['x'],params['y'],params['radius']),(127.01,37.27,500))
                self.assertEqual(params['query'],'김밥')
        asyncio.run(check())

    def test_hangul_and_space_normalisation(self):
        self.assertEqual(r.normalise_query('  김밥  '),'김밥')
        async def check():
            payload={'elements':[{'type':'node','id':1,'lon':127.01,'lat':37.27,'tags':{'amenity':'restaurant','name':'수원 김밥'}}]}
            with patch('seoul_transit.open_data.public_request',new_callable=AsyncMock,return_value=(payload,s.now().isoformat(),False)):
                rows,_,_=await r.overpass(127.01,37.27,500,'수원김밥')
                self.assertEqual(len(rows),1)
        asyncio.run(check())

    def test_photon_filters_other_country_wrong_category_and_circle(self):
        async def check():
            data={'features':[{'properties':{'countrycode':country,'osm_key':'amenity','osm_value':kind,'osm_type':'N','osm_id':i,'name':'김밥'},'geometry':{'coordinates':[127.01,37.27]}} for i,country,kind in [(1,'KR','restaurant'),(2,'US','restaurant'),(3,'KR','cafe')]]}
            with patch('seoul_transit.open_data.public_request',new_callable=AsyncMock,return_value=(data,s.now().isoformat(),False)) as fetch:
                rows,_,_=await r.photon(127.01,37.27,500,'김밥')
                self.assertEqual(len(rows),1)
                self.assertNotIn('lang',fetch.call_args.args[1])
        asyncio.run(check())

    def test_unknown_price_or_policy_never_confirms_budget(self):
        self.store(evidence_record())
        data=r.assess(self.assessed(),10000,1)
        self.assertEqual(data['status'],'meets_verified_constraints')
        item=evidence_record()
        del item['policy']['minimum_servings']
        self.store(item)
        self.assertEqual(r.assess(self.assessed(),10000,1)['status'],'insufficient_evidence')

    def test_two_portions_not_two_diners_and_budget_counts_both(self):
        self.store(evidence_record(minimum=2))
        self.assertEqual(r.assess(self.assessed(),10000,1)['status'],'insufficient_evidence')
        result=r.assess(self.assessed(),20000,1)
        self.assertEqual(result['status'],'meets_verified_constraints')
        self.assertEqual(result['total_krw'],16000)
        self.assertEqual(result['quantity'],2)

    def test_solo_denied_explicitly(self):
        self.store(evidence_record(solo=False))
        self.assertEqual(r.assess(self.assessed(),10000,1)['status'],'does_not_meet_verified_constraints')

    def test_minimum_bill_uses_whole_portions_not_fake_exact_total(self):
        data=evidence_record(price=10000)
        data['policy']['minimum_order_krw']=verified(15000)
        self.store(data)
        result=r.assess(self.assessed(),15000,1)
        self.assertEqual(result['status'],'insufficient_evidence')
        self.assertEqual(result['known_over_budget_options'][0]['total_krw'],20000)

    def test_unknown_item_policy_does_not_fall_back_to_optimistic_global_rule(self):
        data=evidence_record()
        data['menu'][0]['minimum_servings']={'value':2,'status':'unverified'}
        self.store(data)
        self.assertEqual(r.assess(self.assessed(),10000,1)['status'],'insufficient_evidence')

    def test_stale_missing_source_and_future_evidence_downgrade(self):
        for checked in [(s.now()-timedelta(days=31)).isoformat(),(s.now()+timedelta(days=1)).isoformat(),None]:
            data=verified(8000)
            data['checked_at']=checked
            self.assertEqual(e.normalise(data)['status'],'unverified')
        data=verified(8000)
        data['source_url']=None
        self.assertEqual(e.normalise(data)['status'],'unverified')

    def test_menu_never_supplies_policy_or_translation(self):
        data=evidence_record()
        del data['policy']
        self.store(data)
        menu=r.details('osm:node:1','menu')
        self.assertIsNone(menu['data']['items'][0]['name_vi']['value'])
        self.assertEqual(r.details('osm:node:1','policy')['status'],'unknown')

    def test_malformed_registry_does_not_expose_claims(self):
        self.path.write_text('{"restaurants":[{"restaurant_id":"osm:node:1","policy":{"minimum_servings":{"value":-1}}}]}')
        result=r.details('osm:node:1','policy')
        self.assertEqual(result['status'],'unknown')
        self.assertTrue(result['evidence_warning'])

    def test_opening_hours_do_not_prove_open_now(self):
        data=evidence_record()
        data['opening_hours']=verified('Mo-Su 00:00-24:00')
        self.store(data)
        self.assertIsNone(self.assessed()['open_now']['value'])

    def test_rank_confirmed_above_closer_unknown(self):
        self.store(evidence_record())
        async def check():
            with patch.object(r,'overpass',new_callable=AsyncMock,return_value=([row('osm:node:2'),row(x=127.011)],s.now().isoformat(),False)):
                result=await r.rank(127.01,37.27)
                self.assertEqual(result['data'][0]['restaurant_id'],'osm:node:1')
                self.assertIn('straight_line',result['ranking_method'])
        asyncio.run(check())

    def test_ors_failure_does_not_invent_walking_distance(self):
        async def check():
            data=row()
            with patch.dict(os.environ,{'ORS_API_KEY':'secret'}),patch.object(s,'request',new_callable=AsyncMock,side_effect=s.Unavailable('error')):
                await r.walking(data,127.01,37.27)
                self.assertIsNone(data['walking_distance_m']['value'])
        asyncio.run(check())

    def test_invalid_gps_budget_party_and_id(self):
        for args in [(float('nan'),37),(127,91),(127,37,0),(127,37,500,0),(127,37,500,10000,0)]:
            with self.assertRaises(ValueError): r.validate(*args)
        with self.assertRaises(ValueError): r.details('../../etc/passwd','menu')

if __name__=='__main__': unittest.main()

class AdditionalEvidenceTests(unittest.TestCase):
    setUp = RestaurantTests.setUp
    tearDown = RestaurantTests.tearDown
    store = RestaurantTests.store
    assessed = RestaurantTests.assessed
    # Separate cases reuse only temporary registry setup, no real venue facts.
    def test_mandatory_fees_count_against_budget(self):
        data=evidence_record(price=9000)
        data['policy']['mandatory_extra_krw']=verified(2000)
        self.store(data)
        self.assertEqual(r.assess(self.assessed(),10000,1)['status'],'insufficient_evidence')

    def test_set_capacity_and_people(self):
        data=evidence_record(price=18000)
        data['menu'][0]['price_basis']=verified('per_set')
        data['menu'][0]['serves_people']=verified(2)
        data['policy']['one_item_per_person']=verified(False)
        self.store(data)
        assessment=r.assess(self.assessed(),10000,2)
        self.assertEqual(assessment['total_krw'],18000)
        self.assertEqual(assessment['quantity'],1)

    def test_all_sources_fail_is_unavailable_with_attempts(self):
        async def check():
            with patch.object(r,'overpass',new_callable=AsyncMock,side_effect=s.Unavailable('outage')),patch.object(r,'photon',new_callable=AsyncMock,side_effect=s.Unavailable('outage')):
                result=await r.search_nearby(127.01,37.27)
                self.assertEqual(result['status'],'unavailable')
                self.assertEqual(result['data'],[])
                self.assertEqual(len(result['provider_attempts']),3)
        asyncio.run(check())

    def test_partial_overpass_result_triggers_independent_fallback(self):
        async def check():
            with patch('seoul_transit.open_data.public_request',new_callable=AsyncMock,return_value=({'elements':[],'remark':'runtime error'},s.now().isoformat(),False)):
                with self.assertRaises(s.Unavailable):
                    await r.overpass(127.01,37.27,500,'')
        asyncio.run(check())

    def test_expired_open_now_not_inferred_from_hours(self):
        data=evidence_record()
        data['open_now']=verified(True)
        data['open_now']['checked_at']=(s.now()-timedelta(minutes=6)).isoformat()
        self.store(data)
        self.assertEqual(self.assessed()['open_now']['status'],'unverified')

    def test_invalid_photo_url_is_not_returned_as_image(self):
        data=evidence_record()
        data['menu_images']=[{'value':'javascript:alert(1)','status':'unverified'}]
        self.store(data)
        self.assertIsNone(r.details('osm:node:1','menu')['data']['images'][0]['value'])

    def test_routed_distance_is_not_geodesic_multiplier(self):
        async def check():
            data=row()
            response={'features':[{'properties':{'summary':{'distance':712.4,'duration':540}}}]}
            with patch.dict(os.environ,{'ORS_API_KEY':'secret'}),patch.object(s,'request',new_callable=AsyncMock,return_value=response) as request:
                await r.walking(data,127.01,37.27)
                self.assertEqual(data['walking_distance_m']['value'],712)
                self.assertEqual(data['walking_duration_seconds']['value'],540)
                self.assertEqual(request.call_args.kwargs['headers']['Authorization'],'secret')
        asyncio.run(check())

class PhotonReverseTests(unittest.TestCase):
    def test_no_name_query_uses_category_reverse_in_kilometres(self):
        async def check():
            with patch('seoul_transit.open_data.public_request',new_callable=AsyncMock,return_value=({'features':[]},s.now().isoformat(),False)) as fetch:
                await r.photon(127.01,37.27,500,'')
                endpoint,params=fetch.call_args.args
                self.assertTrue(endpoint.endswith('/reverse'))
                self.assertEqual(params['radius'],0.5)
                self.assertNotIn('q',params)
                self.assertIn('amenity:restaurant',params['osm_tag'])
        asyncio.run(check())
