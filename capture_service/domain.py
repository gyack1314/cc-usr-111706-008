"""解释领域原文；待核来源不转换成确认结论。

角色边界：
- agenda 议程：只记录会议安排与生命周期（延期/撤回/重排），不得记载决议；
- minutes 纪要：会议举行后才可能出现，决议只能由纪要承载；
- support 附件：开发商等第三方材料，附件来源随原文与收据留存。
同一案号的历次版次属于同一项目；不同部门案号仅凭正式交叉引用合并，
其余关系一律登记为待核，不参与归并。
"""
import json
import re

AGENDA = 'agenda'
MINUTES = 'minutes'
LIFECYCLE = {'scheduled', 'postponed', 'withdrawn', 'rescheduled'}
FORMAL = 'formal-cross-reference'
RELATED = 'related'
CONFIRMED = 'confirmed'
PENDING = 'pending'
_REVISION = re.compile(r'^([rm])(\d+)$')
_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def revision_order(version):
    m = _REVISION.fullmatch(str(version))
    if not m:
        raise ValueError('来源版次不明')
    return m.group(1), int(m.group(2))


def _link(source, target, basis, state, version, note):
    return {'source_docket': source, 'target_docket': target, 'basis': basis,
            'state': state, 'version': version, 'note': note}


def _decode_links(docket_id, payload, version):
    out = []
    for ref in payload.get('cross_references') or []:
        target = str(ref.get('docket', ''))
        if not target or target == 'None':
            raise ValueError('交叉引用案号不明')
        if target == docket_id:
            raise ValueError('交叉引用不得指向本案号')
        if str(ref.get('authority', '')) == 'formal':
            out.append(_link(docket_id, target, FORMAL, CONFIRMED, version,
                             str(ref.get('note', ''))))
        else:
            out.append(_link(docket_id, target, RELATED, PENDING, version,
                             'authority=' + str(ref.get('authority', 'missing'))))
    for ref in payload.get('related_dockets') or []:
        target = str(ref.get('docket', ''))
        if not target or target == 'None':
            raise ValueError('关联案号不明')
        if target == docket_id:
            raise ValueError('关联关系不得指向本案号')
        out.append(_link(docket_id, target, RELATED, PENDING, version,
                         str(ref.get('note', ''))))
    return out


def decode(raw, receipt):
    d = json.loads(raw.decode('utf-8'))
    revision = str(d.get('revision', ''))
    revision_order(revision)
    identity = str(d.get('docket'))
    if not identity or identity == 'None':
        raise ValueError('来源身份不明')
    if 'meeting' in d and not _DATE.fullmatch(str(d['meeting'])):
        raise ValueError('会议日期格式不明')
    links = []
    if 'attachment' in d:
        if str(d.get('docket', '')) in ('', 'None'):
            raise ValueError('附件缺少所属案号')
        row = {'type': 'support', 'id': str(d['attachment']),
               'version': revision, 'kind': d.get('kind', 'support'), 'payload': d}
    else:
        kind = d.get('kind', AGENDA)
        if kind not in (AGENDA, MINUTES):
            raise ValueError('资料角色不明')
        if kind == AGENDA:
            if 'decisions' in d:
                raise ValueError('议程不得记载会议决议')
            if d.get('status') not in LIFECYCLE:
                raise ValueError('议程生命周期状态不明')
        else:
            if 'status' in d:
                raise ValueError('纪要不得承载议程生命周期状态')
        row = {'type': 'docket', 'id': identity, 'version': revision,
               'kind': kind, 'payload': d}
        links = _decode_links(identity, d, revision)
    return {'entities': [row], 'links': links}


def assess(rows):
    primary = [r for r in rows if r['type'] == 'docket']
    support = [r for r in rows if r['type'] == 'support']
    has_minutes = any(r['payload'].get('kind') == MINUTES for r in primary)
    reasons = []
    if not has_minutes:
        reasons.append('会议纪要及决议尚未发布')
    if not primary:
        reasons.append('缺少主要来源')
    if not support:
        reasons.append('缺少关联来源')
    return {'publishable': False, 'reasons': reasons,
            'primary_count': len(primary), 'support_count': len(support)}
