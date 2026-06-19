# Copyright 2026 Ledo <https://ledoweb.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.hr_expense.tests.common import TestExpenseCommon


@tagged("-at_install", "post_install")
class TestHrExpenseAdvanceClearingTrip(TestExpenseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        advance_account = cls.company_data["default_account_deferred_expense"]
        advance_account.reconcile = True
        cls.emp_advance = cls.env.ref("hr_expense_advance_clearing.product_emp_advance")
        cls.emp_advance.property_account_expense_id = advance_account
        cls.product_a.standard_price = 0
        cls.employee = cls.expense_employee
        cls.trip = cls.env["hr.trip"].create(
            {
                "name": "Munich",
                "start_date": date(2026, 2, 1),
                "end_date": date(2026, 2, 7),
                "employee_id": cls.employee.id,
            }
        )
        cls.advance = cls.env["hr.expense"].create(
            {
                "name": "Munich advance",
                "employee_id": cls.employee.id,
                "product_id": cls.emp_advance.id,
                "total_amount_currency": 1000.0,
                "expense_type": "advance",
                "payment_mode": "own_account",
            }
        )
        cls.exp_a = cls.env["hr.expense"].create(
            {
                "name": "Hotel",
                "employee_id": cls.employee.id,
                "product_id": cls.product_a.id,
                "total_amount_currency": 300.0,
                "trip_id": cls.trip.id,
            }
        )
        cls.exp_b = cls.env["hr.expense"].create(
            {
                "name": "Meals",
                "employee_id": cls.employee.id,
                "product_id": cls.product_a.id,
                "total_amount_currency": 120.0,
                "trip_id": cls.trip.id,
            }
        )

    def test_apply_advance_clears_trip_expenses(self):
        self.trip.advance_id = self.advance
        self.trip.action_apply_advance()
        self.assertEqual(self.exp_a.clearing_advance_id, self.advance)
        self.assertEqual(self.exp_b.clearing_advance_id, self.advance)

    def test_apply_advance_without_advance_raises(self):
        self.trip.advance_id = False
        with self.assertRaises(UserError):
            self.trip.action_apply_advance()

    def test_apply_advance_skips_already_cleared(self):
        self.trip.advance_id = self.advance
        self.exp_a.clearing_advance_id = self.advance
        self.trip.action_apply_advance()
        self.assertEqual(self.exp_b.clearing_advance_id, self.advance)
