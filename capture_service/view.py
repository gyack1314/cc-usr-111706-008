"""按领域解释结果展示项目证据、时间线与缺口。

项目归并规则：只有 state=confirmed 的正式交叉引用把不同案号并入同一项目，
pending 关系仅列入待核清单。项目当前状态取议程最高版次，旧版次保留在时间线，
因此纪要晚到不会抹掉旧公告，任何历史版次的原文仍可回放。
"""
from .ledger import entities, links, receipt_urls
from .domain import assess, revision_order, AGENDA, MINUTES, CONFIRMED, PENDING


def _sort_versions(rows):
    return sorted(rows, key=lambda r: revision_order(r['version']))


def _build_projects(rows, urls):
    dockets = sorted({r['id'] for r in rows if r['type'] == 'docket'})
    attachments = {}
    for r in rows:
        if r['type'] == 'support':
            attachments.setdefault(r['payload'].get('docket'), []).append(r)
    projects = []
    for docket in dockets:
        docs = [r for r in rows if r['type'] == 'docket' and r['id'] == docket]
        timeline = []
        latest_agenda = None
        for r in sorted(docs, key=lambda r: r['arrival_seq']):
            p = r['payload']
            kind = p.get('kind', AGENDA)
            entry = {'kind': kind, 'revision': r['version'],
                     'arrival_seq': r['arrival_seq'],
                     'source_url': urls.get(r['source']),
                     'source_sha256': r['source']}
            if kind == AGENDA:
                entry['status'] = p.get('status')
                if 'meeting' in p:
                    entry['meeting_date'] = p['meeting']
                if 'location' in p:
                    entry['location'] = p['location']
                if 'attachments' in p:
                    entry['agenda_attachments'] = list(p['attachments'])
                latest_agenda = entry
            else:
                if 'meeting' in p:
                    entry['meeting_date'] = p['meeting']
                if 'decisions' in p:
                    entry['decisions'] = list(p['decisions'])
            timeline.append(entry)
        agendas = [e for e in timeline if e['kind'] == AGENDA]
        latest_agenda = (sorted(agendas, key=lambda e: revision_order(e['revision']))[-1]
                         if agendas else None)
        support_rows = _sort_versions(attachments.get(docket, []))
        support = [{'attachment_id': r['id'], 'revision': r['version'],
                    'kind': r['payload'].get('kind', 'support'),
                    'declared_source': r['payload'].get('source'),
                    'source_url': urls.get(r['source']),
                    'source_sha256': r['source']}
                   for r in support_rows]
        gaps = []
        if not any(e['kind'] == MINUTES for e in timeline):
            gaps.append('会议纪要及决议尚未发布')
        if latest_agenda is None:
            gaps.append('缺少议程主要来源')
        else:
            if 'meeting_date' not in latest_agenda:
                gaps.append('最新议程缺少会议日期')
            if 'location' not in latest_agenda:
                gaps.append('最新议程缺少地点')
            if latest_agenda['status'] == 'withdrawn':
                gaps.append('项目已撤回，后续材料不应再登记为新会议')
        if not support:
            gaps.append('缺少附件关联来源')
        projects.append({'docket': docket, 'current_status':
                         latest_agenda['status'] if latest_agenda else None,
                         'meeting_date':
                         latest_agenda.get('meeting_date') if latest_agenda else None,
                         'location':
                         latest_agenda.get('location') if latest_agenda else None,
                         'agenda_revision':
                         latest_agenda['revision'] if latest_agenda else None,
                         'timeline': timeline, 'attachments': support,
                         'gaps': gaps, 'publishable': not gaps})
    return projects, attachments


def _clusters(dockets, confirmed):
    parent = {d: d for d in dockets}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for link in confirmed:
        a, b = link['source_docket'], link['target_docket']
        if a in parent and b in parent:
            parent[find(a)] = find(b)
    groups = {}
    for d in dockets:
        groups.setdefault(find(d), []).append(d)
    return [sorted(v) for v in groups.values()]


def overview(c, collection):
    rows = entities(c, collection)
    all_links = links(c, collection)
    urls = receipt_urls(c, collection)
    result = assess(rows)
    result['collection'] = collection
    result['records'] = [{'type': r['type'], 'id': r['id'],
                          'version': r['version'], 'source_sha256': r['source']}
                         for r in rows]
    projects, attachments = _build_projects(rows, urls)
    by_docket = {p['docket']: p for p in projects}
    dockets = [p['docket'] for p in projects]
    confirmed = [l for l in all_links if l['state'] == CONFIRMED]
    pending = [l for l in all_links if l['state'] == PENDING]
    grouped = _clusters(dockets, confirmed)
    result['projects'] = []
    for members in grouped:
        primary = members[0]
        base = by_docket[primary]
        merged_timeline = sorted(
            (e for docket in members for e in by_docket[docket]['timeline']),
            key=lambda e: e['arrival_seq'])
        merged_attachments = [a for docket in members
                              for a in by_docket[docket]['attachments']]
        merged_gaps = sorted({g for docket in members
                              for g in by_docket[docket]['gaps']})
        result['projects'].append({
            'project_id': 'project:' + primary,
            'dockets': members,
            'current_status': base['current_status'],
            'meeting_date': base['meeting_date'],
            'location': base['location'],
            'agenda_revision': base['agenda_revision'],
            'timeline': merged_timeline,
            'attachments': merged_attachments,
            'gaps': merged_gaps,
            'publishable': not merged_gaps,
        })
    result['confirmed_links'] = confirmed
    result['pending_links'] = pending
    orphan_attachments = sorted(a for a in attachments if a not in by_docket)
    result['orphan_attachments'] = orphan_attachments
    result['reasons'] = sorted(set(result['reasons'] +
                                   [g for p in result['projects'] for g in p['gaps']]))
    result['publishable'] = bool(projects) and all(p['publishable'] for p in result['projects'])
    return result
