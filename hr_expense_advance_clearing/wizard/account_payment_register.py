# Copyright 2020 Ecosoft Co., Ltd (https://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)


from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    advance_id = fields.Many2one(
        comodel_name="hr.expense",
        domain="[('expense_type', '=', 'advance')]",
        help="Set from default_advance_id when the Return Advance action opens "
        "this wizard. It has to be a field rather than read from the context at "
        "payment time: core calls _init_payments() under clean_context(), which "
        "drops every default_* key, so the context value is gone by then.",
    )

    def _validate_over_return(self):
        """For a return-advance wizard: cannot return more than the actual
        remaining residual (advance.clearing_residual minus any pending
        clearings that haven't been posted yet)."""
        clearings = (
            self.env["hr.expense"]
            .browse(self.env.context.get("clearing_expense_ids", []))
            .filtered(lambda e: e.state == "approved")
        )
        amount_not_clear = sum(clearings.mapped("total_amount"))
        actual_remaining = self.source_amount_currency - amount_not_clear
        symbol = self.source_currency_id.symbol
        more_info = ""
        if amount_not_clear:
            note = self.env._("\nNote: pending amount clearing is %(symbol)s%(amount)s")
            more_info = note % {
                "symbol": symbol,
                "amount": f"{amount_not_clear:,.2f}",
            }
        if float_compare(self.amount, actual_remaining, 2) == 1:
            msg = self.env._(
                "You cannot return advance more than actual remaining "
                "(%(symbol)s%(amount)s)%(more_info)s"
            )
            raise UserError(
                msg
                % {
                    "symbol": symbol,
                    "amount": f"{actual_remaining:,.2f}",
                    "more_info": more_info,
                }
            )

    def _init_payments(self, to_process, edit_mode=False):
        if self.env.context.get("hr_return_advance"):
            self._validate_over_return()
            for x in to_process:
                x["create_vals"]["partner_type"] = "customer"
                if self.advance_id:
                    x["create_vals"]["advance_id"] = self.advance_id.id
        return super()._init_payments(to_process, edit_mode)

    def _create_payments(self):
        """For a clearing-payment where the clearing exceeds the advance,
        mark the payment as paid so the residual is recomputed."""
        payments = super()._create_payments()
        if self.env.context.get("expense_clearing"):
            for payment in payments:
                payment.write({"move_id": payment.move_id.id, "state": "paid"})
        return payments
