This module answers two questions Odoo 19.0 leaves unanswered for employee
reimbursements: which payment settled this expense, and which expenses did
this payment settle.

Core links a payment to expenses only when the payment's journal entry *is*
the expense entry — the company-paid case, covered by
`account.payment.expense_ids`. For an employee-paid expense the two entries
are separate and reconciled with each other, so core stops at entry level
(`account.move.reconciled_payment_ids`). This module lifts that relationship
onto the records themselves, as `hr.expense.payment_ids` and
`account.payment.reconciled_expense_ids`.

Both fields are derived from core's own move-level link data, so they cannot
drift from the standard relationship and nothing is stored that could go
stale. Reconciled payments — partial ones included — and payments registered
through the payment wizard that have no journal entry yet are both covered.
