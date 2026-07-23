This module links each employee-paid expense to the payment(s) that settled
it, in both directions: `hr.expense.payment_ids` and
`account.payment.reconciled_expense_ids`.

The link is computed from the reconciliation between the expense's journal
entry and the payment's journal items — the same way core derives
`reconciled_bill_ids` on payments. It therefore always reflects the current
accounting state (partial payments included), needs no manual bookkeeping,
and covers payments however they were registered (expense's Register
Payment button, the journal entry's own button, or manual reconciliation).

Odoo 19.0 core's `account.payment.expense_ids` only covers company-paid
expenses (whose journal entry *is* the payment's move); this module covers
the employee-reimbursement direction that core does not track.
