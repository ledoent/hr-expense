# Copyright 2026 Ledo <https://ledoweb.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.exceptions import UserError


class HrTrip(models.Model):
    _inherit = "hr.trip"

    advance_id = fields.Many2one(
        comodel_name="hr.expense",
        string="Trip Advance",
        domain="[('expense_type', '=', 'advance'), ('employee_id', '=', employee_id)]",
        help="Advance paid to the employee for this trip. Use 'Apply Advance' "
        "to clear the trip's expenses against it.",
    )
    advance_residual = fields.Monetary(
        related="advance_id.clearing_residual",
        string="Advance Remaining",
    )
    currency_id = fields.Many2one(related="advance_id.currency_id")

    @api.onchange("employee_id")
    def _onchange_employee_clear_advance(self):
        # The advance must belong to the trip's employee.
        if self.advance_id and self.advance_id.employee_id != self.employee_id:
            self.advance_id = False

    def action_apply_advance(self):
        """Clear the trip's regular expenses against the trip advance, by
        setting clearing_advance_id on each one that is not already cleared."""
        self.ensure_one()
        if not self.advance_id:
            raise UserError(self.env._("Set a Trip Advance first."))
        clearings = self.expense_ids.filtered(
            lambda expense: expense.expense_type == "expense"
            and not expense.clearing_advance_id
        )
        if not clearings:
            raise UserError(
                self.env._("No unlinked regular expenses to clear on this trip.")
            )
        clearings.write({"clearing_advance_id": self.advance_id.id})

    def action_view_advance(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.expense",
            "res_id": self.advance_id.id,
            "view_mode": "form",
        }
