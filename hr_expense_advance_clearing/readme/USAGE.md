First-time setup: open product **Employee Advance** (auto-created on
install) and set its expense account to your "Employee Advance"
current-asset account with `Allow Reconciliation`.

**Create an Employee Advance**

1. Expenses → My Expenses, click New.
2. Set `Expense Type` to **Advance** (Employee Advance product + own_account auto-fill).
3. Optionally set `Clearing Product` — it's the default product for
   clearing expense lines that reference this advance.
4. Set the amount, Save.
5. Submit → Approve → Post → Register Payment. The advance is paid to
   the employee.

**Clear the Advance with a regular expense**

1. Expenses → My Expenses, New (or pick an existing draft).
2. Leave `Expense Type` as **Expense** and set `Clearing Advance` to the
   advance you want to clear against. The `Advance Remaining` smart
   field shows what's left of the advance.
3. Submit → Approve → Post. On post, the clearing expense's receivable
   line auto-reconciles against the advance's receivable line.

What happens at post time:

- `clearing_total ≤ advance_residual` → fully covered. No further
  payment needed; the advance's residual updates.
- `clearing_total > advance_residual` → the excess remains on the
  clearing expense's move. Register Payment for the difference.

**Return unused advance**

1. Open the paid advance with `clearing_residual > 0`.
2. Click **Return Advance** (header button). The Register Payment wizard
   opens pre-filled with the residual.
3. Confirm. The advance is now fully closed; `clearing_residual = 0`.

**Trip integration** (when `hr_expense_trip` is installed)

A trip's `expense_ids` can include both an advance and the regular
expenses paid out of it. The trip module wires a "Clear Trip" button
that calls `action_clear_advance` on the trip's regular expenses with
the trip's advance as the target. This module does not depend on
`hr_expense_trip`; the integration is one-way from the trip side.
