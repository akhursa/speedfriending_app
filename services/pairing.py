import random
from sqlalchemy import func
from sqlmodel import select
from models import Pairing, PairHistory

def _match(ids, met, budget):
    """Рандомизированный backtracking: идеальное паросочетание без повторов или None."""
    order = ids[:]
    random.shuffle(order)
    used, pairs, steps = set(), [], [0]

    def rec():
        steps[0] += 1
        if steps[0] > budget:
            return False
        p = next((x for x in order if x not in used), None)
        if p is None:
            return True
        used.add(p)
        cands = [c for c in order if c not in used and (min(p, c), max(p, c)) not in met]
        random.shuffle(cands)
        for c in cands:
            used.add(c); pairs.append((p, c))
            if rec():
                return True
            pairs.pop(); used.discard(c)
        used.discard(p)
        return False

    return pairs if rec() else None

def _greedy_min_repeats(ids, met):
    """Запасной вариант: повторы неизбежны, минимизируем жадно."""
    order = ids[:]; random.shuffle(order)
    used, pairs = set(), []
    for p in order:
        if p in used: continue
        used.add(p)
        cands = [c for c in order if c not in used]
        fresh = [c for c in cands if (min(p, c), max(p, c)) not in met]
        c = (fresh or cands)[0]
        used.add(c); pairs.append((p, c))
    return pairs

def make_pairs(session, event_id, participant_ids, round_number):
    rows = session.exec(select(PairHistory.a_id, PairHistory.b_id).where(PairHistory.event_id == event_id)).all()
    met = {(min(a, b), max(a, b)) for (a, b) in rows}
    ids = participant_ids[:]
    rest_person, pairs = None, None

    if len(ids) % 2 == 1:
        rest_data = session.exec(select(Pairing.p1_id, func.count(Pairing.id)).where(Pairing.event_id == event_id, Pairing.p2_id == None).group_by(Pairing.p1_id)).all()
        rc = {pid: 0 for pid in ids}
        for pid, cnt in rest_data:
            if pid in rc: rc[pid] = cnt
        by_rest = sorted(ids, key=lambda x: (rc[x], random.random()))
        for cand in by_rest:                       # сначала те, кто отдыхал меньше всех
            rest = [x for x in ids if x != cand]
            pairs = _match(rest, met, 20000)
            if pairs is not None:
                rest_person = cand; break
        if pairs is None:
            rest_person = by_rest[0]
            pairs = _greedy_min_repeats([x for x in ids if x != rest_person], met)
    else:
        pairs = _match(ids, met, 20000) or _greedy_min_repeats(ids, met)

    out = []
    for a, b in pairs:
        out.append((a, b))
        k = (min(a, b), max(a, b))
        if k not in met:
            session.add(PairHistory(event_id=event_id, a_id=k[0], b_id=k[1], round_number=round_number))
            met.add(k)
    if rest_person is not None:
        out.append((rest_person, None))
    session.flush()
    return out
