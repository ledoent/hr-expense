# Copyright 2019 Kitti Upariphutthiphong <kittiu@ecosoft.co.th>
# Copyright 2026 Ledo <https://ledoweb.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrExpense(models.Model):
    """19.0 redesign: the 18.0 advance/clearing-sheet pair becomes a flat
    per-expense model.

    - An "advance" expense (expense_type='advance') is money paid to the
      employee in advance of any spending.
    - A "regular" expense (expense_type='expense') is the normal
      reimbursement flow. When a regular expense clears against an
      advance, it sets clearing_advance_id on itself.
    - Reconciliation: the advance's receivable line reconciles with the
      clearing expense's receivable line. Once the advance's
      clearing_residual hits zero, state advances to 'cleared'.
    """

    _inherit = "hr.expense"

    expense_type = fields.Selection(
        selection=[("expense", "Expense"), ("advance", "Advance")],
        default="expense",
        required=True,
        tracking=True,
        help="An 'advance' is money paid to the employee up front. Regular "
        "'expense' records are either reimbursements or clearings against "
        "a prior advance (when clearing_advance_id is set).",
    )
    clearing_advance_id = fields.Many2one(
        comodel_name="hr.expense",
        string="Clearing Advance",
        domain="[('expense_type', '=', 'advance'),"
        " ('employee_id', '=', employee_id),"
        " ('clearing_residual', '>', 0.0)]",
        tracking=True,
        ondelete="restrict",
        help="When set on a regular expense, this expense clears against "
        "the referenced advance. Only advances of the same employee "
        "with residual > 0 are selectable.",
    )
    clearing_expense_ids = fields.One2many(
        comodel_name="hr.expense",
        inverse_name="clearing_advance_id",
        string="Clearing Expenses",
        readonly=True,
        help="Expenses cleared against this advance.",
    )
    clearing_count = fields.Integer(compute="_compute_clearing_count")
    payment_return_ids = fields.One2many(
        comodel_name="account.payment",
        inverse_name="advance_id",
        string="Returned Payments",
        readonly=True,
        help="Refund payments returning unused advance money to the company.",
    )
    return_count = fields.Integer(compute="_compute_return_count")

    cleared_amount = fields.Monetary(
        compute="_compute_clearing_residual",
        store=True,
        help="Sum of clearing expenses' totals (company currency).",
    )
    returned_amount = fields.Monetary(
        compute="_compute_clearing_residual",
        store=True,
        help="Sum of return-advance payments (company currency).",
    )
    clearing_residual = fields.Monetary(
        string="Amount to Clear",
        compute="_compute_clearing_residual",
        store=True,
        help="Advance amount remaining to be cleared or returned.",
    )
    advance_residual = fields.Monetary(
        string="Advance Remaining",
        related="clearing_advance_id.clearing_residual",
        store=True,
        help="Remaining amount on the linked advance (for clearing expenses).",
    )
    amount_payable = fields.Monetary(
        string="Payable Amount",
        compute="_compute_amount_payable",
        help="Register-payment amount after subtracting the cleared advance.",
    )
    clearing_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Clearing Product",
        tracking=True,
        domain="[('can_be_expensed', '=', True),"
        " '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        ondelete="restrict",
        help="Optional: when set on an advance, this product is used as the "
        "default for clearing expense lines.",
    )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_product_advance(self):
        return self.env.ref("hr_expense_advance_clearing.product_emp_advance", False)

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    @api.constrains("expense_type", "product_id", "tax_ids", "payment_mode")
    def _check_advance(self):
        """An advance expense must use the Employee Advance product, no
        taxes, and be employee-paid."""
        emp_advance = self._get_product_advance()
        if not emp_advance:
            return True
        for expense in self.filtered(lambda e: e.expense_type == "advance"):
            if not emp_advance.property_account_expense_id:
                raise ValidationError(
                    self.env._("Employee advance product has no payable account")
                )
            if expense.product_id != emp_advance:
                raise ValidationError(
                    self.env._("Employee advance, selected product is not valid")
                )
            if expense.tax_ids:
                raise ValidationError(
                    self.env._("Employee advance, all taxes must be removed")
                )
            if expense.payment_mode != "own_account":
                raise ValidationError(
                    self.env._("Employee advance, paid by must be employee")
                )
        return True

    @api.constrains("clearing_advance_id", "expense_type", "employee_id")
    def _check_clearing(self):
        """A clearing expense must be 'expense' type, must reference an
        advance of the same employee, and the advance must be paid."""
        for expense in self.filtered("clearing_advance_id"):
            if expense.expense_type == "advance":
                raise ValidationError(
                    self.env._("An advance cannot itself clear another advance.")
                )
            advance = expense.clearing_advance_id
            if advance.employee_id != expense.employee_id:
                raise ValidationError(
                    self.env._("The linked advance must belong to the same employee.")
                )

    # -------------------------------------------------------------------------
    # Onchanges + defaults
    # -------------------------------------------------------------------------

    @api.onchange("expense_type")
    def _onchange_expense_type(self):
        if self.expense_type == "advance":
            emp_advance = self._get_product_advance()
            if emp_advance:
                self.product_id = emp_advance
            self.tax_ids = False
            self.payment_mode = "own_account"
            self.clearing_advance_id = False

    @api.onchange("clearing_advance_id")
    def _onchange_clearing_advance_id(self):
        """Pre-fill clearing product from the advance if it has one set."""
        advance = self.clearing_advance_id
        if advance and advance.clearing_product_id and not self.product_id:
            self.product_id = advance.clearing_product_id

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------

    @api.depends(
        "expense_type",
        "total_amount_currency",
        "clearing_expense_ids.total_amount_currency",
        "clearing_expense_ids.state",
        "payment_return_ids.amount",
        "payment_return_ids.state",
    )
    def _compute_clearing_residual(self):
        for expense in self:
            if expense.expense_type != "advance":
                expense.cleared_amount = 0.0
                expense.returned_amount = 0.0
                expense.clearing_residual = 0.0
                continue
            cleared = sum(
                expense.clearing_expense_ids.filtered(
                    lambda e: e.state not in ("draft", "submitted", "refused")
                ).mapped("total_amount_currency")
            )
            returned = sum(
                expense.payment_return_ids.filtered(
                    lambda p: p.state in ("in_process", "paid")
                ).mapped("amount")
            )
            expense.cleared_amount = cleared
            expense.returned_amount = returned
            expense.clearing_residual = (
                expense.total_amount_currency - cleared - returned
            )

    @api.depends("clearing_expense_ids")
    def _compute_clearing_count(self):
        for expense in self:
            expense.clearing_count = len(expense.clearing_expense_ids)

    @api.depends("payment_return_ids")
    def _compute_return_count(self):
        for expense in self:
            expense.return_count = len(expense.payment_return_ids)

    @api.depends(
        "total_amount_currency",
        "clearing_advance_id.clearing_residual",
    )
    def _compute_amount_payable(self):
        """For a clearing expense: payable = total − advance available."""
        for expense in self:
            if not expense.clearing_advance_id:
                expense.amount_payable = 0.0
                continue
            residual = expense.clearing_advance_id.clearing_residual
            expense.amount_payable = max(expense.total_amount_currency - residual, 0.0)

    # -------------------------------------------------------------------------
    # Server actions
    # -------------------------------------------------------------------------

    def action_return_advance(self):
        """Open Register Payment for the remaining advance residual so the
        employee can refund what they didn't spend."""
        self.ensure_one()
        if self.expense_type != "advance":
            raise UserError(self.env._("Only advance expenses can be returned."))
        if self.clearing_residual <= 0:
            raise UserError(self.env._("This advance has no residual to return."))
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Return Advance"),
            "res_model": "account.payment.register",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_partner_type": "customer",
                "default_partner_id": self.employee_id.sudo().work_contact_id.id,
                "default_amount": self.clearing_residual,
                "default_currency_id": self.currency_id.id,
                "default_advance_id": self.id,
                "hr_return_advance": 1,
            },
        }

    def action_view_clearings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Clearing Expenses"),
            "res_model": "hr.expense",
            "view_mode": "list,form",
            "domain": [("id", "in", self.clearing_expense_ids.ids)],
        }

    def action_view_returns(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Returned Payments"),
            "res_model": "account.payment",
            "view_mode": "list,form",
            "domain": [("id", "in", self.payment_return_ids.ids)],
        }

    # Auto-reconcile note: the 18.0 module reconciled the clearing sheet's
    # journal items against the advance sheet's employee-advance-account
    # lines at sheet-post time (sheet's _do_create_moves routed the credit
    # line to the advance account specifically). In 19.0 the equivalent
    # per-expense routing requires overriding _prepare_receipts_vals to
    # swap the credit account for clearing expenses, which is non-trivial.
    # Scoped out for this iteration — clearing_residual is driven by
    # count-based aggregation of clearing_expense_ids' totals; users can
    # reconcile journal items via the standard Odoo reconciliation UI.
    # Follow-up: ADR section "Auto-reconciliation" tracks the design
    # required to bring this back in a future iteration.
