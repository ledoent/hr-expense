# Copyright 2022 Ecosoft Co., Ltd. (https://ecosoft.co.th)
# Copyright 2026 Ledo <https://ledoweb.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    # 18.0 pointed at hr.expense.sheet; 19.0 points at the advance expense.
    advance_id = fields.Many2one(
        comodel_name="hr.expense",
        string="Advance",
        domain="[('expense_type', '=', 'advance')]",
        readonly=True,
        help="The employee advance this payment relates to — the advance it "
        "pays out, or the advance whose unused balance it returns.",
    )

    def _synchronize_from_moves(self, changed_fields):
        """Skip the standard move-payment sync for return-advance payments
        — the move is a generic entry, not the payment's own posting flow."""
        self = (
            self.with_context(skip_account_move_synchronization=True)
            if self.filtered("advance_id")
            else self
        )
        return super()._synchronize_from_moves(changed_fields)

    @api.model
    def _get_valid_payment_account_types(self):
        account_types = super()._get_valid_payment_account_types()
        if self.env.context.get("hr_return_advance"):
            account_types.append("asset_current")
        return account_types
