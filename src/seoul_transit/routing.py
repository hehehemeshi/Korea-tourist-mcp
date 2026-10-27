"""Route only over operator-supplied, attributed directed edges; never infer adjacency."""
import heapq
import json
import itertools
import os
from pathlib import Path
from urllib.parse import urlparse
from .service import Unavailable, now, text


def plan(origin, destination):
    origin, destination = text(origin), text(destination)
    path = os.getenv('NETWORK_FILE')
    if not path:
        raise Unavailable('Chưa có đồ thị tuyến đã xác minh. Cấu hình NETWORK_FILE; không thể suy đoán tuyến.')
    network = json.loads(Path(path).read_text())
    source = network['source']
    host = urlparse(source).hostname or ''
    if not (host.endswith('.go.kr') or host in ('seoulmetro.co.kr', 'www.seoulmetro.co.kr', 'www.korail.com')):
        raise ValueError('Đồ thị phải ghi nguồn cơ quan chính thức.')
    verified = __import__('datetime').date.fromisoformat(network['verified_on'])
    age = (now().date() - verified).days
    if age < 0 or age > 90:
        raise Unavailable('Đồ thị tuyến cần được xác minh lại (tối đa 90 ngày).')
    graph = {}
    for edge in network['edges']:
        if edge['kind'] not in ('ride', 'transfer') or edge['seconds'] <= 0:
            raise ValueError('Cạnh tuyến không hợp lệ.')
        graph.setdefault(edge['from'], []).append(edge)
    counter = itertools.count()
    queue = [(0, next(counter), origin, [])]
    seen = set()
    while queue:
        cost, _, node, steps = heapq.heappop(queue)
        if node in seen:
            continue
        seen.add(node)
        if node == destination:
            return dict(status='ok', data=steps, planned_seconds=cost,
                transfers=sum(s['kind'] == 'transfer' for s in steps),
                source=source, verified_on=network['verified_on'], fetched_at=now().isoformat(),
                data_kind='static_route_not_live', platform=None,
                note='Chỉ trong phạm vi đồ thị; chưa gồm thời gian chờ, gián đoạn hoặc lịch tàu cuối.')
        for e in graph.get(node, []):
            # Counter makes equal-cost heap entries independent of dictionary ordering.
            if e['to'] not in seen:
                heapq.heappush(queue, (cost + e['seconds'], next(counter), e['to'], steps + [e]))
    return dict(status='no_data', data=[], source=source, fetched_at=now().isoformat(),
                note='Không tìm thấy tuyến trong dữ liệu đã xác minh.')
