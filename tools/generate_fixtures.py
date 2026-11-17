"""生成生命周期与交叉引用冻结样例（合成数据，不访问网络）。"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_case(case_dir, origin, payloads):
    case_dir.mkdir(parents=True, exist_ok=True)
    steps = []
    for name, url, payload in payloads:
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
        (case_dir / name).write_bytes(raw)
        steps.append({
            'request': {'method': 'GET', 'url': url,
                        'body_sha256': hashlib.sha256(b'').hexdigest()},
            'response': {'file': name, 'status': 200,
                         'bytes': len(raw),
                         'sha256': hashlib.sha256(raw).hexdigest()},
        })
    manifest = {'allowed_origins': [origin], 'steps': steps}
    (case_dir / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


write_case(ROOT / 'data/lifecycle', 'https://planning.example.test', [
    ('agenda-r1.bin', 'https://planning.example.test/hearing-docket/D-7/r1',
     {'docket': 'D-7', 'revision': 'r1', 'kind': 'agenda',
      'meeting': '2026-12-10', 'location': '市政厅三号会议室',
      'status': 'scheduled', 'attachments': ['A-70']}),
    ('attachment-a70.bin', 'https://planning.example.test/hearing-docket/A-70',
     {'docket': 'D-7', 'revision': 'r1', 'attachment': 'A-70',
      'kind': 'developer-statement', 'source': '北岭数据中心开发商',
      'status': 'available'}),
    ('agenda-r2.bin', 'https://planning.example.test/hearing-docket/D-7/r2',
     {'docket': 'D-7', 'revision': 'r2', 'kind': 'agenda',
      'meeting': '2026-12-10', 'location': '市政厅三号会议室',
      'status': 'postponed', 'attachments': ['A-70'],
      'note': '听证延期，案号不变'}),
    ('agenda-r3.bin', 'https://planning.example.test/hearing-docket/D-7/r3',
     {'docket': 'D-7', 'revision': 'r3', 'kind': 'agenda',
      'meeting': '2027-01-14', 'location': '市政厅三号会议室',
      'status': 'rescheduled', 'attachments': ['A-70']}),
    ('minutes-m1.bin', 'https://planning.example.test/hearing-docket/D-7/m1',
     {'docket': 'D-7', 'revision': 'm1', 'kind': 'minutes',
      'meeting': '2027-01-14',
      'decisions': ['有条件批准，须补充降噪方案']}),
    ('agenda-d11-r1.bin', 'https://planning.example.test/hearing-docket/D-11/r1',
     {'docket': 'D-11', 'revision': 'r1', 'kind': 'agenda',
      'meeting': '2026-11-20', 'location': '市政厅一号会议室',
      'status': 'scheduled', 'attachments': []}),
    ('agenda-d11-r2.bin', 'https://planning.example.test/hearing-docket/D-11/r2',
     {'docket': 'D-11', 'revision': 'r2', 'kind': 'agenda',
      'meeting': '2026-11-20', 'location': '市政厅一号会议室',
      'status': 'withdrawn', 'attachments': []}),
])

write_case(ROOT / 'data/crossref', 'https://planning.example.test', [
    ('agenda-x1-r1.bin', 'https://planning.example.test/hearing-docket/X-1/r1',
     {'docket': 'X-1', 'revision': 'r1', 'kind': 'agenda',
      'meeting': '2026-12-05', 'location': '规划局听证室',
      'status': 'scheduled', 'attachments': [],
      'cross_references': [
          {'docket': 'X-2', 'authority': 'formal',
           'note': '规划局案号与环评案号正式互引'},
          {'docket': 'X-3', 'authority': 'inferred',
           'note': '同地块线索，待核'}],
      'related_dockets': [
          {'docket': 'X-4', 'note': '开发商自述相邻项目'}]}),
    ('agenda-x2-r1.bin', 'https://planning.example.test/hearing-docket/X-2/r1',
     {'docket': 'X-2', 'revision': 'r1', 'kind': 'agenda',
      'meeting': '2026-12-05', 'location': '规划局听证室',
      'status': 'scheduled', 'attachments': []}),
])
print('frozen samples written')
