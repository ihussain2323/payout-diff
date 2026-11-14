# Payout Diff

Trace a bank deposit back to the charges, fees, and refunds in a processor export. This offline reconciliation CLI produces a JSON audit trail and a queue of exceptions. The sample files are synthetic.

## Reproduce the sample

Requires Python 3.10+ and its standard library.

```sh
python3 payout_diff.py examples/ledger.csv examples/bank.csv
python3 -m unittest discover -s tests -v
```

Payout `po_1` settles at $86.80 after a $3.20 fee and a $10 refund. Its bank reference confirms the match. Two other payouts each claim the same $45 deposit. Both stay open for review. The final referenced EUR payout is short by one cent. Its candidate record retains the observed amount and currency.

## Matching rules

1. Group signed processor entries by payout ID. Require one currency per group and use the latest entry date as the settlement date.
2. Check explicit bank references first. A single deposit matches if the currency and amount agree. Report multiple references or an amount/currency disagreement for review, regardless of deposit date.
3. For a payout without a reference, consider only unreferenced deposits in the same currency with the exact net amount. The deposit date must fall between settlement and `--days` calendar days later, inclusive (default 3). Allocate only when both the payout and the deposit have exactly one candidate.
4. Include every unallocated deposit in the report. Output order is deterministic. Duplicate source IDs are input errors.

Use the example CSV headers for your own exports. Dates are ISO calendar dates. Amounts use signed decimal strings and a two-decimal minor unit. Split deposits, FX conversion, and currencies with a different minor unit require a different matching policy. No bank credentials are used.

For batch jobs, add `--strict`. A clean report exits 0, open exceptions exit 1, and invalid input exits 2.

## Review exceptions with operations

```sh
python3 review.py examples/ledger.csv examples/bank.csv workpaper.html
```

Open the resulting HTML file in a browser. Toggle **Show only exceptions** and expand a payout to inspect its source entry IDs, candidate deposits, dates, and amounts. The workpaper runs offline. Its per-currency control totals tie expected payouts to matched and open ledger amounts, and bank deposits to matched and unallocated bank amounts. A balanced control total can still contain unresolved exceptions.
