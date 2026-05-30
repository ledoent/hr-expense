# Copyright 2019 Tecnativa - Ernesto Tejeda
# Copyright 2021 Ecosoft Co., Ltd (http://ecosoft.co.th/)
# Copyright 2026 Ledo <https://ledoweb.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    expense_ids = fields.Many2many(
        comodel_name="hr.expense",
        relation="payment_hr_expense_rel",
        column1="payment_id",
        column2="expense_id",
        string="Expenses",
        readonly=True,
        copy=False,
    )
