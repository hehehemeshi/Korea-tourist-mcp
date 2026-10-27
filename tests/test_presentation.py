import base64
import copy
import json
import unittest
from urllib.parse import urlparse, parse_qs
from seoul_transit import presentation as p

def fact(v, source='https://example.org/source', status='unverified'):
    return dict(value=v,status=status,source_url=source,checked_at='2026-10-27T10:00:00+09:00')

def row(n=1):
    return dict(restaurant_id=f'osm:node:{n}',name=fact('식당'),address=fact('주소'),
        longitude=fact(127.001),latitude=fact(37.267),straight_line_distance_m=fact(n*10),
        menu=[dict(name_ko=fact('칼국수'),price_krw=fact(5000))])

def result(rows):
    return dict(status='ok',search=dict(longitude=127.,latitude=37.266),data=rows,
        ranking_method='budget_first',fetched_at='2026-10-27T10:00:00+09:00')

class PresentationTests(unittest.TestCase):
    def test_nearest_ten_preserves_evidence_without_mutating_input(self):
        src=result([row(n) for n in range(12,0,-1)]); before=copy.deepcopy(src)
        out=p.format_result(src)
        self.assertEqual(src,before)
        self.assertEqual([r['restaurant_id'] for r in out['data']],[f'osm:node:{n}' for n in range(1,11)])
        self.assertTrue(out['display_truncated'])
        self.assertEqual(out['data'][0]['name'],src['data'][-1]['name'])
        self.assertEqual(out['assessment_ranking_method'],'budget_first')

    def test_missing_inline_menu_and_review(self):
        r=row();r.update(address=fact(None),menu=[])
        out=p.format_result(result([r])); c=out['presentation']['restaurants'][0]
        self.assertEqual(c['address'],p.MISSING)
        self.assertEqual(c['reviews']['summary'],p.MISSING)
        self.assertIn('| Chưa có thông tin | Chưa có thông tin |',out['markdown'])
        self.assertIn('Số lượt đánh giá: Chưa có thông tin',out['markdown'])

    def test_inline_translation_price_and_time(self):
        out=p.format_result(result([row()]))
        self.assertIn('칼국수 | Mì cắt dao | ₩5,000 (chưa xác minh hiện tại)',out['markdown'])
        self.assertIn('2026-10-27T10:00:00+09:00',out['markdown'])
        menu=out['presentation']['restaurants'][0]['menu'][0]
        self.assertEqual(menu['translation_method'],'literal_glossary_translation')
        self.assertEqual(p.menu_card({'name_ko':fact('특선')})['name_vi'],p.MISSING)

    def test_zero_and_review_provenance(self):
        r=row();r.update(rating=fact(0),review_count=fact(0),review_highlights=[fact('Quán nhỏ'),fact('Không nguồn',None)])
        c=p.format_result(result([r]))['presentation']['restaurants'][0]
        self.assertEqual(c['reviews']['rating_display'],'0/5')
        self.assertEqual(c['reviews']['review_count_display'],'0')
        self.assertEqual(c['reviews']['summary'],'Quán nhỏ')
        self.assertEqual(p.money(fact(0)),'₩0')
        self.assertEqual(p.review_card({'rating':fact(8),'review_count':fact(1.5)})['rating_display'],p.MISSING)
        self.assertEqual(p.review_card({'rating':fact(5)})['summary'],p.MISSING)

    def test_shared_map_and_walking_link_use_supplied_coordinates(self):
        report=p.format_result(result([row(2),row(1)]))['presentation']
        features=report['map']['features']
        self.assertEqual(features[0]['geometry']['coordinates'],[127.,37.266])
        self.assertEqual([f['properties']['number'] for f in features[1:]],[1,2])
        link=report['restaurants'][0]['walking_directions_url']
        query=parse_qs(urlparse(link).query)
        self.assertEqual(query['origin'],['37.266,127.0'])
        self.assertEqual(query['destination'],['37.267,127.001'])
        self.assertEqual(query['travelmode'],['walking'])
        url=urlparse(report['map_url']);self.assertEqual(url.query,'')
        payload=json.loads(base64.urlsafe_b64decode(url.fragment+'='*(-len(url.fragment)%4)))
        self.assertEqual(payload['origin'],[127.,37.266])
        self.assertEqual(payload['restaurants'][0]['number'],1)
        self.assertEqual(report['restaurants'][0]['walking_distance_display'],p.MISSING)

    def test_missing_origin_does_not_invent_it(self):
        src=result([row()]);src.pop('search')
        out=p.format_result(src)
        self.assertIsNone(out['presentation']['restaurants'][0]['walking_directions_url'])
        self.assertFalse(any(f['properties']['kind']=='origin' for f in out['presentation']['map']['features']))

    def test_error_remains_visible(self):
        out=p.format_result({'status':'unavailable','message':'Nguồn lỗi'})
        self.assertIn('Nguồn lỗi',out['markdown'])
        self.assertIn('không khả dụng',out['markdown'])
        self.assertEqual(out['status'],'unavailable')

    def test_unsafe_source_and_name(self):
        r=row();r['name']=fact('<script>alert(1)</script> | x')
        r['review_highlights']=[fact('Fake','javascript:alert(1)')]
        out=p.format_result(result([r]))
        self.assertNotIn('<script>',out['markdown'])
        self.assertEqual(out['presentation']['restaurants'][0]['reviews']['summary'],p.MISSING)
        self.assertIsNone(p.coords(float('nan'),37))
        self.assertIsNone(p.safe_url('https://user:pass@example.org'))
