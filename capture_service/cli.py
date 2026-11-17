"""重放冻结来源并显示采集状态与项目时间线。"""
import argparse
import json
from .transport import Replay
from .ledger import connect, receive, receipt_raw
from .view import overview


def _run(manifest, db_path):
    replay = Replay(manifest)
    db = connect(db_path)
    collection = 'hearings'
    for step in replay.steps:
        req = step['request']
        raw, receipt = replay.request(req['method'], req['url'])
        receive(db, collection, raw, receipt)
    return db, collection


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['inspect', 'timeline'])
    p.add_argument('manifest')
    p.add_argument('--db', default=':memory:',
                   help='SQLite 路径；默认内存库，给路径可累积多次采集')
    args = p.parse_args()
    db, collection = _run(args.manifest, args.db)
    if args.command == 'inspect':
        print(json.dumps(overview(db, collection), ensure_ascii=False, indent=2))
    else:
        view = overview(db, collection)
        for project in view['projects']:
            print('项目', project['project_id'], '案号', ','.join(project['dockets']))
            for entry in project['timeline']:
                raw = receipt_raw(db, collection, entry['source_sha256'])
                print(' ', entry['revision'], entry['kind'],
                      entry.get('status') or entry.get('meeting_date', ''),
                      '原文可回放' if raw is not None else '原文缺失')
    db.close()


if __name__ == '__main__':
    main()
