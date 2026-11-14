"""Render an offline reconciliation workpaper from the original two exports."""
import argparse
from html import escape
from pathlib import Path

from payout_diff import reconcile


def money(cents):
    whole, fraction = divmod(abs(cents), 100)
    return f"{'-' if cents < 0 else ''}{whole:,}.{fraction:02d}"


def table(headers, rows):
    labels = ''.join(f'<th scope="col">{escape(h)}</th>' for h in headers)
    body = ''.join('<tr>' + ''.join(f'<td>{escape(str(cell))}</td>' for cell in row) + '</tr>' for row in rows)
    return f'<div class="scroll"><table><thead><tr>{labels}</tr></thead><tbody>{body}</tbody></table></div>'


def render(report):
    controls = report['controls_by_currency']
    balances = table(['Currency', 'Expected', 'Bank', 'Matched', 'Open payouts', 'Open deposits'],
                     ((cur, *(money(row[k]) for k in ['ledger_cents', 'bank_cents', 'matched_cents',
                       'open_ledger_cents', 'unallocated_bank_cents'])) for cur, row in controls.items()))
    cases = []
    for payout in report['payouts']:
        status = payout['status']
        candidates = payout['candidates']
        evidence = table(['Candidate deposit', 'Date', 'Currency', 'Observed'],
                         ((c['deposit_id'], c['date'], c['currency'], money(c['amount_cents'])) for c in candidates))
        if not candidates:
            evidence = '<p>No eligible bank deposit.</p>'
        entry_ids = ', '.join(escape(key) for key in payout['entry_ids'])
        matched = status.startswith('matched_')
        category = 'matched' if matched else 'open'
        cases.append(f'<details class="{category}"><summary><b>{escape(payout["payout_id"])}</b>'
                     f'<span>{escape(status.replace("_", " "))}</span>'
                     f'<strong>{escape(payout["currency"])} {money(payout["expected_cents"])}</strong></summary>'
                     f'<section><p>Ledger entries <code>{entry_ids}</code></p>{evidence}</section></details>')
    unallocated = ', '.join(escape(key) for key in report['unallocated_deposits']) or 'None'
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Payout reconciliation</title><style>
:root{font:16px/1.55 system-ui;color:#192d32;background:#f4f6f4}body{max-width:960px;margin:auto;padding:3vw}
h1{font-size:clamp(2rem,5vw,3.4rem);letter-spacing:-.05em;margin-bottom:.4em}h2{margin-top:2em}
.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;background:white;font-variant-numeric:tabular-nums}
th,td{white-space:nowrap;padding:.65em .8em;border-bottom:1px solid #d6ddda;text-align:left}th{font-size:.85em}
details{background:white;border-left:4px solid #358072;margin:.5em 0}details.open{border-color:#9e561e}
summary{cursor:pointer;padding:1em}summary span{margin-left:1em}summary strong{float:right}section{padding:0 1em 1em}
input:checked~details.matched{display:none}code{overflow-wrap:anywhere}input{accent-color:#236a60}
@media(max-width:520px){summary strong{display:block;float:none}summary span{font-size:.9em}}
</style><main><h1>Payout reconciliation</h1><h2>Control totals</h2>''' + balances + '''
<h2>Trace a payout</h2><input id="open" type="checkbox"> <label for="open">Show only exceptions</label>
''' + ''.join(cases) + '<h2>Unallocated bank deposits</h2><p>' + unallocated + '</p></main></html>'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger')
    parser.add_argument('bank')
    parser.add_argument('output', type=Path)
    parser.add_argument('--days', type=int, default=3)
    args = parser.parse_args()
    try:
        document = render(reconcile(args.ledger, args.bank, args.days))
        if args.output.resolve() in {Path(args.ledger).resolve(), Path(args.bank).resolve()}:
            raise ValueError('choose an output path separate from the source exports')
        args.output.write_text(document, encoding='utf-8')
    except (OSError, ValueError) as exc:
        parser.exit(2, f'{parser.prog}: {exc}\n')
