# Copyright 2019 Kitti Upariphutthiphong <kittiu@ecosoft.co.th>
# Copyright 2024 Tecnativa - Víctor Martínez
# Copyright 2026 Ledo <https://ledoweb.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.hr_expense.tests.common import TestExpenseCommon


@tagged("-at_install", "post_install")
class TestHrExpenseAdvanceClearing(TestExpenseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        advance_account = cls.company_data["default_account_deferred_expense"]
        advance_account.reconcile = True
        cls.emp_advance = cls.env.ref("hr_expense_advance_clearing.product_emp_advance")
        cls.emp_advance.property_account_expense_id = advance_account
        cls.product_a.standard_price = 0

    def _new_advance(self, amount=1000.0):
        advance = self.env["hr.expense"].create(
            {
                "name": f"Advance {amount}",
                "employee_id": self.expense_employee.id,
                "product_id": self.emp_advance.id,
                "total_amount_currency": amount,
                "expense_type": "advance",
                "payment_mode": "own_account",
            }
        )
        advance.action_submit()
        if advance.state == "submitted":
            advance.action_approve()
        return advance

    def _new_clearing(self, advance, amount):
        return self.env["hr.expense"].create(
            {
                "name": f"Clearing {amount}",
                "employee_id": self.expense_employee.id,
                "product_id": self.product_a.id,
                "total_amount_currency": amount,
                "payment_mode": "own_account",
                "clearing_advance_id": advance.id,
            }
        )

    def test_advance_constraint_taxes_forbidden(self):
        """An advance expense cannot carry taxes."""
        tax = self.env["account.tax"].create(
            {"name": "T", "amount": 10.0, "type_tax_use": "purchase"}
        )
        advance = self.env["hr.expense"].create(
            {
                "name": "Advance",
                "employee_id": self.expense_employee.id,
                "product_id": self.emp_advance.id,
                "total_amount_currency": 100.0,
                "expense_type": "advance",
                "payment_mode": "own_account",
            }
        )
        with self.assertRaises(ValidationError):
            advance.tax_ids = [(6, 0, tax.ids)]

    def test_clearing_constraint_same_employee(self):
        """A clearing expense's advance must belong to the same employee."""
        advance = self._new_advance()
        # hr.employee creation requires resource.resource access in 19.0;
        # use sudo() since this test isn't exercising employee permissions.
        other_emp = self.env["hr.employee"].sudo().create({"name": "Other"})
        with self.assertRaises(ValidationError):
            self.env["hr.expense"].create(
                {
                    "name": "Mismatch",
                    "employee_id": other_emp.id,
                    "product_id": self.product_a.id,
                    "total_amount_currency": 50.0,
                    "clearing_advance_id": advance.id,
                }
            )

    def test_clearing_residual_tracks_drafts_vs_approved(self):
        """clearing_residual excludes draft/submitted/refused clearings;
        only approved+ clearings count."""
        advance = self._new_advance(1000.0)
        c_draft = self._new_clearing(advance, 300.0)
        self.assertEqual(c_draft.state, "draft")
        self.assertEqual(advance.cleared_amount, 0.0)
        self.assertEqual(advance.clearing_residual, 1000.0)
        c_draft.action_submit()
        if c_draft.state == "submitted":
            c_draft.action_approve()
        advance.invalidate_recordset(["cleared_amount", "clearing_residual"])
        self.assertEqual(advance.cleared_amount, 300.0)
        self.assertEqual(advance.clearing_residual, 700.0)

    def test_amount_payable_on_clearing(self):
        """A clearing expense's amount_payable = max(total − advance_residual, 0)."""
        advance = self._new_advance(1000.0)
        c_eq = self._new_clearing(advance, 1000.0)
        self.assertEqual(c_eq.amount_payable, 0.0)
        c_gt = self._new_clearing(advance, 1500.0)
        self.assertEqual(c_gt.amount_payable, 500.0)
        c_lt = self._new_clearing(advance, 500.0)
        self.assertEqual(c_lt.amount_payable, 0.0)

    def test_employee_advance_count(self):
        """advance_count + advance_expense_ids on hr.employee."""
        self.assertEqual(self.expense_employee.advance_count, 0)
        self._new_advance(500.0)
        self.expense_employee.invalidate_recordset(["advance_count"])
        self.assertEqual(self.expense_employee.advance_count, 1)

    def test_action_return_advance_guards(self):
        """action_return_advance gates on expense_type + residual, and
        returns the payment-register wizard action when valid."""
        advance = self._new_advance(500.0)
        # A regular expense cannot be returned.
        regular = self.env["hr.expense"].create(
            {
                "name": "regular",
                "employee_id": self.expense_employee.id,
                "product_id": self.product_a.id,
                "total_amount_currency": 50.0,
                "payment_mode": "own_account",
            }
        )
        with self.assertRaises(UserError):
            regular.action_return_advance()
        # The advance has residual → action returns the wizard.
        self.assertGreater(advance.clearing_residual, 0)
        action = advance.action_return_advance()
        self.assertEqual(action["res_model"], "account.payment.register")
        self.assertEqual(action["context"]["default_advance_id"], advance.id)
        self.assertTrue(action["context"].get("hr_return_advance"))
        # Once fully cleared, residual is zero → action raises.
        clearing = self._new_clearing(advance, 500.0)
        clearing.action_submit()
        if clearing.state == "submitted":
            clearing.action_approve()
        advance.invalidate_recordset(["cleared_amount", "clearing_residual"])
        self.assertEqual(advance.clearing_residual, 0.0)
        with self.assertRaises(UserError):
            advance.action_return_advance()
