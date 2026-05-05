# Copyright 2024 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from collections import defaultdict

from odoo import fields, models
from odoo.exceptions import UserError


class HrExpense(models.Model):
    _inherit = "hr.expense"

    trip_id = fields.Many2one(
        comodel_name="hr.trip",
        string="Trip",
        ondelete="set null",
        index=True,
    )
    # Related fields used by decoration-success / decoration-warning in the trip
    # form's expense list to flag dates outside the trip date range.
    trip_start_date = fields.Date(
        related="trip_id.start_date",
        store=False,
    )
    trip_end_date = fields.Date(
        related="trip_id.end_date",
        store=False,
    )

    def action_add_existing_expenses(self):
        self.ensure_one()
        trip_id = self.env.context.get("default_trip_id")
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Add: Expenses"),
            "res_model": "hr.trip",
            "res_id": trip_id,
            "view_mode": "form",
            "target": "new",
        }

    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if "trip_id" in fields_list and not defaults.get("trip_id"):
            expense_date = defaults.get("date")
            employee_id = defaults.get("employee_id")
            if expense_date and employee_id:
                trip = self.env["hr.trip"].search(
                    [
                        ("employee_id", "=", employee_id),
                        ("start_date", "<=", expense_date),
                        ("end_date", ">=", expense_date),
                    ],
                    limit=1,
                )
                if trip:
                    defaults["trip_id"] = trip.id
        return defaults

    def action_post(self):
        # Check if any expense has a linked trip that is not in "done" state
        for expense in self:
            if expense.trip_id and expense.trip_id.state != "done":
                raise UserError(
                    self.env._(
                        "Cannot post expense '%(expense)s' because it is linked to "
                        "trip '%(trip)s' which is not in 'Done' state. "
                        "Please mark the trip as done first.",
                        expense=expense.name,
                        trip=expense.trip_id.name,
                    )
                )
        return super().action_post()

    def action_create_trip(self):
        if not self:
            return False

        already_linked = self.filtered("trip_id")
        if already_linked:
            raise UserError(
                self.env._(
                    "Some selected expenses are already linked to a trip. "
                    "Please unselect them before creating trips."
                )
            )

        expenses_by_employee = defaultdict(lambda: self.env["hr.expense"])
        for expense in self:
            expenses_by_employee[expense.employee_id] |= expense

        created_trips = self.env["hr.trip"]
        for employee, expenses in expenses_by_employee.items():
            expense_dates = expenses.mapped("date")
            trip = self.env["hr.trip"].create(
                {
                    "name": self.env._("Trip - %s", employee.name),
                    "employee_id": employee.id,
                    "start_date": min(expense_dates),
                    "end_date": max(expense_dates),
                    "state": "receipts",
                }
            )
            expenses.write({"trip_id": trip.id})
            created_trips |= trip

        action = self.env.ref("hr_expense_trip.action_hr_trip_my").sudo().read()[0]
        action["domain"] = [("id", "in", created_trips.ids)]
        if len(created_trips) == 1:
            action["views"] = [(False, "form")]
            action["res_id"] = created_trips.id
        return action
