The module adds no menu or view of its own; it exposes two searchable fields
that other modules and custom views build on:

- `hr.expense.payment_ids` — the payments linked to the expense's journal
  entry, whether by reconciliation or by the payment register.
- `account.payment.reconciled_expense_ids` — the reverse direction, the
  employee-paid expenses this payment settled.

Both are readable by employees without accounting access, and both can be
searched (`[("payment_ids", "in", payment_ids)]` and the mirror image), so
they can be dropped straight into a view, a filter or a report.

**Upgrading from 18.0.** Up to 18.0 the module stored its own
payment/expense-sheet table. 19.0 has no expense sheet and stores nothing —
both fields derive from core. Most 18.0 links survive that on their own,
because the payment register had already recorded them in core's own table
against the sheet's journal entry, and OpenUpgrade re-points that entry at
the expense. The upgrade script `migrations/19.0.1.0.0/post-migration.py`
carries over the remainder: links this module had recorded from a
reconciliation that has since been undone, which nothing in the accounting
data can rebuild. It logs how many links it carried, and does nothing at all
on a fresh install.
