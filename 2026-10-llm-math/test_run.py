#!/usr/bin/env -S uv run --script
"""Offline checks for deterministic cases, accurate scoring, and restart behavior."""
import json
import tempfile
from pathlib import Path

from run import (VERSION, final_integer, identity, latest, load, missing,
                 operands, planned, strict_integer)


def main() -> None:
    cfg = json.loads(Path('plan.json').read_text())
    plan = planned(cfg)
    observations = load()
    assert len(plan) == 712 and len({identity(x) for x in plan}) == len(plan)
    assert not missing(plan, observations), 'all saved requests should be cached'
    assert len(missing(plan, [])) == len(plan), 'deleting raw results must schedule all calls'

    # Same fixed seed across models; operand lengths, oracle, and prompt version.
    for digits in [2, 8, 35, 50]:
        case = operands(digits, 10, cfg['seed'])
        assert case == operands(digits, 10, cfg['seed'])
        assert len(case) == 10
        assert all(len(str(a)) == digits and len(str(b)) == digits for a, b in case)
    assert len(VERSION) == 12
    assert final_integer('66 × 71 = 4686. So the answer is 4,686.') == 4686
    assert final_integer('12345678') == 12345678
    assert final_integer('') is None and not strict_integer('Answer: 42')
    assert strict_integer('1,234')

    observed = latest(observations)
    candidate = plan[-1]
    without_one = [r for r in observations if identity(r) != identity(candidate)]
    assert [identity(r) for r in missing(plan, without_one)] == [identity(candidate)]
    errored = next(x for x in plan if observed[identity(x)]['status'] != 'ok')
    assert not missing([errored], observations)
    assert len(missing([errored], observations, retry_errors=True)) == 1
    credit_pending = missing(plan, observations, retry_credit_errors=True)
    assert not credit_pending, "credit retries already produced cached API replies"

    # Retry a 402, but do not repeat it if the latest failure is actually a 401.
    credit = dict(observed[identity(plan[0])], status="error", error="code: 402")
    auth = dict(credit, error="code: 401")
    assert latest([credit, auth])[identity(credit)]["error"] == "code: 401"
    assert not missing([plan[0]], [credit, auth], retry_credit_errors=True)
    assert len(missing([plan[0]], [auth, credit], retry_credit_errors=True)) == 1
    assert not missing([plan[0]], [credit, auth], retry_errors=False)

    # A duplicate earlier error must not displace a later successful reply.
    good = dict(observed[identity(plan[0])], status='ok')
    bad = dict(good, status='error')
    assert latest([bad, good])[identity(good)]['status'] == 'ok'
    assert latest([good, bad])[identity(good)]['status'] == 'ok'
    with tempfile.TemporaryDirectory() as folder:
        location = Path(folder) / 'results.jsonl'
        assert load(location) == []
        location.write_text(json.dumps(good) + '\n')
        assert len(load(location)) == 1

    # Independently check recorded reference products, not merely the stored correctness bit.
    for r in observed.values():
        assert int(r['expected']) == int(r['a']) * int(r['b'])
        if r['status'] == 'ok' and r.get('format_ok'):
            # Early pilot runs stored a strict-format `correct` flag; prose
            # answers were re-scored as arithmetic-correct in analyze.py.
            assert (final_integer(r['answer']) == int(r['expected'])) == r['correct']
    print(f'PASS: cached plan {len(plan)} requests, {len(observations)} raw attempts; resume, deletion, oracle and scoring')


if __name__ == '__main__':
    main()
