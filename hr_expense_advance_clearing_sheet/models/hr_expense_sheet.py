# Copyright 2026 Ledo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    expense_type = fields.Selection(
        selection=[("expense", "Expense"), ("advance", "Employee Advance")],
        compute="_compute_expense_type",
        store=True,
        help="An expense report is an advance only when every line on it is "
        "one. hr_expense_advance_clearing constrains lines individually and "
        "does not forbid mixing, so a report holding both an advance and an "
        "ordinary expense is treated as an ordinary report.",
    )
    advance_sheet_id = fields.Many2one(
        comodel_name="hr.expense.sheet",
        string="Clearing Advance Report",
        compute="_compute_advance_sheet_id",
        store=True,
        index=True,
        help="The advance report this report clears. Derived from the advance "
        "each line clears, so it cannot disagree with the lines.",
    )
    clearing_sheet_ids = fields.One2many(
        comodel_name="hr.expense.sheet",
        inverse_name="advance_sheet_id",
        string="Clearing Reports",
    )
    clearing_count = fields.Integer(compute="_compute_clearing_count")
    advance_residual = fields.Monetary(
        string="Advance Remaining",
        compute="_compute_advance_amounts",
        help="Sum of the amount still to be cleared on this report's advance lines.",
    )

    @api.depends("expense_line_ids.expense_type")
    def _compute_expense_type(self):
        for sheet in self:
            types = set(sheet.expense_line_ids.mapped("expense_type"))
            sheet.expense_type = "advance" if types == {"advance"} else "expense"

    @api.depends("expense_line_ids.clearing_advance_id.sheet_id")
    def _compute_advance_sheet_id(self):
        """Derive the sheet-level link from the line-level one.

        A report clears an advance report when its lines clear that report's
        lines. Lines pointing at advances on more than one report leave this
        empty rather than pick one — the per-line links stay authoritative.
        """
        for sheet in self:
            advance_sheets = sheet.expense_line_ids.clearing_advance_id.sheet_id
            sheet.advance_sheet_id = (
                advance_sheets if len(advance_sheets) == 1 else False
            )

    @api.depends("clearing_sheet_ids")
    def _compute_clearing_count(self):
        for sheet in self:
            sheet.clearing_count = len(sheet.clearing_sheet_ids)

    @api.depends("expense_line_ids.clearing_residual")
    def _compute_advance_amounts(self):
        for sheet in self:
            advance_lines = sheet.expense_line_ids.filtered(
                lambda line: line.expense_type == "advance"
            )
            sheet.advance_residual = sum(advance_lines.mapped("clearing_residual"))

    def action_view_clearing_sheets(self):
        self.ensure_one()
        return {
            "name": self.env._("Clearing Reports"),
            "type": "ir.actions.act_window",
            "res_model": "hr.expense.sheet",
            "view_mode": "list,form",
            "domain": [("id", "in", self.clearing_sheet_ids.ids)],
        }

    def _get_open_advance_lines(self):
        return self.expense_line_ids.filtered(
            lambda line: line.expense_type == "advance" and line.clearing_residual > 0
        )

    def action_clear_advance(self):
        """Create a draft clearing report prefilled from this advance report.

        The clearing sheet is created server-side rather than opened with
        default_* context keys: the 19.0 web client strips default_* from the
        new-record context, so the 18.0 open-a-prefilled-form pattern silently
        seeds nothing. advance_sheet_id is never written — it materializes
        from the seeded per-line links, which stay authoritative.
        """
        self.ensure_one()
        advance_lines = self._get_open_advance_lines().filtered("clearing_product_id")
        if not advance_lines:
            raise UserError(
                self.env._(
                    "Nothing to clear: this report has no advance line with "
                    "both a remaining amount and a clearing product. Set a "
                    "clearing product on the advance lines to prefill their "
                    "clearings."
                )
            )
        clearing_sheet = self.env["hr.expense.sheet"].create(
            {
                "name": self.env._("Clearing: %s", self.name),
                "employee_id": self.employee_id.id,
                "expense_line_ids": [
                    Command.create(self._prepare_clearing_expense_vals(line))
                    for line in advance_lines
                ],
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.expense.sheet",
            "res_id": clearing_sheet.id,
            "view_mode": "form",
        }

    def _prepare_clearing_expense_vals(self, advance_line):
        return {
            "name": advance_line.clearing_product_id.display_name,
            "employee_id": self.employee_id.id,
            "product_id": advance_line.clearing_product_id.id,
            "total_amount_currency": advance_line.clearing_residual,
            "payment_mode": "own_account",
            "clearing_advance_id": advance_line.id,
        }

    def action_return_advance(self):
        """Return the remaining advance across every line of this report.

        A single open advance line delegates to the per-expense action so the
        wizard keeps its exact single-advance behavior. With several lines the
        wizard opens over all their open advance move lines and the bridge
        wizard override batches them per advance line — one payment each,
        stamped with its advance — so every line's residual stays accurate.
        """
        self.ensure_one()
        advance_lines = self._get_open_advance_lines()
        if not advance_lines:
            raise UserError(
                self.env._("This report has no advance residual to return.")
            )
        if len(advance_lines) == 1:
            return advance_lines.action_return_advance()
        account_advance = (
            advance_lines._get_product_advance().property_account_expense_id
        )
        move_lines = advance_lines.account_move_id.line_ids.filtered(
            lambda line: line.account_id == account_advance and not line.reconciled
        )
        if not move_lines:
            raise UserError(self.env._("No open advance lines found to return."))
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Return Advance"),
            "res_model": "account.payment.register",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_model": "account.move.line",
                "active_ids": move_lines.ids,
                "default_partner_type": "customer",
                "default_partner_id": self.employee_id.sudo().work_contact_id.id,
                "default_currency_id": self.currency_id.id,
                "hr_return_advance": 1,
                "hr_return_advance_sheet": 1,
            },
        }
