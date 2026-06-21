# Copyright 2026 Ledo <https://ledoweb.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.exceptions import UserError


class HrTrip(models.Model):
    _inherit = "hr.trip"

    payable_expense_count = fields.Integer(
        compute="_compute_payable_expense_count",
        help="Posted, not fully paid expenses linked to the trip.",
    )

    @api.depends(
        "expense_ids.account_move_id.payment_state",
        "expense_ids.account_move_id.state",
    )
    def _compute_payable_expense_count(self):
        for trip in self:
            trip.payable_expense_count = len(trip._payable_expenses())

    def _payable_expenses(self):
        """Trip expenses with a posted move that is not yet fully paid."""
        self.ensure_one()
        return self.expense_ids.filtered(
            lambda expense: expense.account_move_id.state == "posted"
            and expense.account_move_id.payment_state
            in ("not_paid", "partial", "in_payment")
        )

    def action_pay_trip(self):
        """Register a single payment covering the trip's payable expenses by
        threading them through the standard expense register-payment flow."""
        self.ensure_one()
        payable = self._payable_expenses()
        if not payable:
            raise UserError(
                self.env._("No posted, unpaid expenses to pay on this trip.")
            )
        return payable.action_pay()
