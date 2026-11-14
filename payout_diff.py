"""Reconcile processor balance entries against a bank-export CSV in integer cents."""
import argparse
import csv
from collections import defaultdict
from datetime import date, timedelta
import json
from pathlib import Path
import re


def read_rows(path, fields):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not set(fields) <= set(reader.fieldnames) or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError(f'{path}: expected unique headers including {", ".join(fields)}')
        for row in reader:
            try:
                if None in row or any(row[field] is None for field in fields):
                    raise ValueError('incorrect number of columns')
                yield {field: row[field].strip() for field in fields}
            except ValueError as exc:
                raise ValueError(f'{path}:{reader.line_num}: {exc}') from exc


def cents(value):
    if not re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?', value):
        raise ValueError(f'invalid two-decimal amount {value!r}')
    whole, _, fraction = value.lstrip('-').partition('.')
    amount = int(whole) * 100 + int(fraction.ljust(2, '0'))
    return -amount if value.startswith('-') else amount


def load(path, identifier, fields):
    result = {}
    for row in read_rows(path, [identifier, 'currency', 'date', 'amount', *fields]):
        key = row[identifier]
        if not key or key in result:
            raise ValueError(f'{path}: duplicate or empty {identifier} {key!r}')
        if not re.fullmatch(r'[A-Z]{3}', row['currency']):
            raise ValueError(f'{path}: expected uppercase three-letter currency')
        row['date'] = date.fromisoformat(row['date'])
        row['amount'] = cents(row['amount'])
        result[key] = row
    return result


def reconcile(ledger_path, bank_path, days=3):
    if not 0 <= days <= 365:
        raise ValueError('days must be in [0, 365]')
    ledger = load(ledger_path, 'entry_id', ['payout_id'])
    deposits = load(bank_path, 'deposit_id', ['reference'])
    grouped = defaultdict(list)
    for entry in ledger.values():
        if not entry['payout_id']:
            raise ValueError('empty payout_id')
        grouped[entry['payout_id']].append(entry)
    payouts = {}
    for key, entries in sorted(grouped.items()):
        currency = entries[0]['currency']
        if any(e['currency'] != currency for e in entries):
            raise ValueError(f'{key}: mixed currencies in payout')
        payouts[key] = (currency, sum(e['amount'] for e in entries), max(e['date'] for e in entries))
    references = defaultdict(list)
    amounts = defaultdict(list)
    for key, deposit in sorted(deposits.items()):
        if deposit['reference']:
            references[deposit['reference']].append(key)
        else:
            amounts[deposit['currency'], deposit['amount']].append(key)
    candidates = {}
    owners = defaultdict(list)
    for key, (currency, amount, day) in payouts.items():
        if key in references:
            continue
        eligible = [d for d in amounts[currency, amount] if
                    timedelta(0) <= deposits[d]['date'] - day <= timedelta(days=days)]
        candidates[key] = eligible
        for deposit_id in eligible:
            owners[deposit_id].append(key)

    results = []
    used = set()
    for key, (currency, amount, day) in payouts.items():
        ids = references.get(key) or candidates.get(key, [])
        if key in references:
            if len(ids) > 1:
                status = 'duplicate_reference'
            else:
                bank = deposits[ids[0]]
                status = 'matched_reference' if (bank['currency'], bank['amount']) == (currency, amount) else 'reference_mismatch'
        elif not ids:
            status = 'missing_deposit'
        elif len(ids) == 1 and len(owners[ids[0]]) == 1:
            status = 'matched_amount_date'
        else:
            status = 'ambiguous'
        if status.startswith('matched_'):
            used.update(ids)
        results.append(dict(payout_id=key, status=status, currency=currency, expected_cents=amount,
                            settlement_date=day.isoformat(), entry_ids=sorted(e['entry_id'] for e in grouped[key]),
                            candidates=[dict(deposit_id=d, amount_cents=deposits[d]['amount'],
                                             currency=deposits[d]['currency'], date=deposits[d]['date'].isoformat())
                                        for d in ids]))
    return dict(payouts=results, unallocated_deposits=sorted(set(deposits) - used))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger')
    parser.add_argument('bank')
    parser.add_argument('--days', type=int, default=3)
    parser.add_argument('--strict', action='store_true', help='exit 1 if any exception remains')
    args = parser.parse_args()
    try:
        report = reconcile(args.ledger, args.bank, args.days)
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(2, f'{parser.prog}: {exc}\n')
    print(json.dumps(report, indent=2))
    if args.strict and (report['unallocated_deposits'] or any(not r['status'].startswith('matched_') for r in report['payouts'])):
        parser.exit(1)


if __name__ == '__main__':
    main()
