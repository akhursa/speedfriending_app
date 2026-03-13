import random

from sqlalchemy import func
from sqlmodel import Session, select

from models import Pairing, PairHistory


def make_pairs(
    session: Session,
    event_id: int,
    participant_ids: list[int],
    round_number: int,
) -> list[tuple[int, int | None]]:
    rows = session.exec(
        select(PairHistory.a_id, PairHistory.b_id).where(
            PairHistory.event_id == event_id
        )
    ).all()
    met = {(min(a, b), max(a, b)) for (a, b) in rows}

    ids = participant_ids[:]
    random.shuffle(ids)

    rest_person = None
    if len(ids) % 2 == 1:
        rest_data = session.exec(
            select(Pairing.p1_id, func.count(Pairing.id))
            .where(Pairing.event_id == event_id, Pairing.p2_id == None)
            .group_by(Pairing.p1_id)
        ).all()
        rest_counts = {pid: 0 for pid in participant_ids}
        for pid, count in rest_data:
            if pid in rest_counts:
                rest_counts[pid] = count

        min_rest = min(rest_counts.values())
        candidates = sorted(
            [pid for pid in participant_ids if rest_counts[pid] == min_rest]
        )
        rest_person = candidates[(round_number - 1) % len(candidates)]
        ids = [pid for pid in ids if pid != rest_person]

    pairs: list[tuple[int, int | None]] = []
    used: set[int] = set()

    for p in ids:
        if p in used:
            continue

        partner = None
        for candidate in ids:
            if candidate in used or candidate == p:
                continue
            key = (min(p, candidate), max(p, candidate))
            if key not in met:
                partner = candidate
                break

        if partner is None:
            for candidate in ids:
                if candidate in used or candidate == p:
                    continue
                partner = candidate
                break

        used.add(p)
        if partner is not None:
            used.add(partner)
            pairs.append((p, partner))
            a, b = min(p, partner), max(p, partner)
            if (a, b) not in met:
                session.add(
                    PairHistory(
                        event_id=event_id,
                        a_id=a,
                        b_id=b,
                        round_number=round_number,
                    )
                )
                met.add((a, b))
        else:
            pairs.append((p, None))

    if rest_person is not None:
        pairs.append((rest_person, None))

    session.flush()
    return pairs
