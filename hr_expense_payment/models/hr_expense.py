# Copyright 2019 Tecnativa - Ernesto Tejeda
# Copyright 2021 Ecosoft Co., Ltd (http://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class HrExpense(models.Model):
    _inherit = "hr.expense"

    payment_ids = fields.Many2many(
        comodel_name="account.payment",
        string="Payments",
        compute="_compute_payment_ids",
        # Employees read their expenses without accounting access; the
        # reconciliation walk needs sudo.
        compute_sudo=True,
        search="_search_payment_ids",
        help="Payments whose journal items have been reconciled with this "
        "expense's journal entry.",
    )

    @api.depends(
        "account_move_id.line_ids.matched_debit_ids",
        "account_move_id.line_ids.matched_credit_ids",
    )
    def _compute_payment_ids(self):
        for expense in self:
            expense.payment_ids = expense.account_move_id._get_reconciled_payments()

    def _search_payment_ids(self, operator, value):
        if operator not in ("in", "="):
            return NotImplemented
        payments = self.env["account.payment"].browse(value)
        return [("id", "in", payments.reconciled_expense_ids.ids)]
