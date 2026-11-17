"""按来源身份原子登记原文、领域记录与案号关系。

receipts 与 entities 只追加不改写：同一实体新版次另插一行，旧公告原文
始终可经 receipts 回放；同一版次再次送达而原文不同即冲突回滚。
links 记录案号关系，state 区分正式交叉引用与待核关系，待核不产生归并。
"""
import hashlib
import json
import sqlite3
from .domain import decode

SCHEMA = """
CREATE TABLE IF NOT EXISTS receipts(collection TEXT NOT NULL,body_sha256 TEXT NOT NULL,source_url TEXT NOT NULL,status INTEGER NOT NULL,raw BLOB NOT NULL,PRIMARY KEY(collection,body_sha256));
CREATE TABLE IF NOT EXISTS entities(collection TEXT NOT NULL,entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,version TEXT NOT NULL,receipt_sha256 TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(collection,entity_type,entity_id,version),FOREIGN KEY(collection,receipt_sha256) REFERENCES receipts(collection,body_sha256));
CREATE TABLE IF NOT EXISTS links(collection TEXT NOT NULL,source_docket TEXT NOT NULL,target_docket TEXT NOT NULL,basis TEXT NOT NULL,state TEXT NOT NULL,version TEXT NOT NULL,note TEXT NOT NULL,receipt_sha256 TEXT NOT NULL,PRIMARY KEY(collection,source_docket,target_docket,state),FOREIGN KEY(collection,receipt_sha256) REFERENCES receipts(collection,body_sha256));
"""


def connect(path):
    c = sqlite3.connect(path)
    c.execute('PRAGMA foreign_keys=ON')
    c.executescript(SCHEMA)
    return c


def receive(c, collection, raw, receipt):
    if receipt['status'] != 200:
        raise ValueError('来源未返回成功正文')
    sha = hashlib.sha256(raw).hexdigest()
    if sha != receipt['body_sha256']:
        raise ValueError('收据与原文不符')
    decoded = decode(raw, receipt)
    with c:
        c.execute('INSERT OR IGNORE INTO receipts VALUES(?,?,?,?,?)',
                  (collection, sha, receipt['url'], receipt['status'], raw))
        for row in decoded['entities']:
            payload = json.dumps(row['payload'], ensure_ascii=False, sort_keys=True)
            key = (collection, row['type'], row['id'], row['version'])
            prior = c.execute(
                'SELECT receipt_sha256,payload_json FROM entities '
                'WHERE collection=? AND entity_type=? AND entity_id=? AND version=?',
                key).fetchone()
            if prior and prior != (sha, payload):
                raise ValueError('同一实体版本原文冲突')
            c.execute('INSERT OR IGNORE INTO entities VALUES(?,?,?,?,?,?)',
                      (*key, sha, payload))
        for link in decoded['links']:
            key = (collection, link['source_docket'], link['target_docket'], link['state'])
            prior = c.execute(
                'SELECT basis,version,note,receipt_sha256 FROM links '
                'WHERE collection=? AND source_docket=? AND target_docket=? AND state=?',
                key).fetchone()
            current = (link['basis'], link['version'], link['note'], sha)
            if prior and prior != current:
                raise ValueError('同一案号关系声明冲突')
            c.execute('INSERT OR IGNORE INTO links VALUES(?,?,?,?,?,?,?,?)',
                      (collection, link['source_docket'], link['target_docket'],
                       link['basis'], link['state'], link['version'], link['note'], sha))
    return sha


def entities(c, collection):
    rows = c.execute(
        'SELECT rowid,entity_type,entity_id,version,receipt_sha256,payload_json '
        'FROM entities WHERE collection=?', (collection,)).fetchall()
    return [{'arrival_seq': r[0], 'type': r[1], 'id': r[2], 'version': r[3],
             'source': r[4], 'payload': json.loads(r[5])} for r in rows]


def links(c, collection):
    return [dict(source_docket=r[0], target_docket=r[1], basis=r[2], state=r[3],
                 version=r[4], note=r[5], source=r[6])
            for r in c.execute(
                'SELECT source_docket,target_docket,basis,state,version,note,receipt_sha256 '
                'FROM links WHERE collection=? ORDER BY source_docket,target_docket,state',
                (collection,))]


def receipt_urls(c, collection):
    return dict(c.execute(
        'SELECT body_sha256,source_url FROM receipts WHERE collection=?',
        (collection,)).fetchall())


def receipt_raw(c, collection, body_sha256):
    row = c.execute(
        'SELECT raw FROM receipts WHERE collection=? AND body_sha256=?',
        (collection, body_sha256)).fetchone()
    return row[0] if row else None
