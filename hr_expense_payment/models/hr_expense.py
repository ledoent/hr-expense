# Copyright 2019 Tecnativa - Ernesto Tejeda
# Copyright 2021 Ecosoft Co., Ltd (http://ecosoft.co.th/)
# Copyright 2026 Ledo <https://ledoweb.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class HrExpense(models.Model):
    _inherit = "hr.expense"

    payment_ids = fields.Many2many(
        comodel_name="account.payment",
        relation="payment_hr_expense_rel",
        column1="expense_id",
        column2="payment_id",
        string="Payments",
        readonly=True,
        copy=False,
    )

    def action_pay(self):
        """Thread expense ids through to the register-payment wizard so the
        resulting account.payment records back-link to the source expenses."""
        action = super().action_pay()
        if action and isinstance(action, dict):
            ctx = dict(action.get("context") or {})
            ctx["hr_expense_ids"] = self.ids
            action["context"] = ctx
        return action
