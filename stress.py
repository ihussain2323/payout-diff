"""Generate a seeded payout close and check every allocation against independent labels."""
import argparse
import csv
from itertools import cycle
import json
from pathlib import Path
import random
import tempfile
import time

from payout_diff import reconcile

SCENARIOS = ('reference', 'fallback', 'short', 'wrong_currency', 'missing', 'ambiguous_pair', 'duplicate_reference')


def decimal(cents):
    return f"{'-' if cents < 0 else ''}{abs(cents)//100}.{abs(cents)%100:02}"


def exercise(count, seed):
    rng = random.Random(seed)
    labels = {}
    expected_claims = {}
    ledger = []
    deposits = []
    nets = rng.sample(range(10000, 20000000), count)
    scenarios = cycle(SCENARIOS)
    for i, net in enumerate(nets):
        scenario = next(scenarios)
        cur = rng.choice(('USD', 'EUR', 'GBP'))
        payout = f'p{i}'
        deposit = f'b{i}'
        fee = rng.randint(10, 250)
        row = [payout, cur, '2025-03-03']
        ledger.extend([[f'c{i}', *row, decimal(net + fee)], [f'f{i}', *row, decimal(-fee)]])
        expected_claims[payout] = []
        if scenario == 'missing':
            labels[payout] = 'missing_deposit'
            continue
        ref = '' if scenario in ('fallback', 'ambiguous_pair') else payout
        currency = 'CAD' if scenario == 'wrong_currency' else cur
        value = net - 1 if scenario == 'short' else net
        deposits.append([deposit, ref, currency, '2025-03-04', decimal(value)])
        expected_claims[payout].append(deposit)
        if scenario == 'ambiguous_pair':
            twin = payout + 'x'
            ledger.append([f't{i}', twin, cur, '2025-03-03', decimal(net)])
            labels[twin] = 'ambiguous'
            expected_claims[twin] = [deposit]
        if scenario == 'duplicate_reference':
            deposits.append([deposit + 'x', ref, currency, '2025-03-05', decimal(value)])
            expected_claims[payout].append(deposit + 'x')
        labels[payout] = {'reference': 'matched_reference', 'fallback': 'matched_amount_date',
                          'short': 'reference_mismatch', 'wrong_currency': 'reference_mismatch',
                          'ambiguous_pair': 'ambiguous', 'duplicate_reference': 'duplicate_reference'}[scenario]
    rng.shuffle(deposits)
    rng.shuffle(ledger)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for filename, header, rows in [
                ('ledger', ['entry_id','payout_id','currency','date','amount'], ledger),
                ('bank', ['deposit_id','reference','currency','date','amount'], deposits)]:
            with (root/filename).open('w', newline='', encoding='utf-8') as stream:
                writer = csv.writer(stream)
                writer.writerow(header)
                writer.writerows(rows)
        start = time.perf_counter()
        report = reconcile(root/'ledger', root/'bank')
        elapsed = time.perf_counter() - start
    if len(report['payouts']) != len(labels):
        raise RuntimeError('payout count does not match input')
    allocated = set()
    for row in report['payouts']:
        key = row['payout_id']
        ids = [c['deposit_id'] for c in row['candidates']]
        if labels[key] != row['status'] or ids != sorted(expected_claims[key]):
            raise RuntimeError(f'{key}: expected {labels[key]} and {expected_claims[key]}, got {row}')
        if row['status'].startswith('matched_'):
            if allocated.intersection(ids):
                raise RuntimeError(f'{key}: deposit allocated twice')
            allocated.update(ids)
    unused = {row[0] for row in deposits} - allocated
    if unused != set(report['unallocated_deposits']):
        raise RuntimeError('unallocated deposit IDs do not tie')
    for currency, control in report['controls_by_currency'].items():
        if control['matched_cents'] + control['open_ledger_cents'] != control['ledger_cents']:
            raise RuntimeError(f'{currency}: ledger control does not tie')
        if control['matched_cents'] + control['unallocated_bank_cents'] != control['bank_cents']:
            raise RuntimeError(f'{currency}: bank control does not tie')
    return dict(seed=seed, ledger_entries=len(ledger), payouts=len(labels), bank_deposits=len(deposits),
                allocated_deposits=len(allocated), unallocated_deposits=len(unused), reconcile_seconds=round(elapsed, 4))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--groups', type=int, default=10000)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    if not 7 <= args.groups <= 1000000:
        parser.error('groups must be between 7 and 1,000,000')
    print(json.dumps(exercise(args.groups, args.seed), indent=2))
