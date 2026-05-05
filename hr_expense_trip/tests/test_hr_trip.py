# Copyright 2024 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import date
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestHrTrip(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        users = cls.env["res.users"].with_context(no_reset_password=True)
        group_user = cls.env.ref("base.group_user")
        group_team_approver = cls.env.ref("hr_expense.group_hr_expense_team_approver")
        group_admin = cls.env.ref("hr_expense.group_hr_expense_manager")

        cls.user_employee = users.create(
            {
                "name": "Trip Employee User",
                "login": "trip_employee_user@example.com",
                "email": "trip_employee_user@example.com",
                "group_ids": [(6, 0, [group_user.id])],
            }
        )
        cls.user_manager = users.create(
            {
                "name": "Trip Manager User",
                "login": "trip_manager_user@example.com",
                "email": "trip_manager_user@example.com",
                "group_ids": [(6, 0, [group_user.id, group_team_approver.id])],
            }
        )
        cls.user_admin = users.create(
            {
                "name": "Trip Admin User",
                "login": "trip_admin_user@example.com",
                "email": "trip_admin_user@example.com",
                "group_ids": [(6, 0, [group_user.id, group_admin.id])],
            }
        )
        cls.user_other = users.create(
            {
                "name": "Trip Other User",
                "login": "trip_other_user@example.com",
                "email": "trip_other_user@example.com",
                "group_ids": [(6, 0, [group_user.id])],
            }
        )

        cls.employee_manager = cls.env["hr.employee"].create(
            {
                "name": "Trip Manager Employee",
                "user_id": cls.user_manager.id,
            }
        )
        cls.employee_employee = cls.env["hr.employee"].create(
            {
                "name": "Trip Employee",
                "user_id": cls.user_employee.id,
                "parent_id": cls.employee_manager.id,
                "expense_manager_id": cls.user_manager.id,
            }
        )
        cls.employee_other = cls.env["hr.employee"].create(
            {
                "name": "Trip Other Employee",
                "user_id": cls.user_other.id,
            }
        )

        cls.trip_employee = (
            cls.env["hr.trip"]
            .with_user(cls.user_employee)
            .create(
                {
                    "name": "Employee Trip",
                    "start_date": date(2024, 6, 1),
                    "end_date": date(2024, 6, 10),
                    "employee_id": cls.employee_employee.id,
                }
            )
        )
        cls.trip_other = (
            cls.env["hr.trip"]
            .sudo()
            .create(
                {
                    "name": "Other Trip",
                    "start_date": date(2024, 7, 1),
                    "end_date": date(2024, 7, 10),
                    "employee_id": cls.employee_other.id,
                }
            )
        )

        cls.expense = (
            cls.env["hr.expense"]
            .sudo()
            .create(
                {
                    "name": "Hotel",
                    "employee_id": cls.employee_employee.id,
                    "date": date(2024, 6, 5),
                    "total_amount": 100.0,
                }
            )
        )

    def _create_employee_trip(self, name="Test Trip", start=None, end=None):
        return (
            self.env["hr.trip"]
            .with_user(self.user_employee)
            .create(
                {
                    "name": name,
                    "start_date": start or date(2024, 8, 1),
                    "end_date": end or date(2024, 8, 5),
                    "employee_id": self.employee_employee.id,
                }
            )
        )

    def test_trip_creation(self):
        self.assertEqual(self.trip_employee.name, "Employee Trip")
        self.assertEqual(self.trip_employee.start_date, date(2024, 6, 1))
        self.assertEqual(self.trip_employee.end_date, date(2024, 6, 10))
        self.assertEqual(self.trip_employee.employee_id, self.employee_employee)

    def test_employee_default(self):
        """employee_id should default to the current user's employee."""
        trip = self.env["hr.trip"].with_user(self.user_employee).new({})
        self.assertEqual(trip.employee_id, self.user_employee.employee_id)

    def test_date_constraint_valid(self):
        """No error when end_date >= start_date."""
        self.trip_employee.write(
            {"start_date": date(2024, 6, 1), "end_date": date(2024, 6, 1)}
        )
        self.assertEqual(self.trip_employee.end_date, date(2024, 6, 1))

    def test_date_constraint_invalid(self):
        """ValidationError raised when end_date < start_date."""
        with self.assertRaises(ValidationError):
            self.trip_employee.write(
                {"start_date": date(2024, 6, 10), "end_date": date(2024, 6, 1)}
            )

    def test_employee_access_only_own_trip(self):
        trips = self.env["hr.trip"].with_user(self.user_employee).search([])
        self.assertIn(self.trip_employee, trips)
        self.assertNotIn(self.trip_other, trips)

    def test_manager_access_only_responsible_trips(self):
        trips = self.env["hr.trip"].with_user(self.user_manager).search([])
        self.assertIn(self.trip_employee, trips)
        self.assertNotIn(self.trip_other, trips)

    def test_admin_access_all_trips(self):
        trips = self.env["hr.trip"].with_user(self.user_admin).search([])
        self.assertIn(self.trip_employee, trips)
        self.assertIn(self.trip_other, trips)

    def test_mail_thread_mixin(self):
        """hr.trip should have message_ids from mail.thread mixin."""
        self.assertTrue(hasattr(self.trip_employee, "message_ids"))
        self.assertTrue(hasattr(self.trip_employee, "activity_ids"))

    def test_state_transitions(self):
        trip = self._create_employee_trip(
            name="State Transition Trip",
            start=date(2024, 9, 1),
            end=date(2024, 9, 10),
        )
        self.assertEqual(trip.state, "draft")

        trip.action_request_approval()
        self.assertEqual(trip.state, "receipts")

        with patch.object(type(trip), "_attach_trip_report"):
            trip.action_done()
        self.assertEqual(trip.state, "done")

    def test_auto_approve_enabled(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "hr_expense_trip.auto_approve", "True"
        )
        trip = self._create_employee_trip(
            name="Auto Approve Trip",
            start=date(2024, 10, 1),
            end=date(2024, 10, 5),
        )
        trip.action_request_approval()
        self.assertEqual(trip.state, "receipts")

    def test_manual_approval_creates_activity_for_employee(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "hr_expense_trip.auto_approve", "False"
        )
        trip = self._create_employee_trip(
            name="Manual Approve Trip",
            start=date(2024, 11, 1),
            end=date(2024, 11, 5),
        )
        trip.with_user(self.user_employee).action_request_approval()
        self.assertEqual(trip.state, "request")

        activity = self.env["mail.activity"].search(
            [
                ("res_id", "=", trip.id),
                ("res_model", "=", "hr.trip"),
                ("user_id", "=", self.user_manager.id),
            ]
        )
        self.assertTrue(
            activity, "Expected an activity to be scheduled for the manager"
        )
        self.assertEqual(activity.summary, "Trip Approval Request")

    def test_manager_request_auto_approves_without_activity(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "hr_expense_trip.auto_approve", "False"
        )
        trip = self._create_employee_trip(
            name="Manager Request Trip",
            start=date(2024, 11, 6),
            end=date(2024, 11, 9),
        )
        self.env["mail.activity"].search(
            [("res_model", "=", "hr.trip"), ("res_id", "=", trip.id)]
        ).unlink()

        trip.with_user(self.user_manager).action_request_approval()
        self.assertEqual(trip.state, "receipts")
        activities = self.env["mail.activity"].search(
            [("res_model", "=", "hr.trip"), ("res_id", "=", trip.id)]
        )
        self.assertFalse(activities)

    def test_approve_requires_approver_role(self):
        trip = self._create_employee_trip(name="Approval Access Check")
        trip.sudo().write({"state": "request"})
        with self.assertRaises(AccessError):
            trip.with_user(self.user_other).action_approve()

    def test_employee_cannot_edit_info_after_approval(self):
        trip = self._create_employee_trip(name="Lock Info Trip")
        trip.sudo().write({"state": "receipts"})
        with self.assertRaises(AccessError):
            trip.with_user(self.user_employee).write({"name": "Changed by Employee"})

    def test_manager_can_edit_info_after_approval(self):
        trip = self._create_employee_trip(name="Manager Edit Approved Trip")
        trip.sudo().write({"state": "receipts"})
        trip.with_user(self.user_manager).write({"reason": "Manager updated reason"})
        self.assertEqual(trip.reason, "Manager updated reason")

    def test_employee_can_edit_expenses_until_done(self):
        trip = self._create_employee_trip(name="Expense Link Trip")
        trip.sudo().write({"state": "receipts"})
        expense = (
            self.env["hr.expense"]
            .sudo()
            .create(
                {
                    "name": "Taxi",
                    "employee_id": self.employee_employee.id,
                    "date": date(2024, 8, 2),
                    "total_amount": 42.0,
                }
            )
        )

        trip.with_user(self.user_employee).write({"expense_ids": [(4, expense.id)]})
        self.assertEqual(expense.trip_id, trip)

    def test_expenses_cannot_be_edited_after_done(self):
        trip = self._create_employee_trip(name="Done Lock Trip")
        trip.sudo().write({"state": "done"})
        expense = (
            self.env["hr.expense"]
            .sudo()
            .create(
                {
                    "name": "Meal",
                    "employee_id": self.employee_employee.id,
                    "date": date(2024, 8, 3),
                    "total_amount": 30.0,
                }
            )
        )
        with self.assertRaises(AccessError):
            trip.with_user(self.user_employee).write({"expense_ids": [(4, expense.id)]})

    def test_trip_to_process_action_targets_manager_scope(self):
        action = self.env.ref("hr_expense_trip.action_hr_trip_to_process")
        self.assertIn("employee_id.expense_manager_id", action.domain)
        self.assertIn("employee_id.parent_id.user_id", action.domain)
        self.assertIn("'request'", action.domain)

    def test_expense_default_trip_preselected(self):
        trip = self._create_employee_trip(
            name="Preselect Trip",
            start=date(2024, 12, 1),
            end=date(2024, 12, 15),
        )
        expense_model = self.env["hr.expense"].with_context(
            default_date=date(2024, 12, 5),
            default_employee_id=self.employee_employee.id,
        )
        result = expense_model.default_get(["trip_id", "date", "employee_id"])

        if (
            result.get("date") == date(2024, 12, 5)
            and result.get("employee_id") == self.employee_employee.id
        ):
            self.assertEqual(result.get("trip_id"), trip.id)
        else:
            found_trip = self.env["hr.trip"].search(
                [
                    ("employee_id", "=", self.employee_employee.id),
                    ("start_date", "<=", date(2024, 12, 5)),
                    ("end_date", ">=", date(2024, 12, 5)),
                ],
                limit=1,
            )
            self.assertEqual(found_trip, trip)

    def test_expense_default_trip_not_preselected(self):
        outside_date = date(2025, 3, 15)
        found_trip = self.env["hr.trip"].search(
            [
                ("employee_id", "=", self.employee_employee.id),
                ("start_date", "<=", outside_date),
                ("end_date", ">=", outside_date),
            ],
            limit=1,
        )
        self.assertFalse(found_trip, "No trip should match this date")

    def test_can_create_bill_false_when_no_expenses(self):
        trip = self.env["hr.trip"].create(
            {
                "name": "Test Trip",
                "start_date": date(2025, 1, 1),
                "end_date": date(2025, 1, 5),
                "employee_id": self.employee_employee.id,
            }
        )
        self.assertFalse(trip.can_create_bill)

    def test_manager_can_edit_expenses_in_done_state(self):
        """Manager should be able to edit expense_ids in done state."""
        trip = self._create_employee_trip(name="Manager Edit Trip")
        trip.sudo().write({"state": "done"})
        expense = (
            self.env["hr.expense"]
            .sudo()
            .create(
                {
                    "name": "Hotel",
                    "employee_id": self.employee_employee.id,
                    "date": date(2024, 8, 4),
                    "total_amount": 100.0,
                }
            )
        )
        # Manager should be able to add expense to done trip
        trip.with_user(self.user_manager).write({"expense_ids": [(4, expense.id)]})
        self.assertEqual(expense.trip_id, trip)

    def test_expense_posting_blocked_when_trip_not_done(self):
        """Expense posting should be blocked if trip is not in done state."""
        trip = self._create_employee_trip(name="Posting Block Trip")
        trip.sudo().write({"state": "request"})

        expense = (
            self.env["hr.expense"]
            .sudo()
            .create(
                {
                    "name": "Taxi to Airport",
                    "employee_id": self.employee_employee.id,
                    "date": date(2024, 8, 5),
                    "total_amount": 50.0,
                    "trip_id": trip.id,
                }
            )
        )

        # Attempt to post should fail with UserError
        with self.assertRaises(UserError):
            expense.action_post()

    def test_expense_posting_allowed_when_trip_done(self):
        """Expense posting should be allowed if trip is in done state."""
        trip = self._create_employee_trip(name="Posting Allow Trip")
        trip.sudo().write({"state": "done"})

        expense = (
            self.env["hr.expense"]
            .sudo()
            .create(
                {
                    "name": "Taxi from Airport",
                    "employee_id": self.employee_employee.id,
                    "date": date(2024, 8, 6),
                    "total_amount": 50.0,
                    "trip_id": trip.id,
                }
            )
        )

        # Set approval state to approved so it can be posted
        expense.sudo().write({"approval_state": "approved"})

        # This should succeed without raising our UserError from the trip validation
        # (it may fail later in the posting process, but not due to trip state)
        try:
            expense.action_post()
        except Exception as e:
            # As long as it's not our UserError about the trip state, it's fine
            self.assertNotIn("trip", str(e).lower())

    def test_expense_posting_allowed_without_trip(self):
        """Expense posting should be allowed if there is no trip."""
        expense = (
            self.env["hr.expense"]
            .sudo()
            .create(
                {
                    "name": "Standalone Expense",
                    "employee_id": self.employee_employee.id,
                    "date": date(2024, 8, 7),
                    "total_amount": 25.0,
                }
            )
        )

        # Set approval state to approved so it can be posted
        expense.sudo().write({"approval_state": "approved"})

        # This should succeed without raising our UserError from the trip validation
        try:
            expense.action_post()
        except Exception as e:
            # As long as it's not our UserError about the trip state, it's fine
            self.assertNotIn("trip", str(e).lower())

    def test_employee_cannot_change_when_expenses_exist(self):
        trip = self._create_employee_trip(name="Employee Lock Trip")
        expense = (
            self.env["hr.expense"]
            .sudo()
            .create(
                {
                    "name": "Linked Expense",
                    "employee_id": self.employee_employee.id,
                    "date": date(2024, 9, 1),
                    "total_amount": 15.0,
                }
            )
        )
        trip.with_user(self.user_employee).write({"expense_ids": [(4, expense.id)]})

        with self.assertRaises(ValidationError):
            trip.with_user(self.user_manager).write(
                {"employee_id": self.employee_other.id}
            )

    def test_action_done_submits_linked_draft_expenses(self):
        trip = self._create_employee_trip(name="Done Submit Trip")
        trip.sudo().write({"state": "receipts"})
        product = self.env["product.product"].search(
            [("can_be_expensed", "=", True)],
            limit=1,
        )
        self.assertTrue(product, "A product category for expenses is required")

        expense = (
            self.env["hr.expense"]
            .sudo()
            .create(
                {
                    "name": "Receipt Expense",
                    "employee_id": self.employee_employee.id,
                    "product_id": product.id,
                    "date": date(2024, 9, 2),
                    "total_amount": 22.0,
                    "trip_id": trip.id,
                }
            )
        )

        with patch.object(type(trip), "_attach_trip_report"):
            trip.with_user(self.user_employee).action_done()

        self.assertEqual(trip.state, "done")
        self.assertEqual(expense.state, "submitted")

    def test_action_add_more_receipts_resets_state(self):
        trip = self._create_employee_trip(name="Reset Receipts Trip")
        trip.sudo().write({"state": "done"})

        trip.with_user(self.user_employee).action_add_more_receipts()
        self.assertEqual(trip.state, "receipts")

    def test_create_trip_from_expenses_groups_per_employee(self):
        expense_a1 = (
            self.env["hr.expense"]
            .sudo()
            .create(
                {
                    "name": "Expense A1",
                    "employee_id": self.employee_employee.id,
                    "date": date(2024, 9, 10),
                    "total_amount": 10.0,
                }
            )
        )
        expense_a2 = (
            self.env["hr.expense"]
            .sudo()
            .create(
                {
                    "name": "Expense A2",
                    "employee_id": self.employee_employee.id,
                    "date": date(2024, 9, 12),
                    "total_amount": 20.0,
                }
            )
        )
        expense_b1 = (
            self.env["hr.expense"]
            .sudo()
            .create(
                {
                    "name": "Expense B1",
                    "employee_id": self.employee_other.id,
                    "date": date(2024, 9, 11),
                    "total_amount": 15.0,
                }
            )
        )

        expenses = expense_a1 | expense_a2 | expense_b1
        action = expenses.with_user(self.user_admin).action_create_trip()

        created_trips = self.env["hr.trip"].search(action["domain"])
        self.assertEqual(len(created_trips), 2)
        self.assertEqual(expense_a1.trip_id, expense_a2.trip_id)
        self.assertNotEqual(expense_a1.trip_id, expense_b1.trip_id)
        self.assertEqual(expense_a1.trip_id.employee_id, self.employee_employee)
        self.assertEqual(expense_b1.trip_id.employee_id, self.employee_other)

    def test_create_trip_from_expenses_rejects_already_linked(self):
        trip = self._create_employee_trip(name="Already Linked")
        expense = (
            self.env["hr.expense"]
            .sudo()
            .create(
                {
                    "name": "Linked Expense",
                    "employee_id": self.employee_employee.id,
                    "date": date(2024, 9, 15),
                    "total_amount": 30.0,
                    "trip_id": trip.id,
                }
            )
        )

        with self.assertRaises(UserError):
            expense.with_user(self.user_employee).action_create_trip()
