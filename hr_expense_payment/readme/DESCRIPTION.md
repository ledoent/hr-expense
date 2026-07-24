This module links each employee-paid expense to the payment(s) that settled
it, in both directions: `hr.expense.payment_ids` and
`account.payment.reconciled_expense_ids`.

Both fields are computed from core's own move-level link data —
`account.move.reconciled_payment_ids` on the expense side and
`account.payment.invoice_ids` / `reconciled_bill_ids` on the payment side —
so they always agree with the standard relationship: reconciled payments
(partial ones included) and wizard-registered payments that have no journal
entry yet are both covered, and nothing is stored that could go stale.

Odoo 19.0 core tracks this relationship only at the journal-entry level and
its `account.payment.expense_ids` only covers company-paid expenses; this
module lifts the employee-reimbursement direction to named, searchable
fields on `hr.expense` and `account.payment`.
