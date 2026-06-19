This module records a bidirectional link between each `hr.expense` record
and the `account.payment` records that paid it (via `hr.expense.payment_ids`
and `account.payment.expense_ids`).

When a user clicks **Register Payment** on a posted employee-paid expense
(`payment_mode='own_account'`), the resulting payment back-links to the
source expense. A `post_init_hook` backfills the link for payments that
predate the module install by walking reconciliation chains.

19.0 note: Odoo core's `hr.expense.action_pay()` already exists and
launches the standard register-payment wizard. This module *adds the
back-link* — core doesn't track which payment(s) paid which expense
beyond the implicit reconciliation graph.
