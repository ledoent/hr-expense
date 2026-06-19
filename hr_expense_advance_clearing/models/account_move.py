# Copyright 2022 Ecosoft Co., Ltd. (https://ecosoft.co.th)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _check_hr_advance_move_reconciled(self):
        """Block draft/cancel/reverse while the advance line is still
        reconciled with a clearing or return."""
        av_moves = self.filtered(
            lambda m: any(
                line.expense_id.expense_type == "advance" for line in m.line_ids
            )
        )
        emp_advance = self.env.ref(
            "hr_expense_advance_clearing.product_emp_advance", False
        )
        if not emp_advance:
            return
        reconciled_av_move_lines = av_moves.mapped("line_ids").filtered(
            lambda line: line.product_id == emp_advance and line.matching_number
        )
        if reconciled_av_move_lines:
            raise UserError(
                self.env._(
                    "This operation is not allowed as some advance amount was "
                    "already cleared/returned.\nPlease cancel those documents "
                    "first."
                )
            )

    def button_draft(self):
        self._check_hr_advance_move_reconciled()
        return super().button_draft()

    def button_cancel(self):
        self._check_hr_advance_move_reconciled()
        return super().button_cancel()

    def _reverse_moves(self, default_values_list=None, cancel=False):
        self._check_hr_advance_move_reconciled()
        return super()._reverse_moves(
            default_values_list=default_values_list, cancel=cancel
        )

    def _compute_amount(self):
        """For a clearing expense's move, report only the unreconciled
        receivable/payable residual."""
        res = super()._compute_amount()
        for move in self:
            total_residual = 0.0
            total_residual_currency = 0.0
            for line in move.line_ids:
                if line.account_type not in ("asset_receivable", "liability_payable"):
                    continue
                # Line residual amount on a clearing expense.
                clearing = line.expense_id.filtered("clearing_advance_id")
                if clearing:
                    total_residual += line.amount_residual
                    total_residual_currency += line.amount_residual_currency
            if total_residual and total_residual_currency:
                sign = move.direction_sign
                move.amount_residual = -sign * total_residual
                move.amount_residual_signed = total_residual_currency
        return res

    def action_force_register_payment(self):
        """Allow Register Payment on a clearing expense's entry move when its
        total exceeds the advance, which core would otherwise block."""
        if all(
            m.move_type == "entry"
            and any(line.expense_id.clearing_advance_id for line in m.line_ids)
            for m in self
        ):
            return self.line_ids.action_register_payment(ctx={"expense_clearing": 1})
        return super().action_force_register_payment()
