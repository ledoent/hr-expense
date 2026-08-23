# Copyright 2026 Ledo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    @api.model
    def _get_line_batch_key(self, line):
        """One batch — so one payment — per advance line.

        Core posts every own-account expense of an employee into a single
        move, so splitting per move (the wizard's ungrouped behavior) would
        still produce one payment spanning all the advances of a report.
        Keying the batch by expense keeps a 1:1 payment-to-advance mapping,
        the only shape advance_id and the per-line residuals can express.
        """
        res = super()._get_line_batch_key(line)
        if self.env.context.get("hr_return_advance_sheet"):
            res["hr_advance_expense_id"] = line.expense_id.id
        return res

    def _validate_over_return(self):
        """Per-advance-line overrun check for report-level returns.

        The parent module's validation compares wizard-level amounts that only
        exist in the wizard's single-batch edit mode; a report-level return
        runs multi-batch, where they are zero and the comparison misfires.
        Here each payment returns its move line's residual, so the check is
        per line: it must not exceed that advance's remaining amount (which,
        unlike the move line, also discounts approved-but-unposted clearings).
        """
        if not self.env.context.get("hr_return_advance_sheet"):
            return super()._validate_over_return()
        for batch_result in self.batches:
            for line in batch_result["lines"]:
                advance = line.expense_id
                if (
                    float_compare(
                        line.amount_residual_currency,
                        advance.clearing_residual,
                        2,
                    )
                    == 1
                ):
                    raise UserError(
                        self.env._(
                            "You cannot return advance %(advance)s more than "
                            "its actual remaining (%(amount).2f)",
                            advance=advance.name,
                            amount=advance.clearing_residual,
                        )
                    )

    def _init_payments(self, to_process, edit_mode=False):
        """Stamp each return payment with the advance line it returns."""
        if self.env.context.get("hr_return_advance_sheet"):
            for vals in to_process:
                advance = vals["to_reconcile"].expense_id
                if len(advance) != 1:
                    raise UserError(
                        self.env._(
                            "Every return payment must map to exactly one "
                            "advance line; register the lines separately."
                        )
                    )
                vals["create_vals"]["advance_id"] = advance.id
        return super()._init_payments(to_process, edit_mode=edit_mode)
