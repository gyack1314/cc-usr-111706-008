"""核对项目归并、生命周期版次、纪要晚到与交叉引用待核。"""
import hashlib
import unittest
from pathlib import Path
from capture_service.transport import Replay
from capture_service.ledger import connect, receive, receipt_raw
from capture_service.view import overview
from capture_service.domain import decode

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = 'hearings'


def load(manifest_path):
    replay = Replay(manifest_path)
    db = connect(':memory:')
    for step in replay.steps:
        req = step['request']
        raw, receipt = replay.request(req['method'], req['url'])
        receive(db, COLLECTION, raw, receipt)
    return db


class ProjectLifecycle(unittest.TestCase):
    def setUp(self):
        self.db = load(ROOT / 'data/lifecycle/manifest.json')

    def test_rescheduling_keeps_single_project(self):
        view = overview(self.db, COLLECTION)
        d7 = [p for p in view['projects'] if 'D-7' in p['dockets']]
        self.assertEqual(len(d7), 1)
        project = d7[0]
        self.assertEqual(project['current_status'], 'rescheduled')
        self.assertEqual(project['agenda_revision'], 'r3')
        self.assertEqual(project['meeting_date'], '2027-01-14')
        self.assertEqual([e['revision'] for e in project['timeline'] if e['kind'] == 'agenda'],
                         ['r1', 'r2', 'r3'])

    def test_late_minutes_do_not_erase_old_announcements(self):
        project = next(p for p in overview(self.db, COLLECTION)['projects']
                       if 'D-7' in p['dockets'])
        r1 = next(e for e in project['timeline'] if e['revision'] == 'r1')
        self.assertEqual(r1['status'], 'scheduled')
        self.assertEqual(r1['meeting_date'], '2026-12-10')
        raw = receipt_raw(self.db, COLLECTION, r1['source_sha256'])
        self.assertIsNotNone(raw)
        self.assertIn(b'"status": "scheduled"', raw)

    def test_attachment_source_retained(self):
        project = next(p for p in overview(self.db, COLLECTION)['projects']
                       if 'D-7' in p['dockets'])
        self.assertEqual(len(project['attachments']), 1)
        att = project['attachments'][0]
        self.assertEqual(att['attachment_id'], 'A-70')
        self.assertEqual(att['declared_source'], '北岭数据中心开发商')
        self.assertTrue(att['source_url'].startswith('https://planning.example.test/'))

    def test_withdrawn_project_flagged_not_duplicated(self):
        view = overview(self.db, COLLECTION)
        d11 = [p for p in view['projects'] if 'D-11' in p['dockets']]
        self.assertEqual(len(d11), 1)
        self.assertEqual(d11[0]['current_status'], 'withdrawn')
        self.assertIn('项目已撤回，后续材料不应再登记为新会议', d11[0]['gaps'])

    def test_decisions_only_from_minutes(self):
        project = next(p for p in overview(self.db, COLLECTION)['projects']
                       if 'D-7' in p['dockets'])
        minutes = [e for e in project['timeline'] if e['kind'] == 'minutes']
        self.assertEqual([e['revision'] for e in minutes], ['m1'])
        self.assertIn('有条件批准，须补充降噪方案', minutes[0]['decisions'])
        agendas = [e for e in project['timeline'] if e['kind'] == 'agenda']
        self.assertTrue(all('decisions' not in e for e in agendas))

    def test_timeline_follows_arrival_order(self):
        project = next(p for p in overview(self.db, COLLECTION)['projects']
                       if 'D-7' in p['dockets'])
        self.assertEqual([e['revision'] for e in project['timeline']],
                         ['r1', 'r2', 'r3', 'm1'])


class CrossReferences(unittest.TestCase):
    def setUp(self):
        self.db = load(ROOT / 'data/crossref/manifest.json')

    def test_only_formal_reference_merges_dockets(self):
        view = overview(self.db, COLLECTION)
        merged = [p for p in view['projects'] if set(p['dockets']) == {'X-1', 'X-2'}]
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['project_id'], 'project:X-1')
        self.assertEqual(len(view['projects']), 1)
        self.assertEqual(len(view['confirmed_links']), 1)
        self.assertEqual(len(merged[0]['timeline']), 2)
        self.assertTrue(all(e['kind'] == 'agenda' for e in merged[0]['timeline']))

    def test_other_relationships_remain_pending(self):
        view = overview(self.db, COLLECTION)
        pending = {(l['source_docket'], l['target_docket'])
                   for l in view['pending_links']}
        self.assertEqual(pending, {('X-1', 'X-3'), ('X-1', 'X-4')})
        self.assertTrue(all(l['state'] == 'pending' for l in view['pending_links']))

    def test_changed_relationship_claim_rolls_back(self):
        from capture_service.ledger import links
        raw = ('{"docket":"X-1","revision":"r2","kind":"agenda",'
               '"meeting":"2026-12-05","location":"规划局听证室","status":"scheduled",'
               '"cross_references":[{"docket":"X-2","authority":"formal",'
               '"note":"改口：非正式互引"}]}'.encode('utf-8'))
        receipt = {'url': 'https://planning.example.test/hearing-docket/X-1/r2',
                   'status': 200, 'body_sha256': hashlib.sha256(raw).hexdigest()}
        before = links(self.db, COLLECTION)
        with self.assertRaises(ValueError):
            receive(self.db, COLLECTION, raw, receipt)
        self.assertEqual(links(self.db, COLLECTION), before)


class DomainGuards(unittest.TestCase):
    def test_agenda_cannot_carry_decisions(self):
        raw = ('{"docket":"D-9","revision":"r1","kind":"agenda",'
               '"meeting":"2026-12-01","location":"听证室","status":"scheduled",'
               '"decisions":["批准"]}'.encode('utf-8'))
        with self.assertRaises(ValueError):
            decode(raw, {})

    def test_minutes_cannot_carry_lifecycle_status(self):
        raw = ('{"docket":"D-9","revision":"m1","kind":"minutes",'
               '"meeting":"2026-12-01","status":"scheduled"}'.encode('utf-8'))
        with self.assertRaises(ValueError):
            decode(raw, {})

    def test_unknown_revision_rejected(self):
        with self.assertRaises(ValueError):
            decode(b'{"docket":"D-9","revision":"v1"}', {})


if __name__ == '__main__':
    unittest.main()
