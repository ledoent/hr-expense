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
            self._set_state("receipts")
        else:
            self._set_state("request")
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
        self._set_state("receipts")

    def _set_state(self, state):
        """Single entry point for workflow state transitions. Bypasses the
        post-approval write lock so the workflow buttons keep working for the
        employee, while direct field edits stay protected."""
        self.with_context(skip_trip_write_protection=True).write({"state": state})

    @api.constrains("employee_id", "expense_ids")
    def _check_expense_employee(self):
        """Linked expenses must belong to the trip's employee. This also blocks
        changing the employee once expenses are linked."""
        for trip in self:
            if any(
                expense.employee_id != trip.employee_id for expense in trip.expense_ids
            ):
                raise ValidationError(
                    self.env._(
                        "Linked expenses must belong to the trip's employee. "
                        "Unlink them before changing the employee."
                    )
                )

    def write(self, vals):
        # Workflow transitions (via _set_state) and internal writes bypass the
        # post-approval lock.
        if self.env.context.get("skip_trip_write_protection"):
            return super().write(vals)
        # Expenses can no longer be (un)linked once the trip is done, unless the
        # user is an approver.
        if "expense_ids" in vals:
            locked = self.filtered(
                lambda trip: trip.state == "done" and not trip._is_user_trip_approver()
            )
            if locked:
                raise AccessError(
                    self.env._(
                        "Expenses cannot be modified once the trip is marked as done."
                    )
                )
        # Any other field (state included) is locked once the trip is approved,
        # unless the user is an approver. The workflow buttons go through
        # _set_state and are therefore exempt.
        if set(vals) - {"expense_ids"}:
            locked = self.filtered(
                lambda trip: trip.state in ("receipts", "done")
                and not trip._is_user_trip_approver()
            )
            if locked:
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
        self._set_state("done")
        self._attach_trip_report()

    def action_add_more_receipts(self):
        self.ensure_one()
        self._set_state("receipts")

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
        expenses = self.expense_ids.filtered(lambda e: e.state == "approved")
        moves = self._post_trip_expenses(expenses)

        if moves:
            self._attach_trip_report_to_moves(moves)
            if len(moves) == 1:
                return moves[0].get_formview_action()
            else:
                action = self.env.ref("account.action_move_journal_line")
                action_dict = action.read()[0]
                action_dict["domain"] = [("id", "in", moves.ids)]
                return action_dict

    def _post_trip_expenses(self, expenses):
        """Post the trip's approved expenses and return the resulting moves.

        Company-paid expenses post directly through the standard flow. For
        employee-paid ('own_account') expenses, core ``hr.expense.action_post``
        only returns an interactive posting wizard and creates no move on its
        own, so calling it here would silently post nothing. We instead build
        and post the receipt entries the wizard would create, so "Create Bill"
        works in one click for the (common) employee-paid case.
        """
        company_expenses = expenses.filtered(
            lambda e: e.payment_mode == "company_account"
        )
        employee_expenses = expenses - company_expenses
        moves = self.env["account.move"]
        if company_expenses:
            company_expenses.action_post()
            moves |= company_expenses.account_move_id
        if employee_expenses:
            journal = self._employee_expense_journal()
            receipt_vals = [
                {
                    **vals,
                    "journal_id": journal.id,
                    "invoice_date": fields.Date.context_today(self),
                }
                for vals in employee_expenses._prepare_receipts_vals()
            ]
            employee_moves = self.env["account.move"].sudo().create(receipt_vals)
            employee_moves.action_post()
            moves |= employee_moves
        return moves

    def _employee_expense_journal(self):
        """Resolve the purchase journal for employee-paid expense entries,
        mirroring the default of core's expense posting wizard."""
        company = self.env.company
        journal = company.expense_journal_id
        if not journal:
            journal = company.parent_ids[::-1].expense_journal_id[:1]
        if not journal:
            journal = self.env["account.journal"].search(
                [
                    *self.env["account.journal"]._check_company_domain(company.id),
                    ("type", "=", "purchase"),
                ],
                limit=1,
            )
        return journal

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
