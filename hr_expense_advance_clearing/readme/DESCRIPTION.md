Lets the company pay an "advance" to an employee, then later reconcile
that advance against the actual expenses incurred.

In Odoo 19.0 the workflow is per-expense (the 18.0 advance-sheet vs
clearing-sheet pair is gone with `hr.expense.sheet`):

- An **advance expense** has `expense_type='advance'`, uses the
  `Employee Advance` product, no taxes. Paid to the employee via the
  standard `action_pay`.
- A **clearing expense** is a regular `hr.expense` with
  `clearing_advance_id` set to the advance. On posting, its receivable
  line auto-reconciles against the advance's receivable line.
- The advance's `clearing_residual` tracks the unreconciled balance.
  When it hits zero, the advance is fully cleared.

Three scenarios remain:

- `clearing_total = advance` — fully reconciled, advance is closed.
- `clearing_total > advance` — Register Payment on the clearing expense's
  difference (the wizard understands the `expense_clearing` context).
- `clearing_total < advance` — use **Return Advance** on the advance
  expense to refund the residual back to the company.

19.0 note: `hr_expense_trip` (when available) is the natural clearing
scope — a "Clear Trip" button on the trip would call
`action_clear_advance` on the trip's `expense_ids`. Trip integration
lives in the trip module, not here.
