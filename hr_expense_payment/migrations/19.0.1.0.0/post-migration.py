# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging

from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

LEGACY_RELATION = "payment_expense_sheet_rel"


def migrate(cr, version):
    """Carry the 18.0 payment/expense-sheet links onto the expense entries.

    Up to 18.0 this module stored its own `payment_expense_sheet_rel` table
    (payment <-> hr.expense.sheet). 19.0 has no expense sheet and the module
    stores nothing: both directions are derived from core's move-level link
    data. Most 18.0 links survive that change on their own, because the
    register wizard already recorded them in core's own
    `account_move__account_payment` table against the sheet's journal entry,
    and OpenUpgrade re-points that same entry at the expense
    (`hr_expense.account_move_id`).

    What does not survive is a link this module recorded from a
    reconciliation that has since been undone: nothing in the accounting data
    still proves it. Those rows are carried into core's table, which is the
    19.0 field for "payments linked to this entry" regardless of the current
    reconciliation state -- the same thing 18.0 displayed.

    The sheet is reached through core's own `hr.expense.former_sheet_id`,
    which OpenUpgrade fills by renaming 18.0's `hr_expense.sheet_id` onto it.
    """
    if not table_exists(cr, LEGACY_RELATION):
        # Fresh 19.0 install, or the 18.0 table was already dropped.
        return
    cr.execute(
        """
        INSERT INTO account_move__account_payment (invoice_id, payment_id)
        SELECT DISTINCT expense.account_move_id, legacy.payment_id
        FROM payment_expense_sheet_rel AS legacy
        JOIN hr_expense AS expense ON expense.former_sheet_id = legacy.sheet_id
        WHERE expense.account_move_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM account_payment AS payment
              WHERE payment.id = legacy.payment_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM account_move__account_payment AS existing
              WHERE existing.invoice_id = expense.account_move_id
                AND existing.payment_id = legacy.payment_id
          )
        """
    )
    _logger.info(
        "hr_expense_payment: carried %s payment link(s) from %s onto the "
        "expense journal entries.",
        cr.rowcount,
        LEGACY_RELATION,
    )
