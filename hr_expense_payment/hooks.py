# Copyright 2019 Tecnativa - Ernesto Tejeda
# Copyright 2026 Ledo <https://ledoweb.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).


def post_init_hook(env):
    """Backfill payment_ids on existing employee-paid expenses by walking
    reconciliation: expense -> account_move_id.line_ids -> full_reconcile_id
    -> reconciled_line_ids.payment_id."""
    expenses = env["hr.expense"].search(
        [("payment_mode", "=", "own_account"), ("account_move_id", "!=", False)]
    )
    for expense in expenses:
        amls = expense.account_move_id.line_ids
        reconcile = amls.mapped("full_reconcile_id")
        aml_payment = reconcile.mapped("reconciled_line_ids").filtered(
            lambda r, amls=amls: r not in amls
        )
        payment = aml_payment.mapped("payment_id")
        if payment:
            payment.write({"expense_ids": [(4, expense.id)]})
