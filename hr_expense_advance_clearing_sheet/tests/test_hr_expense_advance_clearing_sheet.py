# Copyright 2026 Ledo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from odoo.addons.hr_expense.tests.common import TestExpenseCommon


@tagged("-at_install", "post_install")
class TestAdvanceClearingSheet(TestExpenseCommon):
    """The scenario raised on OCA/hr-expense#358.

    One 10,000 advance covering three purposes, cleared line by line, and the
    report-level grouping derived from those per-line links.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        advance_account = cls.company_data["default_account_deferred_expense"]
        advance_account.reconcile = True
        cls.advance_product = cls.env.ref(
            "hr_expense_advance_clearing.product_emp_advance"
        )
        cls.advance_product.property_account_expense_id = advance_account
        cls.product_a.standard_price = 0
        cls.employee = cls.expense_employee
        cls.expense_product = cls.product_a

    def _advance_line(self, sheet, amount):
        return self.env["hr.expense"].create(
            {
                "name": f"Advance {amount}",
                "employee_id": self.employee.id,
                "product_id": self.advance_product.id,
                "total_amount_currency": amount,
                "expense_type": "advance",
                "payment_mode": "own_account",
                "sheet_id": sheet.id,
            }
        )

    def _sheet(self, name):
        return self.env["hr.expense.sheet"].create(
            {"name": name, "employee_id": self.employee.id}
        )

    def test_advance_sheet_type_derived_from_lines(self):
        """A report of nothing but advance lines is an advance report."""
        sheet = self._sheet("Advance 10,000")
        for amount in (3000.0, 5000.0, 2000.0):
            self._advance_line(sheet, amount)
        self.assertEqual(sheet.expense_type, "advance")
        self.assertEqual(len(sheet.expense_line_ids), 3)

    def test_ordinary_report_is_not_an_advance(self):
        sheet = self._sheet("Ordinary")
        self.env["hr.expense"].create(
            {
                "name": "Hotel",
                "employee_id": self.employee.id,
                "product_id": self.expense_product.id,
                "total_amount_currency": 500.0,
                "payment_mode": "own_account",
                "sheet_id": sheet.id,
            }
        )
        self.assertEqual(sheet.expense_type, "expense")

    def test_mixed_report_is_not_an_advance(self):
        """Only a report that is entirely advances counts as one.

        The parent module constrains lines individually and does not forbid
        mixing, so this case is reachable and has to be decided here.
        """
        sheet = self._sheet("Mixed")
        self._advance_line(sheet, 1000.0)
        self.env["hr.expense"].create(
            {
                "name": "Hotel",
                "employee_id": self.employee.id,
                "product_id": self.expense_product.id,
                "total_amount_currency": 500.0,
                "payment_mode": "own_account",
                "sheet_id": sheet.id,
            }
        )
        self.assertEqual(
            sheet.expense_type,
            "expense",
            "a report mixing an advance with an ordinary expense is not an advance",
        )

    def test_clearing_grouping_is_derived_from_line_links(self):
        """The report-level link follows the per-line links, never replaces them."""
        advance_sheet = self._sheet("Advance 10,000")
        general = self._advance_line(advance_sheet, 3000.0)
        hotel = self._advance_line(advance_sheet, 5000.0)

        clearing_sheet = self._sheet("Clearing")
        for advance_line, amount in ((general, 2500.0), (hotel, 4800.0)):
            self.env["hr.expense"].create(
                {
                    "name": f"Clearing of {advance_line.name}",
                    "employee_id": self.employee.id,
                    "product_id": self.expense_product.id,
                    "total_amount_currency": amount,
                    "payment_mode": "own_account",
                    "sheet_id": clearing_sheet.id,
                    "clearing_advance_id": advance_line.id,
                }
            )
        self.assertEqual(
            clearing_sheet.advance_sheet_id,
            advance_sheet,
            "the clearing report must resolve to the advance report its lines clear",
        )
        self.assertIn(clearing_sheet, advance_sheet.clearing_sheet_ids)
        self.assertEqual(advance_sheet.clearing_count, 1)

    def test_lines_clearing_two_reports_leave_the_link_empty(self):
        """Rather than pick one arbitrarily — the per-line links stay authoritative."""
        first = self._sheet("Advance A")
        second = self._sheet("Advance B")
        line_a = self._advance_line(first, 1000.0)
        line_b = self._advance_line(second, 1000.0)

        clearing_sheet = self._sheet("Clearing across two")
        for advance_line in (line_a, line_b):
            self.env["hr.expense"].create(
                {
                    "name": f"Clearing of {advance_line.name}",
                    "employee_id": self.employee.id,
                    "product_id": self.expense_product.id,
                    "total_amount_currency": 400.0,
                    "payment_mode": "own_account",
                    "sheet_id": clearing_sheet.id,
                    "clearing_advance_id": advance_line.id,
                }
            )
        self.assertFalse(clearing_sheet.advance_sheet_id)
        self.assertFalse(first.clearing_sheet_ids)

    def test_advance_residual_sums_the_advance_lines(self):
        sheet = self._sheet("Advance 10,000")
        lines = [self._advance_line(sheet, a) for a in (3000.0, 5000.0, 2000.0)]
        expected = sum(line.clearing_residual for line in lines)
        self.assertEqual(sheet.advance_residual, expected)

    def _post_sheet(self, sheet):
        sheet.action_submit()
        if sheet.state == "submitted":
            sheet.action_approve()
        sheet.action_post()
        return sheet

    def test_clear_advance_creates_prefilled_clearing_sheet(self):
        """Clear Advance builds a draft clearing report from the open lines.

        The report-level link then materializes from the seeded per-line
        links, never from a direct write.
        """
        sheet = self._sheet("Advance 10,000")
        lines = [self._advance_line(sheet, a) for a in (3000.0, 5000.0, 2000.0)]
        for line in lines:
            line.clearing_product_id = self.expense_product
        self._post_sheet(sheet)
        action = sheet.action_clear_advance()
        clearing_sheet = self.env["hr.expense.sheet"].browse(action["res_id"])
        self.assertEqual(clearing_sheet.employee_id, self.employee)
        self.assertEqual(len(clearing_sheet.expense_line_ids), 3)
        self.assertEqual(
            clearing_sheet.expense_line_ids.clearing_advance_id,
            sheet.expense_line_ids,
        )
        self.assertEqual(
            sorted(clearing_sheet.expense_line_ids.mapped("total_amount_currency")),
            [2000.0, 3000.0, 5000.0],
            "each clearing line must prefill the advance line's residual",
        )
        self.assertEqual(
            clearing_sheet.advance_sheet_id,
            sheet,
            "the derived report-level link must resolve from the seeded lines",
        )

    def test_clear_advance_skips_lines_without_clearing_product(self):
        """Only advance lines carrying a clearing product can be prefilled
        (a clearing expense needs a product); the others are left alone."""
        sheet = self._sheet("Advance, one clearing product")
        with_product = self._advance_line(sheet, 3000.0)
        self._advance_line(sheet, 5000.0)
        with_product.clearing_product_id = self.expense_product
        self._post_sheet(sheet)
        action = sheet.action_clear_advance()
        clearing_sheet = self.env["hr.expense.sheet"].browse(action["res_id"])
        self.assertEqual(
            clearing_sheet.expense_line_ids.clearing_advance_id, with_product
        )

    def test_clear_advance_without_clearing_products_is_refused(self):
        sheet = self._sheet("Advance, no clearing product")
        self._advance_line(sheet, 1000.0)
        self._post_sheet(sheet)
        with self.assertRaises(UserError):
            sheet.action_clear_advance()

    def test_return_advance_single_line_delegates(self):
        """One open advance line keeps the per-expense wizard behavior,
        advance_id seeding included."""
        sheet = self._sheet("Advance single")
        line = self._advance_line(sheet, 500.0)
        self._post_sheet(sheet)
        action = sheet.action_return_advance()
        self.assertEqual(action["res_model"], "account.payment.register")
        self.assertEqual(action["context"]["default_advance_id"], line.id)

    def test_return_advance_multi_line_maps_each_payment(self):
        """A multi-advance report returns one payment per advance move, each
        stamped with its own advance so per-line residuals stay accurate.

        Driven through Form: create() would precompute what the dialog
        cannot, passing against a wizard that opens broken.
        """
        sheet = self._sheet("Advance 1,000")
        first = self._advance_line(sheet, 600.0)
        second = self._advance_line(sheet, 400.0)
        self._post_sheet(sheet)
        action = sheet.action_return_advance()
        self.assertEqual(
            set(action["context"]["active_ids"]),
            set(
                (first + second)
                .account_move_id.line_ids.filtered(
                    lambda ml: not ml.reconciled
                    and ml.account_id
                    == self.advance_product.property_account_expense_id
                )
                .ids
            ),
        )
        form = Form(
            self.env["account.payment.register"].with_context(**action["context"])
        )
        wizard = form.save()
        payments = wizard._create_payments()
        self.assertEqual(len(payments), 2)
        self.assertEqual(
            {p.advance_id: p.amount for p in payments},
            {first: 600.0, second: 400.0},
        )
        (first + second).invalidate_recordset(["returned_amount", "clearing_residual"])
        self.assertEqual(first.clearing_residual, 0.0)
        self.assertEqual(second.clearing_residual, 0.0)
        self.assertEqual(sheet.advance_residual, 0.0)

    def test_return_advance_grouping_not_offered(self):
        """One payment spanning several advances could not say which advance
        line it returns, so the wizard must not offer to group them — the
        per-expense batch key leaves nothing groupable."""
        sheet = self._sheet("Advance grouped")
        self._advance_line(sheet, 600.0)
        self._advance_line(sheet, 400.0)
        self._post_sheet(sheet)
        action = sheet.action_return_advance()
        form = Form(
            self.env["account.payment.register"].with_context(**action["context"])
        )
        wizard = form.save()
        self.assertEqual(len(wizard.batches), 2, "one batch per advance line")
        self.assertFalse(wizard.can_group_payments)

    def test_return_advance_multi_line_over_return_is_refused(self):
        """An approved-but-unposted clearing lowers what may still be
        returned below the move line's residual; the per-line check must
        catch the overrun the wizard would otherwise pay."""
        sheet = self._sheet("Advance with pending clearing")
        first = self._advance_line(sheet, 600.0)
        self._advance_line(sheet, 400.0)
        self._post_sheet(sheet)
        clearing = self.env["hr.expense"].create(
            {
                "name": "Pending clearing",
                "employee_id": self.employee.id,
                "product_id": self.expense_product.id,
                "total_amount_currency": 100.0,
                "payment_mode": "own_account",
                "clearing_advance_id": first.id,
            }
        )
        clearing.action_submit()
        if clearing.state == "submitted":
            clearing.action_approve()
        action = sheet.action_return_advance()
        form = Form(
            self.env["account.payment.register"].with_context(**action["context"])
        )
        wizard = form.save()
        with self.assertRaises(UserError):
            wizard._create_payments()

    def test_return_advance_without_residual_is_refused(self):
        sheet = self._sheet("Nothing to return")
        with self.assertRaises(UserError):
            sheet.action_return_advance()
