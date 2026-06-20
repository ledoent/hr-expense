# Copyright 2024 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import date
from unittest.mock import patch

from odoo.exceptions import AccessError

from odoo.addons.hr_expense.tests.common import TestExpenseCommon


class TestHrTripPosting(TestExpenseCommon):
    """ "Create Bill" routing for employee-paid expenses.

    The rest of the suite mocks ``hr.expense.action_post`` wholesale, which is
    exactly why the employee-paid no-op slipped through: in 19.0 core only posts
    employee-paid ('own_account') expenses through an interactive wizard, so the
    trip's old ``expenses.action_post()`` call returned that wizard and created
    no move. This checks the fixed routing -- the trip builds and posts the
    receipt entries itself -- without depending on chart specifics (building the
    move-line vals is core's job and varies by localization).
    """

    def _done_employee_trip(self):
        trip = self.env["hr.trip"].create(
            {
                "name": "Posting Trip",
                "start_date": date(2024, 6, 1),
                "end_date": date(2024, 6, 10),
                "employee_id": self.expense_employee.id,
            }
        )
        expense = self.env["hr.expense"].create(
            {
                "name": "Flight",
                "employee_id": self.expense_employee.id,
                "total_amount_currency": 100.0,
                "payment_mode": "own_account",
                "trip_id": trip.id,
                "company_id": self.company_data["company"].id,
            }
        )
        expense.approval_state = "approved"
        trip.action_done()
        return trip, expense

    def test_create_bill_posts_employee_paid_via_receipt_entries(self):
        trip, expense = self._done_employee_trip()
        self.assertTrue(trip.can_create_bill)
        journal = self.env["account.journal"].search(
            [("type", "=", "purchase")], limit=1
        )

        expense_cls = type(self.env["hr.expense"])
        move_cls = type(self.env["account.move"])
        empty_move = self.env["account.move"]

        with (
            patch.object(
                expense_cls, "_prepare_receipts_vals", return_value=[{"ref": "receipt"}]
            ) as prepare,
            patch.object(type(trip), "_employee_expense_journal", return_value=journal),
            patch.object(move_cls, "create", return_value=empty_move) as move_create,
            patch.object(move_cls, "action_post") as move_post,
            patch.object(expense_cls, "action_post") as expense_action_post,
        ):
            trip.action_post()

        # Employee-paid expenses are posted by building + posting receipt
        # entries...
        prepare.assert_called_once()
        move_create.assert_called_once()
        receipt_vals = move_create.call_args.args[0]
        self.assertEqual(receipt_vals[0]["journal_id"], journal.id)
        self.assertIn("invoice_date", receipt_vals[0])
        move_post.assert_called_once()
        # ...not by delegating to core ``hr.expense.action_post`` (which only
        # returns a wizard for own_account expenses and created no move -- the
        # original bug).
        expense_action_post.assert_not_called()

    def test_create_bill_blocked_until_all_expenses_approved(self):
        """Guard rail preserved: no posting until the trip can create a bill."""
        trip, expense = self._done_employee_trip()
        expense.approval_state = "submitted"
        self.assertFalse(trip.can_create_bill)
        with patch.object(type(self.env["account.move"]), "create") as move_create:
            with self.assertRaises(AccessError):
                trip.action_post()
        move_create.assert_not_called()
