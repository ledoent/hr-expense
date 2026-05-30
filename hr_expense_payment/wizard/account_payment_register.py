# Copyright 2019 Tecnativa - Ernesto Tejeda
# Copyright 2020 Ecosoft Co., Ltd (https://ecosoft.co.th/)
# Copyright 2026 Ledo <https://ledoweb.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        expense_ids = self.env.context.get("hr_expense_ids")
        if expense_ids:
            payment_vals["expense_ids"] = [(6, 0, expense_ids)]
        return payment_vals

    def _create_payment_vals_from_batch(self, batch_result):
        payment_vals = super()._create_payment_vals_from_batch(batch_result)
        expense_ids = self.env.context.get("hr_expense_ids")
        if expense_ids:
            # Caller-supplied expense ids take precedence (action_pay path).
            payment_vals["expense_ids"] = [(6, 0, expense_ids)]
            return payment_vals
        # Auto-derive from the moves in the batch — covers payments registered
        # from the account.move side (e.g. directly on the in_receipt) so the
        # back-link still populates.
        moves = self.env["account.move"].browse(batch_result["lines"].move_id.ids)
        expenses = moves.expense_ids
        if expenses:
            payment_vals["expense_ids"] = [(6, 0, expenses.ids)]
        return payment_vals
