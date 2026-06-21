# Copyright 2026 Ledo <https://ledoweb.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestHrExpensePaymentTrip(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env["hr.employee"].create({"name": "Trip Payer"})
        cls.trip = cls.env["hr.trip"].create(
            {
                "name": "Berlin",
                "start_date": date(2026, 1, 1),
                "end_date": date(2026, 1, 5),
                "employee_id": cls.employee.id,
            }
        )
        cls.expense = cls.env["hr.expense"].create(
            {
                "name": "Hotel",
                "employee_id": cls.employee.id,
                "date": date(2026, 1, 2),
                "total_amount": 100.0,
                "trip_id": cls.trip.id,
            }
        )

    def test_no_payable_expenses_raises(self):
        """Nothing posted/payable yet -> a clear error, not a silent no-op."""
        self.assertEqual(self.trip.payable_expense_count, 0)
        with self.assertRaises(UserError):
            self.trip.action_pay_trip()

    def test_pay_trip_delegates_to_expense_action_pay(self):
        """A single payment flow is delegated to the trip's payable expenses."""
        with (
            patch.object(
                type(self.trip), "_payable_expenses", return_value=self.expense
            ),
            patch.object(
                type(self.expense),
                "action_pay",
                return_value={"type": "ir.actions.act_window"},
            ) as mocked_pay,
        ):
            action = self.trip.action_pay_trip()
        mocked_pay.assert_called_once()
        self.assertEqual(action["type"], "ir.actions.act_window")
