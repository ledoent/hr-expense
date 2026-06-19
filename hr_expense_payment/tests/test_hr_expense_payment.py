# Copyright 2019 Tecnativa - Ernesto Tejeda
# Copyright 2021 Ecosoft Co., Ltd (http://ecosoft.co.th/)
# Copyright 2024 Tecnativa - Víctor Martínez
# Copyright 2026 Ledo <https://ledoweb.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import Form, tagged

from odoo.addons.hr_expense.tests.common import TestExpenseCommon

from ..hooks import post_init_hook


@tagged("-at_install", "post_install")
class TestHrExpensePayment(TestExpenseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Build an employee-paid expense, submit + approve + post (= receipt).
        cls.expense = cls.create_expenses({"payment_mode": "own_account"})
        cls.expense.action_submit()
        cls.expense.action_approve()
        cls.post_expenses_with_wizard(cls.expense)

    def _get_payment_wizard(self):
        action = self.expense.action_pay()
        wizard_form = Form(
            self.env[action["res_model"]].with_context(**action["context"])
        )
        wizard_form.journal_id = self.company_data["default_journal_bank"]
        wizard_form.amount = self.expense.total_amount
        return wizard_form.save()

    def test_action_pay_links_payment_back_to_expense(self):
        """After action_pay → create_payment, the resulting payment's
        expense_ids includes the source expense and the expense's
        payment_ids includes the new payment."""
        self.assertFalse(self.expense.payment_ids)
        wizard = self._get_payment_wizard()
        wizard.action_create_payments()
        self.assertEqual(len(self.expense.payment_ids), 1)
        payment = self.expense.payment_ids
        self.assertIn(self.expense, payment.expense_ids)

    def test_post_init_hook_backfills_legacy_payments(self):
        """post_init_hook walks reconciliation to recover the back-link for
        payments that pre-date the module install."""
        wizard = self._get_payment_wizard()
        wizard.action_create_payments()
        payment = self.expense.payment_ids
        self.assertEqual(len(payment), 1)
        # Wipe the back-link, then re-run the hook.
        payment.expense_ids = False
        self.assertFalse(self.expense.payment_ids)
        post_init_hook(self.env)
        self.assertEqual(len(self.expense.payment_ids), 1)
