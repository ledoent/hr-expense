# Copyright 2024 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class HrTrip(models.Model):
    _name = "hr.trip"
    _description = "HR Trip"
    _order = "start_date desc, name"
    _inherit = ["mail.thread.main.attachment", "mail.activity.mixin"]

    name = fields.Char(required=True)
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    reason = fields.Text()
    partner_id = fields.Many2one(
        comodel_name="res.partner",
    )
    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        default=lambda self: self.env.user.employee_id,
    )
    expense_ids = fields.One2many(
        comodel_name="hr.expense",
        inverse_name="trip_id",
        domain="[('employee_id', '=', employee_id), ('trip_id', 'in', [False,id])]",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("request", "Requested"),
            ("receipts", "Collect Receipts"),
            ("done", "Done"),
        ],
        default="draft",
        tracking=True,
    )
    can_edit_trip_info = fields.Boolean(
        compute="_compute_can_edit_trip_info",
    )
    can_create_bill = fields.Boolean(
        compute="_compute_can_create_bill",
    )

    @api.depends("employee_id")
    def _compute_can_edit_trip_info(self):
        user = self.env.user
        for trip in self:
            trip.can_edit_trip_info = trip._is_user_trip_approver(user)

    @api.depends("expense_ids", "expense_ids.state")
    def _compute_can_create_bill(self):
        for trip in self:
            if not trip.expense_ids:
                trip.can_create_bill = False
            else:
                trip.can_create_bill = trip.state == "done" and all(
                    exp.state == "approved" for exp in trip.expense_ids
                )

    def _is_user_trip_approver(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        if user.has_group("hr_expense.group_hr_expense_manager"):
            return True
        if not (
            user.has_group("hr_expense.group_hr_expense_team_approver")
            or user.has_group("hr_expense.group_hr_expense_user")
        ):
            return False
        return (
            self.employee_id.expense_manager_id == user
            or self.employee_id.parent_id.user_id == user
        )

    def action_print_trip(self):
        self.ensure_one()
        return self.env.ref("hr_expense_trip.action_report_hr_trip").report_action(self)

    def action_request_approval(self):
        self.ensure_one()
        auto_approve = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("hr_expense_trip.auto_approve", default="True")
        )
        if auto_approve == "True" or self._is_user_trip_approver():
            self.state = "receipts"
        else:
            self.state = "request"
            manager_employee = self.employee_id.parent_id
            manager = manager_employee.user_id if manager_employee else False
            if manager:
                activity_type = self.env.ref("mail.mail_activity_data_todo")
                self.activity_schedule(
                    activity_type_id=activity_type.id,
                    summary=self.env._("Trip Approval Request"),
                    user_id=manager.id,
                )

    def action_approve(self):
        self.ensure_one()
        if not self._is_user_trip_approver():
            raise AccessError(self.env._("You are not allowed to approve this trip."))
        self.state = "receipts"

    def write(self, vals):
        if self.env.context.get("skip_trip_write_protection"):
            return super().write(vals)

        state_only_done_transition = (
            set(vals) == {"state"} and vals.get("state") == "done"
        )
        state_only_receipts_transition = (
            set(vals) == {"state"} and vals.get("state") == "receipts"
        )

        if "employee_id" in vals:
            blocked_trips = self.filtered(
                lambda trip: trip.expense_ids
                and trip.employee_id.id != vals["employee_id"]
            )
            if blocked_trips:
                raise ValidationError(
                    self.env._(
                        "You cannot change the employee once expenses are "
                        "linked to the trip."
                    )
                )

        if "expense_ids" in vals and any(trip.state == "done" for trip in self):
            # Only managers and administrators can edit expenses in "done" state
            if not any(trip._is_user_trip_approver() for trip in self):
                raise AccessError(
                    self.env._(
                        "Expenses cannot be modified once the trip is marked as done."
                    )
                )

        protected_fields = set(vals) - {"expense_ids"}
        if protected_fields and not (
            state_only_done_transition or state_only_receipts_transition
        ):
            blocked_trips = self.filtered(
                lambda trip: trip.state in ("receipts", "done")
                and not trip._is_user_trip_approver()
            )
            if blocked_trips:
                raise AccessError(
                    self.env._(
                        "Only managers and administrators can edit trip information "
                        "after approval."
                    )
                )

        return super().write(vals)

    def action_done(self):
        self.ensure_one()
        draft_expenses = self.expense_ids.filtered(
            lambda expense: expense.state == "draft"
        )
        for expense in draft_expenses:
            submit_user = expense.employee_id.user_id or self.env.user
            expense.with_user(submit_user).action_submit()
        self.state = "done"
        self._attach_trip_report()

    def action_add_more_receipts(self):
        self.ensure_one()
        self.state = "receipts"

    def _attach_trip_report(self):
        self.ensure_one()
        pdf_content, _mime = self.env["ir.actions.report"]._render_qweb_pdf(
            "hr_expense_trip.action_report_hr_trip", res_ids=self.ids
        )
        attachment = self.env["ir.attachment"].create(
            {
                "name": self.env._("%s - Trip Report.pdf", self.name),
                "type": "binary",
                "datas": base64.b64encode(pdf_content),
                "res_model": self._name,
                "res_id": self.id,
                "mimetype": "application/pdf",
            }
        )
        self.with_context(skip_trip_write_protection=True).message_post(
            attachment_ids=[attachment.id]
        )

    def action_post(self):
        self.ensure_one()
        if not self.can_create_bill:
            raise AccessError(
                self.env._("All expenses must be in approved state to create a bill.")
            )
        moves = self.env["account.move"]
        expenses = self.expense_ids.filtered(lambda e: e.state == "approved")
        expenses.action_post()
        moves = expenses.account_move_id

        if moves:
            self._attach_trip_report_to_moves(moves)
            if len(moves) == 1:
                return moves[0].get_formview_action()
            else:
                action = self.env.ref("account.action_move_journal_line")
                action_dict = action.read()[0]
                action_dict["domain"] = [("id", "in", moves.ids)]
                return action_dict

    def _attach_trip_report_to_moves(self, moves):
        self.ensure_one()
        pdf_content, _mime = self.env["ir.actions.report"]._render_qweb_pdf(
            "hr_expense_trip.action_report_hr_trip", res_ids=self.ids
        )
        attachment = self.env["ir.attachment"].create(
            {
                "name": self.env._("%s - Trip Report.pdf", self.name),
                "type": "binary",
                "datas": base64.b64encode(pdf_content),
                "res_model": "account.move",
                "res_id": moves[0].id,
                "mimetype": "application/pdf",
            }
        )
        for move in moves:
            move.message_post(attachment_ids=[attachment.id])

    @api.constrains("start_date", "end_date")
    def _check_date_range(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError(
                    self.env._(
                        "End date (%(end)s) must not be before start date (%(start)s).",
                        end=rec.end_date,
                        start=rec.start_date,
                    )
                )
